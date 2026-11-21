"""Run 3-Condition Paired Ablation & Adaptive Interview Benchmark for Module 3 (100 CV-JD Cases).

Evaluates all 100 fixed test cases (`module3_100_cases.json`) across 3 strictly paired conditions
using identical student model (`qwen/qwen3.7-flash`), fixed shared Blueprint, fixed criteria,
fixed target depth, fixed question budget (`max_questions=3`), and identical scripted answers:

1. `one_shot`: Direct single-prompt LLM generation for Turn 1 and Turn 2 without multi-step
   chaining, verification preparation, or alignment review.
2. `chain_no_verification`: Full `EvidenceWorkflow` adaptive chain (`QuestionGenerator`,
   `AlignmentReviewer`, `ReflectiveJudge`, policy transitions) with `verification_sources=None`.
3. `chain_full_verification`: Full `EvidenceWorkflow` with source-backed `verification_sources`
   enabling `prepare_verification`, `detail_to_verify` grounding, and CV-to-JD fallback logic.

Captures exact runtime telemetry (preparation success/timeout/failure, JD fallback reasons,
alignment rejections, regeneration attempts, latency) and persists results atomically to JSONL
with full resumption support.
"""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
import json
import logging
import os
from pathlib import Path
import re
import sys
import threading
from time import perf_counter
from typing import Any, Dict, List, Optional, Set, Tuple

from dotenv import load_dotenv
import httpx  # noqa: F401 - eager import before ThreadPoolExecutor prevents Python 3.14 lazy-import race
import openai

ai_service_dir = Path(__file__).resolve().parents[2]
if str(ai_service_dir) not in sys.path:
    sys.path.insert(0, str(ai_service_dir))

from adaptive_questioning.evidence import telemetry
from adaptive_questioning.evidence.models import (
    NextQuestionRequest,
    StartRequest,
    TransitionRequest,
)
from adaptive_questioning.evidence.policy_config import InterviewPolicy
from adaptive_questioning.evidence.provider import AlignmentReview, DSPyAssessmentProvider
from adaptive_questioning.evidence.workflow import EvidenceWorkflow
from adaptive_questioning.optimization.compiler import DEFAULT_COMPILED_DIR

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logging.getLogger("LiteLLM").setLevel(logging.WARNING)
logging.getLogger("httpx").setLevel(logging.WARNING)
logger = logging.getLogger("benchmark_module3")

CONDITIONS = ("one_shot", "chain_no_verification", "chain_full_verification")


class SessionTelemetryCapture(logging.Handler):
    """Thread-safe log handler capturing telemetry events and workflow warnings keyed by session_id."""

    def __init__(self) -> None:
        super().__init__(level=logging.INFO)
        self._lock = threading.Lock()
        self._events: Dict[str, List[Dict[str, Any]]] = {}
        self._warnings: Dict[str, List[str]] = {}

    def emit(self, record: logging.LogRecord) -> None:
        msg = record.getMessage()
        if msg.startswith("interview."):
            m_sid = re.search(r"session_id=(\S+)", msg)
            if m_sid:
                sid = m_sid.group(1)
                ev_name = msg.split(" ", 1)[0].removeprefix("interview.")
                fields = dict(re.findall(r"(\w+)=([^\s]+)", msg))
                fields.pop("session_id", None)
                with self._lock:
                    self._events.setdefault(sid, []).append({"event": ev_name, "fields": fields})
        elif record.levelno >= logging.WARNING and "for session " in msg:
            m_sid = re.search(r"for session (\S+)", msg)
            if m_sid:
                sid = m_sid.group(1).rstrip(":,")
                with self._lock:
                    self._warnings.setdefault(sid, []).append(msg)

    def pop_session(self, sid: str) -> Tuple[List[Dict[str, Any]], List[str]]:
        with self._lock:
            return self._events.pop(sid, []), self._warnings.pop(sid, [])


