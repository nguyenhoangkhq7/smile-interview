"""
Compiler and Teleprompter utilities for Adaptive Questioning DSPy Modules.
Supports both offline LabeledFewShot seeding and online BootstrapFewShot optimization.
"""

import os
from pathlib import Path
from typing import Optional, Union
import dspy

from adaptive_questioning.core.engine import (
    DSPyQuestionGeneratorModule,
    DSPyReflectiveJudgeModule,
)
from adaptive_questioning.optimization.dataset import (
    get_gold_judge_examples,
    get_gold_question_examples,
)
from adaptive_questioning.optimization.metrics import (
    get_judge_lm,
    judge_evaluation_metric,
    question_generation_metric,
    set_judge_lm,
)

DEFAULT_COMPILED_DIR = Path(__file__).resolve().parent.parent / "compiled_modules"


def compile_with_labeled_few_shot(
    k_question: int = 3,
    k_judge: int = 3,
) -> tuple[DSPyQuestionGeneratorModule, DSPyReflectiveJudgeModule]:
    """
    Fast, deterministic offline compilation via `dspy.LabeledFewShot`.
    Seeds modules with gold few-shot demonstrations without requiring LLM calls.
    """
    q_module = DSPyQuestionGeneratorModule()
    q_examples = get_gold_question_examples()
    q_teleprompter = dspy.LabeledFewShot(k=min(k_question, len(q_examples)))
    compiled_q = q_teleprompter.compile(q_module, trainset=q_examples)

    j_module = DSPyReflectiveJudgeModule()
    j_examples = get_gold_judge_examples()
    j_teleprompter = dspy.LabeledFewShot(k=min(k_judge, len(j_examples)))
    compiled_j = j_teleprompter.compile(j_module, trainset=j_examples)

    return compiled_q, compiled_j


def compile_with_bootstrap_few_shot(
    lm: dspy.LM,
    judge_lm: Optional[dspy.LM] = None,
    max_bootstrapped_demos: int = 2,
    max_labeled_demos: int = 2,
    metric_threshold: float = 0.75,
    train_split: str = "train",
) -> tuple[DSPyQuestionGeneratorModule, DSPyReflectiveJudgeModule]:
    """
    Full scientific optimization via `dspy.BootstrapFewShot` (Khattab et al., 2023).
    Supports an independent `judge_lm` (Teacher) evaluating the `lm` (Student).
    Requires an active `dspy.LM` connection.

    NOTE: `metric_threshold` is mandatory for float-valued metrics. Without it, DSPy
    accepts any truthy score (e.g. 0.25) as a "successful" trace and injects it as a demo.
    """
    if judge_lm is not None:
        set_judge_lm(judge_lm)

    with dspy.context(lm=lm):
        q_module = DSPyQuestionGeneratorModule()
        q_teleprompter = dspy.BootstrapFewShot(
            metric=question_generation_metric,
            metric_threshold=metric_threshold,
            max_bootstrapped_demos=max_bootstrapped_demos,
            max_labeled_demos=max_labeled_demos,
        )
        compiled_q = q_teleprompter.compile(
            q_module, trainset=get_gold_question_examples(split=train_split)
        )

        j_module = DSPyReflectiveJudgeModule()
        j_teleprompter = dspy.BootstrapFewShot(
            metric=judge_evaluation_metric,
            metric_threshold=metric_threshold,
            max_bootstrapped_demos=max_bootstrapped_demos,
            max_labeled_demos=max_labeled_demos,
        )
        compiled_j = j_teleprompter.compile(
            j_module, trainset=get_gold_judge_examples(split=train_split)
        )

    return compiled_q, compiled_j


