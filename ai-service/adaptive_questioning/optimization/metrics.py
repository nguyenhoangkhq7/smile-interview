"""
Evaluation Metrics for DSPy Teleprompter Optimization (Phase 4 / NCKH).
Computes quantitative alignment scores for Step 2A (Question Generator)
and Step 2B (Reflective PBA Judge).

Includes both:
  1. Structural format checks (Fast, offline deterministic).
  2. Semantic LLM-as-a-Judge evaluation (Topic Drift prevention, Single-Intent discipline,
     and Technical Concreteness) activated whenever an active `dspy.LM` is present.
"""

import os
from typing import Any, Optional
import dspy
import numpy as np

from adaptive_questioning.schemas.state import MetamorphicTag

# ---------------------------------------------------------------------------
# Dedicated Judge 1 LM Registry (Model-Agnostic Independent Evaluator)
# ---------------------------------------------------------------------------

_CONFIGURED_JUDGE_LM: Optional[dspy.LM] = None


def set_judge_lm(lm: Optional[dspy.LM]) -> None:
    """Explicitly register an independent LLM instance to serve as Judge 1."""
    global _CONFIGURED_JUDGE_LM
    _CONFIGURED_JUDGE_LM = lm


def get_judge_lm() -> Optional[dspy.LM]:
    """
    Retrieve the configured Judge 1 LLM.
    Priority:
      1. Explicitly set via `set_judge_lm(...)`.
      2. Environment variable `AQ_JUDGE_MODEL` or `JUDGE_MODEL`.
      3. Fallback to None (which allows falling back to `dspy.settings.lm` or heuristic).
    """
    global _CONFIGURED_JUDGE_LM
    if _CONFIGURED_JUDGE_LM is not None:
        return _CONFIGURED_JUDGE_LM

    judge_model = os.getenv("AQ_JUDGE_MODEL") or os.getenv("JUDGE_MODEL")
    if judge_model:
        api_key = (
            os.getenv("AQ_JUDGE_API_KEY")
            or os.getenv("JUDGE_API_KEY")
            or os.getenv("OPENROUTER_API_KEY")
            or os.getenv("OPENAI_API_KEY")
        )
        base_url = (
            os.getenv("AQ_JUDGE_BASE_URL")
            or os.getenv("JUDGE_BASE_URL")
            or ("https://openrouter.ai/api/v1" if os.getenv("OPENROUTER_API_KEY") else None)
        )
        try:
            is_openrouter = base_url and ("openrouter.ai" in base_url)
            if is_openrouter:
                dspy_model_name = (
                    judge_model
                    if judge_model.startswith("openrouter/")
                    else f"openrouter/{judge_model}"
                )
            else:
                dspy_model_name = (
                    judge_model if "/" in judge_model else f"openai/{judge_model}"
                )
            _CONFIGURED_JUDGE_LM = dspy.LM(
                dspy_model_name,
                api_key=api_key,
                api_base=base_url,
                temperature=0.0,
            )
            return _CONFIGURED_JUDGE_LM
        except Exception:
            pass

    return None



# ---------------------------------------------------------------------------
# Declarative Semantic Judge Signature for Step 2A (Relevance Theory & Zero Topic Drift)
# ---------------------------------------------------------------------------

class QuestionSemanticJudgeSignature(dspy.Signature):
    """
    Evaluate the semantic quality of an adaptive technical interview question:
    1. is_on_topic: Does the question strictly focus on probing the target technical skill without topic drift?
       (Must NOT ask about unrelated everyday life, hobbies, culinary topics, or unrelated technologies).
    2. is_single_intent: Does the question maintain One-Question-One-Answer discipline?
       (Must NOT compound multiple independent questions using phrases like 'đồng thời', 'và giải thích', 'sau đó làm gì').
    3. is_concrete_technical: Does the question ask for concrete technical experience/trade-offs rather than generic definitions?
    """

    target_skill_context: str = dspy.InputField(
        desc="Target skill ID, required proficiency s_jd, CV evidence, and context job being investigated"
    )
    question: str = dspy.InputField(
        desc="The candidate question generated for the technical interview"
    )

    is_on_topic: bool = dspy.OutputField(
        desc="True if the question directly investigates the target skill without topic drift; False if off-topic"
    )
    is_single_intent: bool = dspy.OutputField(
        desc="True if asking exactly one cohesive technical problem/decision; False if bundled with multiple separate questions"
    )
    is_concrete_technical: bool = dspy.OutputField(
        desc="True if asking for real incident handling, trade-offs, or implementation specifics; False if a trivial textbook definition"
    )
    judge_rationale: str = dspy.OutputField(
        desc="Short 1-sentence justification of the semantic evaluation"
    )


