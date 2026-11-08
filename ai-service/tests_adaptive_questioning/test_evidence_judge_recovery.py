"""Provider contract failures are retried, never converted into candidate performance."""
import json

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from adaptive_questioning.evidence.errors import JudgmentUnavailableError
from adaptive_questioning.evidence.models import Judgment, Snapshot
from adaptive_questioning.evidence.routes import router
from test_evidence_workflow import setup, start, answer


@pytest.mark.parametrize("failure", ["missing", "extra", "duplicate", "renamed", "schema", "quote"])
def test_invalid_judgment_is_retried_with_exact_targets_without_double_counting(setup, monkeypatch, failure):
    provider, engine, _ = setup
    provider.limit_criteria = True
    initial = start(engine).snapshot
    original = initial.model_dump_json()
    original_judge = provider.judge
    calls = []

    def judge(context):
        values = json.loads(context)
        calls.append(values)
        valid = original_judge(context)
        if len(calls) > 1:
            return valid
        if failure == "schema":
            return Judgment.model_validate({"observations": "not a list"})
        broken = valid.model_copy(deep=True)
        if failure == "missing":
            broken.observations = []
        elif failure == "extra":
            state = initial.objectives[initial.pending_turn.objective_id]
            unused = next(c.criterion_id for c in state.objective.criteria if c.criterion_id not in initial.pending_turn.question.criterion_ids)
            broken.observations.append(broken.observations[0].model_copy(update={"criterion_id": unused}))
        elif failure == "duplicate":
            broken.observations.append(broken.observations[0].model_copy())
        elif failure == "renamed":
            broken.observations[0].criterion_id = "invented-criterion"
        elif failure == "quote":
            broken.observations[0].response_excerpt = "invented excerpt"
        return broken

    monkeypatch.setattr(provider, "judge", judge)
    result = answer(engine, initial)
    assert len(calls) == 2
    expected = initial.pending_turn.question.criterion_ids
    for context in calls:
        assert context["required_criterion_ids"] == expected
        assert [c["criterion_id"] for c in context["target_criteria"]] == expected
        assert [c["criterion_id"] for c in context["objective"]["criteria"]] == expected
        assert context["turn"]["answer"] == "EXPLAIN ANALYZE"
    assert "validation_error" in calls[1]
    assert result.snapshot.state_version == initial.state_version + 1
    assert len(result.snapshot.turns) == 1
    assert result.snapshot.objectives[initial.pending_turn.objective_id].turns_spent == 1
    assert initial.model_dump_json() == original


def test_exhausted_judge_returns_503_and_same_answer_can_be_retried(setup, monkeypatch):
    provider, engine, _ = setup
    initial = start(engine).snapshot
    saved = initial.model_dump_json()
    original_judge = provider.judge
    calls = []

    def invalid(context):
        calls.append(json.loads(context))
        result = original_judge(context)
        result.observations = []
        return result

    monkeypatch.setattr(provider, "judge", invalid)
    app = FastAPI()
    app.include_router(router)
    app.state.evidence_workflow = engine
    payload = {"snapshot": initial.model_dump(mode="json"), "turn_id": initial.pending_turn.turn_id,
               "expected_state_version": initial.state_version, "candidate_response": "EXPLAIN ANALYZE"}
    with TestClient(app) as client:
        response = client.post('/api/v2/interview/respond', json=payload)
        assert response.status_code == 503
        assert "chưa bị chấm điểm" in response.json()["detail"]
        assert "targeted criteria" not in response.json()["detail"]
        assert len(calls) == initial.policy.judgment_attempts
        assert initial.model_dump_json() == saved
        monkeypatch.setattr(provider, "judge", original_judge)
        retried = client.post('/api/v2/interview/respond', json=payload)
        assert retried.status_code == 200
        assert retried.json()["snapshot"]["state_version"] == initial.state_version + 1
        assert len(retried.json()["snapshot"]["turns"]) == 1


def test_judgment_retry_stops_at_deadline_without_mutating_input(setup, monkeypatch):
    provider, engine, now = setup
    initial = start(engine).snapshot
    saved = initial.model_dump_json()
    original_judge = provider.judge
    calls = []

    def invalid(context):
        calls.append(context)
        now[0] = initial.deadline_at
        result = original_judge(context)
        result.observations = []
        return result

    monkeypatch.setattr(provider, "judge", invalid)
    with pytest.raises(JudgmentUnavailableError):
        answer(engine, initial)
    assert len(calls) == 1
    assert initial.model_dump_json() == saved


def test_old_snapshots_default_to_bounded_judgment_retries(setup):
    _, engine, _ = setup
    value = start(engine).snapshot.model_dump(mode="json")
    del value["policy"]["judgment_attempts"]
    assert Snapshot.model_validate(value).policy.judgment_attempts == 2