def evaluate_modules_on_dev(
    q_module: DSPyQuestionGeneratorModule,
    j_module: DSPyReflectiveJudgeModule,
    lm: Optional[dspy.LM] = None,
    split: str = "dev",
) -> dict:
    """
    Evaluate compiled modules on held-out devset to quantify optimization quality.
    """
    dev_q = get_gold_question_examples(split=split)
    dev_j = get_gold_judge_examples(split=split)

    active_ctx = dspy.context(lm=lm) if lm is not None else dspy.context()
    q_scores = []
    j_scores = []

    with active_ctx:
        for ex in dev_q:
            try:
                pred = q_module(
                    reference_layer_context=ex.reference_layer_context,
                    main_layer_directives=ex.main_layer_directives,
                )
                score = question_generation_metric(ex, pred, lm=lm)
                q_scores.append(score)
            except Exception:
                q_scores.append(0.0)

        for ex in dev_j:
            try:
                pred = j_module(
                    reference_layer_rubric=ex.reference_layer_rubric,
                    question_and_slot=ex.question_and_slot,
                    candidate_response=ex.candidate_response,
                )
                score = judge_evaluation_metric(ex, pred)
                j_scores.append(score)
            except Exception:
                j_scores.append(0.0)

    avg_q = float(sum(q_scores) / len(q_scores)) if q_scores else 0.0
    avg_j = float(sum(j_scores) / len(j_scores)) if j_scores else 0.0

    return {
        "dev_split": split,
        "question_examples_count": len(dev_q),
        "judge_examples_count": len(dev_j),
        "question_generator_avg_score": round(avg_q, 4),
        "reflective_judge_avg_score": round(avg_j, 4),
    }


def save_compiled_modules(
    compiled_q: DSPyQuestionGeneratorModule,
    compiled_j: DSPyReflectiveJudgeModule,
    target_dir: Optional[Union[str, Path]] = None,
) -> tuple[Path, Path]:
    """Save compiled module artifacts as JSON files."""
    out_dir = Path(target_dir or DEFAULT_COMPILED_DIR)
    out_dir.mkdir(parents=True, exist_ok=True)

    q_path = out_dir / "question_generator.json"
    j_path = out_dir / "reflective_judge.json"

    compiled_q.save(str(q_path))
    compiled_j.save(str(j_path))
    return q_path, j_path


def seed_default_compiled_artifacts(target_dir: Optional[Union[str, Path]] = None) -> tuple[Path, Path]:
    """Seed default production artifacts in `adaptive_questioning/compiled_modules`."""
    compiled_q, compiled_j = compile_with_labeled_few_shot()
    return save_compiled_modules(compiled_q, compiled_j, target_dir=target_dir)


