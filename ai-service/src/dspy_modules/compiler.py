"""
Compiler and Teleprompter utilities for Module 2 (skill_gap) DSPy Modules.
Supports both deterministic offline LabeledFewShot seeding (with full Chain-of-Thought reasoning)
and online BootstrapFewShot optimization with train/validation evaluation.
"""

import argparse
from pathlib import Path
from typing import Any, Dict, Optional, Tuple, Union
import dspy

from src.dspy_modules.modules import (
    DSPyJobBlockExtractorModule,
    DSPySpanMapperModule,
    DSPyJDRequirementParserModule,
    DSPySpanRichnessAnalyzerModule,
)
from src.dspy_modules.dataset import (
    get_gold_job_extraction_examples,
    get_gold_span_mapping_examples,
    get_gold_jd_requirement_examples,
    get_gold_span_richness_examples,
    get_dspy_trainset_and_valset,
)
from src.dspy_modules.metrics import (
    job_extraction_metric,
    span_mapping_metric,
    jd_requirement_metric,
    span_richness_metric,
    evaluate_dspy_dataset,
)

DEFAULT_COMPILED_DIR = Path(__file__).resolve().parent.parent.parent / "compiled_modules"


def compile_with_labeled_few_shot(
    k: int = 4,
) -> Tuple[
    DSPyJobBlockExtractorModule,
    DSPySpanMapperModule,
    DSPyJDRequirementParserModule,
    DSPySpanRichnessAnalyzerModule,
]:
    """
    Fast, deterministic offline compilation via `dspy.LabeledFewShot`.
    Seeds all 4 DSPy modules with up to `k` diverse gold Chain-of-Thought demonstrations
    without requiring live LLM calls.
    """
    job_mod = DSPyJobBlockExtractorModule()
    job_ex = get_gold_job_extraction_examples()
    compiled_job = dspy.LabeledFewShot(k=min(k, len(job_ex))).compile(job_mod, trainset=job_ex)

    map_mod = DSPySpanMapperModule()
    map_ex = get_gold_span_mapping_examples()
    compiled_map = dspy.LabeledFewShot(k=min(k, len(map_ex))).compile(map_mod, trainset=map_ex)

    jd_mod = DSPyJDRequirementParserModule()
    jd_ex = get_gold_jd_requirement_examples()
    compiled_jd = dspy.LabeledFewShot(k=min(k, len(jd_ex))).compile(jd_mod, trainset=jd_ex)

    rich_mod = DSPySpanRichnessAnalyzerModule()
    rich_ex = get_gold_span_richness_examples()
    compiled_rich = dspy.LabeledFewShot(k=min(k, len(rich_ex))).compile(rich_mod, trainset=rich_ex)

    return compiled_job, compiled_map, compiled_jd, compiled_rich


def compile_with_bootstrap_few_shot(
    lm: dspy.LM,
    max_bootstrapped_demos: int = 3,
    max_labeled_demos: int = 4,
    metric_threshold: float = 0.85,
) -> Tuple[
    DSPyJobBlockExtractorModule,
    DSPySpanMapperModule,
    DSPyJDRequirementParserModule,
    DSPySpanRichnessAnalyzerModule,
]:
    """
    Full scientific optimization via `dspy.BootstrapFewShot` (Khattab et al., 2023).
    Filters teacher traces strictly through the 4 multi-component domain metrics.
    """
    splits = get_dspy_trainset_and_valset(train_ratio=0.8)

    with dspy.context(lm=lm):
        compiled_job = dspy.BootstrapFewShot(
            metric=job_extraction_metric,
            metric_threshold=metric_threshold,
            max_bootstrapped_demos=max_bootstrapped_demos,
            max_labeled_demos=max_labeled_demos,
        ).compile(DSPyJobBlockExtractorModule(), trainset=splits["job_extractor"][0])

        compiled_map = dspy.BootstrapFewShot(
            metric=span_mapping_metric,
            metric_threshold=metric_threshold,
            max_bootstrapped_demos=max_bootstrapped_demos,
            max_labeled_demos=max_labeled_demos,
        ).compile(DSPySpanMapperModule(), trainset=splits["span_mapper"][0])

        compiled_jd = dspy.BootstrapFewShot(
            metric=jd_requirement_metric,
            metric_threshold=metric_threshold,
            max_bootstrapped_demos=max_bootstrapped_demos,
            max_labeled_demos=max_labeled_demos,
        ).compile(DSPyJDRequirementParserModule(), trainset=splits["jd_parser"][0])

        compiled_rich = dspy.BootstrapFewShot(
            metric=span_richness_metric,
            metric_threshold=metric_threshold,
            max_bootstrapped_demos=max_bootstrapped_demos,
            max_labeled_demos=max_labeled_demos,
        ).compile(DSPySpanRichnessAnalyzerModule(), trainset=splits["span_richness"][0])

    return compiled_job, compiled_map, compiled_jd, compiled_rich