class InstrumentedProviderProxy:
    """Thin proxy over DSPyAssessmentProvider recording per-session LLM attempts and alignment verdicts."""

    def __init__(self, inner: DSPyAssessmentProvider) -> None:
        self._inner = inner
        self.lm = inner.lm
        self.fast_lm = inner.fast_lm
        self._local = threading.local()

    def reset_counters(self) -> None:
        self._local.question_calls = 0
        self._local.review_calls = 0
        self._local.review_verdicts = []
        self._local.judge_calls = 0
        self._local.prep_calls = 0

    def get_counters(self) -> Dict[str, Any]:
        return {
            "question_calls": getattr(self._local, "question_calls", 0),
            "review_calls": getattr(self._local, "review_calls", 0),
            "review_verdicts": list(getattr(self._local, "review_verdicts", [])),
            "judge_calls": getattr(self._local, "judge_calls", 0),
            "prep_calls": getattr(self._local, "prep_calls", 0),
        }

    def blueprint(self, context: str):
        return self._inner.blueprint(context)

    def prepare_verification(self, context: str, *, deadline: float):
        self._local.prep_calls = getattr(self._local, "prep_calls", 0) + 1
        return self._inner.prepare_verification(context, deadline=deadline)

    def question(self, context: str):
        self._local.question_calls = getattr(self._local, "question_calls", 0) + 1
        return self._inner.question(context)

    def review_question(self, context: str):
        self._local.review_calls = getattr(self._local, "review_calls", 0) + 1
        res = self._inner.review_question(context)
        verdict = res.verdict if isinstance(res, AlignmentReview) else str(res)
        verdicts = getattr(self._local, "review_verdicts", None)
        if verdicts is None:
            verdicts = []
            self._local.review_verdicts = verdicts
        verdicts.append(verdict)
        return res

    def judge(self, context: str):
        self._local.judge_calls = getattr(self._local, "judge_calls", 0) + 1
        return self._inner.judge(context)

    def __getattr__(self, item: str):
        return getattr(self._inner, item)


