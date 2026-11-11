"""Recovered corpus, evidence-only metrics and usable DSPy compile/load paths."""
import hashlib
import json

import dspy
import pytest

from adaptive_questioning.evidence.assessment import validate_judgment
from adaptive_questioning.evidence.models import Judgment, Turn
from adaptive_questioning.evidence.provider import DSPyAssessmentProvider
from adaptive_questioning.evidence.question_validation import question_errors
from adaptive_questioning.optimization import compiler
from adaptive_questioning.optimization.dataset import (
    CORPUS_PATH, corpus_records, get_gold_judge_examples, get_gold_question_examples,
)
from adaptive_questioning.optimization.metrics import (
    judge_evaluation_metric, question_generation_metric, set_judge_lm,
)


@pytest.fixture(autouse=True)
def clear_teacher():
    set_judge_lm(None)
    yield
    set_judge_lm(None)


@pytest.mark.parametrize("kind, getter", [
    ("questions", get_gold_question_examples), ("judgments", get_gold_judge_examples),
])
def test_all_cases_and_original_split_survive(kind, getter):
    records = corpus_records(kind)
    assert len(records) == len(getter()) == 20
    train, dev = getter("train"), getter("dev")
    assert len(train) == 14 and len(dev) == 6
    assert [ex.context for ex in getter("val")] == [ex.context for ex in dev]
    assert not {ex.context for ex in train}.intersection(ex.context for ex in dev)
    assert all(list(ex.inputs().keys()) == ["context"] for ex in getter())
    assert all(set(ex.labels().keys()) == ({"question"} if kind == "questions" else {"judgment"})
               for ex in getter())
    with pytest.raises(ValueError):
        getter("invalid")


def test_original_source_texts_are_preserved():
    questions = corpus_records("questions")
    judgments = corpus_records("judgments")
    # Digests of the 20 original questions / 20 original candidate responses from
    # the pre-removal corpus; guards against silently replacing it with new data.
    q_digest = hashlib.sha256(json.dumps([r["source_question"] for r in questions], ensure_ascii=False).encode()).hexdigest()
    j_digest = hashlib.sha256(json.dumps([r["source_response"] for r in judgments], ensure_ascii=False).encode()).hexdigest()
    assert q_digest == "62a4e6e704dc134aa6c16c7ba1b1ee0bbfacd8dbec4fbcbda4f3830a1529cda5"
    assert j_digest == "6409aef479458a2aa148ab745b725397df60221af91d46678273f1741f0350b3"
    for record in judgments:
        assert record["context"]["turn"]["answer"] == record["source_response"]


def test_current_training_data_has_no_probability_contracts():
    payload = CORPUS_PATH.read_text(encoding="utf-8")
    for getter in (get_gold_question_examples, get_gold_judge_examples):
        for example in getter():
            payload += example.context + str(example.labels())
    for retired in ("raw_belief", "raw_posterior_probs", "metamorphic_tag", "Phân phối niềm tin", "P_{t-1}",
                    "MINOR_SHIFT", "MODERATE_SHIFT", "DECISIVE_SHIFT", "INVARIANT"):
        assert retired not in payload


def test_gold_cases_meet_runtime_contracts():
    for example in get_gold_question_examples():
        context = json.loads(example.context)
        assert not question_errors(example.question, context, context["target_criteria"])
        assert len(example.question.text.split()) <= 55
        assert question_generation_metric(example, dspy.Prediction(question=example.question)) == 0.7
    for example in get_gold_judge_examples():
        validate_judgment(example.judgment, Turn.model_validate(json.loads(example.context)["turn"]))
        assert judge_evaluation_metric(example, dspy.Prediction(judgment=example.judgment)) == 1


@pytest.mark.parametrize("change", ["abductive", "criterion", "depth", "mode", "bundled", "off_topic", "long"])
def test_question_metric_rejects_invalid_or_unfocused_questions(change):
    example = get_gold_question_examples()[0]
    question = example.question.model_copy(deep=True)
    if change == "abductive": question.hypothesis_A = "   "
    elif change == "criterion": question.criterion_ids = ["other:c1"]
    elif change == "depth": question.depth = 1
    elif change == "mode": question.mode = "DESIGN"
    elif change == "bundled": question.text += " Bạn cấu hình logging thế nào?"
    elif change == "off_topic": question.text = "Bạn thích ăn món gì vào buổi tối?"
    elif change == "long": question.text = "Hệ thống đang chạy. " * 40 + question.text
    assert question_generation_metric(example, dspy.Prediction(question=question)) == 0


@pytest.mark.parametrize("change", ["quote", "criterion", "performance", "gap", "hint"])
def test_judge_metric_rejects_ungrounded_or_incorrect_assessment(change):
    example = get_gold_judge_examples()[1]  # a substantive Terraform answer
    judgment = example.judgment.model_copy(deep=True)
    item = judgment.observations[0]
    if change == "quote": item.response_excerpt = "Ứng viên đã kiểm thử thành công mọi tình huống."
    elif change == "criterion": item.criterion_id = "wrong:c1"
    elif change == "performance": item.performance = "BELOW"
    elif change == "gap": item.unresolved_aspects = ["thiếu bằng chứng"]
    elif change == "hint": judgment.feedback_contains_hint = True
    assert judge_evaluation_metric(example, dspy.Prediction(judgment=judgment)) == 0


