"""Recovered corpus, evidence-only metrics and usable DSPy compile/load paths."""
import hashlib
import json

import dspy
import pytest
from fastapi import FastAPI, Request

from adaptive_questioning.evidence.assessment import validate_judgment
from adaptive_questioning.evidence.models import Judgment, Turn
from adaptive_questioning.evidence.provider import DSPyAssessmentProvider
from adaptive_questioning.evidence.question_validation import question_errors
from adaptive_questioning.evidence.routes import workflow
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
    assert len(records) == 20
    assert len(getter()) == 24
    train, dev = getter("train"), getter("dev")
    assert len(train) == 16 and len(dev) == 8
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
        for turn in context["history"]:
            assert {"mode", "depth", "assistance"}.isdisjoint(turn["question"])
        assert not question_errors(example.question, context)
        assert len(example.question.text.split()) <= 55
        assert question_generation_metric(example, dspy.Prediction(question=example.question)) == 0.7
    for example in get_gold_judge_examples():
        context = json.loads(example.context)
        assert "required_criterion_ids" not in context
        assert {"mode", "depth", "assistance"}.isdisjoint(context["turn"]["question"])
        validate_judgment(example.judgment, Turn.model_validate(context["turn"]))
        assert judge_evaluation_metric(example, dspy.Prediction(judgment=example.judgment)) == 1


@pytest.mark.parametrize("change", ["empty_scope", "criterion", "depth", "mode", "bundled", "off_topic", "long"])
def test_question_metric_rejects_invalid_or_unfocused_questions(change):
    example = get_gold_question_examples()[0]
    question = example.question.model_copy(deep=True)
    if change == "empty_scope": question.evidence_scope = "   "
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
    q_module, j_module = compiler.compile_with_labeled_few_shot(2, 2, use_extended=True)
    assert len(q_module.initial.predict.demos) == len(q_module.followup.predict.demos) == len(q_module.diagnostic.predict.demos) == 2
    assert len(j_module.assess.predict.demos) == 2
    compiler.save_compiled_modules(q_module, j_module, tmp_path)
    question, judgment = get_gold_question_examples()[0], get_gold_judge_examples()[1]
    lm = dspy.utils.DummyLM([
        {"plan": "Lượt INITIAL mức L4 bám đúng tiêu chí.", "reasoning": "Lượt INITIAL mức L4 bám đúng tiêu chí.", "question": question.question.model_dump(mode="json")},
        {"plan": "Đánh giá bằng chứng nguyên văn Terraform.", "reasoning": "Đánh giá bằng chứng nguyên văn Terraform.", "assessment": {
            "observations": [o.model_dump(mode="json") for o in judgment.judgment.observations],
            "explicit_inability": judgment.judgment.explicit_inability,
            "inability_excerpt": judgment.judgment.inability_excerpt,
            "feedback": judgment.judgment.feedback,
            "feedback_contains_hint": judgment.judgment.feedback_contains_hint,
        }},
    ])
    lm.adapter = dspy.JSONAdapter()
    provider = DSPyAssessmentProvider(lm=lm, compiled_dir=str(tmp_path))
    assert len(provider.question_module.initial.predict.demos) == len(provider.judge_module.assess.predict.demos) == 2
    assert provider.question(question.context) == question.question
    assert provider.judge(judgment.context) == judgment.judgment
    assert len(lm.history) == 2


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
    assert len(compiler.load_compiled_modules(tmp_path)[0].initial.predict.demos) == 3


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
    assert all(options["metric_threshold"] == 0.8 and len(trainset) == 16 for options, trainset in calls)
    seen = []
    def capture(*args, lm=None): seen.append(lm); return 1.0
    monkeypatch.setattr(compiler, "question_generation_metric", capture)
    monkeypatch.setattr(compiler, "judge_evaluation_metric", capture)
    for options, trainset in calls:
        assert options["metric"](trainset[0], object()) == 1.0
    assert seen == [teacher, teacher]
    with pytest.raises(ValueError): compiler.compile_with_bootstrap_few_shot(student, train_split="dev")
    with pytest.raises(ValueError): compiler.compile_with_bootstrap_few_shot(student, metric_threshold=0.5)


@pytest.mark.parametrize("depth_ok, fits, expected", [(True, True, 1.0), (False, True, 0.0), (True, False, 0.0)])
def test_semantic_teacher_can_reject_shallow_questions(depth_ok, fits, expected):
    example = get_gold_question_examples()[0]
    teacher = dspy.utils.DummyLM([{"is_on_topic": True, "is_single_intent": True,
                                  "is_depth_appropriate": depth_ok, "fits_conversation": fits, "rationale": "Task depth checked"}])
    assert question_generation_metric(example, dspy.Prediction(question=example.question), lm=teacher) == expected