def _run_one_shot(
    case: Dict[str, Any],
    oa_client: openai.OpenAI,
    student_model_raw: str,
) -> Dict[str, Any]:
    """Condition 1: Single-prompt direct generation without multi-step chaining or verification."""
    isk = case["interview_skill"]
    obj = case["blueprint"]["objectives"][0]
    c1 = obj["criteria"][0]
    c2 = obj["criteria"][1] if len(obj["criteria"]) > 1 else None
    depth = obj["target_depth"]
    mode = obj["suitable_modes"][0]["mode"]
    cv_spans = isk.get("cv_evidence_spans") or []
    jd_spans = isk.get("jd_evidence_spans") or []

    # Turn 1: One-shot Q1
    p1 = (
        "Bạn là người phỏng vấn kỹ thuật bằng tiếng Việt. Dựa trên thông tin CV, JD và yêu cầu kỹ năng mục tiêu dưới đây, "
        "hãy đặt câu hỏi phỏng vấn mở đầu (1 câu hỏi trực tiếp bằng tiếng Việt, đúng độ sâu yêu cầu, không gợi sẵn đáp án).\n\n"
        f"- Kỹ năng mục tiêu: {isk.get('jd_skill_name') or isk['jd_skill_id']}\n"
        f"- Nhiệm vụ JD: {obj['claim']}\n"
        f"- Trích đoạn JD: {json.dumps(jd_spans, ensure_ascii=False)}\n"
        f"- Trích đoạn CV liên quan (nếu có): {json.dumps(cv_spans, ensure_ascii=False)}\n"
        f"- Ngữ cảnh CV: {isk.get('context_job', '')}\n"
        f"- Tiêu chí trọng tâm: {c1['description']} (Bằng chứng kỳ vọng: {c1['expected_evidence']})\n"
        f"- Chế độ & Độ sâu yêu cầu: {mode}, mức L{depth} (L1 nền tảng, L2 vận dụng, L3 phân tích, L4 thiết kế/trade-off)\n\n"
        "Trả về STRICT JSON: {\"question\": \"...\"}"
    )

    t0 = perf_counter()
    q1_text = ""
    err_msg = None
    try:
        r1 = oa_client.chat.completions.create(
            model=student_model_raw,
            messages=[{"role": "user", "content": p1}],
            response_format={"type": "json_object"},
            temperature=0.0,
            seed=42,
            max_tokens=512,
            extra_body={"reasoning": {"effort": "none"}},
        )
        q1_text = str(json.loads(r1.choices[0].message.content.strip()).get("question", "")).strip()
    except Exception as exc:
        err_msg = f"one_shot_t1:{type(exc).__name__}:{exc}"
    t1_sec = round(perf_counter() - t0, 3)

    # Turn 2: One-shot adaptive continuation given frozen scripted answer
    next_crit_text = (
        f"Tiêu chí tiếp theo (c2): {c2['description']} (Bằng chứng kỳ vọng: {c2['expected_evidence']})"
        if c2 else "Không còn tiêu chí tiếp theo; có thể kết thúc nếu ứng viên đã đạt tiêu chí hiện tại."
    )
    p2 = (
        "Bạn là người phỏng vấn kỹ thuật bằng tiếng Việt. Dưới đây là lịch sử lượt 1 và câu trả lời của ứng viên. "
        "Hãy tự đánh giá ngắn gọn và quyết định bước tiếp theo: hỏi làm rõ/xác minh thêm trên cùng tiêu chí (FOLLOW_UP), "
        "chuyển sang tiêu chí tiếp theo (NEXT_CRITERION), hoặc kết thúc phần kỹ năng này (FINISH).\n\n"
        f"- Kỹ năng mục tiêu: {isk.get('jd_skill_name') or isk['jd_skill_id']}\n"
        f"- Trích đoạn CV (nếu có): {json.dumps(cv_spans, ensure_ascii=False)}\n"
        f"- Tiêu chí 1 (c1): {c1['description']} (Đạt chuẩn: {c1['at_target']})\n"
        f"- {next_crit_text}\n"
        f"- Câu hỏi lượt 1: {q1_text}\n"
        f"- Câu trả lời ứng viên: {case['scripted_answer']}\n\n"
        "Trả về STRICT JSON: {\"decision\": \"FOLLOW_UP\" | \"NEXT_CRITERION\" | \"FINISH\", \"next_question\": \"... (để chuỗi rỗng nếu FINISH)\"}"
    )

    t1 = perf_counter()
    t2_decision = "FOLLOW_UP"
    q2_text = ""
    if not err_msg:
        try:
            r2 = oa_client.chat.completions.create(
                model=student_model_raw,
                messages=[{"role": "user", "content": p2}],
                response_format={"type": "json_object"},
                temperature=0.0,
                seed=42,
                max_tokens=512,
                extra_body={"reasoning": {"effort": "none"}},
            )
            d2 = json.loads(r2.choices[0].message.content.strip())
            t2_decision = str(d2.get("decision", "FOLLOW_UP")).upper()
            q2_text = str(d2.get("next_question", "")).strip()
            if t2_decision == "FINISH":
                q2_text = ""
        except Exception as exc:
            err_msg = f"one_shot_t2:{type(exc).__name__}:{exc}"
    t2_sec = round(perf_counter() - t1, 3)

    return {
        "case_id": case["case_id"],
        "pair_id": case["pair_id"],
        "condition": "one_shot",
        "evidence_group": case["evidence_group"],
        "scenario": case["scenario"],
        "status": "FAILED" if err_msg else "OK",
        "error_message": err_msg,
        "prepared_focuses": {},
        "prep_seconds": 0.0,
        "turn1": {
            "action": "INITIAL",
            "criterion_id": "c1",
            "depth": depth,
            "mode": mode,
            "question": q1_text,
            "generation_seconds": t1_sec,
            "question_calls": 1,
            "review_calls": 0,
            "alignment_rejections": 0,
            "review_verdicts": [],
        },
        "scripted_answer": case["scripted_answer"],
        "turn1_judgment": None,
        "turn2": {
            "finished": t2_decision == "FINISH" or not q2_text,
            "termination_reason": "ONE_SHOT_FINISH" if (t2_decision == "FINISH" or not q2_text) else None,
            "action": t2_decision,
            "criterion_id": "c2" if (t2_decision == "NEXT_CRITERION" and c2) else ("c1" if q2_text else None),
            "depth": depth,
            "mode": mode,
            "question": q2_text,
            "generation_seconds": t2_sec,
            "question_calls": 1,
            "review_calls": 0,
            "alignment_rejections": 0,
            "review_verdicts": [],
        },
        "telemetry": {
            "verification_timed_out": False,
            "verification_batch_failed": False,
            "jd_fallback_no_focus": False,
            "jd_fallback_cv_drafts_rejected": False,
            "events": [],
        },
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
    }