if __name__ == "__main__":
    import argparse
    import sys
    from dotenv import load_dotenv

    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    # Load environment variables
    _env_root = Path(__file__).resolve().parent.parent.parent / ".env"
    _env_pkg = Path(__file__).resolve().parent.parent / ".env"
    load_dotenv(_env_root)
    load_dotenv(_env_pkg, override=True)

    parser = argparse.ArgumentParser(
        description="DSPy Prompt Compiler for Adaptive Questioning (Step 2A & Step 2B)"
    )
    parser.add_argument(
        "--bootstrap",
        action="store_true",
        help="Use BootstrapFewShot with LLM execution to dynamically discover optimal prompt traces.",
    )
    parser.add_argument(
        "--max-bootstrapped",
        type=int,
        default=2,
        help="Maximum bootstrapped demonstrations to discover (default: 2).",
    )
    parser.add_argument(
        "--max-labeled",
        type=int,
        default=2,
        help="Maximum gold labeled demonstrations to include (default: 2).",
    )
    parser.add_argument(
        "--out-dir",
        type=str,
        default=str(DEFAULT_COMPILED_DIR),
        help="Target output directory for compiled JSON artifacts.",
    )
    parser.add_argument(
        "--model",
        type=str,
        default=None,
        help="Model to use for the interview module being optimized (defaults to runtime engine model).",
    )
    parser.add_argument(
        "--judge-model",
        type=str,
        default=None,
        help="Independent Model for Judge 1 (Topic Drift & Single-Intent Evaluator). Can also be set via AQ_JUDGE_MODEL in .env.",
    )
    parser.add_argument(
        "--judge-api-key",
        type=str,
        default=None,
        help="Optional separate API key for the Judge 1 model.",
    )
    parser.add_argument(
        "--judge-base-url",
        type=str,
        default=None,
        help="Optional separate base URL for the Judge 1 model.",
    )
    parser.add_argument(
        "--metric-threshold",
        type=float,
        default=0.75,
        help="Minimum metric score for a bootstrapped trace to be accepted as a demo (default: 0.75).",
    )
    parser.add_argument(
        "--evaluate",
        action="store_true",
        help="Evaluate compiled modules on held-out devset after compilation.",
    )
    args = parser.parse_args()

    if args.bootstrap:
        # Setup Interview Generator LM (Student)
        from adaptive_questioning.core.engine import OpenAILLMEngine

        runtime_engine = OpenAILLMEngine(model=args.model)
        if runtime_engine.dspy_lm is None:
            raise RuntimeError(
                "Bootstrap optimization requires OPENAI_API_KEY or OPENROUTER_API_KEY set in .env."
            )
        generator_lm = runtime_engine.dspy_lm

        # Setup Independent Judge 1 LM (Teacher / Evaluator)
        judge_model_name = (
            args.judge_model
            or os.getenv("AQ_JUDGE_MODEL")
            or os.getenv("JUDGE_MODEL")
        )
        judge_lm: Optional[dspy.LM] = None
        if judge_model_name:
            j_api_key = (
                args.judge_api_key
                or os.getenv("AQ_JUDGE_API_KEY")
                or os.getenv("JUDGE_API_KEY")
                or runtime_engine.api_key
            )
            j_base_url = (
                args.judge_base_url
                or os.getenv("AQ_JUDGE_BASE_URL")
                or os.getenv("JUDGE_BASE_URL")
                or runtime_engine.base_url
            )
            is_openrouter = j_base_url and ("openrouter.ai" in j_base_url)
            if is_openrouter:
                dspy_judge_name = (
                    judge_model_name
                    if judge_model_name.startswith("openrouter/")
                    else f"openrouter/{judge_model_name}"
                )
            else:
                dspy_judge_name = (
                    judge_model_name
                    if "/" in judge_model_name
                    else f"openai/{judge_model_name}"
                )
            print(f"[*] Initializing Independent Judge 1 LM: '{dspy_judge_name}'")
            judge_lm = dspy.LM(
                dspy_judge_name,
                api_key=j_api_key,
                api_base=j_base_url,
                temperature=0.0,
            )
            set_judge_lm(judge_lm)
        else:
            print(f"[*] No separate Judge 1 model specified; using compiler LM as fallback.")

        print(f"[*] Interview Generator Model (Student): '{runtime_engine.model}'")
        print("[*] Running BootstrapFewShot optimization to discover optimal prompts...")
        comp_q, comp_j = compile_with_bootstrap_few_shot(
            lm=generator_lm,
            judge_lm=judge_lm,
            max_bootstrapped_demos=args.max_bootstrapped,
            max_labeled_demos=args.max_labeled,
            metric_threshold=args.metric_threshold,
        )
    else:
        print("[*] Compiling with fast deterministic LabeledFewShot from gold dataset...")
        comp_q, comp_j = compile_with_labeled_few_shot()

    q_file, j_file = save_compiled_modules(comp_q, comp_j, target_dir=args.out_dir)
    print(f"[+] Successfully compiled and saved optimal prompt artifacts:")
    print(f"    - Question Generator : {q_file}")
    print(f"    - Reflective Judge   : {j_file}")

    if args.evaluate:
        import json
        print("[*] Evaluating compiled modules on held-out dev split...")
        lm_for_eval = generator_lm if args.bootstrap else None
        eval_results = evaluate_modules_on_dev(comp_q, comp_j, lm=lm_for_eval, split="dev")
        print(f"[+] Dev Evaluation Results: {json.dumps(eval_results, indent=2, ensure_ascii=False)}")


