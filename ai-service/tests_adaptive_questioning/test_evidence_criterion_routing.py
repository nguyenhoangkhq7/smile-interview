"""Adaptive criterion coverage and bounded probes through the real workflow."""
import json

import pytest

from adaptive_questioning.evidence.models import Action, Assessment, Snapshot
from adaptive_questioning.evidence.policy_config import InterviewPolicy
from adaptive_questioning.evidence.reporting import report
from test_evidence_workflow import setup, start, answer, skill


def state_of(result):
    return next(iter(result.snapshot.objectives.values()))


def partial(provider, monkeypatch):
    provider.observation, provider.performance = "UNCLEAR", "UNDETERMINED"
    original = provider.judge
    gaps = ["initial ambiguity"]

    def judge(context):
        judgment = original(context)
        for observation in judgment.observations:
            observation.unresolved_aspects = gaps.copy() if provider.performance == "UNDETERMINED" else []
        return judgment

    monkeypatch.setattr(provider, "judge", judge)
    return gaps


def test_one_criterion_per_turn_until_all_three_are_verified(setup, monkeypatch):
    provider, engine, _ = setup
    provider.criterion_count = 3
    contexts = []
    original = provider.question

    def question(context):
        contexts.append(json.loads(context))
        return original(context)

    monkeypatch.setattr(provider, "question", question)
    result = start(engine)
    asked = []
    while not result.public.is_finished:
        asked.extend(result.snapshot.pending_turn.question.criterion_ids)
        result = answer(engine, result.snapshot)
    assert len(asked) == len(set(asked)) == 3
    assert result.public.report.objectives[0].assessment == Assessment.AT
    assert all(len(c["target_criteria"]) == len(c["objective"]["criteria"]) == 1 for c in contexts)
    assert all(c["probe_reason"] for c in contexts)


def test_a_single_criterion_can_take_four_turns_with_narrowing_gaps(setup, monkeypatch):
    provider, engine, _ = setup
    gaps = partial(provider, monkeypatch)
    result = start(engine)
    criterion = result.snapshot.pending_turn.question.criterion_ids
    for gap in ["validation scope is unspecified", "input constraints are unspecified", "remaining boundary is unspecified"]:
        gaps[:] = [gap]
        result = answer(engine, result.snapshot)
        assert not result.public.is_finished
        assert result.snapshot.pending_turn.question.criterion_ids == criterion
        assert result.snapshot.pending_turn.question_depth == 2
    assert state_of(result).criterion_progress[criterion[0]].turns_spent == 3
    provider.observation, provider.performance = "SUPPORTS", "AT_TARGET"
    result = answer(engine, result.snapshot)
    assert result.public.is_finished
    assert result.public.report.objectives[0].assessment == Assessment.AT
    assert result.public.report.objectives[0].criteria[0].turns_spent == 4


def test_clarifications_and_diagnostics_are_available_for_each_criterion(setup):
    provider, engine, _ = setup
    provider.criterion_count = 2
    result = start(engine)
    for index in range(2):
        provider.observation, provider.performance = "UNCLEAR", "UNDETERMINED"
        result = answer(engine, result.snapshot)
        assert result.snapshot.pending_turn.action == Action.CLARIFY
        provider.observation, provider.performance = "CONTRADICTS", "BELOW"
        result = answer(engine, result.snapshot)
        assert result.snapshot.pending_turn.action == Action.EASIER
        provider.observation, provider.performance = "SUPPORTS", "AT_TARGET"
        result = answer(engine, result.snapshot)
        assert result.snapshot.pending_turn.action == Action.FOLLOW_UP
        result = answer(engine, result.snapshot)
        assert result.public.is_finished == (index == 1)
    progress = list(state_of(result).criterion_progress.values())
    assert all(p.clarification_spent and p.easier_spent and p.turns_spent == 4 for p in progress)
    assert state_of(result).assessment == Assessment.AT


