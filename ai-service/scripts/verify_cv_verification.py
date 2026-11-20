"""Run one synthetic CV/JD case on the configured provider, before or after a change."""
import argparse
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

from adaptive_questioning.evidence.models import NextQuestionRequest, StartRequest, TransitionRequest
from adaptive_questioning.evidence.policy_config import InterviewPolicy
from adaptive_questioning.evidence.provider import DSPyAssessmentProvider
from adaptive_questioning.evidence.workflow import EvidenceWorkflow
from adaptive_questioning.optimization.compiler import DEFAULT_COMPILED_DIR

JD = "Giải thích cách API tạo đơn xử lý việc client gửi lại yêu cầu sau timeout."
CV = "Đã xử lý lỗi tạo đơn hàng trùng khi client gửi lại yêu cầu."
TASK_ID = "create-order-retry"
SKILL = "api_http"
CRITERIA = [
    {
        "description": "Nhận diện hai lần gửi của cùng một yêu cầu tạo đơn.",
        "expected_evidence": "Một định danh ổn định để đối chiếu lần gửi lại với yêu cầu đã lưu.",
        "below_target": "Dựa trên dữ liệu có thể thay đổi giữa hai lần gửi.",
        "at_target": "Giữ nguyên định danh khi thử lại và đối chiếu với bản ghi đã lưu.",
        "above_target": "Giới hạn phạm vi định danh để phân biệt các nguồn gửi.",
    },
    {
        "description": "Xử lý lần gửi lại khi yêu cầu gốc đã hoàn tất.",
        "expected_evidence": "Cách trả lại kết quả của lần xử lý gốc cho yêu cầu trùng.",
        "below_target": "Tạo thêm một đơn cho yêu cầu đã hoàn tất.",
        "at_target": "Trả lại kết quả đã lưu của lần xử lý gốc.",
        "above_target": "Diễn giải được cách giữ nhất quán kết quả qua các lần gửi lại.",
    },
]
ANSWERS = {
    "c1": ["Em kiểm tra trong database.",
           "Client giữ nguyên idempotency key khi gửi lại. Server tra khóa đó trong database."],
    "c2": ["Server trả lại mã đơn và phản hồi đã lưu ở lần xử lý gốc."],
}


def scenario() -> StartRequest:
    return StartRequest.model_validate({
        "session_id": "synthetic-cv-verification",
        "config": {"max_questions": 3, "duration_seconds": 600},
        "skills": [{
            "jd_skill_id": SKILL, "jd_skill_name": "HTTP API", "semantic_alignment": "MATCH",
            "required_proficiency": 3, "importance_weight": 0.9, "cv_evidence_spans": [CV],
            "job_tasks": [{"task_id": TASK_ID, "description": JD, "required_level": 3,
                           "evidence_spans": [JD], "requirement_kind": "REQUIRED"}],
        }],
        "blueprint": {"objectives": [{
            "requirement_id": f"{SKILL}:{TASK_ID}", "skill_id": SKILL, "claim": JD,
            "target_depth": 2, "depth_basis": "TASK",
            "depth_rationale": "Vận dụng cách nhận diện yêu cầu gửi lại vào một API cụ thể.",
            "depth_evidence_spans": [JD], "criteria": CRITERIA,
            "suitable_modes": [{"mode": "TECHNICAL_EXPLANATION"}],
        }]},
        "verification_sources": {"cv": {CV: CV}, "jd": {JD: JD}},
    })


def run(provider: DSPyAssessmentProvider) -> dict:
    now = datetime(2026, 11, 20, tzinfo=timezone.utc)
    workflow = EvidenceWorkflow(provider, clock=lambda: now, policy=InterviewPolicy(allow_extension_probes=False))
    request = scenario()
    result = workflow.start(request)
    verification = getattr(result.snapshot, "verification", None)
    counts: Counter[str] = Counter()
    while result.snapshot.pending_turn is not None:
        snapshot = result.snapshot
        turn = snapshot.pending_turn
        key = turn.question.criterion_ids[0].rsplit(":", 1)[-1]
        answers = ANSWERS[key]
        reply = answers[min(counts[key], len(answers) - 1)]
        counts[key] += 1
        result = workflow.respond(TransitionRequest(
            snapshot=snapshot, turn_id=turn.turn_id,
            expected_state_version=snapshot.state_version, candidate_response=reply,
            defer_question=True,
        ))
        if result.snapshot.next_question_action is not None:
            result = workflow.next_question(NextQuestionRequest(
                snapshot=result.snapshot, expected_state_version=result.snapshot.state_version,
            ))
    report = result.public.report.objectives[0]
    return {
        "model": provider.lm.model,
        "review_model": provider.fast_lm.model,
        "cv": CV, "jd": JD, "criteria": CRITERIA, "question_budget": request.config.max_questions,
        "target_depth": 2,
        "prepared_focuses": {key.rsplit(":", 1)[-1]: focus.model_dump(mode="json")
                             for key, focus in verification.focus_by_criterion.items()} if verification else {},
        "turns": [{
            "criterion": turn.question.criterion_ids[0].rsplit(":", 1)[-1],
            "action": turn.action.value, "question": turn.question.text, "answer": turn.answer,
            "observations": [item.model_dump(mode="json") for item in turn.judgment.observations],
        } for turn in result.snapshot.turns],
        "criteria_assessments": {item.criterion_id.rsplit(":", 1)[-1]: item.assessment.value
                                 for item in report.criteria},
        "essential_criteria_asked": {"count": len(counts), "total": len(CRITERIA)},
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    load_dotenv(Path(__file__).resolve().parents[2] / ".env")
    provider = DSPyAssessmentProvider(compiled_dir=str(DEFAULT_COMPILED_DIR))
    result = run(provider)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Recorded {len(result['turns'])} synthetic turns.")


if __name__ == "__main__":
    main()
