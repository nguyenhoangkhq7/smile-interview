"""Compare the legacy explicit prompt with DSPy on the labeled holdout split."""

import asyncio
from typing import Any

import dspy

from matching_cv.app.core.config import settings
from matching_cv.app.services.llm_service import LLMService
from matching_cv.app.services.prompt_templates import EXPLICIT_SKILL_SYSTEM_PROMPT
from matching_cv.app.services.dspy_explicit_skill_service import dspy_explicit_skill_service
from matching_cv.dspy_modules.dataset import get_train_val_split
from matching_cv.dspy_modules.metrics import explicit_skill_metric


def _prediction(raw_result: dict[str, Any]) -> dspy.Prediction:
    candidates = raw_result.get("explicit_skills") or raw_result.get("skills") or []
    return dspy.Prediction(explicit_skills=candidates)


async def compare_holdout() -> tuple[float, float]:
    """Run each holdout document through both extractors and return mean F0.5 scores."""
    _, validation = get_train_val_split()
    legacy_scores = []
    dspy_scores = []
    llm_service = LLMService()
    for example in validation:
        legacy = await llm_service.extract_explicit_skills(
            text=example.document_text,
            document_type=example.document_type,
            system_prompt=EXPLICIT_SKILL_SYSTEM_PROMPT,
            prompt_variant="legacy_default",
        )
        optimized = await dspy_explicit_skill_service.extract(
            text=example.document_text,
            document_type=example.document_type,
        )
        legacy_scores.append(explicit_skill_metric(example, _prediction(legacy)))
        dspy_scores.append(explicit_skill_metric(example, _prediction(optimized)))
    return sum(legacy_scores) / len(legacy_scores), sum(dspy_scores) / len(dspy_scores)


def main() -> None:
    if not settings.OPENROUTER_API_KEY:
        raise SystemExit("OPENROUTER_API_KEY is required to run the live holdout comparison.")
    legacy_score, dspy_score = asyncio.run(compare_holdout())
    print(f"Legacy prompt holdout F0.5: {legacy_score:.3f}")
    print(f"DSPy extractor holdout F0.5: {dspy_score:.3f}")
    print(f"Delta: {dspy_score - legacy_score:+.3f}")


if __name__ == "__main__":
    main()