def _run_chain_condition(
    case: Dict[str, Any],
    condition: str,
    proxy: InstrumentedProviderProxy,
    capture: SessionTelemetryCapture,
) -> Dict[str, Any]:
    """Run Condition 2 (`chain_no_verification`) or Condition 3 (`chain_full_verification`)."""
    use_verification = condition == "chain_full_verification"
    sid = f"{case['case_id']}__{condition}"
    token = telemetry.session_id.set(sid)
    proxy.reset_counters()

    now = datetime(2026, 11, 20, tzinfo=timezone.utc)
    workflow = EvidenceWorkflow(
        proxy,
        clock=lambda: now,
        policy=InterviewPolicy(allow_extension_probes=False),
    )

    req_payload: Dict[str, Any] = {
        "session_id": sid,
        "config": {"max_questions": 3, "duration_seconds": 600, "interaction_mode": "TEXT"},
        "skills": [case["interview_skill"]],
        "blueprint": case["blueprint"],
    }
    if use_verification:
        req_payload["verification_sources"] = case["verification_sources"]

    err_msg = None
    prep_sec = 0.0
    t1_sec = 0.0
    t2_sec = 0.0
    prepared_focuses: Dict[str, Any] = {}
    t1_info: Dict[str, Any] = {}
    t2_info: Dict[str, Any] = {}
    t1_judgment: Optional[Dict[str, Any]] = None

    try:
        request = StartRequest.model_validate(req_payload)
        t0 = perf_counter()
        result = workflow.start(request)
        total_start_sec = perf_counter() - t0

        snap1 = result.snapshot
        ver = getattr(snap1, "verification", None)
        if ver is not None:
            prepared_focuses = {
                k.rsplit(":", 1)[-1]: v.model_dump(mode="json")
                for k, v in ver.focus_by_criterion.items()
            }

        c_after_t1 = proxy.get_counters()
        turn1 = snap1.pending_turn
        if turn1 is None:
            raise RuntimeError(f"Workflow finished immediately without Q1 (reason={snap1.termination_reason})")

        t1_verdicts = c_after_t1["review_verdicts"]
        t1_info = {
            "action": turn1.action.value,
            "criterion_id": turn1.question.criterion_ids[0].rsplit(":", 1)[-1],
            "full_criterion_id": turn1.question.criterion_ids[0],
            "depth": turn1.question_depth,
            "mode": turn1.mode.value,
            "evidence_scope": turn1.question.evidence_scope,
            "question": turn1.question.text,
            "generation_seconds": round(total_start_sec, 3),
            "question_calls": c_after_t1["question_calls"],
            "review_calls": c_after_t1["review_calls"],
            "alignment_rejections": sum(1 for v in t1_verdicts if v != "ALIGNED"),
            "review_verdicts": t1_verdicts,
        }

        # Turn 2: Submit frozen scripted answer, judge, and generate Q2 if not finished
        proxy.reset_counters()
        t_resp0 = perf_counter()
        resp_res = workflow.respond(
            TransitionRequest(
                snapshot=snap1,
                turn_id=turn1.turn_id,
                expected_state_version=snap1.state_version,
                candidate_response=case["scripted_answer"],
                defer_question=True,
            )
        )
        snap_after_judge = resp_res.snapshot
        completed_turn1 = snap_after_judge.turns[-1]
        if completed_turn1.judgment is not None:
            t1_judgment = completed_turn1.judgment.model_dump(mode="json")

        next_action = snap_after_judge.next_question_action
        q2_turn = None
        if next_action is not None:
            nq_res = workflow.next_question(
                NextQuestionRequest(
                    snapshot=snap_after_judge,
                    expected_state_version=snap_after_judge.state_version,
                )
            )
            snap2 = nq_res.snapshot
            q2_turn = snap2.pending_turn
        else:
            snap2 = snap_after_judge

        t2_sec = round(perf_counter() - t_resp0, 3)
        c_after_t2 = proxy.get_counters()
        t2_verdicts = c_after_t2["review_verdicts"]

        if q2_turn is not None:
            t2_info = {
                "finished": False,
                "termination_reason": None,
                "action": q2_turn.action.value,
                "criterion_id": q2_turn.question.criterion_ids[0].rsplit(":", 1)[-1],
                "full_criterion_id": q2_turn.question.criterion_ids[0],
                "depth": q2_turn.question_depth,
                "mode": q2_turn.mode.value,
                "evidence_scope": q2_turn.question.evidence_scope,
                "question": q2_turn.question.text,
                "generation_seconds": t2_sec,
                "question_calls": c_after_t2["question_calls"],
                "review_calls": c_after_t2["review_calls"],
                "alignment_rejections": sum(1 for v in t2_verdicts if v != "ALIGNED"),
                "review_verdicts": t2_verdicts,
            }
        else:
            t2_info = {
                "finished": True,
                "termination_reason": snap2.termination_reason,
                "action": "FINISH",
                "criterion_id": None,
                "depth": None,
                "mode": None,
                "question": "",
                "generation_seconds": t2_sec,
                "question_calls": c_after_t2["question_calls"],
                "review_calls": c_after_t2["review_calls"],
                "alignment_rejections": sum(1 for v in t2_verdicts if v != "ALIGNED"),
                "review_verdicts": t2_verdicts,
            }
    except Exception as exc:
        err_msg = f"{condition}:{type(exc).__name__}:{exc}"
        logger.warning(f"Failed {sid}: {err_msg}")
    finally:
        telemetry.session_id.reset(token)

    events, warnings = capture.pop_session(sid)
    for ev in events:
        if ev["event"] == "verification.prepared":
            try:
                prep_sec = float(ev["fields"].get("elapsed_seconds", 0.0))
            except ValueError:
                pass
    if t1_info:
        t1_info["generation_seconds"] = round(max(0.0, t1_info.get("generation_seconds", 0.0) - prep_sec), 3)

    return {
        "case_id": case["case_id"],
        "pair_id": case["pair_id"],
        "condition": condition,
        "evidence_group": case["evidence_group"],
        "scenario": case["scenario"],
        "status": "FAILED" if err_msg else "OK",
        "error_message": err_msg,
        "prepared_focuses": prepared_focuses,
        "prep_seconds": round(prep_sec, 3),
        "turn1": t1_info,
        "scripted_answer": case["scripted_answer"],
        "turn1_judgment": t1_judgment,
        "turn2": t2_info,
        "telemetry": {
            "verification_timed_out": any(ev["event"] == "verification.timed_out" for ev in events),
            "verification_batch_failed": any(ev["event"] == "verification.batch_failed" for ev in events),
            "jd_fallback_no_focus": any(
                ev["event"] == "verification.jd_context" and ev["fields"].get("reason") == "no_verified_focus"
                for ev in events
            ),
            "jd_fallback_cv_drafts_rejected": any(
                ev["event"] == "verification.jd_context" and ev["fields"].get("reason") == "cv_drafts_rejected"
                for ev in events
            ),
            "warning_count": len(warnings),
            "events": events,
        },
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
    }


