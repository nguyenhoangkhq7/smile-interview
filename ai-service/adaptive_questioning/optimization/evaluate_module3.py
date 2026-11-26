"""Evaluate Module 3 3-Condition Paired Ablation (Automated Checks + Blind Independent LLM-as-a-Judge).

Computes all deterministic checks and blind randomized cross-family LLM-as-a-Judge scores
(`google/gemini-2.5-flash` != student `qwen/qwen3.7-flash`) across all 100 paired CV-JD cases:
1. Automated checks: verbatim CV/JD source quoting, single-task compliance (`single_question`),
   missing-code guard, exact duplicate & SBERT Q1-Q2 similarity, preparation success/timeout/error,
   JD-fallback rate, alignment rejections, regeneration retries, question word length, latency.
2. Blind randomized LLM-as-a-Judge (anonymous A/B/C per case, shuffled order to mitigate position bias):
   - 6 QGEval-aligned criteria (pass/fail + 1-5 scale): target skill/gap alignment, source grounding
     without ungrounded CV claims, missing-detail focus, clarity/answerability/depth fit, adaptive
     Turn-2 response, avoiding repetition/over-probing.
   - `detail_to_verify` relevance audit for Condition 3 prepared focuses.
   - Blind pairwise preference / win-rate.
3. Paired statistical inference: 95% Wilson Score Confidence Intervals + Exact Paired McNemar
   test p-values comparing all condition pairs on the exact same 100 cases.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
import json
import logging
import math
import os
from pathlib import Path
import random
import sys
import threading
from typing import Any, Dict, List, Optional, Tuple

from dotenv import load_dotenv
import httpx  # noqa: F401 - eager import before ThreadPoolExecutor prevents Python 3.14 lazy-import race
import numpy as np
import openai
import scipy.stats

ai_service_dir = Path(__file__).resolve().parents[2]
if str(ai_service_dir) not in sys.path:
    sys.path.insert(0, str(ai_service_dir))

from adaptive_questioning.evidence.question_validation import (
    _missing_referenced_code,
    single_question,
)
from matching_cv.app.core.model_loader import ModelLoader

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logging.getLogger("httpx").setLevel(logging.WARNING)
logger = logging.getLogger("evaluate_module3")

CONDITIONS = ("one_shot", "chain_no_verification", "chain_full_verification")
JUDGE_CRITERIA = (
    "on_target_skill_gap",
    "source_grounded_no_hallucination",
    "focuses_missing_detail",
    "clear_answerable_depth_fit",
    "turn2_adapts_to_answer",
    "avoids_repetition_overprobing",
)


def wilson_ci_95(successes: int, total: int) -> Tuple[float, float, float]:
    """Return (rate, low_95, high_95) using the Wilson score interval."""
    if total <= 0:
        return 0.0, 0.0, 0.0
    z = 1.959963984540054
    p = successes / total
    denom = 1.0 + z * z / total
    center = (p + z * z / (2.0 * total)) / denom
    half = (z * math.sqrt((p * (1.0 - p) + z * z / (4.0 * total)) / total)) / denom
    return round(p, 4), round(max(0.0, center - half), 4), round(min(1.0, center + half), 4)


def mcnemar_exact(vec_a: List[int], vec_b: List[int]) -> Dict[str, Any]:
    """Exact paired McNemar test on binary outcomes for matched cases."""
    n = min(len(vec_a), len(vec_b))
    b = sum(1 for a, x in zip(vec_a, vec_b) if a == 1 and x == 0)  # A wins
    c = sum(1 for a, x in zip(vec_a, vec_b) if a == 0 and x == 1)  # B wins
    if b + c == 0:
        p_val = 1.0
    else:
        p_val = float(scipy.stats.binomtest(min(b, c), n=b + c, p=0.5, alternative="two-sided").pvalue)
    return {
        "n_paired": n,
        "a_only_pass": b,
        "b_only_pass": c,
        "diff_a_minus_b": round((sum(vec_a) - sum(vec_b)) / max(1, n), 4),
        "p_value": round(p_val, 5),
        "significant_0_05": p_val < 0.05,
    }


def _check_policy_adaptive_match(rec: Dict[str, Any], num_criteria: int) -> bool:
    """Deterministic structural check of Turn 2 adaptation against the controlled scenario."""
    scenario = rec["scenario"]
    t2 = rec.get("turn2") or {}
    finished = bool(t2.get("finished"))
    action = str(t2.get("action") or "").upper()
    crit2 = t2.get("criterion_id")
    judg = rec.get("turn1_judgment") or {}

    if scenario == "SUFFICIENT":
        # Should advance to c2 or cleanly finish — NOT stay repeating c1
        if finished:
            return True
        if num_criteria >= 2 and crit2 is not None and crit2 != "c1":
            return True
        return action == "NEXT_CRITERION"

    if scenario == "VAGUE":
        # Should probe/clarify c1 (NOT finish prematurely and NOT skip to c2)
        if finished:
            return False
        return (crit2 == "c1") and action in {"CLARIFY", "FOLLOW_UP", "PROBE_DEEPER", "ASK_EASIER"}

    if scenario == "CONTRADICT_CV":
        # Should probe/verify/clarify/diagnose c1 — must NOT accept c1 as AT_TARGET and move on
        obs = judg.get("observations") or []
        accepted_at_target = any(o.get("performance") in {"AT_TARGET", "ABOVE"} for o in obs)
        if accepted_at_target:
            return False
        if not finished and crit2 == "c1":
            return True
        return action in {"VERIFY_CONTRADICTION", "CLARIFY", "FOLLOW_UP", "ASK_EASIER"}

    if scenario == "NO_EXPERIENCE":
        # Should acknowledge inability and either ask easier diagnostic, move to c2, or finish
        if finished:
            return True
        if action in {"ASK_EASIER", "NEXT_CRITERION"}:
            return True
        if crit2 is not None and crit2 != "c1":
            return True
        return bool(judg.get("explicit_inability")) and action != "INITIAL"

    return False


def _blind_judge_case(
    client: openai.OpenAI,
    judge_model: str,
    case: Dict[str, Any],
    runs_by_cond: Dict[str, Dict[str, Any]],
    case_idx: int,
) -> Dict[str, Any]:
    """Run one blind randomized 3-way evaluation with an independent cross-family Judge LM."""
    rng = random.Random(42 + case_idx)
    cond_order = list(CONDITIONS)
    rng.shuffle(cond_order)
    label_to_cond = {lbl: c for lbl, c in zip(("A", "B", "C"), cond_order)}
    cond_to_label = {c: lbl for lbl, c in label_to_cond.items()}

    obj = case["blueprint"]["objectives"][0]
    c1 = obj["criteria"][0]
    c2 = obj["criteria"][1] if len(obj["criteria"]) > 1 else None
    isk = case["interview_skill"]

    systems_block = []
    for lbl in ("A", "B", "C"):
        cond = label_to_cond[lbl]
        rec = runs_by_cond[cond]
        t1 = rec.get("turn1") or {}
        t2 = rec.get("turn2") or {}
        t2_desc = (
            f"[KẾT THÚC / KHÔNG HỎI THÊM] (reason={t2.get('termination_reason')})"
            if t2.get("finished") or not t2.get("question")
            else f"[Action={t2.get('action')}, Target={t2.get('criterion_id')}] {t2.get('question')}"
        )
        systems_block.append(
            f"### Hệ thống {lbl}\n"
            f"- Câu hỏi lượt 1 (Q1): {t1.get('question', '')}\n"
            f"- Phản hồi/Câu hỏi lượt 2 (Q2): {t2_desc}\n"
        )

    focus_dict = runs_by_cond["chain_full_verification"].get("prepared_focuses") or {}
    c1_focus = focus_dict.get("c1") or (next(iter(focus_dict.values())) if focus_dict else None)
    focus_eval_note = (
        f"Chi tiết xác minh chuẩn bị trước (đánh giá riêng độc lập): {json.dumps(c1_focus, ensure_ascii=False)}"
        if c1_focus else "Không có chi tiết xác minh chuẩn bị trước (trả về prepared_focus_relevant = null)."
    )

    scenario_expectation = {
        "SUFFICIENT": "Ứng viên đã trả lời ĐỦ bằng chứng cho c1 -> Hệ thống tốt KHÔNG hỏi lặp lại c1, mà chuyển sang c2 hoặc kết thúc.",
        "VAGUE": "Ứng viên trả lời MƠ HỒ, thiếu bằng chứng cốt lõi của c1 -> Hệ thống tốt phải hỏi làm rõ đúng phần còn thiếu của c1.",
        "CONTRADICT_CV": "Ứng viên trả lời MÂU THUẪN với thông tin CV hoặc sai kiến thức -> Hệ thống tốt yêu cầu làm rõ/xác minh trung lập, KHÔNG quy chụp ứng viên nói dối và KHÔNG bỏ qua.",
        "NO_EXPERIENCE": "Ứng viên thừa nhận CHƯA CÓ KINH NGHIỆM -> Hệ thống tốt ghi nhận lịch sự và chuyển tiếp (hạ độ khó nền tảng, sang tiêu chí khác, hoặc kết thúc), KHÔNG hỏi vòng quanh/ép trả lời.",
    }[case["scenario"]]

    prompt = f"""Bạn là giám khảo đánh giá độc lập chất lượng hệ thống phỏng vấn kỹ thuật AI (theo khung QGEval).
