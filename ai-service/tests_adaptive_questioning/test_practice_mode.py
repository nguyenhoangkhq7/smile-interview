"""Verify Practice vs Assessment mode, clarifying questions, behavioral STAR fallback, and coaching."""
from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from adaptive_questioning.evidence.models import (
    Assessment, BlueprintDraft, ConversationRequest, CriterionDraft, InterviewOpening, Mode, ObjectiveDraft,
    PriorAttemptContext, StartRequest, SuitableMode,
)
from adaptive_questioning.evidence.routes import router
from test_evidence_workflow import answer, setup, skill, start


def test_practice_mode_include_mastered_skills_rehearses_mastered_objectives(setup):
    provider, engine, _ = setup
    prior = PriorAttemptContext(mastered_skill_ids={"postgresql"})
    assessment_res = engine.start(StartRequest(
        session_id="assess-mastered",
        skills=[skill("postgresql")],
        prior_attempts=prior,
        config={"session_purpose": "ASSESSMENT"},
    ))
    assert assessment_res.public.is_finished
    assert assessment_res.public.report.termination_reason == "ALL_COMPATIBLE_SKILLS_MASTERED"

    practice_res = engine.start(StartRequest(
        session_id="practice-mastered",
        skills=[skill("postgresql")],
        prior_attempts=prior,
        config={"session_purpose": "PRACTICE", "include_mastered_skills": True},
    ))
    assert not practice_res.public.is_finished
    assert practice_res.public.pending_turn is not None


def test_focused_behavioral_on_technical_jd_synthesizes_star_objectives(setup):
    provider, engine, _ = setup
    res = engine.start(StartRequest(
        session_id="behavioral-fallback",
        skills=[skill("postgresql")],
        opening=InterviewOpening(role_title="Backend Java Intern"),
        config={"focused_question_mode": Mode.BEHAVIORAL, "max_questions": 3},
    ))
    assert not res.public.is_finished
    assert res.snapshot.queue
    first_obj = res.snapshot.objectives[res.snapshot.queue[0]].objective
    assert first_obj.skill_id == "behavioral_competency"
    assert any(m.mode == Mode.BEHAVIORAL for m in first_obj.suitable_modes)


def test_mixed_mode_switches_turn_mode_to_cover_essential_criteria(setup, monkeypatch):
    provider, engine, _ = setup

    def two_mode_blueprint(context):
        import json
        req_id, req = next(iter(json.loads(context)["requirements"].items()))
        return BlueprintDraft(objectives=[ObjectiveDraft(
            requirement_id=req_id,
            skill_id=req["skill_id"],
            target_depth=2,
            criteria=[
                CriterionDraft(
                    description="Viết hàm giải quyết bài toán",
                    expected_evidence="Mã nguồn xử lý đúng",
                    below_target="Sai logic",
                    at_target="Đúng logic",
                    above_target="Tối ưu O(n)",
                    essential=True,
                ),
                CriterionDraft(
                    description="Giải thích độ phức tạp thời gian",
                    expected_evidence="Nêu độ phức tạp Big-O",
                    below_target="Nêu sai độ phức tạp",
                    at_target="Nêu đúng O(n) và lý do",
                    above_target="Phân tích worst-case",
                    essential=True,
                ),
            ],
            suitable_modes=[
                SuitableMode(mode=Mode.CODING, criterion_indices=[0]),
                SuitableMode(mode=Mode.TECHNICAL_EXPLANATION, criterion_indices=[1]),
            ],
        )])

    monkeypatch.setattr(provider, "blueprint", two_mode_blueprint)
    first = start(engine)
    assert first.public.pending_turn.mode == Mode.CODING
    second = answer(engine, first.snapshot, "def f(x): return x")
    assert not second.public.is_finished
    assert second.public.pending_turn.mode == Mode.TECHNICAL_EXPLANATION
    final = answer(engine, second.snapshot, "Độ phức tạp thời gian là O(n) vì duyệt tuyến tính một lần.")
    assert final.public.is_finished
    assert final.public.report.objectives[0].assessment == Assessment.AT


