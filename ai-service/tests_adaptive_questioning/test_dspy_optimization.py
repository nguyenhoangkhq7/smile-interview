"""
Unit tests for DSPy Teleprompter Optimization, Metrics, and Compiled Module Seeding.
Verifies compliance with Khattab et al. (2023) declarative programming and few-shot compilation.
"""

from pathlib import Path
import tempfile
import dspy
import pytest

from adaptive_questioning.core.engine import (
    DSPyQuestionGeneratorModule,
    DSPyReflectiveJudgeModule,
    OpenAILLMEngine,
)
from adaptive_questioning.optimization.compiler import (
    compile_with_labeled_few_shot,
    save_compiled_modules,
    seed_default_compiled_artifacts,
)
from adaptive_questioning.optimization.dataset import (
    get_gold_judge_examples,
    get_gold_question_examples,
)
from adaptive_questioning.optimization.metrics import (
    judge_evaluation_metric,
    question_generation_metric,
)
from adaptive_questioning.schemas.state import MetamorphicTag


class TestDSPyOptimization:
    """Test suite for DSPy Dataset, Metrics, and Compilation."""

    def test_gold_dataset_integrity(self):
        q_examples = get_gold_question_examples()
        assert len(q_examples) >= 3
        for ex in q_examples:
            assert isinstance(ex, dspy.Example)
            assert "reference_layer_context" in ex
            assert "main_layer_directives" in ex
            assert ex.question.endswith("?")

        j_examples = get_gold_judge_examples()
        assert len(j_examples) >= 3
        for ex in j_examples:
            assert isinstance(ex, dspy.Example)
            assert "reference_layer_rubric" in ex
            assert "candidate_response" in ex
            assert len(ex.raw_posterior_probs) == 3

    def test_question_generation_metric(self):
        gold = dspy.Example(
            question="Anh/chị giải quyết sự cố này như thế nào?",
            surprising_fact_C="Discrepancy observed in CV",
            hypothesis_A="Underlying lack of experience",
            target_slot_id="java_spring:primary",
        )
        pred_good = dspy.Prediction(
            question="Trong dự án thực tế, anh/chị đã xử lý vấn đề transaction rollback như thế nào?",
            surprising_fact_C="CV ghi CRUD cơ bản nhưng JD yêu cầu chuyên sâu",
            hypothesis_A="Ứng viên chưa nắm vững Transaction Propagation",
            target_slot_id="java_spring:primary",
        )
        score_good = question_generation_metric(gold, pred_good)
        assert score_good == 1.0

        pred_bad = dspy.Prediction(
            question="Bạn biết gì về Java???",  # Multiple question marks, too short
            surprising_fact_C="",
            hypothesis_A="",
            target_slot_id="invalid_slot",
        )
        score_bad = question_generation_metric(gold, pred_bad)
        assert score_bad == 0.0

    def test_judge_evaluation_metric(self):
        gold = dspy.Example(
            metamorphic_tag=MetamorphicTag.DECISIVE_SHIFT,
            raw_posterior_probs=[0.85, 0.10, 0.05],
            reflective_insight="Ứng viên thừa nhận rõ ràng thiếu kinh nghiệm trong production.",
        )
        pred_good = dspy.Prediction(
            metamorphic_tag=MetamorphicTag.DECISIVE_SHIFT,
            raw_posterior_probs=[0.80, 0.15, 0.05],
            reflective_insight="Ứng viên thừa nhận chưa từng làm việc với production transactions.",
        )
        score_good = judge_evaluation_metric(gold, pred_good)
        assert score_good == 1.0

        pred_wrong_tag = dspy.Prediction(
            metamorphic_tag=MetamorphicTag.INVARIANT,
            raw_posterior_probs=[0.33, 0.33, 0.34],
            reflective_insight="Đánh giá không khớp.",
        )
        score_wrong = judge_evaluation_metric(gold, pred_wrong_tag)
        assert score_wrong < 0.50

    def test_labeled_few_shot_compilation(self):
        comp_q, comp_j = compile_with_labeled_few_shot(k_question=2, k_judge=2)
        assert isinstance(comp_q, DSPyQuestionGeneratorModule)
        assert isinstance(comp_j, DSPyReflectiveJudgeModule)

        q_state = comp_q.dump_state()
        assert len(q_state["generate.predict"].get("demos", [])) == 2

        j_state = comp_j.dump_state()
        assert len(j_state["evaluate.predict"].get("demos", [])) == 2

    def test_compiled_modules_save_and_load(self):
        comp_q, comp_j = compile_with_labeled_few_shot(k_question=2, k_judge=2)
        with tempfile.TemporaryDirectory() as tmp_dir:
            q_path, j_path = save_compiled_modules(comp_q, comp_j, target_dir=tmp_dir)
            assert q_path.exists()
            assert j_path.exists()

            loaded_q = DSPyQuestionGeneratorModule()
            loaded_q.load(str(q_path))
            assert len(loaded_q.dump_state()["generate.predict"].get("demos", [])) == 2

            loaded_j = DSPyReflectiveJudgeModule()
            loaded_j.load(str(j_path))
            assert len(loaded_j.dump_state()["evaluate.predict"].get("demos", [])) == 2

    def test_openai_engine_auto_detects_compiled_artifacts(self, tmp_path):
        # When default artifacts are seeded, OpenAILLMEngine automatically loads them
        seed_default_compiled_artifacts(target_dir=tmp_path)
        engine = OpenAILLMEngine(api_key="test_fake_key", compiled_dir=tmp_path)
        assert engine.is_compiled is True

    def test_expanded_gold_dataset_splits_and_tags(self):
        train_q = get_gold_question_examples(split="train")
        dev_q = get_gold_question_examples(split="dev")
        all_q = get_gold_question_examples(split="all")

        assert len(train_q) == 14
        assert len(dev_q) == 6
        assert len(all_q) == 20

        # Check that k=2 sub-slot probing exists in the dataset
        sub_slot_examples = [ex for ex in all_q if getattr(ex, "new_sub_slot", None) is not None]
        assert len(sub_slot_examples) >= 4

        train_j = get_gold_judge_examples(split="train")
        dev_j = get_gold_judge_examples(split="dev")
        all_j = get_gold_judge_examples(split="all")

        assert len(train_j) == 14
        assert len(dev_j) == 6
        assert len(all_j) == 20

        # Verify all 4 Metamorphic tags are covered
        tags = {ex.metamorphic_tag for ex in all_j}
        assert MetamorphicTag.INVARIANT in tags
        assert MetamorphicTag.MINOR_SHIFT in tags
        assert MetamorphicTag.MODERATE_SHIFT in tags
        assert MetamorphicTag.DECISIVE_SHIFT in tags

        # Check probability simplex sum for all judge examples
        for ex in all_j:
            assert abs(sum(ex.raw_posterior_probs) - 1.0) < 1e-4

    def test_off_topic_penalty_and_single_intent_metric(self):
        gold = get_gold_question_examples()[0]

        # Valid on-topic question
        pred_valid = dspy.Prediction(
            question="Trong Spring Boot, khi cấu hình rollback cho transaction, anh/chị xử lý propagation thế nào?",
            surprising_fact_C="CV ghi CRUD cơ bản nhưng JD yêu cầu chuyên sâu",
            hypothesis_A="Ứng viên chưa nắm vững Transaction Propagation",
            target_slot_id="java_spring:primary",
        )
        score_valid = question_generation_metric(gold, pred_valid)
        assert score_valid >= 0.85

        # Off-topic question (culinary / daily life)
        pred_off_topic = dspy.Prediction(
            question="Anh/chị thích ăn phở bò tái lăn hay phở gà vào buổi sáng hơn?",
            surprising_fact_C="Ứng viên có nhiều sở thích ẩm thực",
            hypothesis_A="Ứng viên thích đồ ăn truyền thống",
            target_slot_id="java_spring:primary",
        )
        score_off_topic = question_generation_metric(gold, pred_off_topic)
        # Off-topic receives ZERO semantic score (score <= 0.40), strictly failing the 0.75 threshold
        assert score_off_topic <= 0.40

        # Compound question with multiple markers
        pred_compound = dspy.Prediction(
            question="Anh/chị xử lý rollback thế nào, đồng thời giải thích cơ chế propagation trong Spring?",
            surprising_fact_C="CV ghi CRUD cơ bản nhưng JD yêu cầu chuyên sâu",
            hypothesis_A="Ứng viên chưa nắm vững Transaction Propagation",
            target_slot_id="java_spring:primary",
        )
        score_compound = question_generation_metric(gold, pred_compound)
        # Loses single-intent points
        assert score_compound < score_valid