def test_stagnation_switches_criteria_and_does_not_fail_candidate(setup):
    provider, engine, _ = setup
    provider.criterion_count = 2
    provider.observation, provider.performance = "NO_EVIDENCE", "UNDETERMINED"
    result = start(engine)
    first = result.snapshot.pending_turn.question.criterion_ids
    for _ in range(3):
        result = answer(engine, result.snapshot, "irrelevant")
    assert result.snapshot.pending_turn.question.criterion_ids != first
    assert state_of(result).criterion_progress[first[0]].stop_reason == "NO_PROGRESS"
    provider.observation, provider.performance = "SUPPORTS", "AT_TARGET"
    result = answer(engine, result.snapshot)
    objective = result.public.report.objectives[0]
    assert result.public.is_finished
    assert objective.assessment == Assessment.INSUFFICIENT
    assert objective.stop_reason == "NO_PROGRESS"
    assert objective.criteria[0].assessment == Assessment.INSUFFICIENT
    assert objective.criteria[1].assessment == Assessment.AT
    assert objective.weaknesses == []
    assert objective.study_recommendations == []


def test_criterion_hard_limit_applies_even_when_gaps_keep_changing(setup, monkeypatch):
    provider, engine, _ = setup
    gaps = partial(provider, monkeypatch)
    result = start(engine)
    for index in range(6):
        gaps[:] = [f"Unverified aspect {index}"]
        result = answer(engine, result.snapshot)
    assert result.public.is_finished
    assert len(result.snapshot.turns) == 6
    assert state_of(result).assessment == Assessment.INSUFFICIENT
    assert state_of(result).stop_reason == "CRITERION_BUDGET"


def test_three_turns_yield_to_other_skill_and_resume_without_losing_progress(setup, monkeypatch):
    provider, engine, _ = setup
    gaps = partial(provider, monkeypatch)
    result = start(engine, [skill(), skill("java")])
    first_id = result.snapshot.pending_turn.objective_id
    for index in range(3):
        gaps[:] = [f"Unverified aspect {index}"]
        result = answer(engine, result.snapshot)
    assert result.snapshot.pending_turn.objective_id != first_id
    assert result.snapshot.objectives[first_id].lifecycle == "PLANNED"
    provider.observation, provider.performance = "SUPPORTS", "AT_TARGET"
    result = answer(engine, result.snapshot)
    assert result.snapshot.pending_turn.objective_id == first_id
    assert result.snapshot.objectives[first_id].turns_spent == 3
    result = answer(engine, result.snapshot)
    assert result.public.is_finished
    assert all(s.assessment == Assessment.AT for s in result.snapshot.objectives.values())


@pytest.mark.parametrize("kind", ["multiple_ids", "numbered_requests", "multiple_questions"])
def test_bundled_question_is_rejected_and_regenerated(setup, monkeypatch, kind):
    provider, engine, _ = setup
    provider.criterion_count = 2
    original = provider.question
    calls = []

    def question(context):
        calls.append(json.loads(context))
        result = original(context)
        if len(calls) == 1:
            if kind == "multiple_ids":
                result.criterion_ids.append("unrequested-criterion")
            elif kind == "numbered_requests":
                result.text = "Bài tập:\n1. Hãy viết prompt.\n2. Sau khi AI trả lời, hãy review mã.\n3. Nếu mã sai, hãy sửa lỗi."
            else:
                result.text = "Bạn sẽ viết prompt gì? Bạn review mã thế nào?"
        return result

    monkeypatch.setattr(provider, "question", question)
    initial = start(engine)
    assert initial.public.pending_turn
    assert len(calls) == 2
    assert calls[1]["validation_error"]
    assert len(calls[1]["required_question_contract"]["criterion_ids"]) == 1