def save_compiled_modules(
    compiled_job: DSPyJobBlockExtractorModule,
    compiled_map: DSPySpanMapperModule,
    compiled_jd: DSPyJDRequirementParserModule,
    compiled_rich: DSPySpanRichnessAnalyzerModule,
    target_dir: Optional[Union[str, Path]] = None,
) -> Dict[str, Path]:
    """Save compiled DSPy module artifacts as JSON files in `skill_gap/compiled_modules`."""
    out_dir = Path(target_dir or DEFAULT_COMPILED_DIR)
    out_dir.mkdir(parents=True, exist_ok=True)

    paths = {
        "job_extractor": out_dir / "job_extractor.json",
        "span_mapper": out_dir / "span_mapper.json",
        "jd_parser": out_dir / "jd_parser.json",
        "span_richness": out_dir / "span_richness.json",
    }
    compiled_job.save(str(paths["job_extractor"]))
    compiled_map.save(str(paths["span_mapper"]))
    compiled_jd.save(str(paths["jd_parser"]))
    compiled_rich.save(str(paths["span_richness"]))
    return paths


def seed_default_compiled_artifacts(
    target_dir: Optional[Union[str, Path]] = None,
    k: int = 4,
) -> Dict[str, Path]:
    """Seed default compiled artifacts via LabeledFewShot with `k` gold Chain-of-Thought demos."""
    c_job, c_map, c_jd, c_rich = compile_with_labeled_few_shot(k=k)
    return save_compiled_modules(c_job, c_map, c_jd, c_rich, target_dir=target_dir)


def verify_gold_dataset_self_consistency() -> Dict[str, Dict[str, Any]]:
    """
    Verify that all gold examples in `dataset.py` achieve 1.0000 self-consistency
    under the 4 upgraded multi-component metrics.
    """
    job_ex = get_gold_job_extraction_examples()
    map_ex = get_gold_span_mapping_examples()
    jd_ex = get_gold_jd_requirement_examples()
    rich_ex = get_gold_span_richness_examples()

    return {
        "job_extractor": evaluate_dspy_dataset(
            job_ex,
            lambda ex: dspy.Prediction(job_blocks=ex.job_blocks),
            job_extraction_metric,
        ),
        "span_mapper": evaluate_dspy_dataset(
            map_ex,
            lambda ex: dspy.Prediction(span_mappings=ex.span_mappings),
            span_mapping_metric,
        ),
        "jd_parser": evaluate_dspy_dataset(
            jd_ex,
            lambda ex: dspy.Prediction(requirements=ex.requirements),
            jd_requirement_metric,
        ),
        "span_richness": evaluate_dspy_dataset(
            rich_ex,
            lambda ex: dspy.Prediction(analyses=ex.analyses),
            span_richness_metric,
        ),
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Compile DSPy modules for Module 2 (skill_gap).")
    parser.add_argument(
        "--mode",
        choices=["labeled", "bootstrap"],
        default="labeled",
        help="Compilation mode: 'labeled' (offline deterministic) or 'bootstrap' (online with LLM).",
    )
    parser.add_argument("--k", type=int, default=4, help="Number of few-shot demos per module.")
    args = parser.parse_args()

    if args.mode == "labeled":
        saved = seed_default_compiled_artifacts(k=args.k)
        stats = verify_gold_dataset_self_consistency()
        print("Compiled Module 2 DSPy artifacts via LabeledFewShot:")
        for name, p in saved.items():
            st = stats[name]
            print(f"  - {name}: {p} (gold dataset count={st['count']}, self-consistency={st['mean_score']})")
    else:
        from src.adapters.llm_client import DSPyLLMClient

        client = DSPyLLMClient()
        if client.dspy_lm is None:
            raise RuntimeError("Set OPENROUTER_API_KEY or OPENAI_API_KEY to run bootstrap compilation.")
        c_job, c_map, c_jd, c_rich = compile_with_bootstrap_few_shot(lm=client.dspy_lm)
        saved = save_compiled_modules(c_job, c_map, c_jd, c_rich)
        print("Compiled Module 2 DSPy artifacts via BootstrapFewShot:")
        for name, p in saved.items():
            print(f"  - {name}: {p}")
