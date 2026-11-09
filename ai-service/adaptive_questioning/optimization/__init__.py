"""Recovered DSPy tools; lazy exports also support running the compiler as a module."""
from importlib import import_module

_EXPORTS = {
    **{name: "compiler" for name in (
        "DEFAULT_COMPILED_DIR", "compile_with_bootstrap_few_shot", "compile_with_labeled_few_shot",
        "evaluate_modules_on_dev", "load_compiled_modules", "save_compiled_modules", "seed_default_compiled_artifacts")},
    **{name: "dataset" for name in ("get_gold_judge_examples", "get_gold_question_examples")},
    **{name: "metrics" for name in ("judge_evaluation_metric", "question_generation_metric")},
}
__all__ = list(_EXPORTS)


def __getattr__(name):
    if name not in _EXPORTS:
        raise AttributeError(name)
    return getattr(import_module(f"{__name__}.{_EXPORTS[name]}"), name)