def test_recovery_rebuilds_per_criterion_actions_from_legacy_turns(setup):
    provider, engine, _ = setup
    provider.observation, provider.performance = "UNCLEAR", "UNDETERMINED"
    result = answer(engine, start(engine).snapshot)
    result = answer(engine, result.snapshot)
    payload = result.snapshot.model_dump(mode="json")
    for value in payload["objectives"].values():
        value.pop("criterion_progress")
        value.pop("active_criterion_id")
    restored = Snapshot.model_validate(payload)
    provider.observation, provider.performance = "SUPPORTS", "AT_TARGET"
    result = answer(engine, restored)
    progress = next(iter(state_of(result).criterion_progress.values()))
    assert progress.turns_spent == 3
    assert progress.clarification_spent
    assert state_of(result).assessment == Assessment.AT


def test_public_projection_does_not_modify_snapshot(setup):
    _, engine, _ = setup
    snapshot = start(engine).snapshot
    saved = snapshot.model_dump_json()
    report(snapshot)
    assert snapshot.model_dump_json() == saved


def test_invalid_soft_and_hard_policy_is_rejected():
    with pytest.raises(ValueError, match="hard limit"):
        InterviewPolicy(criterion_soft_limit=4, max_turns_per_criterion=3)


def test_soft_limit_covers_unasked_criterion_before_returning_to_deep_probe(setup, monkeypatch):
    provider, engine, _ = setup
    provider.criterion_count = 2
    gaps = partial(provider, monkeypatch)
    result = start(engine)
    first = result.snapshot.pending_turn.question.criterion_ids
    for index in range(3):
        gaps[:] = [f"Remaining aspect {index}"]
        result = answer(engine, result.snapshot)
    assert result.snapshot.pending_turn.question.criterion_ids != first
    provider.observation, provider.performance = "SUPPORTS", "AT_TARGET"
    result = answer(engine, result.snapshot)
    assert result.snapshot.pending_turn.question.criterion_ids == first
    result = answer(engine, result.snapshot)
    assert state_of(result).assessment == Assessment.AT
    assert result.public.report.objectives[0].criteria[0].turns_spent == 4


def test_extension_is_requested_separately_for_each_criterion(setup, monkeypatch):
    provider, engine, _ = setup
    provider.criterion_count = 2
    engine.policy = InterviewPolicy(allow_extension_probes=True)
    original = provider.blueprint

    def blueprint(context):
        value = original(context)
        value.objectives[0].extension_depth = 3
        return value

    monkeypatch.setattr(provider, "blueprint", blueprint)
    result = start(engine)
    result = answer(engine, result.snapshot)
    result = answer(engine, result.snapshot)
    provider.performance = "ABOVE"
    for _ in range(2):
        assert result.snapshot.pending_turn.action == Action.DEEPER
        assert len(result.snapshot.pending_turn.question.criterion_ids) == 1
        result = answer(engine, result.snapshot)
    assert result.public.is_finished
    assert state_of(result).assessment == Assessment.ABOVE
    assert all(p.deeper_spent for p in state_of(result).criterion_progress.values())
    assert all(c.assessment == Assessment.ABOVE for c in result.public.report.objectives[0].criteria)


def test_problem_data_can_contain_numbered_rows_and_code_question_marks():
    from adaptive_questioning.evidence.question_validation import single_question
    assert single_question("Dữ liệu:\n1. alice@example.com\n2. bob@example.com\nBạn kiểm tra dữ liệu này thế nào?")
    assert single_question("Với mẫu `SELECT ? WHERE id = ?`, hãy giải thích cách truyền tham số?")


def test_incomplete_anchor_cannot_be_marked_passed(setup, monkeypatch):
    from adaptive_questioning.evidence.errors import JudgmentUnavailableError
    provider, engine, _ = setup
    initial = start(engine).snapshot
    saved = initial.model_dump_json()
    original = provider.judge

    def invalid(context):
        judgment = original(context)
        judgment.observations[0].unresolved_aspects = ["The essential validation rule is not established"]
        return judgment

    monkeypatch.setattr(provider, "judge", invalid)
    with pytest.raises(JudgmentUnavailableError):
        answer(engine, initial)
    assert initial.model_dump_json() == saved
