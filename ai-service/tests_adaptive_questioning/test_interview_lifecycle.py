"""The introduction never becomes technical evidence or consumes its budget."""
from datetime import datetime, timedelta, timezone
import json

import pytest

from adaptive_questioning.evidence.errors import ProviderUnavailableError
from adaptive_questioning.evidence.models import (
    ConversationRequest, DialogueMessage, InterviewConfig, InterviewOpening, Snapshot, StartRequest, TransitionRequest,
)
from adaptive_questioning.evidence.provider import DSPyAssessmentProvider
from adaptive_questioning.evidence.workflow import EvidenceWorkflow
from adaptive_questioning.evidence.routes import router
from fastapi import FastAPI
from fastapi.testclient import TestClient
from test_evidence_workflow import ScriptedProvider, skill


def setup(mode="TEXT"):
    provider = ScriptedProvider()
    now = [datetime(2026, 11, 12, tzinfo=timezone.utc)]
    engine = EvidenceWorkflow(provider, clock=lambda: now[0])
    result = engine.start(StartRequest(session_id="lifecycle", skills=[skill()],
        config=InterviewConfig(interaction_mode=mode, max_questions=1),
        opening=InterviewOpening(company="Smile", role_title="Backend Developer")))
    return provider, now, engine, result.snapshot


def command(engine, snapshot, action, introduction=""):
    return engine.converse(ConversationRequest(snapshot=snapshot,
        message_id=snapshot.conversation.message.message_id, expected_state_version=snapshot.state_version,
        action=action, introduction=introduction))


@pytest.mark.parametrize("mode", ["TEXT", "VOICE"])
def test_opening_introduction_and_farewell_are_separate_from_assessment(mode):
    provider, now, engine, snapshot = setup(mode)
    expected_start_phase = "SELF_INTRODUCTION" if mode == "TEXT" else "OPENING"
    assert snapshot.conversation.phase == expected_start_phase
    assert snapshot.pending_turn is None and not snapshot.turns
    assert provider.question_number == 0
    assert "Smile" in snapshot.conversation.message.text
    assert "Backend Developer" in snapshot.conversation.message.text
    assert "role_title" not in snapshot.conversation.opening.model_dump()
    if mode == "VOICE":
        snapshot = command(engine, snapshot, "NEXT").snapshot
        assert snapshot.conversation.phase == "SELF_INTRODUCTION"
    now[0] += timedelta(seconds=100)
    result = command(engine, snapshot, "SUBMIT_INTRODUCTION", "Em tên Nam, em dùng Spring Boot.")
    snapshot = result.snapshot
    assert snapshot.conversation.phase == "INTERVIEW"
    assert snapshot.conversation.introduction == "Em tên Nam, em dùng Spring Boot."
    assert snapshot.deadline_at == now[0] + timedelta(seconds=900)
    assert not snapshot.turns and provider.question_number == 1
    assert "Cảm ơn" in snapshot.pending_turn.introduction
    assert all(not objective.evidence for objective in result.public.report.objectives)
    result = engine.respond(TransitionRequest(snapshot=snapshot, turn_id=snapshot.pending_turn.turn_id,
        expected_state_version=snapshot.state_version, candidate_response="EXPLAIN ANALYZE"))
    snapshot = result.snapshot
    assert snapshot.is_finished and snapshot.conversation.phase == "CLOSING"
    assert len(snapshot.turns) == 1
    assert "chào bạn" in snapshot.conversation.message.text
    assert command(engine, snapshot, "NEXT").snapshot.conversation.phase == "FINISHED"


def test_introduction_personalizes_first_question_without_entering_judge():
    provider, _, engine, snapshot = setup()
    question_contexts = []
    judge_contexts = []
    original_q = provider.question
    original_j = provider.judge
    provider.question = lambda context: (question_contexts.append(json.loads(context)), original_q(context))[1]
    provider.judge = lambda context: (judge_contexts.append(json.loads(context)), original_j(context))[1]
    after_intro = command(engine, snapshot, "SUBMIT_INTRODUCTION", "SECRET_UNSCORED_INTRO")
    assert question_contexts[0]["candidate_introduction"] == "SECRET_UNSCORED_INTRO"
    engine.respond(TransitionRequest(
        snapshot=after_intro.snapshot,
        turn_id=after_intro.snapshot.pending_turn.turn_id,
        expected_state_version=after_intro.snapshot.state_version,
        candidate_response="EXPLAIN ANALYZE",
    ))
    assert "SECRET_UNSCORED_INTRO" not in json.dumps(judge_contexts)


