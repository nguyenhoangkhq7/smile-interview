"""Question generation sees its probe chain without leaking unrelated answers."""
import json

import pytest

from adaptive_questioning.evidence.models import Action, RecordedEvidence
from adaptive_questioning.evidence.dspy_modules import build_question_inputs
from adaptive_questioning.evidence.provider import encode_context
from test_evidence_depth_policy import audit, task_skill
from test_evidence_workflow import answer, start


def question_context(provider):
    return next(values for kind, values in reversed(provider.contexts) if kind == "question")


@pytest.mark.parametrize("interaction_mode", ["TEXT", "VOICE"])
def test_switching_objective_excludes_unrelated_answer_but_preserves_transcript(audit, interaction_mode):
    provider, engine, _ = audit
    initial = start(engine, [task_skill(name="java"), task_skill(name="python")],
                    interaction_mode=interaction_mode)
    unrelated_answer = "PRIVATE_OTHER_OBJECTIVE_ANSWER " * 500
    result = answer(engine, initial.snapshot, unrelated_answer)
    assert result.snapshot.pending_turn.objective_id != initial.snapshot.pending_turn.objective_id
    context = question_context(provider)
    assert context["history"] == []
    assert context["prior_observations"] == []
    assert context["other_questions"] == []
    assert initial.snapshot.pending_turn.question.text not in json.dumps(context)
    assert "PRIVATE_OTHER_OBJECTIVE_ANSWER" not in json.dumps(context)
    assert result.snapshot.turns[0].answer == unrelated_answer
    assert result.public.turns[0].answer == unrelated_answer
    old_context = dict(context, history=[turn.model_dump(mode="json") for turn in result.snapshot.turns])
    assert len(json.dumps(context)) < len(json.dumps(old_context)) / 2


def test_switching_criterion_keeps_decisions_outside_the_active_grading_history(audit):
    provider, engine, _ = audit
    provider.criterion_count = 2
    initial = start(engine, [task_skill()])
    result = answer(engine, initial.snapshot, "ANSWER_FOR_PREVIOUS_CRITERION")
    assert result.snapshot.pending_turn.objective_id == initial.snapshot.pending_turn.objective_id
    assert result.snapshot.pending_turn.question.criterion_ids != initial.snapshot.pending_turn.question.criterion_ids
    context = question_context(provider)
    assert context["history"] == []
    assert context["case_notes"][0]["candidate_account"] == "ANSWER_FOR_PREVIOUS_CRITERION"
    _, inputs = build_question_inputs(json.dumps(context))
    assert json.loads(inputs["session_context"])["case_notes"] == context["case_notes"]
    assert context["other_questions"] == [{
        "question": initial.snapshot.pending_turn.question.text, "truncated": False,
    }]


def test_repetition_guard_still_checks_questions_from_other_objectives(audit, monkeypatch):
    provider, engine, _ = audit
    initial = start(engine, [task_skill(), task_skill(name="python")])
    previous_question = initial.snapshot.pending_turn.question.text
    original_question = provider.question
    attempts = []

    def repeat_once(context):
        values = json.loads(context)
        attempts.append(values)
        question = original_question(context)
        if len(attempts) == 1:
            question.text = previous_question
        return question

    monkeypatch.setattr(provider, "question", repeat_once)
    result = answer(engine, initial.snapshot)
    assert len(attempts) == 2
    assert attempts[0]["history"] == []
    assert attempts[0]["other_questions"] == []
    assert "repeats a prior turn" in attempts[1]["validation_error"]
    assert result.snapshot.pending_turn.question.text != previous_question
    assert len(result.snapshot.turns) == 1