def test_clarify_endpoint_supports_practice_hints_and_does_not_consume_question_budget(setup):
    provider, engine, _ = setup
    app = FastAPI()
    app.include_router(router)
    app.state.evidence_workflow = engine

    started = engine.start(StartRequest(
        session_id="practice-clarify",
        skills=[skill("postgresql")],
        config={"session_purpose": "PRACTICE", "max_questions": 2},
    ))
    with TestClient(app) as client:
        c1 = client.post("/api/v2/interview/clarify", json={
            "snapshot": started.snapshot.model_dump(mode="json"),
            "turn_id": started.snapshot.pending_turn.turn_id,
            "expected_state_version": started.snapshot.state_version,
            "kind": "CLARIFY_PROMPT",
            "candidate_question": "Bảng dữ liệu có khoảng bao nhiêu dòng?",
        })
        assert c1.status_code == 200
        body1 = c1.json()
        assert len(body1["public"]["turns"]) == 0  # does not consume question budget
        assert len(body1["public"]["pending_turn"]["clarifications"]) == 1
        assert body1["snapshot"]["state_version"] == started.snapshot.state_version + 1

        c2 = client.post("/api/v2/interview/clarify", json={
            "snapshot": body1["snapshot"],
            "turn_id": body1["public"]["pending_turn"]["turn_id"],
            "expected_state_version": body1["public"]["state_version"],
            "kind": "HINT",
            "candidate_question": "",
        })
        assert c2.status_code == 200
        body2 = c2.json()
        assert len(body2["public"]["pending_turn"]["clarifications"]) == 2

        # Third clarification on same turn must be rejected
        c3 = client.post("/api/v2/interview/clarify", json={
            "snapshot": body2["snapshot"],
            "turn_id": body2["public"]["pending_turn"]["turn_id"],
            "expected_state_version": body2["public"]["state_version"],
            "kind": "CLARIFY_PROMPT",
            "candidate_question": "Hỏi thêm nữa?",
        })
        assert c3.status_code == 422

    # Assessment mode must reject HINT requests
    assess_started = engine.start(StartRequest(
        session_id="assess-no-hint",
        skills=[skill("postgresql")],
        config={"session_purpose": "ASSESSMENT"},
    ))
    with TestClient(app) as client:
        denied = client.post("/api/v2/interview/clarify", json={
            "snapshot": assess_started.snapshot.model_dump(mode="json"),
            "turn_id": assess_started.snapshot.pending_turn.turn_id,
            "expected_state_version": assess_started.snapshot.state_version,
            "kind": "HINT",
            "candidate_question": "",
        })
        assert denied.status_code == 422


def test_post_interview_report_includes_reference_answer_star_delivery_and_intro_feedback(setup):
    provider, engine, _ = setup
    started = engine.start(StartRequest(
        session_id="behavioral-coaching",
        skills=[skill("postgresql")],
        opening=InterviewOpening(role_title="Backend Engineer"),
        config={"focused_question_mode": Mode.BEHAVIORAL, "max_questions": 1},
    ))
    intro_done = engine.converse(ConversationRequest(
        snapshot=started.snapshot,
        message_id=started.snapshot.conversation.message.message_id,
        expected_state_version=started.snapshot.state_version,
        action="SUBMIT_INTRODUCTION",
        introduction="Em là sinh viên năm 4 CNTT, từng làm dự án web với PostgreSQL và Spring Boot trong 1 năm.",
    ))
    provider.observation, provider.performance = "CONTRADICTS", "BELOW"
    finished = answer(engine, intro_done.snapshot, "Nhóm em có lần bị trễ tiến độ nên mọi người cố gắng làm thêm.")
    assert finished.public.is_finished
    report = finished.public.report
    assert report.coaching is not None
    assert report.coaching.introduction_feedback
    assert len(report.turn_reviews) == 1
    review = report.turn_reviews[0]
    assert review.reference_answer
    assert any("STAR" in note for note in review.delivery_notes)