Hãy đánh giá MÙ và ĐỘC LẬP từng hệ thống A, B, C trên cùng một ca phỏng vấn dưới đây. KHÔNG thiên vị thứ tự hay độ dài câu hỏi; ưu tiên sự chính xác, bám nguồn CV/JD, tập trung một nhiệm vụ và thích ứng đúng ngữ cảnh.

## Bối cảnh ca phỏng vấn
- Kỹ năng mục tiêu: {isk.get('jd_skill_name') or isk['jd_skill_id']} (mức độ sâu yêu cầu: L{obj['target_depth']}, chế độ: {obj['suitable_modes'][0]['mode']})
- Yêu cầu JD: {obj['claim']}
- Trích đoạn JD gốc: {json.dumps(isk.get('jd_evidence_spans', []), ensure_ascii=False)}
- Trích đoạn CV gốc (nếu rỗng nghĩa là CV KHÔNG có bằng chứng cho kỹ năng này): {json.dumps(isk.get('cv_evidence_spans', []), ensure_ascii=False)}
- Tiêu chí 1 (c1): {c1['description']} | Bằng chứng kỳ vọng: {c1['expected_evidence']} | Đạt chuẩn: {c1['at_target']}
- Tiêu chí 2 (c2): {c2['description'] if c2 else 'Không có (chỉ có 1 tiêu chí)'}
- Câu trả lời kiểm soát của ứng viên sau Q1 (kịch bản {case['scenario']}): "{case['scripted_answer']}"
- Hành vi kỳ vọng ở lượt 2: {scenario_expectation}

