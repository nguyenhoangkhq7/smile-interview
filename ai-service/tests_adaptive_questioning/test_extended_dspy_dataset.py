"""Tests for extended domain-disjoint DSPy corpora across Question, Judge, Alignment, Blueprint, and Dialogue."""
import json

import dspy
import pytest

from adaptive_questioning.evidence.assessment import validate_judgment
from adaptive_questioning.evidence.models import Turn
from adaptive_questioning.evidence.question_validation import question_errors
from adaptive_questioning.optimization.dataset import corpus_records
from adaptive_questioning.optimization.extended_dataset import (
    CORPORA_DIR,
    corpus_summary,
    get_alignment_examples,
    get_blueprint_examples,
    get_extended_dialogue_examples,
    get_extended_judge_examples,
    get_extended_question_examples,
)
from adaptive_questioning.optimization.metrics import (
    ALIGNMENT_VERDICTS,
    alignment_evaluation_metric,
    alignment_macro_f1,
    blueprint_evaluation_metric,
    judge_evaluation_metric,
    question_generation_metric,
    set_judge_lm,
)


@pytest.fixture(autouse=True)
def clear_teacher():
    set_judge_lm(None)
    yield
    set_judge_lm(None)


def test_extended_corpus_counts_and_splits():
    summary = corpus_summary()
    assert summary == {
        "questions": {"train": 18, "dev": 9, "test": 9},
        "judgments": {"train": 19, "dev": 9, "test": 9},
        "alignments": {"train": 18, "dev": 9, "test": 8},
        "blueprints": {"train": 9, "dev": 5, "test": 4},
        "dialogues": {"train": 6, "dev": 3, "test": 3},
    }
    assert len(get_extended_question_examples("all")) == 36
    assert len(get_extended_question_examples("all", include_base=True)) == 60
    assert len(get_extended_question_examples("test", include_base=True)) == 9
    assert len(get_extended_judge_examples("all")) == 37
    assert len(get_extended_judge_examples("all", include_base=True)) == 61
    assert len(get_extended_judge_examples("test", include_base=True)) == 9
    assert len(get_alignment_examples("all")) == 35
    assert len(get_blueprint_examples("all")) == 18
    assert len(get_extended_dialogue_examples("all")) == 12
    assert [ex.context for ex in get_extended_question_examples("val")] == [
        ex.context for ex in get_extended_question_examples("dev")
    ]
    with pytest.raises(ValueError):
        get_extended_question_examples("invalid")  # type: ignore[arg-type]


def test_extended_splits_are_domain_disjoint_and_test_excludes_legacy_skills():
    legacy_skills = {record["context"]["objective"]["skill_id"] for record in corpus_records("questions")}
    extractors = [
        ("questions.json", lambda r: r["context"]["objective"]["skill_id"]),
        ("judgments.json", lambda r: r["context"]["objective"]["skill_id"]),
        ("alignments.json", lambda r: r["skill_id"]),
        ("blueprints.json", lambda r: r["skills"][0]["jd_skill_id"]),
        ("dialogues.json", lambda r: r["objective"]["skill_id"]),
    ]
    for filename, get_skill in extractors:
        records = json.loads((CORPORA_DIR / filename).read_text(encoding="utf-8"))
        by_split = {split: {get_skill(r) for r in records if r["split"] == split} for split in ("train", "dev", "test")}
        assert not (by_split["train"] & by_split["dev"]), filename
        assert not (by_split["train"] & by_split["test"]), filename
        assert not (by_split["dev"] & by_split["test"]), filename
        assert not (by_split["test"] & legacy_skills), filename


