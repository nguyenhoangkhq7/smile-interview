"""Tests for Plan B: Separation of Static Spec and Dynamic Session State."""
from datetime import datetime, timezone
from fastapi import FastAPI
from fastapi.testclient import TestClient

from adaptive_questioning.evidence.models import (
    CompactTransitionRequest, InterviewConfig, InterviewSkill, Snapshot,
    StartRequest, decompose_snapshot, recompose_snapshot
)
from adaptive_questioning.evidence.routes import router
from test_evidence_workflow import setup, start, answer, skill


def test_snapshot_decomposition_recomposition_is_lossless(setup):
    _, engine, _ = setup
    initial = start(engine, [skill("postgresql")]).snapshot
    static, dynamic = decompose_snapshot(initial)

    assert static.session_id == initial.session_id
    assert len(static.skills) == len(initial.skills)
    assert set(static.objectives_blueprint.keys()) == set(initial.objectives.keys())

    assert dynamic.session_id == initial.session_id
    assert dynamic.state_version == initial.state_version
    assert set(dynamic.objectives.keys()) == set(initial.objectives.keys())

    # Recompose must produce identical snapshot
    recomposed = recompose_snapshot(static, dynamic)
    assert recomposed == initial


def test_compact_respond_endpoint_processes_answer_correctly(setup):
    provider, engine, _ = setup
    app = FastAPI()
    app.include_router(router)
    app.state.evidence_workflow = engine

    with TestClient(app) as client:
        # Start via API
        start_payload = {
            "session_id": "test-split-session",
            "skills": [skill("postgresql").model_dump(mode="json")],
            "config": InterviewConfig().model_dump(mode="json"),
        }
        res_start = client.post("/api/v2/interview/start", json=start_payload)
        assert res_start.status_code == 200
        start_data = res_start.json()
        initial_snapshot = Snapshot.model_validate(start_data["snapshot"])

        # Decompose
        static, dynamic = decompose_snapshot(initial_snapshot)

        # Send compact respond
        compact_payload = {
            "session_id": "test-split-session",
            "turn_id": dynamic.pending_turn.turn_id,
            "expected_state_version": dynamic.state_version,
            "candidate_response": "I use EXPLAIN ANALYZE to inspect query execution plans.",
            "dynamic_state": dynamic.model_dump(mode="json"),
            "static_spec": static.model_dump(mode="json"),
        }
        res_compact = client.post("/api/v2/interview/respond-compact", json=compact_payload)
        assert res_compact.status_code == 200
        compact_result = res_compact.json()

        assert "dynamic_state" in compact_result
        assert "public" in compact_result
        assert compact_result["dynamic_state"]["state_version"] == dynamic.state_version + 1
        assert len(compact_result["dynamic_state"]["turns"]) == 1
        assert compact_result["public"]["turns"][0]["answer"] == "I use EXPLAIN ANALYZE to inspect query execution plans."