## Đầu ra 3 hệ thống (đã ẩn danh và xáo trộn thứ tự)
{''.join(systems_block)}

## Đánh giá bổ sung chi tiết xác minh
{focus_eval_note}

## Rubric chấm cho MỖI hệ thống A, B, C (thang 1-5 nguyên và boolean pass = score >= 4):
1. `on_target_skill_gap`: Q1 có đánh đúng kỹ năng và tiêu chí/khoảng trống mục tiêu không?
2. `source_grounded_no_hallucination`: Thông tin nêu về CV/JD trong Q1 & Q2 có hoàn toàn căn cứ trong trích đoạn nguồn không? (Đặt `has_ungrounded_cv_claim = true` nếu hệ thống bịa đặt chi tiết CV hoặc gán kinh nghiệm CV không có trong trích đoạn CV gốc).
3. `focuses_missing_detail`: Q1 có tập trung làm rõ đúng chi tiết còn bỏ ngỏ/cần kiểm chứng (hoặc bám sát nhiệm vụ JD nếu CV không có bằng chứng) không?
4. `clear_answerable_depth_fit`: Q1 & Q2 có rõ ràng, trả lời được trực tiếp, chỉ yêu cầu 1 nhiệm vụ, đúng độ sâu L{obj['target_depth']} và không gợi sẵn đáp án không?
5. `turn2_adapts_to_answer`: Quyết định/câu hỏi lượt 2 có phản ánh đúng câu trả lời vừa nhận theo kịch bản {case['scenario']} không?
6. `avoids_repetition_overprobing`: Hệ thống có tránh hỏi lặp lại ý cũ hoặc tiếp tục đào sâu khi ứng viên đã đủ bằng chứng / đã thừa nhận không biết không? (Đặt `has_unnecessary_repetition = true` nếu có lặp/lan man).