def test_extended_questions_cover_all_modes_depths_actions_and_pass_metrics():
    examples = get_extended_question_examples("all")
    modes, actions, depths, interaction_modes = set(), set(), set(), set()
    has_repair_demo = False
    for ex in examples:
        assert list(ex.inputs().keys()) == ["context"]
        assert set(ex.labels().keys()) == {"question"}
        ctx = json.loads(ex.context)
        modes.add(ex.question.mode)
        actions.add(ctx["action"])
        depths.add(ex.question.depth)
        interaction_modes.add(ctx["interaction_mode"])
        has_repair_demo |= "validation_error" in ctx
        assert not question_errors(ex.question, ctx)
        if ctx["interaction_mode"] == "VOICE":
            assert len(ex.question.text.split()) <= 55
        assert question_generation_metric(ex, dspy.Prediction(question=ex.question)) == 0.7

    assert modes == {"CODING", "DEBUGGING", "DESIGN", "TECHNICAL_EXPLANATION", "BEHAVIORAL"}
    assert actions == {"INITIAL", "FOLLOW_UP", "CLARIFY", "ASK_EASIER", "PROBE_DEEPER", "VERIFY_CONTRADICTION"}
    assert depths == {1, 2, 3, 4}
    assert interaction_modes == {"TEXT", "VOICE"}
    assert has_repair_demo


def test_extended_judgments_cover_hard_cases_and_pass_metrics():
    examples = get_extended_judge_examples("all")
    observations, performances = set(), set()
    line_range_count = coding_check_count = inability_count = 0
    for ex in examples:
        assert list(ex.inputs().keys()) == ["context"]
        assert set(ex.labels().keys()) == {"judgment"}
        ctx = json.loads(ex.context)
        turn = Turn.model_validate(ctx["turn"])
        validate_judgment(ex.judgment.model_copy(deep=True), turn)
        assert judge_evaluation_metric(ex, dspy.Prediction(judgment=ex.judgment)) == 1.0
        for item in ex.judgment.observations:
            observations.add(item.observation)
            performances.add(item.performance)
            line_range_count += int(item.response_line_range is not None)
        coding_check_count += int("coding_checks" in ctx)
        inability_count += int(ex.judgment.explicit_inability)

    assert observations == {"SUPPORTS", "CONTRADICTS", "UNCLEAR", "NO_EVIDENCE"}
    assert performances == {"BELOW", "AT_TARGET", "ABOVE", "UNDETERMINED"}
    assert line_range_count >= 5
    assert coding_check_count >= 2
    assert inability_count >= 2


def test_alignment_examples_cover_all_verdicts_and_macro_f1():
    examples = get_alignment_examples("all")
    verdicts = {ex.verdict for ex in examples}
    assert verdicts == ALIGNMENT_VERDICTS
    for ex in examples:
        assert list(ex.inputs().keys()) == ["context"]
        assert alignment_evaluation_metric(ex, dspy.Prediction(verdict=ex.verdict)) == 1.0
        assert alignment_evaluation_metric(ex, dspy.Prediction(verdict="INVALID_LABEL")) == 0.0
    golds = [ex.verdict for ex in examples]
    assert alignment_macro_f1(golds, golds) == pytest.approx(1.0)
    assert alignment_macro_f1(golds, ["ALIGNED"] * len(golds)) < 0.2


def test_blueprint_examples_validate_offline_and_with_semantic_teacher():
    examples = get_blueprint_examples("all")
    for ex in examples:
        assert set(ex.inputs().keys()) == {"context"}
        assert blueprint_evaluation_metric(ex, dspy.Prediction(blueprint=ex.blueprint)) == 0.7

    sample = examples[0]
    teacher = dspy.utils.DummyLM([
        {"atomic_criteria": True, "grounded_anchors": True, "rationale": "Atomic Vietnamese criteria"},
        {"atomic_criteria": False, "grounded_anchors": True, "rationale": "Bundled criteria"},
    ])
    assert blueprint_evaluation_metric(sample, dspy.Prediction(blueprint=sample.blueprint), lm=teacher) == 1.0
    assert blueprint_evaluation_metric(sample, dspy.Prediction(blueprint=sample.blueprint), lm=teacher) == 0.0

    wrong_depth = sample.blueprint.model_copy(deep=True)
    wrong_depth.objectives[0].target_depth = 4
    assert blueprint_evaluation_metric(sample, dspy.Prediction(blueprint=wrong_depth)) == 0.0


def test_extended_dialogues_pair_valid_judgment_and_next_question():
    pairs = get_extended_dialogue_examples("all")
    assert len(pairs) == 12
    for judge_ex, next_q_ex in pairs:
        assert judge_evaluation_metric(judge_ex, dspy.Prediction(judgment=judge_ex.judgment)) == 1.0
        assert question_generation_metric(next_q_ex, dspy.Prediction(question=next_q_ex.question)) == 0.7
