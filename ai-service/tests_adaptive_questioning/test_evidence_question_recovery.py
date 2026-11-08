"""Recoverable generation failures and precise repair feedback, without weakened contracts."""
import json

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from adaptive_questioning.evidence.question_validation import single_question
from adaptive_questioning.evidence.routes import router
from test_evidence_workflow import setup, start, answer


@pytest.mark.parametrize("text", [
    "Đầu vào:\n1. Nếu chuỗi rỗng, trả về False.\n2. Nếu hợp lệ, trả về True.\nBạn sẽ viết prompt ra sao?",
    'Với URL https://a.example/?x=1 và https://b.example/?x=2, bạn sẽ kiểm thử ra sao?',
    '''Với chuỗi "a?b@example.com" và 'c?d@example.com', bạn kiểm thử hàm ra sao?''',
])
def test_data_question_marks_and_conditional_constraints_are_not_extra_tasks(text):
    assert single_question(text)


@pytest.mark.parametrize("text", [
    "Bạn viết prompt gì? Bạn sẽ review mã ra sao?",
    "1. Hãy viết prompt.\n2. Sau khi AI trả lời, hãy review mã.",
    "1. Viết prompt.\n2. Nếu mã sai, hãy mô tả cách sửa lỗi.",
])
def test_independent_response_tasks_are_still_rejected(text):
    assert not single_question(text)


def test_retry_identifies_the_exact_invalid_field_and_keeps_the_contract(setup, monkeypatch, caplog):
    provider, engine, _ = setup
    original = provider.question
    calls = []

    def question(context):
        calls.append(json.loads(context))
        result = original(context)
        if len(calls) == 1:
            result.depth = 4
        return result

    monkeypatch.setattr(provider, "question", question)
    result = start(engine)
    assert result.public.pending_turn
    assert len(calls) == 2
    assert "depth must equal" in calls[1]["validation_error"]
    assert "criterion_ids" not in calls[1]["validation_error"]
    assert calls[1]["required_question_contract"] == calls[0]["required_question_contract"]
    assert "depth must equal" in caplog.text
    assert result.public.pending_turn.question not in caplog.text


def test_failed_next_question_returns_503_and_retry_preserves_answer_and_snapshot(setup, monkeypatch):
    provider, engine, _ = setup
    provider.criterion_count = 2
    initial = start(engine).snapshot
    saved = initial.model_dump_json()
    original = provider.question

    def invalid(context):
        question = original(context)
        question.evidence_scope = ""
        return question

    monkeypatch.setattr(provider, "question", invalid)
    app = FastAPI()
    app.include_router(router)
    app.state.evidence_workflow = engine
    payload = {"snapshot": initial.model_dump(mode="json"), "turn_id": initial.pending_turn.turn_id,
               "expected_state_version": initial.state_version, "candidate_response": "EXPLAIN ANALYZE"}
    with TestClient(app) as client:
        failed = client.post('/api/v2/interview/respond', json=payload)
        assert failed.status_code == 503
        assert "giữ nguyên" in failed.json()["detail"]
        assert "bounded retry" not in failed.json()["detail"]
        assert initial.model_dump_json() == saved
        monkeypatch.setattr(provider, "question", original)
        retried = client.post('/api/v2/interview/respond', json=payload)
        assert retried.status_code == 200
        result = retried.json()
        assert len(result["snapshot"]["turns"]) == 1
        assert result["snapshot"]["turns"][0]["answer"] == payload["candidate_response"]
        assert result["snapshot"]["state_version"] == initial.state_version + 1


def test_clarification_retry_receives_the_exact_persisted_scope(setup, monkeypatch):
    provider, engine, _ = setup
    provider.observation, provider.performance = "UNCLEAR", "UNDETERMINED"
    initial = start(engine).snapshot
    original = provider.question
    calls = []

    def question(context):
        calls.append(json.loads(context))
        result = original(context)
        if len(calls) == 1:
            result.evidence_scope = "a-different-case"
        return result

    monkeypatch.setattr(provider, "question", question)
    result = answer(engine, initial)
    expected = initial.pending_turn.question.evidence_scope
    assert calls[1]["required_question_contract"]["evidence_scope"] == expected
    assert "CLARIFY must preserve" in calls[1]["validation_error"]
    assert result.snapshot.pending_turn.question.evidence_scope == expected
