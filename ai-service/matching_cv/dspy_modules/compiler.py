"""Compile and evaluate explicit skill extraction modules."""

import argparse
from pathlib import Path
from typing import Optional

import dspy

from matching_cv.dspy_modules.dataset import get_train_val_split
from matching_cv.dspy_modules.metrics import explicit_skill_metric
from matching_cv.dspy_modules.modules import DSPyExplicitSkillExtractorModule


DEFAULT_COMPILED_PATH = Path(__file__).resolve().parent / "compiled_modules" / "explicit_skill_extractor.json"


def evaluate(module: DSPyExplicitSkillExtractorModule, examples: list[dspy.Example]) -> float:
    """Return mean precision-weighted extraction score for a labeled split."""
    if not examples:
        return 1.0
    scores = [explicit_skill_metric(example, module(**example.inputs())) for example in examples]
    return sum(scores) / len(scores)


def compile_labeled_few_shot(k: int = 6) -> DSPyExplicitSkillExtractorModule:
    """Compile a reproducible starter module from human-authored examples."""
    trainset, _ = get_train_val_split()
    module = DSPyExplicitSkillExtractorModule()
    return dspy.LabeledFewShot(k=min(k, len(trainset))).compile(module, trainset=trainset)


def compile_bootstrap(
    lm: dspy.LM,
    max_bootstrapped_demos: int = 4,
    max_labeled_demos: int = 8,
    metric_threshold: float = 0.8,
) -> DSPyExplicitSkillExtractorModule:
    """Optimize demonstrations from gold training data using the extraction metric."""
    trainset, _ = get_train_val_split()
    with dspy.context(lm=lm):
        return dspy.BootstrapFewShot(
            metric=explicit_skill_metric,
            metric_threshold=metric_threshold,
            max_bootstrapped_demos=max_bootstrapped_demos,
            max_labeled_demos=max_labeled_demos,
        ).compile(DSPyExplicitSkillExtractorModule(), trainset=trainset)


def save_compiled(module: DSPyExplicitSkillExtractorModule, path: Optional[Path] = None) -> Path:
    target = path or DEFAULT_COMPILED_PATH
    target.parent.mkdir(parents=True, exist_ok=True)
    module.save(str(target))
    return target


def _configured_lm() -> Optional[dspy.LM]:
    from matching_cv.app.core.config import settings

    api_key = settings.OPENROUTER_API_KEY
    if not api_key:
        return None
    model_name = settings.OPENROUTER_MODEL
    model = model_name if model_name.startswith("openrouter/") else f"openrouter/{model_name}"
    return dspy.LM(
        model,
        api_key=api_key,
        api_base=settings.OPENROUTER_BASE_URL,
        temperature=0.0,
        cache=False,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Compile the explicit skill extraction DSPy module.")
    parser.add_argument("--output", type=Path, default=DEFAULT_COMPILED_PATH)
    parser.add_argument("--k", type=int, default=6)
    parser.add_argument(
        "--evaluate",
        action="store_true",
        help="Run live holdout inference against OpenRouter after compiling.",
    )
    args = parser.parse_args()
    module = compile_labeled_few_shot(args.k)
    path = save_compiled(module, args.output)
    if args.evaluate:
        lm = _configured_lm()
        if lm is None:
            raise SystemExit("OPENROUTER_API_KEY is required for live holdout evaluation.")
        _, validation = get_train_val_split()
        with dspy.context(lm=lm):
            score = evaluate(module, validation)
        print(f"Saved {path}; validation F0.5={score:.3f}")
        return
    print(f"Saved {path}; live evaluation not requested.")


if __name__ == "__main__":
    main()