def test_clarification_keeps_full_original_question_answer_and_scope(audit):
    provider, engine, _ = audit
    provider.observation, provider.performance = "UNCLEAR", "UNDETERMINED"
    initial = start(engine, [task_skill()])
    first = answer(engine, initial.snapshot, "FIRST_UNCLEAR_ANSWER")
    assert first.snapshot.pending_turn.action == Action.CLARIFY
    context = question_context(provider)
    first_turn = first.snapshot.turns[0]
    assert context["history"] == [{
        "turn_id": first_turn.turn_id,
        "action": first_turn.action.value,
        "question_depth": first_turn.question_depth,
        "question": first_turn.question.model_dump(mode="json"),
        "answer": first_turn.answer,
    }]
    assert "judgment" not in context["history"][0]
    assert context["required_question_contract"]["evidence_scope"] == initial.snapshot.pending_turn.question.evidence_scope
    assert context["prior_observations"][0]["response_excerpt"] == "FIRST_UNCLEAR_ANSWER"
    second = answer(engine, first.snapshot, "SECOND_UNCLEAR_ANSWER")
    context = question_context(provider)
    assert [turn["answer"] for turn in context["history"]] == ["FIRST_UNCLEAR_ANSWER", "SECOND_UNCLEAR_ANSWER"]
    assert context["other_questions"] == []
    assert len(second.snapshot.turns) == 2


def test_resumed_chain_keeps_contradictions_and_legacy_multicriterion_turns(audit):
    provider, engine, _ = audit
    provider.criterion_count = 2
    snapshot = start(engine, [task_skill(), task_skill(name="python")]).snapshot
    state = snapshot.objectives[snapshot.queue[0]]
    target, other = [criterion.criterion_id for criterion in state.objective.criteria]
    original = snapshot.pending_turn.model_copy(deep=True)
    original.turn_id, original.answer = "main", "ORIGINAL_TARGET_ANSWER"
    original.question.criterion_ids = [target, other]  # Legacy combined question.
    unrelated = original.model_copy(deep=True)
    unrelated.turn_id, unrelated.answer = "unrelated", "UNRELATED_ANSWER"
    unrelated.objective_id = snapshot.queue[1]
    unrelated.question.criterion_ids = [target]  # Same ID must not cross objective boundaries.
    unrelated.question.text = "Other question " * 100
    other_criterion = original.model_copy(deep=True)
    other_criterion.turn_id, other_criterion.answer = "other-criterion", "OTHER_CRITERION_ANSWER"
    other_criterion.question.criterion_ids = [other]
    other_criterion.question.text = "Same objective other criterion " * 30
    followup = original.model_copy(deep=True)
    followup.turn_id, followup.answer = "followup", "CONFLICTING_TARGET_ANSWER"
    followup.question.criterion_ids = [target]
    snapshot.turns = [original, unrelated, other_criterion, followup]
    state.evidence_history = [RecordedEvidence(
        turn_id="followup", criterion_id=target, question_depth=2, response_excerpt=followup.answer,
        observation="CONTRADICTS", performance="BELOW", rationale="Conflicting evidence",
    ), RecordedEvidence(
        turn_id="different-criterion", criterion_id=other, question_depth=2, response_excerpt="UNRELATED_EVIDENCE",
        observation="SUPPORTS", performance="AT_TARGET", rationale="Other criterion",
    )]
    before = snapshot.model_dump(mode="json")
    # Simulate a persisted session resumed after another objective's turn.
    context = json.loads(encode_context(engine._question_context(snapshot, Action.VERIFY)))
    assert [turn["turn_id"] for turn in context["history"]] == ["main", "followup"]
    assert context["prior_observations"][0]["observation"] == "CONTRADICTS"
    assert len(context["prior_observations"]) == 1
    assert context["other_questions"] == [{"question": other_criterion.question.text[:300], "truncated": True}]
    assert "Other question" not in json.dumps(context)
    assert context["case_notes"][0]["candidate_account"] == "OTHER_CRITERION_ANSWER"
    assert "UNRELATED_ANSWER" not in json.dumps(context)
    assert "UNRELATED_EVIDENCE" not in json.dumps(context)
    assert snapshot.model_dump(mode="json") == before