def evaluate_question_semantics(
    context_text: str,
    question_text: str,
    lm: Optional[dspy.LM] = None,
) -> dict:
    """
    Run semantic evaluation of the question via LLM-as-a-Judge when an LM is available.
    Falls back to robust heuristic checks in offline/test environments.
    """
    active_lm = lm or get_judge_lm() or getattr(dspy.settings, "lm", None)
    if active_lm is not None:
        try:
            with dspy.context(lm=active_lm):
                evaluator = dspy.Predict(QuestionSemanticJudgeSignature)
                pred = evaluator(
                    target_skill_context=context_text,
                    question=question_text,
                )
                on_topic = bool(getattr(pred, "is_on_topic", True))
                single_intent = bool(getattr(pred, "is_single_intent", True))
                concrete = bool(getattr(pred, "is_concrete_technical", True))
                return {
                    "is_on_topic": on_topic,
                    "is_single_intent": single_intent,
                    "is_concrete_technical": concrete,
                    "mode": "llm_judge",
                }
        except Exception:
            pass  # Fall back to heuristic checks if LLM evaluation fails

    # Offline Heuristic Fallback
    q_lower = question_text.lower()
    # Check for obvious off-topic everyday non-technical terms
    everyday_noise = [
        "nấu ăn", "món ăn", "phở", "bún bò", "ẩm thực", "thời tiết",
        "sở thích", "du lịch", "ca nhạc", "phim ảnh", "thể thao", "bóng đá"
    ]
    is_off_topic_heuristic = any(word in q_lower for word in everyday_noise)
    on_topic = not is_off_topic_heuristic

    # Check for obvious compound conjunctions in Vietnamese (avoiding false positive on "tác vụ đồng thời")
    compound_markers = [
        ", đồng thời", "; đồng thời", "đồng thời hãy", "đồng thời cho biết", "đồng thời giải thích",
        "và cho biết", "sau đó làm gì", "và giải thích", "cũng như cho biết"
    ]
    has_compound = any(marker in q_lower for marker in compound_markers)
    single_intent = not has_compound

    # Check for generic/empty phrasing
    is_concrete = len(question_text.split()) >= 8

    return {
        "is_on_topic": on_topic,
        "is_single_intent": single_intent,
        "is_concrete_technical": is_concrete,
        "mode": "heuristic",
    }


