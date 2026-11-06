"""
DSPy Teleprompter and Pipeline Optimization for Adaptive Questioning (Phase 4 / NCKH).
"""

from adaptive_questioning.optimization.compiler import (
    DEFAULT_COMPILED_DIR,
    compile_with_bootstrap_few_shot,
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

__all__ = [
    "DEFAULT_COMPILED_DIR",
    "compile_with_bootstrap_few_shot",
    "compile_with_labeled_few_shot",
    "get_gold_judge_examples",
    "get_gold_question_examples",
    "judge_evaluation_metric",
    "question_generation_metric",
    "save_compiled_modules",
    "seed_default_compiled_artifacts",
]