def test_partial_answer_cannot_be_promoted_to_pass():
    example = get_gold_judge_examples()[8]
    judgment = example.judgment.model_copy(deep=True)
    item = judgment.observations[0]
    item.observation, item.performance = "SUPPORTS", "AT_TARGET"
    item.unresolved_aspects = []
    item.response_excerpt = json.loads(example.context)["turn"]["answer"]
    assert judge_evaluation_metric(example, dspy.Prediction(judgment=judgment)) == 0


def test_labeled_compilation_saves_loads_and_runs_through_v2_provider(tmp_path):
    q_module, j_module = compiler.compile_with_labeled_few_shot(2, 2)
    assert len(q_module.demos) == len(j_module.demos) == 2
    compiler.save_compiled_modules(q_module, j_module, tmp_path)
    question, judgment = get_gold_question_examples()[0], get_gold_judge_examples()[1]
    lm = dspy.utils.DummyLM([
        {"question": question.question.model_dump(mode="json")},
        {"judgment": judgment.judgment.model_dump(mode="json")},
    ])
    provider = DSPyAssessmentProvider(lm=lm, compiled_dir=str(tmp_path))
    assert len(provider.question_module.demos) == len(provider.judge_module.demos) == 2
    assert provider.question(question.context) == question.question
    assert provider.judge(judgment.context) == judgment.judgment


@pytest.mark.parametrize("tamper", ["version", "contract", "file"])
def test_incompatible_artifacts_cannot_load(tmp_path, tamper):
    compiler.seed_default_compiled_artifacts(tmp_path)
    manifest_path = tmp_path / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    if tamper == "version": manifest["version"] = "legacy"
    elif tamper == "contract": manifest["contract_fingerprint"] = "old-schema"
    else: (tmp_path / "question_generator.json").write_text("{}")
    manifest_path.write_text(json.dumps(manifest))
    with pytest.raises(ValueError):
        compiler.load_compiled_modules(tmp_path)


def test_artifact_formatting_changes_across_platforms_remain_loadable(tmp_path):
    compiler.seed_default_compiled_artifacts(tmp_path)
    for filename in ("question_generator.json", "reflective_judge.json"):
        path = tmp_path / filename
        content = json.dumps(json.loads(path.read_text(encoding="utf-8")), ensure_ascii=False, indent=4)
        path.write_bytes(content.replace("\n", "\r\n").encode("utf-8"))
    assert len(compiler.load_compiled_modules(tmp_path)[0].demos) == 3


def test_bootstrap_keeps_train_split_threshold_and_explicit_teacher(monkeypatch):
    calls = []
    teacher = dspy.utils.DummyLM([])
    student = dspy.utils.DummyLM([])
    class FakeBootstrap:
        def __init__(self, **kwargs): self.options = kwargs
        def compile(self, module, trainset):
            calls.append((self.options, trainset))
            return module
    monkeypatch.setattr(dspy, "BootstrapFewShot", FakeBootstrap)
    compiler.compile_with_bootstrap_few_shot(student, judge_lm=teacher)
    assert len(calls) == 2
    assert all(options["metric_threshold"] == 0.8 and len(trainset) == 14 for options, trainset in calls)
    seen = []
    def capture(*args, lm=None): seen.append(lm); return 1.0
    monkeypatch.setattr(compiler, "question_generation_metric", capture)
    monkeypatch.setattr(compiler, "judge_evaluation_metric", capture)
    for options, trainset in calls:
        assert options["metric"](trainset[0], object()) == 1.0
    assert seen == [teacher, teacher]
    with pytest.raises(ValueError): compiler.compile_with_bootstrap_few_shot(student, train_split="dev")
    with pytest.raises(ValueError): compiler.compile_with_bootstrap_few_shot(student, metric_threshold=0.5)


@pytest.mark.parametrize("depth_ok, expected", [(True, 1.0), (False, 0.0)])
def test_semantic_teacher_can_reject_shallow_questions(depth_ok, expected):
    example = get_gold_question_examples()[0]
    teacher = dspy.utils.DummyLM([{"is_on_topic": True, "is_single_intent": True,
                                  "is_depth_appropriate": depth_ok, "rationale": "Task depth checked"}])
    assert question_generation_metric(example, dspy.Prediction(question=example.question), lm=teacher) == expected


def test_semantic_teacher_catches_unreported_solution_hints():
    example = get_gold_judge_examples()[1]
    teacher = dspy.utils.DummyLM([{"supported": True, "safe_feedback": False,
                                  "rationale": "Feedback reveals the solution"}])
    assert judge_evaluation_metric(example, dspy.Prediction(judgment=example.judgment), lm=teacher) == 0


def test_checked_in_artifacts_are_current_and_contain_only_training_demos():
    question, judge = compiler.load_compiled_modules(compiler.DEFAULT_COMPILED_DIR)
    for module, getter in ((question, get_gold_question_examples), (judge, get_gold_judge_examples)):
        train = {example.context for example in getter("train")}
        assert len(module.demos) == 3
        assert all(demo["context"] in train for demo in module.demos)


def test_dev_evaluation_is_held_out_and_reports_failures():
    class Echo:
        def __init__(self, examples, field): self.values = {e.context: e[field] for e in examples}; self.field = field
        def __call__(self, context): return dspy.Prediction(**{self.field: self.values[context]})
    result = compiler.evaluate_modules_on_dev(Echo(get_gold_question_examples("dev"), "question"),
        Echo(get_gold_judge_examples("dev"), "judgment"))
    assert result["question_examples_count"] == result["judge_examples_count"] == 6
    assert result["evaluation_errors"] == 0
    assert result["question_semantic_evaluator"] == "lexical_heuristic"
    with pytest.raises(ValueError): compiler.evaluate_modules_on_dev(None, None, split="train")