@pytest.mark.parametrize("safe, grounded", [(False, True), (True, False)])
def test_semantic_teacher_rejects_unusable_feedback(safe, grounded):
    example = get_gold_judge_examples()[1]
    teacher = dspy.utils.DummyLM([{"supported": True, "safe_feedback": safe, "grounded_feedback": grounded,
                                  "rationale": "Feedback reveals the solution"}])
    assert judge_evaluation_metric(example, dspy.Prediction(judgment=example.judgment), lm=teacher) == 0


def test_default_interview_workflow_loads_checked_in_training_demos(monkeypatch):
    from adaptive_questioning.evidence.dspy_modules import build_judge_stage1_inputs, build_question_inputs
    from adaptive_questioning.optimization.extended_dataset import (
        get_extended_judge_examples, get_extended_question_examples,
    )

    monkeypatch.setattr("adaptive_questioning.evidence.provider.configured_lm", lambda: dspy.utils.DummyLM([]))
    request = Request({"type": "http", "app": FastAPI()})
    provider = workflow(request).provider
    train_q_contracts = {
        build_question_inputs(ex.context)[1]["question_contract"]
        for ex in get_extended_question_examples("train", include_base=True)
    }
    dev_q_contracts = {
        build_question_inputs(ex.context)[1]["question_contract"]
        for ex in get_extended_question_examples("dev", include_base=True)
    }
    for branch in (provider.question_module.initial, provider.question_module.followup, provider.question_module.diagnostic):
        assert 2 <= len(branch.predict.demos) <= 4
        for demo in branch.predict.demos:
            assert demo["question_contract"] in train_q_contracts
            assert demo["question_contract"] not in dev_q_contracts
            assert "reasoning" in demo

    train_j_answers = {
        build_judge_stage1_inputs(ex.context)["candidate_answer"]
        for ex in get_extended_judge_examples("train", include_base=True)
    }
    assert 2 <= len(provider.judge_module.assess.predict.demos) <= 3
    assert all(demo["candidate_answer"] in train_j_answers and "reasoning" in demo
               for demo in provider.judge_module.assess.predict.demos)
    assert all(len(demo["reasoning"]) <= 200 for demo in provider.judge_module.assess.predict.demos)


def test_dev_evaluation_is_held_out_and_reports_failures():
    class Echo:
        def __init__(self, examples, field): self.values = {e.context: e[field] for e in examples}; self.field = field
        def __call__(self, context): return dspy.Prediction(**{self.field: self.values[context]})
    result = compiler.evaluate_modules_on_dev(Echo(get_gold_question_examples("dev"), "question"),
        Echo(get_gold_judge_examples("dev"), "judgment"))
    assert result["question_examples_count"] == result["judge_examples_count"] == 8
    assert result["paired_dialogue_count"] == 2
    assert result["paired_dialogue_avg_score"] == pytest.approx(0.7)
    assert result["evaluation_errors"] == 0
    assert result["question_semantic_evaluator"] == "lexical_heuristic"
    with pytest.raises(ValueError): compiler.evaluate_modules_on_dev(None, None, split="train")


@pytest.mark.parametrize(("action", "expected_branch"), [
    ("INITIAL", "initial"),
    ("FOLLOW_UP", "followup"),
    ("PROBE_DEEPER", "followup"),
    ("VERIFY_CONTRADICTION", "followup"),
    ("CLARIFY", "diagnostic"),
    ("ASK_EASIER", "diagnostic"),
])
def test_question_module_routes_actions_to_focused_cot_branches(action, expected_branch):
    from adaptive_questioning.evidence.dspy_modules import QuestionGeneratorModule

    module = QuestionGeneratorModule()
    assert module.branch_name_for_action(action) == expected_branch
    assert hasattr(module.predictor_for_action(action), "predict")


def test_reflective_judge_short_circuits_inability_in_single_call():
    from adaptive_questioning.evidence.dspy_modules import EvidenceAssessment, ReflectiveJudgeModule

    inability_ex = next(
        ex for ex in get_gold_judge_examples("train")
        if ex.judgment.explicit_inability and all(o.observation == "NO_EVIDENCE" for o in ex.judgment.observations)
    )
    assessment = EvidenceAssessment(
        observations=inability_ex.judgment.observations,
        explicit_inability=True,
        inability_excerpt=inability_ex.judgment.inability_excerpt,
        feedback="Phản hồi dài bị ghi đè khi explicit_inability=True.",
        feedback_contains_hint=True,
    )
    lm = dspy.utils.DummyLM([{"plan": "Ứng viên thừa nhận chưa biết.", "reasoning": "Ứng viên thừa nhận chưa biết.", "assessment": assessment.model_dump(mode="json")}])
    lm.adapter = dspy.JSONAdapter()
    judge = ReflectiveJudgeModule()
    with dspy.context(lm=lm, adapter=dspy.JSONAdapter()):
        result = judge(context=inability_ex.context)
    assert len(lm.history) == 1
    assert result.judgment.feedback == "Cảm ơn bạn đã chia sẻ."
    assert not result.judgment.feedback_contains_hint


