"""Verify hard vs soft question validation tiering and safe fallback behavior."""
import json
import logging

import dspy
import pytest

from adaptive_questioning.evidence.errors import QuestionUnavailableError
from adaptive_questioning.evidence.models import Action, Mode, Question
from adaptive_questioning.evidence.provider import DSPyAssessmentProvider, _judge_reasoning_effort
from adaptive_questioning.evidence.question_validation import (
    VOICE_MAX_WORDS, VOICE_SOFT_MAX_WORDS, validate_question,
)
from test_evidence_workflow import answer, setup, start


def test_validate_question_splits_hard_and_soft_errors():
    contract = {"mode": Mode.DEBUGGING, "depth": 2, "criterion_ids": ["c1"]}
    soft_voice = Question(
        text=" ".join(["API"] * VOICE_MAX_WORDS + ["chậm?"]),
        criterion_ids=["c1"], mode=Mode.DEBUGGING, depth=2, evidence_scope="slow-api",
    )
    outcome = validate_question(soft_voice, {"required_question_contract": contract, "interaction_mode": "VOICE"})
    assert outcome.hard_errors == []
    assert len(outcome.soft_errors) == 1

    hard_voice = Question(
        text=" ".join(["API"] * VOICE_SOFT_MAX_WORDS + ["chậm?"]),
        criterion_ids=["c1"], mode=Mode.DEBUGGING, depth=2, evidence_scope="slow-api",
    )
    hard_outcome = validate_question(hard_voice, {"required_question_contract": contract, "interaction_mode": "VOICE"})
    assert len(hard_outcome.hard_errors) == 1
    assert hard_outcome.soft_errors == []


def test_easier_soft_review_warning_falls_back_after_bounded_repair_without_503(setup, monkeypatch, caplog):
    provider, engine, _ = setup
    first = start(engine)
    provider.observation, provider.performance = "CONTRADICTS", "BELOW"
    reviews = []

    def persistent_soft_warning(context):
        reviews.append(json.loads(context)["question"])
        return {"verdict": "WRONG_DEPTH", "reason": "Câu chẩn đoán hơi sát target."}

    monkeypatch.setattr(provider, "review_question", persistent_soft_warning)
    with caplog.at_level(logging.INFO, logger="uvicorn.error"):
        second = answer(engine, first.snapshot)

    assert second.snapshot.pending_turn is not None
    assert second.snapshot.pending_turn.action == Action.EASIER
    assert len(reviews) == 2
    assert second.snapshot.pending_turn.question.text == reviews[-1]
    assert "interview.question.soft_fallback" in caplog.text


def test_clarify_soft_review_warning_falls_back_without_503(setup, monkeypatch):
    provider, engine, _ = setup
    first = start(engine)
    provider.observation, provider.performance = "UNCLEAR", "UNDETERMINED"
    reviews = []

    def persistent_insufficient(context):
        reviews.append(json.loads(context)["question"])
        return {"verdict": "INSUFFICIENT_EVIDENCE", "reason": "Câu hỏi làm rõ ngắn."}

    monkeypatch.setattr(provider, "review_question", persistent_insufficient)
    second = answer(engine, first.snapshot)

    assert second.snapshot.pending_turn is not None
    assert second.snapshot.pending_turn.action == Action.CLARIFY
    assert len(reviews) == 2


@pytest.mark.parametrize("verdict", ["GIVES_SOLUTION", "UNANSWERABLE", "WRONG_SKILL"])
def test_hard_alignment_verdicts_never_soft_fallback(setup, monkeypatch, verdict):
    provider, engine, _ = setup
    first = start(engine)
    provider.observation, provider.performance = "CONTRADICTS", "BELOW"
    monkeypatch.setattr(provider, "review_question", lambda _: {"verdict": verdict, "reason": "Lỗi nghiêm trọng"})
    with pytest.raises(QuestionUnavailableError):
        answer(engine, first.snapshot)


def test_soft_validation_fallback_still_runs_safety_review(setup, monkeypatch):
    provider, engine, _ = setup
    original = provider.question
    draft_count = 0

    def slightly_long_voice(context):
        nonlocal draft_count
        draft_count += 1
        q = original(context)
        q.text = " ".join(["Hệ", "thống"] * 47 + [f"câu_{draft_count}?"])
        return q

    reviews = []
    monkeypatch.setattr(provider, "question", slightly_long_voice)
    monkeypatch.setattr(provider, "review_question", lambda ctx: (reviews.append(ctx), "ALIGNED")[1])
    result = start(engine, interaction_mode="VOICE")

    assert result.snapshot.pending_turn is not None
    assert draft_count == 3
    assert len(reviews) == 1

    # If the unreviewed soft candidate violates a hard alignment verdict, it must still be rejected.
    monkeypatch.setattr(provider, "review_question", lambda _: "GIVES_SOLUTION")
    with pytest.raises(QuestionUnavailableError):
        start(engine, interaction_mode="VOICE")


def test_judge_reasoning_effort_env_configuration(monkeypatch):
    monkeypatch.delenv("OPENROUTER_JUDGE_REASONING_EFFORT", raising=False)
    assert _judge_reasoning_effort() == "none"

    monkeypatch.setenv("OPENROUTER_JUDGE_REASONING_EFFORT", "low")
    assert _judge_reasoning_effort() == "low"

    monkeypatch.setenv("OPENROUTER_JUDGE_REASONING_EFFORT", "invalid-tier")
    assert _judge_reasoning_effort() == "none"

    monkeypatch.setenv("OPENROUTER_JUDGE_REASONING_EFFORT", "low")
    lm = dspy.LM("openai/gpt-4o-mini", api_key="test-key")
    provider = DSPyAssessmentProvider(lm=lm)
    assert provider.judge_lm.kwargs["extra_body"] == {"reasoning": {"effort": "low"}}
