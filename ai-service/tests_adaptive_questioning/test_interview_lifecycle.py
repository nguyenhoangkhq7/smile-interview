"""The introduction never becomes technical evidence or consumes its budget."""
from datetime import datetime, timedelta, timezone
import json

import pytest

from adaptive_questioning.evidence.models import (
    ConversationRequest, InterviewConfig, InterviewOpening, Snapshot, StartRequest,
    TransitionRequest, decompose_snapshot, recompose_snapshot,
)
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
    assert snapshot.conversation.phase == "OPENING"
    assert snapshot.pending_turn is None and not snapshot.turns
    assert provider.question_number == 0
    assert "Smile" in snapshot.conversation.message.text
    assert "Backend Developer" in snapshot.conversation.message.text
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
    assert result.public.report.evidence_coverage == 0
    result = engine.respond(TransitionRequest(snapshot=snapshot, turn_id=snapshot.pending_turn.turn_id,
        expected_state_version=snapshot.state_version, candidate_response="EXPLAIN ANALYZE"))
    snapshot = result.snapshot
    assert snapshot.is_finished and snapshot.conversation.phase == "CLOSING"
    assert len(snapshot.turns) == 1
    assert "chào bạn" in snapshot.conversation.message.text
    assert command(engine, snapshot, "NEXT").snapshot.conversation.phase == "FINISHED"


def test_introduction_is_not_given_to_question_generator_or_judge():
    provider, _, engine, snapshot = setup()
    contexts = []
    original = provider.question
    provider.question = lambda context: (contexts.append(json.loads(context)), original(context))[1]
    snapshot = command(engine, snapshot, "NEXT").snapshot
    command(engine, snapshot, "SUBMIT_INTRODUCTION", "SECRET_UNSCORED_INTRO")
    assert "SECRET_UNSCORED_INTRO" not in json.dumps(contexts)


def test_skip_reload_compact_and_early_stop():
    _, _, engine, snapshot = setup()
    snapshot = command(engine, snapshot, "NEXT").snapshot
    restored = Snapshot.model_validate_json(snapshot.model_dump_json())
    static, dynamic = decompose_snapshot(restored)
    assert recompose_snapshot(static, dynamic) == restored
    snapshot = command(engine, restored, "SKIP_INTRODUCTION").snapshot
    assert snapshot.conversation.introduction_skipped and not snapshot.turns
    closed = engine.stop(snapshot).snapshot
    assert closed.conversation.phase == "CLOSING"
    assert closed.termination_reason == "USER_STOP"
    assert engine.stop(closed).snapshot.conversation.message == closed.conversation.message


def test_invalid_and_duplicate_phase_commands_do_not_change_original():
    _, _, engine, snapshot = setup()
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


def test_http_conversation_keeps_compact_state_and_public_contract():
    _, _, engine, _ = setup()
    app = FastAPI()
    app.include_router(router)
    app.state.evidence_workflow = engine
    with TestClient(app) as client:
        started = client.post("/api/v2/interview/start", json=StartRequest(
            session_id="http-lifecycle", skills=[skill()], opening=InterviewOpening()).model_dump(mode="json"))
        assert started.status_code == 200
        data = started.json()
        assert data["public"]["pending_turn"] is None
        assert data["public"]["conversation"]["phase"] == "OPENING"
        result = client.post("/api/v2/interview/conversation", json={
            "snapshot": data["snapshot"], "expected_state_version": data["snapshot"]["state_version"],
            "message_id": data["public"]["conversation"]["message"]["message_id"],
            "action": "SKIP_INTRODUCTION",
        })
        assert result.status_code == 200
        updated = result.json()
        assert updated["dynamic_state"]["conversation"]["phase"] == "INTERVIEW"
        assert updated["public"]["pending_turn"]["question"]
        snapshot = Snapshot.model_validate(updated["snapshot"])
        static, dynamic = decompose_snapshot(snapshot)
        assert recompose_snapshot(static, dynamic) == snapshot