def test_skip_reload_and_early_stop():
    from pydantic import ValidationError
    _, _, engine, snapshot = setup()
    assert snapshot.conversation.phase == "SELF_INTRODUCTION"
    bad_payload = snapshot.model_dump(mode="json")
    bad_payload["conversation"]["introduction_skipped"] = False
    with pytest.raises(ValidationError):
        Snapshot.model_validate(bad_payload)
    bad_opening = snapshot.model_dump(mode="json")
    bad_opening["conversation"]["opening"]["role_title"] = "Backend Developer"
    with pytest.raises(ValidationError):
        Snapshot.model_validate(bad_opening)
    restored = Snapshot.model_validate_json(snapshot.model_dump_json())
    snapshot = command(engine, restored, "SKIP_INTRODUCTION").snapshot
    assert snapshot.conversation.phase == "INTERVIEW" and not snapshot.conversation.introduction and not snapshot.turns
    assert "bắt đầu phần trao đổi chuyên môn" in snapshot.pending_turn.introduction
    dumped_conversation = snapshot.conversation.model_dump(mode="json")
    assert "introduction_skipped" not in dumped_conversation
    assert "role_title" not in dumped_conversation["opening"]
    closed = engine.stop(snapshot).snapshot
    assert closed.conversation.phase == "CLOSING"
    assert closed.termination_reason == "USER_STOP"
    assert engine.stop(closed).snapshot.conversation.message == closed.conversation.message


def test_invalid_and_duplicate_phase_commands_do_not_change_original():
    _, _, engine, snapshot = setup("VOICE")
    original = snapshot.model_dump_json()
    with pytest.raises(ValueError):
        command(engine, snapshot, "SUBMIT_INTRODUCTION", "Too soon")
    assert snapshot.model_dump_json() == original
    active = command(engine, snapshot, "NEXT").snapshot
    with pytest.raises(ValueError):
        command(engine, active, "NEXT")
    with pytest.raises(ValueError):
        command(engine, active, "SUBMIT_INTRODUCTION", " ")


def test_timeout_farewell_can_be_finished_after_technical_deadline():
    _, now, engine, snapshot = setup()
    snapshot = command(engine, snapshot, "SKIP_INTRODUCTION").snapshot
    now[0] = snapshot.deadline_at + timedelta(seconds=1)
    closed = engine.stop(snapshot).snapshot
    assert closed.termination_reason == "TIME_BUDGET"
    assert closed.conversation.expires_at > now[0]
    assert command(engine, closed, "NEXT").snapshot.is_finished


def test_http_lifecycle_returns_snapshot_and_public_only(monkeypatch):
    provider, _, engine, _ = setup()
    app = FastAPI()
    app.include_router(router)
    app.state.evidence_workflow = engine
    with TestClient(app) as client:
        started = client.post("/api/v2/interview/start", json=StartRequest(
            session_id="http-lifecycle", skills=[skill()], opening=InterviewOpening()).model_dump(mode="json"))
        assert started.status_code == 200
        data = started.json()
        assert set(data) == {"snapshot", "public"}
        assert data["public"]["pending_turn"] is None
        assert data["public"]["conversation"]["phase"] == "SELF_INTRODUCTION"
        introduction = "Em tên Nam, em dùng Spring Boot."
        result = client.post("/api/v2/interview/conversation", json={
            "snapshot": data["snapshot"],
            "expected_state_version": data["snapshot"]["state_version"],
            "message_id": data["public"]["conversation"]["message"]["message_id"],
            "action": "SUBMIT_INTRODUCTION", "introduction": introduction, "defer_question": True,
        })
        assert result.status_code == 200
        updated = result.json()
        assert set(updated) == {"snapshot", "public"}
        assert updated["snapshot"]["conversation"]["phase"] == "INTERVIEW"
        assert updated["public"]["conversation"]["introduction"] == introduction
        assert updated["public"]["awaiting_question"] and updated["public"]["pending_turn"] is None
        assert provider.question_number == 0
        monkeypatch.setattr(provider, "review_question", lambda _: "GIVES_SOLUTION")
        generation = {"snapshot": updated["snapshot"], "expected_state_version": updated["snapshot"]["state_version"]}
        failed = client.post("/api/v2/interview/next-question", json=generation)
        assert failed.status_code == 503
        monkeypatch.setattr(provider, "review_question", lambda _: "ALIGNED")
        ready = client.post("/api/v2/interview/next-question", json=generation)
        assert ready.status_code == 200
        updated = ready.json()
        assert not updated["public"]["awaiting_question"]
        assert updated["public"]["conversation"]["introduction"] == introduction
        assert "Cảm ơn" in updated["public"]["pending_turn"]["introduction"]
        snapshot = Snapshot.model_validate(updated["snapshot"])
        answered = client.post("/api/v2/interview/respond", json={
            "snapshot": updated["snapshot"], "expected_state_version": snapshot.state_version,
            "turn_id": snapshot.pending_turn.turn_id, "candidate_response": "EXPLAIN ANALYZE",
        })
        assert answered.status_code == 200
        assert set(answered.json()) == {"snapshot", "public"}
        stopped = client.post("/api/v2/interview/stop", json=updated["snapshot"])
        assert stopped.status_code == 200
        assert set(stopped.json()) == {"snapshot", "public"}
        assert stopped.json()["public"]["report"]["termination_reason"] == "USER_STOP"