def test_compile_all_save_load_and_provider_wiring(tmp_path):
    q_mod, j_mod, a_mod, b_mod = compiler.compile_all_modules(strategy="labeled", use_extended=True)
    assert len(a_mod.demos) == 4 and len(b_mod.demos) == 2
    compiler.save_all_compiled_modules(q_mod, j_mod, a_mod, b_mod, tmp_path)

    provider = DSPyAssessmentProvider(lm=dspy.utils.DummyLM([]), compiled_dir=str(tmp_path))
    assert len(provider.alignment_module.demos) == 4
    assert len(provider.blueprint_module.demos) == 2
    assert len(provider.question_module.followup.predict.demos) == 3

    (tmp_path / "alignment_reviewer.json").write_text("{}", encoding="utf-8")
    with pytest.raises(ValueError, match="checksum mismatch"):
        compiler.load_all_compiled_modules(tmp_path)


def test_reflective_judge_normalizes_quotes_ellipsis_and_inability_gaps():
    from adaptive_questioning.evidence.dspy_modules import EvidenceAssessment, ReflectiveJudgeModule
    from adaptive_questioning.evidence.models import Observation

    answer_text = "Em gắn thêm một số ngẫu nhiên từ 0 đến K-1 vào khóa nóng, đồng thời nhân bản bảng nhỏ."
    turn_ctx = json.dumps({"turn": {"answer": answer_text}}, ensure_ascii=False)
    assessment = EvidenceAssessment(
        observations=[Observation(
            criterion_id="c1",
            response_excerpt='"Em gắn thêm một số ngẫu nhiên ... nhân bản bảng nhỏ."',
            observation="SUPPORTS",
            performance="AT_TARGET",
            rationale="Đúng trọng tâm.",
            unresolved_aspects=["dư"],
        )],
    )
    normalized = ReflectiveJudgeModule._normalize_assessment(turn_ctx, assessment)
    assert normalized.observations[0].response_excerpt == "Em gắn thêm một số ngẫu nhiên"
    assert normalized.observations[0].unresolved_aspects == []

    code_ctx = json.dumps({"turn": {"answer": "line1\nline2"}}, ensure_ascii=False)
    line_obs = EvidenceAssessment(
        observations=[Observation(
            criterion_id="c1",
            response_excerpt="line1",
            response_line_range=(1, 2),
            observation="SUPPORTS",
            performance="AT_TARGET",
            rationale="Đúng.",
        )],
    )
    assert ReflectiveJudgeModule._normalize_assessment(code_ctx, line_obs).observations[0].response_excerpt == ""

    inability = EvidenceAssessment(
        observations=[Observation(
            criterion_id="c1",
            observation="NO_EVIDENCE",
            performance="UNDETERMINED",
            rationale="Chưa nhớ.",
            unresolved_aspects=["Phần chưa nhớ"],
        )],
        explicit_inability=True,
        inability_excerpt='"Em không nhớ rõ phép join này"',
    )
    inability_ctx = json.dumps({"turn": {"answer": "Em không nhớ rõ phép join này"}}, ensure_ascii=False)
    cleaned = ReflectiveJudgeModule._normalize_assessment(inability_ctx, inability)
    assert cleaned.inability_excerpt == "Em không nhớ rõ phép join này"
    assert cleaned.observations[0].unresolved_aspects == []

    fabricated = EvidenceAssessment(
        observations=[Observation(
            criterion_id="c1",
            response_excerpt="câu bịa đặt hoàn toàn",
            observation="SUPPORTS",
            performance="AT_TARGET",
            rationale="Bịa.",
        )],
    )
    assert ReflectiveJudgeModule._normalize_assessment(turn_ctx, fabricated).observations[0].response_excerpt == "câu bịa đặt hoàn toàn"


def test_eval_retries_only_transient_transport_errors(monkeypatch):
    monkeypatch.setattr(compiler.time, "sleep", lambda _: None)
    attempts = {"transient": 0, "deterministic": 0}

    def flaky():
        attempts["transient"] += 1
        if attempts["transient"] < 2:
            raise ConnectionError("WinError 10054")
        return "ok"

    def invalid():
        attempts["deterministic"] += 1
        raise ValueError("bad payload")

    assert compiler._retry_transient(flaky) == "ok"
    assert attempts["transient"] == 2
    with pytest.raises(ValueError, match="bad payload"):
        compiler._retry_transient(invalid)
    assert attempts["deterministic"] == 1



