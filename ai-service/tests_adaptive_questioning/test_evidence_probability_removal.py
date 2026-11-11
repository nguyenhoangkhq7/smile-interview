"""Evidence-only contracts, including resuming pre-removal snapshots."""
import json

import pytest

from adaptive_questioning.evidence.models import Judgment, ObjectiveState, Snapshot
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


def test_old_snapshot_probability_fields_are_discarded_before_judging(setup, monkeypatch):
    provider, engine, _ = setup
    provider.criterion_count = 2
    first = answer(engine, start(engine).snapshot)
    old = first.snapshot.model_dump(mode="json")
    for state in old["objectives"].values():
        state["belief"] = [0.1, 0.2, 0.7]
    old["turns"][0]["judgment"].update(raw_belief=[0.1, 0.2, 0.7], tag="DECISIVE_SHIFT")
    restored = Snapshot.model_validate(old)
    original_judge = provider.judge
    contexts = []

    def judge(context):
        contexts.append(json.loads(context))
        # Even a stale provider response must not persist retired fields.
        value = original_judge(context).model_dump()
        return Judgment.model_validate(value | {"raw_belief": [float("nan")], "tag": "obsolete"})

    monkeypatch.setattr(provider, "judge", judge)
    result = answer(engine, restored)
    assert result.public.is_finished
    assert result.public.report.target_attainment == 1
    assert_no_probability_fields(restored.model_dump())
    assert_no_probability_fields(contexts)
    assert_no_probability_fields(result.model_dump())