def question_generation_metric(
    gold: Any,
    pred: Any,
    trace: Optional[Any] = None,
    lm: Optional[dspy.LM] = None,
) -> float:
    """
    Score Step 2A Question Generation quality (0.0 to 1.0):
      Structural Gate & Formatting (0.40):
        +0.20: Concrete question (>= 15 chars) ending with '?' and containing exactly one '?'
        +0.10: Valid Abductive CoT (both Surprising Fact C and Hypothesis A present, >= 10 chars)
        +0.10: Target Slot ID matching gold (or format check) & no sub-slot at k = 1

      Semantic Layer (0.60):
        +0.30: Zero Topic Drift (`is_on_topic` == True). CRITICAL: If off-topic, semantic score = 0.0!
        +0.15: Single-Intent discipline (`is_single_intent` == True)
        +0.15: Concrete technical depth (`is_concrete_technical` == True)
    """
    q_text = str(getattr(pred, "question", "") or "").strip()
    # Basic gating: Malformed questions (too short or multiple '?') receive 0.0 immediately
    if len(q_text) < 15 or not q_text.endswith("?") or q_text.count("?") != 1:
        return 0.0

    c_fact = getattr(pred, "surprising_fact_C", "") or ""
    h_hyp = getattr(pred, "hypothesis_A", "") or ""
    has_cot = len(str(c_fact).strip()) >= 10 and len(str(h_hyp).strip()) >= 10

    slot_id = str(getattr(pred, "target_slot_id", "") or "").strip().strip("'\"`")
    gold_slot = str(getattr(gold, "target_slot_id", "") or "").strip()
    slot_ok = (slot_id == gold_slot) if gold_slot else (":" in slot_id)
    if slot_ok and slot_id.endswith(":primary"):
        slot_ok = getattr(pred, "new_sub_slot", None) in (None, "", "null", "None")

    # If both CoT and target slot are invalid, the prediction is completely broken
    if not has_cot and not slot_ok:
        return 0.0

    struct_score = 0.20
    if has_cot:
        struct_score += 0.10
    if slot_ok:
        struct_score += 0.10

    # Semantic Evaluation Layer
    context_desc = str(getattr(gold, "reference_layer_context", "") or getattr(pred, "reference_layer_context", ""))
    sem_eval = evaluate_question_semantics(context_desc, q_text, lm=lm)

    if not sem_eval["is_on_topic"]:
        # ZERO TOPIC DRIFT PENALTY: Off-topic questions receive 0 semantic credit
        semantic_score = 0.0
    else:
        semantic_score = 0.30
        if sem_eval["is_single_intent"]:
            semantic_score += 0.15
        if sem_eval["is_concrete_technical"]:
            semantic_score += 0.15

    return float(round(struct_score + semantic_score, 4))


def judge_evaluation_metric(
    gold: Any,
    pred: Any,
    trace: Optional[Any] = None,
) -> float:
    """
    Score Step 2B Reflective PBA Judge quality (0.0 to 1.0):
      +0.40: Exact match on Metamorphic Tag classification
      +0.25: Mathematical consistency of raw_posterior_probs (simplex sum ~ 1.0, len = 3)
      +0.20: Directional alignment (MAP level matches gold MAP level)
      +0.15: Reflective insight substance (>= 15 characters, non-trivial)
    """
    score = 0.0

    # 1. Metamorphic Tag Matching
    gold_tag = getattr(gold, "metamorphic_tag", None)
    pred_tag = getattr(pred, "metamorphic_tag", None)

    gold_val = gold_tag.value if isinstance(gold_tag, MetamorphicTag) else str(gold_tag or "")
    pred_val = pred_tag.value if isinstance(pred_tag, MetamorphicTag) else str(pred_tag or "")
    # Tolerate LLM outputs such as "MetamorphicTag.DECISIVE_SHIFT"
    gold_val = gold_val.strip().split(".")[-1]
    pred_val = pred_val.strip().split(".")[-1]

    if gold_val and pred_val and gold_val == pred_val:
        score += 0.40

    # 2. Probability Simplex Integrity
    raw_probs = getattr(pred, "raw_posterior_probs", None)
    if isinstance(raw_probs, (list, tuple)) and len(raw_probs) == 3:
        try:
            arr = [float(x) for x in raw_probs]
            if all(x >= 0.0 for x in arr) and abs(sum(arr) - 1.0) < 0.05:
                score += 0.25

                # 3. Directional Alignment with Gold
                gold_probs = getattr(gold, "raw_posterior_probs", None)
                if isinstance(gold_probs, (list, tuple)) and len(gold_probs) == 3:
                    if int(np.argmax(arr)) == int(np.argmax(gold_probs)):
                        score += 0.20
        except (ValueError, TypeError):
            pass

    # 4. Reflective Insight Substance
    insight = getattr(pred, "reflective_insight", "") or ""
    if len(str(insight).strip()) >= 15:
        score += 0.15

    return float(score)

