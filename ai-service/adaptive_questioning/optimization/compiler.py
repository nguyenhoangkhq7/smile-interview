"""Offline labeled demos and opt-in online DSPy optimization for evidence V2."""
import argparse
import hashlib
import json
from pathlib import Path

import dspy

from adaptive_questioning.evidence.models import Judgment, Question
from adaptive_questioning.evidence.provider import JudgeSignature, QuestionSignature
from .dataset import get_gold_judge_examples, get_gold_question_examples
from .metrics import get_judge_lm, judge_evaluation_metric, question_generation_metric

DEFAULT_COMPILED_DIR = Path(__file__).resolve().parent.parent / "compiled_modules"
ARTIFACT_VERSION = "evidence-dspy-1"


def _fingerprint() -> str:
    contract = {"question_instructions": QuestionSignature.instructions,
                "judge_instructions": JudgeSignature.instructions,
                "question_schema": Question.model_json_schema(), "judgment_schema": Judgment.model_json_schema()}
    return hashlib.sha256(json.dumps(contract, ensure_ascii=False, sort_keys=True).encode()).hexdigest()


def _new_modules() -> tuple[dspy.Predict, dspy.Predict]:
    return dspy.Predict(QuestionSignature), dspy.Predict(JudgeSignature)


def _artifact_digest(path: Path) -> str:
    # Git may convert JSON formatting from LF to CRLF on Windows. Hash the
    # parsed content so equivalent checkouts remain loadable on Linux/Windows.
    value = json.loads(path.read_text(encoding="utf-8"))
    canonical = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode()).hexdigest()


def compile_with_labeled_few_shot(k_question: int = 3, k_judge: int = 3) -> tuple[dspy.Predict, dspy.Predict]:
    """Seed demonstrations using only the train split; no model/API calls."""
    if k_question < 0 or k_judge < 0:
        raise ValueError("Demonstration counts must be nonnegative")
    question, judge = _new_modules()
    train_q, train_j = get_gold_question_examples("train"), get_gold_judge_examples("train")
    return (dspy.LabeledFewShot(k=min(k_question, len(train_q))).compile(question, trainset=train_q),
            dspy.LabeledFewShot(k=min(k_judge, len(train_j))).compile(judge, trainset=train_j))


def compile_with_bootstrap_few_shot(lm: dspy.LM, judge_lm: dspy.LM | None = None,
                                    max_bootstrapped_demos: int = 2, max_labeled_demos: int = 2,
                                    metric_threshold: float = 0.8, train_split: str = "train"):
    """Explicit online operation; an optional separate teacher scores semantics."""
    if train_split != "train":
        raise ValueError("Bootstrap may only train on the train split")
    if not 0.7 < metric_threshold <= 1:
        raise ValueError("Threshold must exceed the offline heuristic ceiling (0.7) and be <= 1")
    teacher = judge_lm if judge_lm is not None else lm

    def question_metric(gold, prediction, trace=None):
        return question_generation_metric(gold, prediction, trace, lm=teacher)

    def judgment_metric(gold, prediction, trace=None):
        return judge_evaluation_metric(gold, prediction, trace, lm=teacher)

    question, judge = _new_modules()
    with dspy.context(lm=lm):
        compiled_q = dspy.BootstrapFewShot(metric=question_metric, metric_threshold=metric_threshold,
            max_bootstrapped_demos=max_bootstrapped_demos, max_labeled_demos=max_labeled_demos).compile(
                question, trainset=get_gold_question_examples("train"))
        compiled_j = dspy.BootstrapFewShot(metric=judgment_metric, metric_threshold=metric_threshold,
            max_bootstrapped_demos=max_bootstrapped_demos, max_labeled_demos=max_labeled_demos).compile(
                judge, trainset=get_gold_judge_examples("train"))
    return compiled_q, compiled_j