Trả về STRICT JSON đúng định dạng sau (không thêm văn bản ngoài JSON):
{{
  "systems": {{
    "A": {{
      "on_target_skill_gap": {{"score": 1-5, "pass": true/false}},
      "source_grounded_no_hallucination": {{"score": 1-5, "pass": true/false}},
      "focuses_missing_detail": {{"score": 1-5, "pass": true/false}},
      "clear_answerable_depth_fit": {{"score": 1-5, "pass": true/false}},
      "turn2_adapts_to_answer": {{"score": 1-5, "pass": true/false}},
      "avoids_repetition_overprobing": {{"score": 1-5, "pass": true/false}},
      "has_ungrounded_cv_claim": true/false,
      "has_unnecessary_repetition": true/false
    }},
    "B": {{ ... }},
    "C": {{ ... }}
  }},
  "best_system": "A" | "B" | "C" | "TIE",
  "prepared_focus_relevant": true | false | null,
  "brief_note": "Tóm tắt ngắn gọn <= 200 ký tự"
}}"""

    for attempt in range(3):
        try:
            resp = client.chat.completions.create(
                model=judge_model,
                messages=[{"role": "user", "content": prompt}],
                response_format={"type": "json_object"},
                temperature=0.0,
                seed=42,
                max_tokens=1024,
            )
            parsed = json.loads(resp.choices[0].message.content.strip())
            sys_map = parsed["systems"]
            assert all(lbl in sys_map for lbl in ("A", "B", "C"))
            # Unblind back to real condition names
            by_cond = {label_to_cond[lbl]: sys_map[lbl] for lbl in ("A", "B", "C")}
            best_raw = str(parsed.get("best_system", "TIE")).strip().upper()
            best_cond = label_to_cond.get(best_raw, "TIE")
            return {
                "case_id": case["case_id"],
                "pair_id": case["pair_id"],
                "evidence_group": case["evidence_group"],
                "scenario": case["scenario"],
                "judge_model": judge_model,
                "label_order": label_to_cond,
                "by_condition": by_cond,
                "best_condition": best_cond,
                "prepared_focus_relevant": parsed.get("prepared_focus_relevant"),
                "brief_note": str(parsed.get("brief_note", ""))[:300],
                "status": "OK",
            }
        except Exception as exc:
            logger.warning(f"Judge retry {attempt + 1}/3 failed on {case['case_id']}: {exc}")

    return {
        "case_id": case["case_id"],
        "pair_id": case["pair_id"],
        "status": "FAILED",
        "by_condition": {},
        "best_condition": "TIE",
        "prepared_focus_relevant": None,
    }


def evaluate_module3(
    cases_path: Path,
    runs_path: Path,
    judge_cache_path: Path,
    report_out: Path,
    *,
    judge_model: str = "google/gemini-2.5-flash",
    workers: int = 6,
) -> Dict[str, Any]:
    root = Path(__file__).resolve().parents[2]
    load_dotenv(root.parent / ".env", override=False)
    load_dotenv(root / ".env", override=False)

    payload = json.loads(cases_path.read_text(encoding="utf-8"))
    cases: List[Dict[str, Any]] = payload["cases"]
    case_by_id = {c["case_id"]: c for c in cases}

    # Load latest OK (or latest FAILED) run record per (case_id, condition)
    runs_map: Dict[Tuple[str, str], Dict[str, Any]] = {}
    for line in runs_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        r = json.loads(line)
        k = (r["case_id"], r["condition"])
        if k not in runs_map or r.get("status") == "OK":
            runs_map[k] = r

    # Filter to cases where all 3 conditions exist
    eval_cases = [
        c for c in cases
        if all((c["case_id"], cond) in runs_map for cond in CONDITIONS)
    ]
    logger.info(f"Evaluating {len(eval_cases)} paired cases across {len(CONDITIONS)} conditions.")

    # 1. Compute SBERT Q1-Q2 cosine similarity via Module 1 model
    logger.info("Loading SBERT model for Q1-Q2 semantic similarity check...")
    sbert = ModelLoader().load_model()

    def _sbert_cos(a: str, b: str) -> Optional[float]:
        if not a.strip() or not b.strip():
            return None
        vecs = sbert.encode([a.strip(), b.strip()])
        v0, v1 = np.asarray(vecs[0], dtype=np.float32), np.asarray(vecs[1], dtype=np.float32)
        denom = float(np.linalg.norm(v0) * np.linalg.norm(v1))
        return round(float(np.clip(np.dot(v0, v1) / max(1e-12, denom), 0.0, 1.0)), 4)

    # 2. Run Blind Independent LLM-as-a-Judge (with resumable JSONL cache)
    judge_by_case: Dict[str, Dict[str, Any]] = {}
    if judge_cache_path.exists():
        for line in judge_cache_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            jr = json.loads(line)
            if jr.get("status") == "OK":
                judge_by_case[jr["case_id"]] = jr

    pending_judge = [
        (idx, c) for idx, c in enumerate(eval_cases)
        if c["case_id"] not in judge_by_case
        and all(runs_map[(c["case_id"], cond)].get("status") == "OK" for cond in CONDITIONS)
    ]
    if pending_judge:
        logger.info(f"Running blind randomized LLM-as-a-Judge ({judge_model}) on {len(pending_judge)} cases...")
        oa_client = openai.OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=os.environ.get("OPENROUTER_API_KEY"),
            timeout=60.0,
        )
        lock = threading.Lock()
        done = 0
        with open(judge_cache_path, "a", encoding="utf-8") as jf:
            with ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
                futs = {
                    pool.submit(
                        _blind_judge_case,
                        oa_client,
                        judge_model,
                        c,
                        {cond: runs_map[(c["case_id"], cond)] for cond in CONDITIONS},
                        idx,
                    ): c["case_id"]
                    for idx, c in pending_judge
                }
                for fut in as_completed(futs):
                    jr = fut.result()
                    with lock:
                        jf.write(json.dumps(jr, ensure_ascii=False) + "\n")
                        jf.flush()
                        if jr.get("status") == "OK":
                            judge_by_case[jr["case_id"]] = jr
                        done += 1
                        if done % 20 == 0 or done == len(pending_judge):
                            logger.info(f"  Judge progress: {done}/{len(pending_judge)}")

    # 3. Aggregate Automated + Blind Judge Metrics per condition
    cond_reports: Dict[str, Any] = {}
    paired_binary_vecs: Dict[str, Dict[str, List[int]]] = {cond: defaultdict(list) for cond in CONDITIONS}
    paired_case_ids = [
        c["case_id"] for c in eval_cases
        if c["case_id"] in judge_by_case
        and all(runs_map[(c["case_id"], cond)].get("status") == "OK" for cond in CONDITIONS)
    ]

    for cond in CONDITIONS:
        recs = [runs_map[(c["case_id"], cond)] for c in eval_cases]
        ok_recs = [r for r in recs if r.get("status") == "OK"]
        n_total = len(recs)
        n_ok = len(ok_recs)

        single_q1, single_q2 = [], []
        miss_code_q1, miss_code_q2 = [], []
        exact_dup = []
        cos_all = []
        cos_by_scenario: Dict[str, List[float]] = defaultdict(list)
        q_words = []
        turns_on_c1 = []
        t1_secs, t2_secs, prep_secs = [], [], []
        align_rejs, regen_retries = [], []
        pol_adapt_all = []
        pol_adapt_by_scenario: Dict[str, List[int]] = defaultdict(list)

        # Verification telemetry & source grounding
        eligible_cv_cases = 0
        prep_produced_focus = 0
        prep_timeouts = 0
        prep_batch_fails = 0
        jd_fb_no_focus = 0
        jd_fb_rejected = 0
        cv_quotes_total = 0
        cv_quotes_exact = 0
        jd_quotes_total = 0
        jd_quotes_exact = 0

        for r in ok_recs:
            c = case_by_id[r["case_id"]]
            num_crit = len(c["blueprint"]["objectives"][0]["criteria"])
            t1 = r.get("turn1") or {}
            t2 = r.get("turn2") or {}
            q1 = str(t1.get("question") or "")
            q2 = str(t2.get("question") or "")

            single_q1.append(1 if (q1 and single_question(q1)) else 0)
            miss_code_q1.append(1 if (q1 and _missing_referenced_code(q1)) else 0)
            if q1:
                q_words.append(len(q1.split()))

            if q2 and not t2.get("finished"):
                single_q2.append(1 if single_question(q2) else 0)
                miss_code_q2.append(1 if _missing_referenced_code(q2) else 0)
                q_words.append(len(q2.split()))
                dup = 1 if (" ".join(q1.casefold().split()) == " ".join(q2.casefold().split())) else 0
                exact_dup.append(dup)
                cs = _sbert_cos(q1, q2)
                if cs is not None:
                    cos_all.append(cs)
                    cos_by_scenario[r["scenario"]].append(cs)

            turns_c1 = 1 + (1 if (not t2.get("finished") and t2.get("criterion_id") == "c1") else 0)
            turns_on_c1.append(turns_c1)

            t1_secs.append(float(t1.get("generation_seconds") or 0.0))
            t2_secs.append(float(t2.get("generation_seconds") or 0.0))
            prep_secs.append(float(r.get("prep_seconds") or 0.0))

            align_rejs.append(int(t1.get("alignment_rejections") or 0) + int(t2.get("alignment_rejections") or 0))
            regen_retries.append(
                max(0, int(t1.get("question_calls") or 0) - 1)
                + max(0, int(t2.get("question_calls") or 0) - (0 if t2.get("finished") else 1))
            )

            pa = 1 if _check_policy_adaptive_match(r, num_crit) else 0
            pol_adapt_all.append(pa)
            pol_adapt_by_scenario[r["scenario"]].append(pa)

            # Verification checks
            tel = r.get("telemetry") or {}
            if tel.get("verification_timed_out"):
                prep_timeouts += 1
            if tel.get("verification_batch_failed"):
                prep_batch_fails += 1
            if tel.get("jd_fallback_no_focus"):
                jd_fb_no_focus += 1
            if tel.get("jd_fallback_cv_drafts_rejected"):
                jd_fb_rejected += 1

            isk = c["interview_skill"]
            is_eligible = (isk.get("semantic_alignment") != "MISSING") and bool(isk.get("cv_evidence_spans"))
            focuses = r.get("prepared_focuses") or {}
            if is_eligible:
                eligible_cv_cases += 1
                if focuses:
                    prep_produced_focus += 1
            for f in focuses.values():
                cv_ex = f.get("cv_excerpt")
                if cv_ex:
                    cv_quotes_total += 1
                    if cv_ex in c["cv_text"]:
                        cv_quotes_exact += 1
                jd_ex = f.get("jd_excerpt")
                if jd_ex:
                    jd_quotes_total += 1
                    if jd_ex in c["jd_text"]:
                        jd_quotes_exact += 1

        # Judge metrics across paired cases
        judge_metric_summary: Dict[str, Any] = {}
        ungrounded_cv_flags: List[int] = []
        unnecessary_rep_flags: List[int] = []
        judge_by_group: Dict[str, Dict[str, List[int]]] = defaultdict(lambda: defaultdict(list))
        judge_by_scenario: Dict[str, Dict[str, List[int]]] = defaultdict(lambda: defaultdict(list))

        for cid in paired_case_ids:
            jr = judge_by_case[cid]
            j_cond = jr["by_condition"][cond]
            grp = jr["evidence_group"]
            sc = jr["scenario"]

            # Store deterministic paired binary flags too
            rec = runs_map[(cid, cond)]
            q1 = str((rec.get("turn1") or {}).get("question") or "")
            paired_binary_vecs[cond]["single_task_q1"].append(1 if (q1 and single_question(q1)) else 0)
            paired_binary_vecs[cond]["policy_adaptive_match"].append(
                1 if _check_policy_adaptive_match(rec, len(case_by_id[cid]["blueprint"]["objectives"][0]["criteria"])) else 0
            )

            for crit in JUDGE_CRITERIA:
                item = j_cond[crit]
                passed = 1 if bool(item.get("pass")) else 0
                paired_binary_vecs[cond][crit].append(passed)
                judge_by_group[grp][crit].append(passed)
                judge_by_scenario[sc][crit].append(passed)

            ug = 1 if bool(j_cond.get("has_ungrounded_cv_claim")) else 0
            ur = 1 if bool(j_cond.get("has_unnecessary_repetition")) else 0
            ungrounded_cv_flags.append(ug)
            unnecessary_rep_flags.append(ur)
            paired_binary_vecs[cond]["no_ungrounded_cv_claim"].append(1 - ug)
            paired_binary_vecs[cond]["no_unnecessary_repetition"].append(1 - ur)

        for crit in JUDGE_CRITERIA:
            scores = [float(judge_by_case[cid]["by_condition"][cond][crit]["score"]) for cid in paired_case_ids]
            passes = paired_binary_vecs[cond][crit]
            rate, lo, hi = wilson_ci_95(sum(passes), len(passes))
            judge_metric_summary[crit] = {
                "pass_rate": rate,
                "ci_95": [lo, hi],
                "mean_score_1_5": round(float(np.mean(scores)), 3) if scores else 0.0,
                "std_score": round(float(np.std(scores)), 3) if scores else 0.0,
            }

        ug_rate, ug_lo, ug_hi = wilson_ci_95(sum(ungrounded_cv_flags), len(ungrounded_cv_flags))
        ur_rate, ur_lo, ur_hi = wilson_ci_95(sum(unnecessary_rep_flags), len(unnecessary_rep_flags))
        st1_rate, st1_lo, st1_hi = wilson_ci_95(sum(single_q1), len(single_q1))
        pa_rate, pa_lo, pa_hi = wilson_ci_95(sum(pol_adapt_all), len(pol_adapt_all))

        cond_reports[cond] = {
            "cases_total": n_total,
            "cases_ok": n_ok,
            "error_rate": round((n_total - n_ok) / max(1, n_total), 4),
            "automated_checks": {
                "single_task_q1_rate": st1_rate,
                "single_task_q1_ci_95": [st1_lo, st1_hi],
                "single_task_q2_rate": round(float(np.mean(single_q2)), 4) if single_q2 else None,
                "missing_code_error_rate_q1": round(float(np.mean(miss_code_q1)), 4) if miss_code_q1 else 0.0,
                "exact_duplicate_q1_q2_rate": round(float(np.mean(exact_dup)), 4) if exact_dup else 0.0,
                "mean_q1_q2_sbert_cosine": round(float(np.mean(cos_all)), 4) if cos_all else None,
                "q1_q2_sbert_cosine_by_scenario": {
                    sc: round(float(np.mean(vs)), 4) for sc, vs in sorted(cos_by_scenario.items())
                },
                "policy_adaptive_match_rate": pa_rate,
                "policy_adaptive_match_ci_95": [pa_lo, pa_hi],
                "policy_adaptive_by_scenario": {
                    sc: round(float(np.mean(vs)), 4) for sc, vs in sorted(pol_adapt_by_scenario.items())
                },
                "mean_turns_on_c1": round(float(np.mean(turns_on_c1)), 3) if turns_on_c1 else 0.0,
                "mean_question_words": round(float(np.mean(q_words)), 1) if q_words else 0.0,
                "mean_alignment_rejections_per_case": round(float(np.mean(align_rejs)), 3) if align_rejs else 0.0,
                "total_alignment_rejections": int(sum(align_rejs)),
                "total_regen_retries": int(sum(regen_retries)),
                "mean_prep_seconds": round(float(np.mean(prep_secs)), 3) if prep_secs else 0.0,
                "mean_t1_seconds": round(float(np.mean(t1_secs)), 3) if t1_secs else 0.0,
                "mean_t2_seconds": round(float(np.mean(t2_secs)), 3) if t2_secs else 0.0,
            },
            "verification_telemetry": {
                "eligible_cv_cases": eligible_cv_cases,
                "prep_success_on_eligible_rate": round(prep_produced_focus / max(1, eligible_cv_cases), 4) if cond == "chain_full_verification" else None,
                "prep_timeout_count": prep_timeouts,
                "prep_batch_fail_count": prep_batch_fails,
                "jd_fallback_no_focus_count": jd_fb_no_focus,
                "jd_fallback_cv_drafts_rejected_count": jd_fb_rejected,
                "cv_source_quotes_exact_rate": round(cv_quotes_exact / cv_quotes_total, 4) if cv_quotes_total else None,
                "cv_source_quotes_count": cv_quotes_total,
                "jd_source_quotes_exact_rate": round(jd_quotes_exact / jd_quotes_total, 4) if jd_quotes_total else None,
                "jd_source_quotes_count": jd_quotes_total,
            },
            "blind_independent_judge": {
                "n_paired": len(paired_case_ids),
                "criteria": judge_metric_summary,
                "ungrounded_cv_claim_rate": ug_rate,
                "ungrounded_cv_claim_ci_95": [ug_lo, ug_hi],
                "unnecessary_repetition_rate": ur_rate,
                "unnecessary_repetition_ci_95": [ur_lo, ur_hi],
                "by_evidence_group": {
                    grp: {cr: round(float(np.mean(vs)), 4) for cr, vs in cr_map.items()}
                    for grp, cr_map in sorted(judge_by_group.items())
                },
                "by_scenario": {
                    sc: {cr: round(float(np.mean(vs)), 4) for cr, vs in cr_map.items()}
                    for sc, cr_map in sorted(judge_by_scenario.items())
                },
            },
        }

    # Blind preference win-rates & prepared_focus relevance
    best_counts = Counter(judge_by_case[cid]["best_condition"] for cid in paired_case_ids)
    focus_rels = [
        judge_by_case[cid]["prepared_focus_relevant"]
        for cid in paired_case_ids
        if judge_by_case[cid].get("prepared_focus_relevant") is not None
    ]
    focus_rel_rate, focus_lo, focus_hi = wilson_ci_95(sum(1 for x in focus_rels if x), len(focus_rels))

    # Paired McNemar significance tests
    comparisons = [
        ("chain_no_verification_vs_one_shot", "chain_no_verification", "one_shot"),
        ("chain_full_vs_chain_no_verification", "chain_full_verification", "chain_no_verification"),
        ("chain_full_vs_one_shot", "chain_full_verification", "one_shot"),
    ]
    mcnemar_metrics = [
        "single_task_q1",
        "policy_adaptive_match",
        *JUDGE_CRITERIA,
        "no_ungrounded_cv_claim",
        "no_unnecessary_repetition",
    ]
    paired_tests: Dict[str, Dict[str, Any]] = {}
    for comp_name, ca, cb in comparisons:
        paired_tests[comp_name] = {
            m: mcnemar_exact(paired_binary_vecs[ca][m], paired_binary_vecs[cb][m])
            for m in mcnemar_metrics
        }

    report = {
        "benchmark_name": "Module 3 Paired Ablation (CV Verification + Adaptive Questioning)",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "total_paired_cases": len(paired_case_ids),
        "judge_model": judge_model,
        "blind_randomized_order": True,
        "scientific_disclosures": [
            "Synthetic CV-JD pairs and controlled scripted candidate answers are used to isolate workflow behavior; they are NOT real HR expert evaluations.",
            "Independent cross-family LLM-as-a-Judge (google/gemini-2.5-flash != qwen/qwen3.7-flash) with anonymized randomized A/B/C ordering is used as a proxy evaluation; LLM judges may retain residual length/style biases (Zheng et al., NeurIPS 2023).",
            "In Condition 2 (`chain_no_verification`), passing `verification_sources=None` causes `EvidenceWorkflow` to omit CV spans and run in JD-only scenario mode, isolating the joint effect of verified CV/JD source grounding + `detail_to_verify` preparation in Condition 3.",
        ],
        "blind_preference_counts": dict(best_counts),
        "blind_preference_rates": {
            k: round(v / max(1, len(paired_case_ids)), 4) for k, v in best_counts.items()
        },
        "prepared_focus_relevance": {
            "evaluated_focuses": len(focus_rels),
            "relevant_rate": focus_rel_rate,
            "ci_95": [focus_lo, focus_hi],
        },
        "conditions": cond_reports,
        "paired_mcnemar_tests": paired_tests,
    }

    report_out.parent.mkdir(parents=True, exist_ok=True)
    report_out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info(f"Module 3 evaluation report saved to {report_out}")

    # Print crisp summary table
    print("\n=== MODULE 3 BENCHMARK SUMMARY (N=" + str(len(paired_case_ids)) + " Paired CV-JD Cases) ===")
    hdr = (
        f"{'Condition':<24} | {'1-Task':>6} | {'PolAdp':>6} | {'OnTgt':>6} | {'SrcGnd':>6} | "
        f"{'Focus':>6} | {'ClrDep':>6} | {'T2Adp':>6} | {'NoRep':>6} | {'UngCV%':>6} | {'Win%':>6} | {'Q1+Q2s':>6}"
    )
    print(hdr)
    print("-" * len(hdr))
    for cond in CONDITIONS:
        c = cond_reports[cond]
        ac = c["automated_checks"]
        bj = c["blind_independent_judge"]
        cr = bj["criteria"]
        win_r = report["blind_preference_rates"].get(cond, 0.0)
        tot_s = ac["mean_prep_seconds"] + ac["mean_t1_seconds"] + ac["mean_t2_seconds"]
        print(
            f"{cond:<24} | "
            f"{ac['single_task_q1_rate']*100:5.1f}% | "
            f"{ac['policy_adaptive_match_rate']*100:5.1f}% | "
            f"{cr['on_target_skill_gap']['pass_rate']*100:5.1f}% | "
            f"{cr['source_grounded_no_hallucination']['pass_rate']*100:5.1f}% | "
            f"{cr['focuses_missing_detail']['pass_rate']*100:5.1f}% | "
            f"{cr['clear_answerable_depth_fit']['pass_rate']*100:5.1f}% | "
            f"{cr['turn2_adapts_to_answer']['pass_rate']*100:5.1f}% | "
            f"{cr['avoids_repetition_overprobing']['pass_rate']*100:5.1f}% | "
            f"{bj['ungrounded_cv_claim_rate']*100:5.1f}% | "
            f"{win_r*100:5.1f}% | "
            f"{tot_s:5.1f}s"
        )
    print(f"Prepared Focus Relevance (Condition 3): {focus_rel_rate*100:.1f}% (n={len(focus_rels)}, 95% CI [{focus_lo*100:.1f}%, {focus_hi*100:.1f}%])")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Evaluate Module 3 3-condition paired runs.")
    parser.add_argument("--cases", type=Path, default=Path("adaptive_questioning/optimization/results/module3_100_cases.json"))
    parser.add_argument("--runs", type=Path, default=Path("adaptive_questioning/optimization/results/module3_runs.jsonl"))
    parser.add_argument("--judge-cache", type=Path, default=Path("adaptive_questioning/optimization/results/module3_judge_scores.jsonl"))
    parser.add_argument("--report-out", type=Path, default=Path("adaptive_questioning/optimization/results/module3_evaluation_report.json"))
    parser.add_argument("--judge-model", type=str, default="google/gemini-2.5-flash")
    parser.add_argument("--workers", type=int, default=6)
    args = parser.parse_args()
    evaluate_module3(
        args.cases,
        args.runs,
        args.judge_cache,
        args.report_out,
        judge_model=args.judge_model,
        workers=args.workers,
    )
