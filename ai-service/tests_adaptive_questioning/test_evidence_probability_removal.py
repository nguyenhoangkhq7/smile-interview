"""Evidence-only contracts, including resuming pre-removal snapshots."""
import json

import pytest

from adaptive_questioning.evidence.models import Assessment, Judgment, ObjectiveState, Snapshot
from adaptive_questioning.evidence.provider import JudgeSignature
from test_evidence_workflow import setup, start, answer


def assert_no_probability_fields(value):
    removed = {"belief", "raw_belief", "tag", "prior_belief", "current_belief", "updated_belief"}
    if isinstance(value, dict):
        assert not removed.intersection(value)
        for child in value.values():
            assert_no_probability_fields(child)
    elif isinstance(value, list):
        for child in value:
            assert_no_probability_fields(child)


def test_judge_contract_requires_only_evidence_fields(setup):
    provider, engine, _ = setup
    initial = start(engine).snapshot
    context = json.dumps({"turn": {"question": initial.pending_turn.question.model_dump(), "answer": "EXPLAIN ANALYZE"}})
    judged = provider.judge(context)
    assert Judgment.model_validate(judged.model_dump()) == judged
    assert "raw_belief" not in Judgment.model_fields
    assert "tag" not in Judgment.model_fields
    assert "belief" not in ObjectiveState.model_fields
    assert "belief" not in JudgeSignature.instructions.lower()
    assert_no_probability_fields(Judgment.model_json_schema())
    assert_no_probability_fields(Snapshot.model_json_schema())


def test_probability_fields_are_rejected_by_strict_models(setup):
    from pydantic import ValidationError
    _, engine, _ = setup
    payload = start(engine).snapshot.model_dump(mode="json")
    for state in payload["objectives"].values():
        state["belief"] = [0.1, 0.2, 0.7]
    with pytest.raises(ValidationError):
        Snapshot.model_validate(payload)