def save_compiled_modules(compiled_q: dspy.Predict, compiled_j: dspy.Predict,
                          target_dir: str | Path | None = None) -> tuple[Path, Path]:
    for module, field, model in ((compiled_q, "question", Question), (compiled_j, "judgment", Judgment)):
        signature = module.signature
        if (set(signature.input_fields) != {"context"} or set(signature.output_fields) != {field}
                or signature.output_fields[field].annotation is not model):
            raise ValueError("Only current typed evidence modules can be saved")
    directory = Path(target_dir or DEFAULT_COMPILED_DIR)
    directory.mkdir(parents=True, exist_ok=True)
    q_path, j_path = directory / "question_generator.json", directory / "reflective_judge.json"
    compiled_q.save(str(q_path))
    compiled_j.save(str(j_path))
    manifest = {"version": ARTIFACT_VERSION, "contract_fingerprint": _fingerprint(), "train_split": "train",
                "digest_format": "canonical-json-sha256", "files": {p.name: _artifact_digest(p) for p in (q_path, j_path)}}
    (directory / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return q_path, j_path


def load_compiled_modules(directory: str | Path) -> tuple[dspy.Predict, dspy.Predict]:
    """Load only JSON artifacts matching current contracts and manifest hashes."""
    directory = Path(directory)
    manifest = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
    if (manifest.get("version") != ARTIFACT_VERSION or manifest.get("contract_fingerprint") != _fingerprint()
            or manifest.get("digest_format") != "canonical-json-sha256"):
        raise ValueError("Incompatible compiled artifacts; recompile for the current evidence contracts")
    modules = _new_modules()
    for module, filename in zip(modules, ("question_generator.json", "reflective_judge.json")):
        path = directory / filename
        if _artifact_digest(path) != manifest.get("files", {}).get(filename):
            raise ValueError("Compiled artifact checksum mismatch")
        module.load(str(path))
    return modules


def seed_default_compiled_artifacts(target_dir: str | Path | None = None) -> tuple[Path, Path]:
    return save_compiled_modules(*compile_with_labeled_few_shot(), target_dir=target_dir)


def evaluate_modules_on_dev(q_module, j_module, lm: dspy.LM | None = None, split: str = "dev",
                            judge_lm: dspy.LM | None = None) -> dict:
    if split not in {"dev", "val"}:
        raise ValueError("Held-out evaluation requires dev or val")
    questions, judgments = get_gold_question_examples(split), get_gold_judge_examples(split)
    q_scores, j_scores, errors = [], [], 0
    teacher = judge_lm if judge_lm is not None else get_judge_lm()
    with dspy.context(lm=lm) if lm is not None else dspy.context():
        for module, examples, metric, scores in (
            (q_module, questions, question_generation_metric, q_scores),
            (j_module, judgments, judge_evaluation_metric, j_scores),
        ):
            for example in examples:
                try:
                    scores.append(metric(example, module(context=example.context), lm=teacher))
                except Exception:
                    errors += 1
                    scores.append(0.0)
    return {"dev_split": split, "question_examples_count": len(questions), "judge_examples_count": len(judgments),
            "question_generator_avg_score": sum(q_scores) / len(q_scores),
            "reflective_judge_avg_score": sum(j_scores) / len(j_scores), "evaluation_errors": errors,
            "question_semantic_evaluator": "independent_lm" if teacher is not None else "lexical_heuristic"}


def main() -> None:
    parser = argparse.ArgumentParser(description="Compile evidence V2 DSPy modules from recovered examples")
    parser.add_argument("--bootstrap", action="store_true", help="Online optimization; invokes the configured LM")
    parser.add_argument("--evaluate", action="store_true", help="Online evaluation on the held-out dev split")
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_COMPILED_DIR)
    parser.add_argument("--metric-threshold", type=float, default=0.8)
    parser.add_argument("--max-bootstrapped", type=int, default=2)
    parser.add_argument("--max-labeled", type=int, default=2)
    args = parser.parse_args()
    lm = None
    if args.bootstrap or args.evaluate:
        from dotenv import load_dotenv
        from adaptive_questioning.evidence.provider import configured_lm
        root = Path(__file__).resolve().parents[2]
        load_dotenv(root.parent / ".env")
        load_dotenv(root / ".env", override=True)
        lm = configured_lm()
    modules = (compile_with_bootstrap_few_shot(lm, metric_threshold=args.metric_threshold,
                  max_bootstrapped_demos=args.max_bootstrapped, max_labeled_demos=args.max_labeled)
               if args.bootstrap else compile_with_labeled_few_shot())
    paths = save_compiled_modules(*modules, target_dir=args.out_dir)
    print("Saved:", *paths)
    if args.evaluate:
        print(json.dumps(evaluate_modules_on_dev(*modules, lm=lm, judge_lm=lm), indent=2))


if __name__ == "__main__":
    main()
