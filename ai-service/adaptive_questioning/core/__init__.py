"""
Core module for Adaptive Questioning Pipeline V2.2.
"""

from adaptive_questioning.core.engine import (
    BaseLLMEngine,
    DSPyQuestionGeneratorModule,
    DSPyReflectiveJudgeModule,
    MockLLMEngine,
    OpenAILLMEngine,
)
from adaptive_questioning.core.math_utils import (
    compute_interpolation_alpha,
    expected_proficiency,
    map_rubric_level,
    normalize_simplex,
    simplex_convex_update,
    simplex_convex_update_detailed,
    temperature_softmax_prior,
    tv_distance,
    verified_skill_gap,
)
from adaptive_questioning.core.prompts import (
    Step2AAbductiveQuestionSignature,
    Step2BReflectivePBAJudgeSignature,
    build_step2a_layers,
    build_step2a_question_prompt,
    build_step2b_judge_prompt,
    build_step2b_layers,
    format_context_anchors,
    format_recent_dialogue,
)
from adaptive_questioning.core.router import (
    check_global_termination,
    check_local_skill_completion,
    compute_completion_rate,
    consolidate_and_garbage_collect,
    generate_hitl_report,
    initialize_session_state,
)

__all__ = [
    "BaseLLMEngine",
    "DSPyQuestionGeneratorModule",
    "DSPyReflectiveJudgeModule",
    "MockLLMEngine",
    "OpenAILLMEngine",
    "compute_interpolation_alpha",
    "expected_proficiency",
    "map_rubric_level",
    "normalize_simplex",
    "simplex_convex_update",
    "simplex_convex_update_detailed",
    "temperature_softmax_prior",
    "tv_distance",
    "verified_skill_gap",
    "Step2AAbductiveQuestionSignature",
    "Step2BReflectivePBAJudgeSignature",
    "build_step2a_layers",
    "build_step2a_question_prompt",
    "build_step2b_judge_prompt",
    "build_step2b_layers",
    "format_context_anchors",
    "format_recent_dialogue",
    "check_global_termination",
    "check_local_skill_completion",
    "compute_completion_rate",
    "consolidate_and_garbage_collect",
    "generate_hitl_report",
    "initialize_session_state",
]