def test_dynamic_opening_and_closing_use_user_and_jd_context_without_leaking_to_assessment():
    class DialogueProvider(ScriptedProvider):
        def __init__(self):
            super().__init__()
            self.opening_contexts = []
            self.closing_contexts = []
            self.question_contexts = []
            self.judge_contexts = []

        def opening_greeting(self, context):
            self.opening_contexts.append(json.loads(context))
            return DialogueMessage(
                text="**Chào Tuấn**, mình là Minh — người phỏng vấn AI cho vị trí Backend tại Smile Fintech. "
                     "Bạn giới thiệu ngắn về bản thân nhé?"
            )

        def closing_farewell(self, context):
            self.closing_contexts.append(json.loads(context))
            return DialogueMessage(
                text="Cảm ơn Tuấn đã chia sẻ về PostgreSQL hôm nay. Chúc bạn một ngày tốt lành, chào bạn!"
            )

        def question(self, context):
            self.question_contexts.append(json.loads(context))
            return super().question(context)

        def judge(self, context):
            self.judge_contexts.append(json.loads(context))
            return super().judge(context)

    provider = DialogueProvider()
    now = [datetime(2026, 11, 18, tzinfo=timezone.utc)]
    engine = EvidenceWorkflow(provider, clock=lambda: now[0])
    start_res = engine.start(StartRequest(
        session_id="dynamic-ctx",
        skills=[skill("postgresql", cv_evidence_spans=["Tối ưu index PostgreSQL"], job_tasks=[{
            "task_id": "sql-1", "description": "Tối ưu truy vấn chậm", "required_level": 3,
            "evidence_spans": ["Tối ưu truy vấn chậm"],
        }])],
        config=InterviewConfig(interaction_mode="VOICE", max_questions=1),
        opening=InterviewOpening(
            company="Smile Fintech",
            role_title="Senior Backend Engineer",
            candidate_name="Nguyễn Minh Tuấn",
            jd_summary="Xây dựng hệ thống thanh toán chịu tải cao",
            cv_summary="SECRET_CV_SUMMARY_5_NAM_JAVA",
            attempt_number=2,
        ),
    ))
    assert "**" not in start_res.public.conversation.message.text
    assert "Chào Tuấn" in start_res.public.conversation.message.text
    assert "jd_summary" not in start_res.public.model_dump_json()
    assert "candidate_name" not in start_res.public.model_dump_json()
    assert len(provider.opening_contexts) == 1
    opening_ctx = provider.opening_contexts[0]
    assert opening_ctx["candidate_name"] == "Nguyễn Minh Tuấn"
    assert opening_ctx["company"] == "Smile Fintech"
    assert opening_ctx["role_title"] == "Senior Backend Engineer"
    assert opening_ctx["attempt_number"] == 2
    assert opening_ctx["interaction_mode"] == "VOICE"
    assert "thanh toán" in opening_ctx["jd_summary"]
    assert "SECRET_CV_SUMMARY_5_NAM_JAVA" in opening_ctx["cv_summary"]
    assert opening_ctx["jd_skills"][0]["skill"] == "PostgreSQL"
    assert opening_ctx["cv_evidence"] == ["Tối ưu index PostgreSQL"]

    snap = command(engine, start_res.snapshot, "NEXT").snapshot
    snap = command(engine, snap, "SUBMIT_INTRODUCTION", "SECRET_INTRO_TAILORED").snapshot
    assert provider.question_contexts[0]["candidate_introduction"] == "SECRET_INTRO_TAILORED"
    assert "SECRET_CV_SUMMARY_5_NAM_JAVA" not in json.dumps(provider.question_contexts)

    finished = engine.respond(TransitionRequest(
        snapshot=snap, turn_id=snap.pending_turn.turn_id,
        expected_state_version=snap.state_version, candidate_response="EXPLAIN ANALYZE",
    ))
    assert "SECRET_INTRO_TAILORED" not in json.dumps(provider.judge_contexts)
    assert "SECRET_CV_SUMMARY_5_NAM_JAVA" not in json.dumps(provider.judge_contexts)
    assert finished.public.conversation.phase == "CLOSING"
    assert "Cảm ơn Tuấn" in finished.public.conversation.message.text
    assert len(provider.closing_contexts) == 1
    closing_ctx = provider.closing_contexts[0]
    assert closing_ctx["candidate_name"] == "Nguyễn Minh Tuấn"
    assert closing_ctx["company"] == "Smile Fintech"
    assert closing_ctx["role_title"] == "Senior Backend Engineer"
    assert closing_ctx["candidate_introduction"] == "SECRET_INTRO_TAILORED"
    assert closing_ctx["topics_discussed"] == ["PostgreSQL"]
    assert closing_ctx["turns_answered"] == 1
    assert closing_ctx["termination_reason"] in {"PLAN_COMPLETE", "QUESTION_BUDGET"}
    assert "judgment" not in json.dumps(closing_ctx)
    assert "observations" not in json.dumps(closing_ctx)