def run_benchmark(
    cases_path: Path,
    runs_out: Path,
    *,
    conditions: Tuple[str, ...] = CONDITIONS,
    workers: int = 6,
    limit: Optional[int] = None,
) -> Dict[str, Any]:
    root = Path(__file__).resolve().parents[2]
    load_dotenv(root.parent / ".env", override=False)
    load_dotenv(root / ".env", override=False)

    payload = json.loads(cases_path.read_text(encoding="utf-8"))
    cases: List[Dict[str, Any]] = payload["cases"]
    if limit is not None:
        cases = cases[:limit]

    runs_out.parent.mkdir(parents=True, exist_ok=True)
    completed: Set[Tuple[str, str]] = set()
    if runs_out.exists():
        for line in runs_out.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                rec = json.loads(line)
                if rec.get("status") == "OK":
                    completed.add((rec["case_id"], rec["condition"]))
            except Exception:
                continue

    pending = [
        (case, cond)
        for case in cases
        for cond in conditions
        if (case["case_id"], cond) not in completed
    ]
    logger.info(f"Total cases={len(cases)}, already completed={len(completed)}, pending jobs={len(pending)}.")
    if not pending:
        return {"completed": len(completed), "pending": 0}

    provider = DSPyAssessmentProvider(compiled_dir=str(DEFAULT_COMPILED_DIR))
    proxy = InstrumentedProviderProxy(provider)
    student_model_raw = provider.lm.model.removeprefix("openrouter/")
    oa_client = openai.OpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=os.environ.get("OPENROUTER_API_KEY"),
        timeout=60.0,
    )

    capture = SessionTelemetryCapture()
    uv_logger = logging.getLogger("uvicorn.error")
    wf_logger = logging.getLogger("adaptive_questioning.evidence.workflow")
    uv_logger.setLevel(logging.INFO)
    uv_logger.addHandler(capture)
    wf_logger.addHandler(capture)

    write_lock = threading.Lock()
    done_cnt = 0
    ok_cnt = 0
    fail_cnt = 0
    t_start = perf_counter()

    def _run_job(case: Dict[str, Any], cond: str) -> Dict[str, Any]:
        if cond == "one_shot":
            return _run_one_shot(case, oa_client, student_model_raw)
        return _run_chain_condition(case, cond, proxy, capture)

    try:
        with open(runs_out, "a", encoding="utf-8") as fout:
            with ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
                futs = {pool.submit(_run_job, c, cond): (c["case_id"], cond) for c, cond in pending}
                for fut in as_completed(futs):
                    rec = fut.result()
                    with write_lock:
                        fout.write(json.dumps(rec, ensure_ascii=False) + "\n")
                        fout.flush()
                        done_cnt += 1
                        if rec["status"] == "OK":
                            ok_cnt += 1
                        else:
                            fail_cnt += 1
                        if done_cnt % 15 == 0 or done_cnt == len(pending):
                            logger.info(
                                f"Progress: {done_cnt}/{len(pending)} (ok={ok_cnt}, fail={fail_cnt}, "
                                f"elapsed={perf_counter() - t_start:.1f}s)"
                            )
    finally:
        uv_logger.removeHandler(capture)
        wf_logger.removeHandler(capture)

    elapsed = round(perf_counter() - t_start, 2)
    summary = {
        "runs_out": str(runs_out),
        "student_model": provider.lm.model,
        "review_model": provider.fast_lm.model,
        "jobs_run": done_cnt,
        "ok": ok_cnt,
        "failed": fail_cnt,
        "elapsed_seconds": elapsed,
    }
    logger.info(f"Module 3 benchmark run complete: {summary}")
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run 3-condition Module 3 benchmark on 100 fixed cases.")
    parser.add_argument("--cases", type=Path, default=Path("adaptive_questioning/optimization/results/module3_100_cases.json"))
    parser.add_argument("--runs-out", type=Path, default=Path("adaptive_questioning/optimization/results/module3_runs.jsonl"))
    parser.add_argument("--workers", type=int, default=6)
    parser.add_argument("--limit", type=int, default=None)
    args = parser.parse_args()
    run_benchmark(args.cases, args.runs_out, workers=args.workers, limit=args.limit)