def test_dialogue_falls_back_safely_on_provider_failure_or_invalid_output(caplog):
    class FlakyDialogueProvider(ScriptedProvider):
        def opening_greeting(self, context):
            raise ProviderUnavailableError("rate limited", status=429)

        def closing_farewell(self, context):
            return DialogueMessage.model_construct(text="ok")

    now = [datetime(2026, 11, 18, tzinfo=timezone.utc)]
    engine = EvidenceWorkflow(FlakyDialogueProvider(), clock=lambda: now[0])
    with caplog.at_level("WARNING"):
        started = engine.start(StartRequest(
            session_id="fallback-test", skills=[skill()],
            opening=InterviewOpening(company="Smile", role_title="QA Engineer", candidate_name="Lan"),
        ))
    assert "Chào Lan" in started.public.conversation.message.text
    assert "Smile" in started.public.conversation.message.text
    assert "QA Engineer" in started.public.conversation.message.text
    stopped = engine.stop(started.snapshot)
    assert "dừng buổi phỏng vấn sớm" in stopped.public.conversation.message.text
    assert "chào bạn" in stopped.public.conversation.message.text
    assert "Falling back to template for opening" in caplog.text
    assert "Falling back to template for closing" in caplog.text


def test_dspy_provider_generates_opening_and_closing_without_slow_retries():
    import dspy

    lm = dspy.utils.DummyLM([
        {"greeting": {"text": "Chào Lan, mình là Minh từ phòng phỏng vấn AI cho vị trí QA tại Smile. Bạn giới thiệu ngắn về mình nhé?"}},
        {"farewell": {"text": "Cảm ơn Lan đã tham gia buổi trao đổi vị trí QA tại Smile hôm nay. Bạn có thể xem kết quả ngay nhé, chào bạn!"}},
    ])
    lm.adapter = dspy.JSONAdapter()
    provider = DSPyAssessmentProvider(lm=lm)
    greeting = provider.opening_greeting(json.dumps({"candidate_name": "Lan", "role_title": "QA", "company": "Smile"}))
    farewell = provider.closing_farewell(json.dumps({"candidate_name": "Lan", "termination_reason": "PLAN_COMPLETE"}))
    assert "Chào Lan" in greeting.text
    assert "Cảm ơn Lan" in farewell.text

    class RateLimitedModule:
        def __init__(self):
            self.calls = 0

        def __call__(self, context):
            self.calls += 1
            error = RuntimeError("429")
            error.status_code = 429
            raise error

    failing = RateLimitedModule()
    provider.opening_module = failing
    with pytest.raises(ProviderUnavailableError):
        provider.opening_greeting("{}")
    assert failing.calls == 1
