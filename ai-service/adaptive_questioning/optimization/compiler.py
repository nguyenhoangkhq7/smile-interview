"""Offline labeled demos, online BootstrapFewShot/MIPROv2 optimization, and held-out eval for V2."""
import argparse
import hashlib
import json
import time
from pathlib import Path
from typing import Literal

import dspy

from adaptive_questioning.evidence.dspy_modules import (
    CandidateFeedbackSignature,
    DiagnosticQuestionSignature,
    EvidenceAssessment,
    EvidenceAssessmentSignature,
    FeedbackDraft,
    FollowUpQuestionSignature,
    InitialQuestionSignature,
    QuestionGeneratorModule,
    ReflectiveJudgeModule,
    build_judge_stage1_inputs,
    build_judge_stage2_inputs,
    build_question_inputs,
)
from adaptive_questioning.evidence.models import BlueprintDraft, Judgment, Question
from adaptive_questioning.evidence.provider import (
    BlueprintSignature,
    QuestionAlignmentSignature,
    encode_context,
)
from .dataset import dialogue_examples, get_gold_judge_examples, get_gold_question_examples
from .extended_dataset import (
    get_alignment_examples,
    get_blueprint_examples,
    get_extended_dialogue_examples,
    get_extended_judge_examples,
    get_extended_question_examples,
)
from .metrics import (
    alignment_evaluation_metric,
    alignment_macro_f1,
    blueprint_evaluation_metric,
    get_judge_lm,
    judge_evaluation_metric,
    question_generation_metric,
)

DEFAULT_COMPILED_DIR = Path(__file__).resolve().parent.parent / "compiled_modules"
ARTIFACT_VERSION = "evidence-dspy-2"
QUESTION_FILE = "question_generator.json"
JUDGE_FILE = "reflective_judge.json"
ALIGNMENT_FILE = "alignment_reviewer.json"
BLUEPRINT_FILE = "blueprint_drafter.json"
CompileStrategy = Literal["labeled", "bootstrap", "random_search", "mipro"]


def _fingerprint() -> str:
    contract = {
        "initial_instructions": InitialQuestionSignature.instructions,
        "followup_instructions": FollowUpQuestionSignature.instructions,
        "diagnostic_instructions": DiagnosticQuestionSignature.instructions,
        "assess_instructions": EvidenceAssessmentSignature.instructions,
        "feedback_instructions": CandidateFeedbackSignature.instructions,
        "question_schema": Question.model_json_schema(),
        "assessment_schema": EvidenceAssessment.model_json_schema(),
        "feedback_schema": FeedbackDraft.model_json_schema(),
    }
    return hashlib.sha256(json.dumps(contract, ensure_ascii=False, sort_keys=True).encode()).hexdigest()


def _full_fingerprint() -> str:
    contract = {
        "core": _fingerprint(),
        "alignment_instructions": QuestionAlignmentSignature.instructions,
        "blueprint_instructions": BlueprintSignature.instructions,
        "blueprint_schema": BlueprintDraft.model_json_schema(),
    }
    return hashlib.sha256(json.dumps(contract, ensure_ascii=False, sort_keys=True).encode()).hexdigest()


def _new_modules() -> tuple[QuestionGeneratorModule, ReflectiveJudgeModule]:
    return QuestionGeneratorModule(), ReflectiveJudgeModule()


def _new_aux_modules() -> tuple[dspy.Predict, dspy.Predict]:
    return dspy.Predict(QuestionAlignmentSignature), dspy.Predict(BlueprintSignature)


def _artifact_digest(path: Path) -> str:
    # Git may convert JSON formatting from LF to CRLF on Windows. Hash the
    # parsed content so equivalent checkouts remain loadable on Linux/Windows.
    value = json.loads(path.read_text(encoding="utf-8"))
    canonical = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode()).hexdigest()


def _question_reasoning(context_text: str, question: Question) -> str:
    data = json.loads(context_text)
    action = data.get("action", "INITIAL")
    mode = data.get("interaction_mode", "TEXT")
    criteria = (data.get("objective") or {}).get("criteria") or [{}]
    expected = criteria[0].get("expected_evidence", "")
    return (
        f"Action={action}, interaction_mode={mode}, mode={question.mode}, depth=L{question.depth}. "
        f"Target expected_evidence: {expected} "
        f"Formulate one focused Vietnamese task preserving criterion_ids={question.criterion_ids} "
        f"and evidence_scope='{question.evidence_scope}' without revealing the answer."
    )


def _judge_reasoning(context_text: str, judgment: Judgment) -> str:
    data = json.loads(context_text)
    depth = (data.get("turn") or {}).get("question_depth", "")
    summary = "; ".join(
        f"{obs.criterion_id}: {obs.observation}/{obs.performance} ({obs.rationale})"
        for obs in judgment.observations
    )
    return f"Assess at question_depth=L{depth} against criterion anchors: {summary}"


def _project_question_examples(
    examples: list[dspy.Example],
    question_mod: QuestionGeneratorModule,
) -> dict[str, list[dspy.Example]]:
    grouped: dict[str, list[dspy.Example]] = {"initial": [], "followup": [], "diagnostic": []}
    for example in examples:
        action, fields = build_question_inputs(example.context)
        question = Question.model_validate(example.question)
        projected = dspy.Example(
            **fields,
            reasoning=_question_reasoning(example.context, question),
            question=question,
        ).with_inputs(*fields.keys())
        grouped[question_mod.branch_name_for_action(action)].append(projected)
    return grouped


def _project_judge_examples(
    examples: list[dspy.Example],
) -> tuple[list[dspy.Example], list[dspy.Example]]:
    stage1_examples, stage2_examples = [], []
    for example in examples:
        judgment = Judgment.model_validate(example.judgment)
        assessment = EvidenceAssessment(
            observations=judgment.observations,
            explicit_inability=judgment.explicit_inability,
            inability_excerpt=judgment.inability_excerpt,
        )
        s1_fields = build_judge_stage1_inputs(example.context)
        stage1_examples.append(
            dspy.Example(
                **s1_fields,
                reasoning=_judge_reasoning(example.context, judgment),
                assessment=assessment,
            ).with_inputs(*s1_fields.keys())
        )
        if assessment.observations and not (
            assessment.explicit_inability
            and all(obs.observation == "NO_EVIDENCE" for obs in assessment.observations)
        ):
            s2_fields = build_judge_stage2_inputs(example.context, assessment)
            stage2_examples.append(
                dspy.Example(
                    **s2_fields,
                    feedback_draft=FeedbackDraft(
                        feedback=judgment.feedback,
                        feedback_contains_hint=judgment.feedback_contains_hint,
                    ),
                ).with_inputs(*s2_fields.keys())
            )
    return stage1_examples, stage2_examples


def _stratify_examples(examples: list[dspy.Example], key_fn) -> list[dspy.Example]:
    """Round-robin interleave examples by class/branch so early bootstrap traces are balanced."""
    buckets: dict[str, list[dspy.Example]] = {}
    for ex in examples:
        buckets.setdefault(str(key_fn(ex)), []).append(ex)
    ordered: list[dspy.Example] = []
    while any(buckets.values()):
        for key in list(buckets):
            if buckets[key]:
                ordered.append(buckets[key].pop(0))
    return ordered


def _clean_judge_demo(demo: dict) -> dict:
    """Clear redundant response_excerpt when multiline response_line_range is used."""
    cleaned = dict(demo)
    assessment = cleaned.get("assessment")
    if isinstance(assessment, dict):
        for obs in assessment.get("observations", []):
            if obs.get("response_line_range") is not None:
                obs["response_excerpt"] = ""
    return cleaned


def _stage1_bucket(demo: dict) -> str:
    raw = demo.get("assessment")
    if hasattr(raw, "explicit_inability"):
        return "INABILITY" if raw.explicit_inability else (str(raw.observations[0].observation) if raw.observations else "EMPTY")
    if isinstance(raw, dict):
        if raw.get("explicit_inability"):
            return "INABILITY"
        obs = raw.get("observations") or []
        return str(obs[0].get("observation", "EMPTY")) if obs else "EMPTY"
    return "OTHER"


def _stage2_bucket(demo: dict) -> str:
    draft = demo.get("feedback_draft")
    text = getattr(draft, "feedback", None) if not isinstance(draft, dict) else draft.get("feedback", "")
    return "NONEMPTY" if (text or "").strip() else "EMPTY"


def _diversify_demos(valid: list, fallback: list, spec: tuple) -> list:
    """Select bootstrapped demos first while covering distinct verdict/feedback buckets."""
    key_fn, dedup_key, target = spec
    chosen, seen_keys, seen_buckets = [], set(), set()
    for item in [*valid, *fallback]:
        ident, bucket = item.get(dedup_key), key_fn(item)
        if ident in seen_keys or bucket in seen_buckets:
            continue
        chosen.append(item)
        seen_keys.add(ident)
        seen_buckets.add(bucket)
        if len(chosen) >= target:
            return chosen
    for item in [*valid, *fallback]:
        ident = item.get(dedup_key)
        if ident not in seen_keys:
            chosen.append(item)
            seen_keys.add(ident)
            if len(chosen) >= target:
                break
    return chosen


def _sanitize_or_backfill_demos(
    question_mod: QuestionGeneratorModule,
    judge_mod: ReflectiveJudgeModule,
    train_q: list[dspy.Example],
    train_j: list[dspy.Example],
    min_demos: int = 2,
) -> None:
    """Keep valid multi-field bootstrapped demos and diversify/backfill from train."""
    grouped_q = _project_question_examples(train_q, question_mod)
    for branch_name, fallback in grouped_q.items():
        predict = getattr(question_mod, branch_name).predict
        req_keys = set(predict.signature.input_fields)
        valid = [demo for demo in predict.demos if req_keys.issubset(demo.keys())]
        if len(valid) < min_demos and fallback:
            existing_contracts = {d.get("question_contract") for d in valid}
            extras = [ex for ex in fallback if ex.question_contract not in existing_contracts]
            valid.extend(extras[: min_demos - len(valid)])
        predict.demos = valid[:4]

    stage1_j, stage2_j = _project_judge_examples(train_j)
    specs = (
        (judge_mod.assess.predict, stage1_j, (_stage1_bucket, "candidate_answer", min(4, max(min_demos, 4))), _clean_judge_demo),
        (judge_mod.feedback, stage2_j, (_stage2_bucket, "question_and_answer", min(4, max(min_demos, 3))), None),
    )
    for predict, fallback, spec, cleaner in specs:
        req_keys = set(predict.signature.input_fields)
        valid = [cleaner(d) if cleaner else d for d in predict.demos if req_keys.issubset(d.keys())]
        predict.demos = _diversify_demos(valid, fallback, spec) if fallback else valid[: spec[2]]


def compile_with_labeled_few_shot(
    k_question: int = 3,
    k_judge: int = 3,
    *,
    use_extended: bool = False,
) -> tuple[QuestionGeneratorModule, ReflectiveJudgeModule]:
    """Seed multi-field CoT demonstrations using only the train split; no model/API calls."""
    if k_question < 0 or k_judge < 0:
        raise ValueError("Demonstration counts must be nonnegative")
    question_mod, judge_mod = _new_modules()
    train_q = (
        get_extended_question_examples("train", include_base=True)
        if use_extended else get_gold_question_examples("train")
    )
    train_j = (
        get_extended_judge_examples("train", include_base=True)
        if use_extended else get_gold_judge_examples("train")
    )
    grouped_q = _project_question_examples(train_q, question_mod)
    for branch_name, branch_examples in grouped_q.items():
        if branch_examples and k_question > 0:
            compiled = dspy.LabeledFewShot(k=min(k_question, len(branch_examples))).compile(
                getattr(question_mod, branch_name), trainset=branch_examples,
            )
            setattr(question_mod, branch_name, compiled)

    stage1_j, stage2_j = _project_judge_examples(train_j)
    if stage1_j and k_judge > 0:
        judge_mod.assess = dspy.LabeledFewShot(k=min(k_judge, len(stage1_j))).compile(
            judge_mod.assess, trainset=stage1_j,
        )
    if stage2_j and k_judge > 0:
        judge_mod.feedback = dspy.LabeledFewShot(k=min(k_judge, len(stage2_j))).compile(
            judge_mod.feedback, trainset=stage2_j,
        )
    return question_mod, judge_mod


def compile_with_bootstrap_few_shot(
    lm: dspy.LM,
    judge_lm: dspy.LM | None = None,
    max_bootstrapped_demos: int = 2,
    max_labeled_demos: int = 2,
    metric_threshold: float = 0.8,
    train_split: str = "train",
    *,
    use_extended: bool = False,
):
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

    train_q = (
        get_extended_question_examples("train", include_base=True)
        if use_extended else get_gold_question_examples("train")
    )
    train_j = (
        get_extended_judge_examples("train", include_base=True)
        if use_extended else get_gold_judge_examples("train")
    )
    stratified_q = _stratify_examples(
        train_q, lambda ex: (json.loads(ex.context).get("action", "INITIAL"), json.loads(ex.context).get("interaction_mode", "TEXT")),
    )
    stratified_j = _stratify_examples(
        train_j,
        lambda ex: (
            ex.judgment.observations[0].observation,
            ex.judgment.explicit_inability,
            ex.judgment.observations[0].response_line_range is not None,
        ),
    )
    question_mod, judge_mod = _new_modules()
    with dspy.context(lm=lm):
        compiled_q = dspy.BootstrapFewShot(
            metric=question_metric, metric_threshold=metric_threshold,
            max_bootstrapped_demos=max_bootstrapped_demos, max_labeled_demos=max_labeled_demos,
        ).compile(question_mod, trainset=stratified_q)
    with dspy.context(lm=lm, adapter=dspy.JSONAdapter()):
        compiled_j = dspy.BootstrapFewShot(
            metric=judgment_metric, metric_threshold=metric_threshold,
            max_bootstrapped_demos=max_bootstrapped_demos, max_labeled_demos=max_labeled_demos,
        ).compile(judge_mod, trainset=stratified_j)
    _sanitize_or_backfill_demos(compiled_q, compiled_j, train_q, train_j, min_demos=max_labeled_demos)
    return compiled_q, compiled_j


def _compile_aux_bootstrap(
    lm: dspy.LM,
    teacher: dspy.LM,
    *,
    max_bootstrapped_demos: int = 3,
    max_labeled_demos: int = 3,
    metric_threshold: float = 0.8,
) -> tuple[dspy.Predict, dspy.Predict]:
    align_mod, bp_mod = _new_aux_modules()
    stratified_align = _stratify_examples(get_alignment_examples("train"), lambda ex: ex.verdict)
    align_k = max(7, max_bootstrapped_demos)
    with dspy.context(lm=lm):
        compiled_a = dspy.BootstrapFewShot(
            metric=alignment_evaluation_metric, metric_threshold=metric_threshold,
            max_bootstrapped_demos=align_k, max_labeled_demos=align_k,
        ).compile(align_mod, trainset=stratified_align)
    stratified_bp = _stratify_examples(
        get_blueprint_examples("train"),
        lambda ex: (bool(ex.allow_extension_probes), len(ex.skills)),
    )
    bp_k = min(3, max(2, max_bootstrapped_demos))
    with dspy.context(lm=lm, adapter=dspy.JSONAdapter()):
        compiled_b = dspy.BootstrapFewShot(
            metric=lambda g, p, t=None: blueprint_evaluation_metric(g, p, t, lm=teacher),
            metric_threshold=metric_threshold,
            max_bootstrapped_demos=bp_k,
            max_labeled_demos=bp_k,
        ).compile(bp_mod, trainset=stratified_bp)
    return compiled_a, compiled_b


def _compile_random_search(
    module: dspy.Module,
    metric,
    trainset: list[dspy.Example],
    lm: dspy.LM,
    *,
    adapter: dspy.Adapter | None = None,
    max_bootstrapped_demos: int = 3,
    max_labeled_demos: int = 4,
    num_candidate_programs: int = 6,
    metric_threshold: float = 0.8,
):
    optimizer = dspy.BootstrapFewShotWithRandomSearch(
        metric=metric,
        max_bootstrapped_demos=max_bootstrapped_demos,
        max_labeled_demos=max_labeled_demos,
        num_candidate_programs=num_candidate_programs,
        num_threads=1,
        metric_threshold=metric_threshold,
    )
    ctx = dspy.context(lm=lm, adapter=adapter) if adapter is not None else dspy.context(lm=lm)
    with ctx:
        return optimizer.compile(module, trainset=trainset)


def _compile_mipro(
    module: dspy.Module,
    metric,
    trainset: list[dspy.Example],
    valset: list[dspy.Example],
    lm: dspy.LM,
    *,
    prompt_lm: dspy.LM,
    adapter: dspy.Adapter | None = None,
    auto: Literal["light", "medium", "heavy"] = "light",
    max_bootstrapped_demos: int = 2,
    max_labeled_demos: int = 0,
):
    try:
        import optuna  # noqa: F401
    except ImportError as exc:
        raise RuntimeError("MIPROv2 requires `optuna` (`pip install dspy[optuna]`); use `--random-search` or `--bootstrap`.") from exc
    optimizer = dspy.MIPROv2(
        metric=metric,
        prompt_model=prompt_lm,
        task_model=lm,
        auto=auto,
        max_bootstrapped_demos=max_bootstrapped_demos,
        max_labeled_demos=max_labeled_demos,
        num_threads=4,
    )
    ctx = dspy.context(lm=lm, adapter=adapter) if adapter is not None else dspy.context(lm=lm)
    with ctx:
        return optimizer.compile(
            module,
            trainset=trainset,
            valset=valset,
            minibatch=False,
            requires_permission_to_run=False,
        )


def compile_all_modules(
    lm: dspy.LM | None = None,
    *,
    strategy: CompileStrategy = "bootstrap",
    judge_lm: dspy.LM | None = None,
    use_extended: bool = True,
    metric_threshold: float = 0.8,
    max_bootstrapped_demos: int = 2,
    max_labeled_demos: int = 2,
) -> tuple[QuestionGeneratorModule, ReflectiveJudgeModule, dspy.Predict, dspy.Predict]:
    """Compile all 4 evidence modules (Question, Judge, Alignment, Blueprint)."""
    if strategy == "labeled":
        compiled_q, compiled_j = compile_with_labeled_few_shot(use_extended=use_extended)
        align_mod, bp_mod = _new_aux_modules()
        compiled_a = dspy.LabeledFewShot(k=min(4, len(get_alignment_examples("train")))).compile(
            align_mod, trainset=get_alignment_examples("train"),
        )
        compiled_b = dspy.LabeledFewShot(k=min(2, len(get_blueprint_examples("train")))).compile(
            bp_mod, trainset=get_blueprint_examples("train"),
        )
        return compiled_q, compiled_j, compiled_a, compiled_b

    if lm is None:
        raise ValueError("Online compilation requires a configured student LM")
    teacher = judge_lm if judge_lm is not None else lm
    if strategy == "bootstrap":
        compiled_q, compiled_j = compile_with_bootstrap_few_shot(
            lm, judge_lm=teacher, max_bootstrapped_demos=max_bootstrapped_demos,
            max_labeled_demos=max_labeled_demos, metric_threshold=metric_threshold,
            use_extended=use_extended,
        )
        compiled_a, compiled_b = _compile_aux_bootstrap(
            lm, teacher, max_bootstrapped_demos=max_bootstrapped_demos,
            max_labeled_demos=max_labeled_demos, metric_threshold=metric_threshold,
        )
        return compiled_q, compiled_j, compiled_a, compiled_b

    if strategy == "random_search":
        train_q = get_extended_question_examples("train", include_base=True) if use_extended else get_gold_question_examples("train")
        train_j = get_extended_judge_examples("train", include_base=True) if use_extended else get_gold_judge_examples("train")
        strat_q = _stratify_examples(train_q, lambda ex: (json.loads(ex.context).get("action", "INITIAL"), json.loads(ex.context).get("interaction_mode", "TEXT")))
        strat_j = _stratify_examples(train_j, lambda ex: (ex.judgment.observations[0].observation, ex.judgment.observations[0].response_line_range is not None))
        strat_a = _stratify_examples(get_alignment_examples("train"), lambda ex: ex.verdict)
        q_mod, j_mod = _new_modules()
        a_mod, b_mod = _new_aux_modules()
        compiled_q = _compile_random_search(
            q_mod, lambda g, p, t=None: question_generation_metric(g, p, t, lm=teacher),
            strat_q, lm, max_bootstrapped_demos=max_bootstrapped_demos, max_labeled_demos=max_labeled_demos,
            metric_threshold=metric_threshold,
        )
        compiled_j = _compile_random_search(
            j_mod, lambda g, p, t=None: judge_evaluation_metric(g, p, t, lm=teacher),
            strat_j, lm, adapter=dspy.JSONAdapter(),
            max_bootstrapped_demos=max_bootstrapped_demos, max_labeled_demos=max_labeled_demos,
            metric_threshold=metric_threshold,
        )
        compiled_a = _compile_random_search(
            a_mod, alignment_evaluation_metric, strat_a, lm,
            max_bootstrapped_demos=max(4, max_bootstrapped_demos), max_labeled_demos=7,
            metric_threshold=metric_threshold,
        )
        compiled_b = _compile_random_search(
            b_mod, lambda g, p, t=None: blueprint_evaluation_metric(g, p, t, lm=teacher),
            get_blueprint_examples("train"), lm, adapter=dspy.JSONAdapter(),
            max_bootstrapped_demos=min(2, max_bootstrapped_demos), max_labeled_demos=min(2, max_labeled_demos),
            metric_threshold=metric_threshold,
        )
        _sanitize_or_backfill_demos(compiled_q, compiled_j, train_q, train_j, min_demos=max_labeled_demos)
        return compiled_q, compiled_j, compiled_a, compiled_b

    train_q = get_extended_question_examples("train", include_base=True) if use_extended else get_gold_question_examples("train")
    dev_q = get_extended_question_examples("dev", include_base=True) if use_extended else get_gold_question_examples("dev")
    train_j = get_extended_judge_examples("train", include_base=True) if use_extended else get_gold_judge_examples("train")
    dev_j = get_extended_judge_examples("dev", include_base=True) if use_extended else get_gold_judge_examples("dev")
    q_mod, j_mod = _new_modules()
    a_mod, b_mod = _new_aux_modules()
    compiled_q = _compile_mipro(
        q_mod, lambda g, p, t=None: question_generation_metric(g, p, t, lm=teacher),
        train_q, dev_q, lm, prompt_lm=teacher,
        max_bootstrapped_demos=max_bootstrapped_demos, max_labeled_demos=0,
    )
    compiled_j = _compile_mipro(
        j_mod, lambda g, p, t=None: judge_evaluation_metric(g, p, t, lm=teacher),
        train_j, dev_j, lm, prompt_lm=teacher, adapter=dspy.JSONAdapter(),
        max_bootstrapped_demos=max_bootstrapped_demos, max_labeled_demos=0,
    )
    compiled_a = _compile_mipro(
        a_mod, alignment_evaluation_metric,
        get_alignment_examples("train"), get_alignment_examples("dev"), lm, prompt_lm=teacher,
        max_bootstrapped_demos=3, max_labeled_demos=3,
    )
    compiled_b = _compile_mipro(
        b_mod, lambda g, p, t=None: blueprint_evaluation_metric(g, p, t, lm=teacher),
        get_blueprint_examples("train"), get_blueprint_examples("dev"), lm, prompt_lm=teacher,
        adapter=dspy.JSONAdapter(), max_bootstrapped_demos=2, max_labeled_demos=2,
    )
    _sanitize_or_backfill_demos(compiled_q, compiled_j, train_q, train_j, min_demos=max_labeled_demos)
    return compiled_q, compiled_j, compiled_a, compiled_b


def save_compiled_modules(
    compiled_q: QuestionGeneratorModule,
    compiled_j: ReflectiveJudgeModule,
    target_dir: str | Path | None = None,
) -> tuple[Path, Path]:
    if not isinstance(compiled_q, QuestionGeneratorModule) or not isinstance(compiled_j, ReflectiveJudgeModule):
        raise ValueError("Only current modular QuestionGeneratorModule and ReflectiveJudgeModule can be saved")
    directory = Path(target_dir or DEFAULT_COMPILED_DIR)
    directory.mkdir(parents=True, exist_ok=True)
    q_path, j_path = directory / QUESTION_FILE, directory / JUDGE_FILE
    compiled_q.save(str(q_path))
    compiled_j.save(str(j_path))
    manifest = {
        "version": ARTIFACT_VERSION,
        "contract_fingerprint": _fingerprint(),
        "train_split": "train",
        "digest_format": "canonical-json-sha256",
        "files": {p.name: _artifact_digest(p) for p in (q_path, j_path)},
    }
    (directory / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return q_path, j_path


def save_all_compiled_modules(
    compiled_q: QuestionGeneratorModule,
    compiled_j: ReflectiveJudgeModule,
    compiled_a: dspy.Predict,
    compiled_b: dspy.Predict,
    target_dir: str | Path | None = None,
) -> tuple[Path, Path, Path, Path]:
    if not isinstance(compiled_q, QuestionGeneratorModule) or not isinstance(compiled_j, ReflectiveJudgeModule):
        raise ValueError("Only current modular QuestionGeneratorModule and ReflectiveJudgeModule can be saved")
    directory = Path(target_dir or DEFAULT_COMPILED_DIR)
    directory.mkdir(parents=True, exist_ok=True)
    paths = (
        directory / QUESTION_FILE,
        directory / JUDGE_FILE,
        directory / ALIGNMENT_FILE,
        directory / BLUEPRINT_FILE,
    )
    for mod, path in zip((compiled_q, compiled_j, compiled_a, compiled_b), paths):
        mod.save(str(path))
    manifest = {
        "version": ARTIFACT_VERSION,
        "contract_fingerprint": _full_fingerprint(),
        "train_split": "train",
        "digest_format": "canonical-json-sha256",
        "files": {p.name: _artifact_digest(p) for p in paths},
    }
    (directory / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return paths


def _verify_manifest(directory: Path, *, require_full: bool = False) -> dict:
    manifest = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
    allowed = {_full_fingerprint()} if require_full else {_fingerprint(), _full_fingerprint()}
    if (
        manifest.get("version") != ARTIFACT_VERSION
        or manifest.get("contract_fingerprint") not in allowed
        or manifest.get("digest_format") != "canonical-json-sha256"
    ):
        raise ValueError("Incompatible compiled artifacts; recompile for the current evidence contracts")
    return manifest


def load_compiled_modules(directory: str | Path) -> tuple[QuestionGeneratorModule, ReflectiveJudgeModule]:
    """Load only JSON artifacts matching current modular contracts and manifest hashes."""
    directory = Path(directory)
    manifest = _verify_manifest(directory)
    modules = _new_modules()
    for module, filename in zip(modules, (QUESTION_FILE, JUDGE_FILE)):
        path = directory / filename
        if _artifact_digest(path) != manifest.get("files", {}).get(filename):
            raise ValueError("Compiled artifact checksum mismatch")
        module.load(str(path))
    return modules


def load_all_compiled_modules(
    directory: str | Path,
) -> tuple[QuestionGeneratorModule, ReflectiveJudgeModule, dspy.Predict, dspy.Predict]:
    """Load all 4 evidence modules when present, or fall back to uncompiled aux Predicts."""
    directory = Path(directory)
    manifest = _verify_manifest(directory)
    files = manifest.get("files", {})
    has_aux = ALIGNMENT_FILE in files and BLUEPRINT_FILE in files
    if has_aux and manifest.get("contract_fingerprint") != _full_fingerprint():
        raise ValueError("Incompatible full compiled artifacts; recompile for current contracts")
    q_mod, j_mod = load_compiled_modules(directory)
    a_mod, b_mod = _new_aux_modules()
    if has_aux:
        for mod, filename in ((a_mod, ALIGNMENT_FILE), (b_mod, BLUEPRINT_FILE)):
            path = directory / filename
            if _artifact_digest(path) != files.get(filename):
                raise ValueError("Compiled artifact checksum mismatch")
            mod.load(str(path))
    return q_mod, j_mod, a_mod, b_mod


def seed_default_compiled_artifacts(
    target_dir: str | Path | None = None,
    *,
    use_extended: bool = True,
) -> tuple[Path, Path]:
    return save_compiled_modules(*compile_with_labeled_few_shot(use_extended=use_extended), target_dir=target_dir)


def _is_transient_lm_error(exc: Exception) -> bool:
    name = type(exc).__name__
    markers = ("TransportError", "ConnectionError", "ConnectError", "Timeout", "APIConnectionError", "RateLimit")
    return any(marker in name or marker in str(exc) for marker in markers)


def _retry_transient(fn, attempts: int = 3):
    for attempt in range(attempts):
        try:
            return fn()
        except Exception as exc:
            if attempt + 1 >= attempts or not _is_transient_lm_error(exc):
                raise
            time.sleep(1.0)


def _score_module(module, examples: list[dspy.Example], spec: tuple) -> tuple[list[float], int]:
    """Run one module across held-out examples under its explicit adapter and count errors."""
    metric, teacher, adapter = spec
    scores: list[float] = []
    errors = 0
    ctx = dspy.context(adapter=adapter) if adapter is not None else dspy.context()
    with ctx:
        for example in examples:
            try:
                pred = _retry_transient(lambda ex=example: module(context=ex.context))
                scores.append(_retry_transient(lambda ex=example, p=pred: metric(ex, p, lm=teacher)))
            except Exception:
                errors += 1
                scores.append(0.0)
    return scores, errors


def _adapter_ctx(lm: dspy.LM | None, adapter: dspy.Adapter):
    return dspy.context(lm=lm, adapter=adapter) if lm is not None else dspy.context(adapter=adapter)


def _score_dialogues(q_module, j_module, spec: tuple) -> tuple[list[float], int]:
    """Evaluate paired Judge -> next Question turns under production adapters."""
    pairs, teacher, lm = spec
    scores: list[float] = []
    errors = 0
    for judge_case, question_case in pairs:
        try:
            with _adapter_ctx(lm, dspy.JSONAdapter()):
                assessment = _retry_transient(lambda jc=judge_case: j_module(context=jc.context))
            context = json.loads(question_case.context)
            context["history"][-1]["judgment"] = Judgment.model_validate(assessment.judgment).model_dump(mode="json")
            next_case = dspy.Example(context=encode_context(context), question=question_case.question)
            with _adapter_ctx(lm, dspy.ChatAdapter()):
                next_question = _retry_transient(lambda nc=next_case: q_module(context=nc.context))
            j_score = _retry_transient(lambda jc=judge_case, a=assessment: judge_evaluation_metric(jc, a, lm=teacher))
            q_score = _retry_transient(lambda nc=next_case, nq=next_question: question_generation_metric(nc, nq, lm=teacher))
            scores.append(min(j_score, q_score))
        except Exception:
            errors += 1
            scores.append(0.0)
    return scores, errors


def evaluate_modules_on_dev(
    q_module,
    j_module,
    lm: dspy.LM | None = None,
    split: str = "dev",
    judge_lm: dspy.LM | None = None,
) -> dict:
    if split not in {"dev", "val"}:
        raise ValueError("Held-out evaluation requires dev or val")
    questions, judgments = get_gold_question_examples(split), get_gold_judge_examples(split)
    teacher = judge_lm if judge_lm is not None else get_judge_lm()
    with dspy.context(lm=lm) if lm is not None else dspy.context():
        q_scores, q_errs = _score_module(q_module, questions, (question_generation_metric, teacher, None))
        j_scores, j_errs = _score_module(j_module, judgments, (judge_evaluation_metric, teacher, dspy.JSONAdapter()))
    dialogue_scores, d_errs = _score_dialogues(q_module, j_module, (dialogue_examples(split), teacher, lm))
    return {
        "dev_split": split,
        "question_examples_count": len(questions),
        "judge_examples_count": len(judgments),
        "paired_dialogue_count": len(dialogue_scores),
        "paired_dialogue_avg_score": sum(dialogue_scores) / len(dialogue_scores),
        "question_generator_avg_score": sum(q_scores) / len(q_scores),
        "reflective_judge_avg_score": sum(j_scores) / len(j_scores),
        "evaluation_errors": q_errs + j_errs + d_errs,
        "question_semantic_evaluator": "independent_lm" if teacher is not None else "lexical_heuristic",
    }


def evaluate_all_modules(
    q_module,
    j_module,
    a_module,
    b_module,
    *,
    lm: dspy.LM | None = None,
    split: Literal["dev", "val", "test"] = "test",
    judge_lm: dspy.LM | None = None,
) -> dict:
    """Evaluate all 4 modules plus paired dialogues on a domain-disjoint split."""
    questions = get_extended_question_examples(split)
    judgments = get_extended_judge_examples(split)
    alignments = get_alignment_examples(split)
    blueprints = get_blueprint_examples(split)
    dialogues = get_extended_dialogue_examples(split)
    teacher = judge_lm if judge_lm is not None else get_judge_lm()
    a_golds, a_preds, a_errs = [ex.verdict for ex in alignments], [], 0

    with dspy.context(lm=lm) if lm is not None else dspy.context():
        q_scores, q_errs = _score_module(q_module, questions, (question_generation_metric, teacher, dspy.ChatAdapter()))
        for ex in alignments:
            try:
                a_preds.append(_retry_transient(lambda e=ex: a_module(context=e.context).verdict))
            except Exception:
                a_errs += 1
                a_preds.append("INVALID")
        j_scores, j_errs = _score_module(j_module, judgments, (judge_evaluation_metric, teacher, dspy.JSONAdapter()))
        b_scores, b_errs = _score_module(b_module, blueprints, (blueprint_evaluation_metric, teacher, dspy.JSONAdapter()))
    d_scores, d_errs = _score_dialogues(q_module, j_module, (dialogues, teacher, lm))

    a_acc = sum(float(g == p) for g, p in zip(a_golds, a_preds)) / max(1, len(a_golds))
    return {
        "split": split,
        "question_count": len(questions),
        "question_avg_score": sum(q_scores) / max(1, len(q_scores)),
        "judge_count": len(judgments),
        "judge_avg_score": sum(j_scores) / max(1, len(j_scores)),
        "alignment_count": len(alignments),
        "alignment_accuracy": a_acc,
        "alignment_macro_f1": alignment_macro_f1(a_golds, a_preds),
        "blueprint_count": len(blueprints),
        "blueprint_avg_score": sum(b_scores) / max(1, len(b_scores)),
        "dialogue_count": len(dialogues),
        "dialogue_avg_score": sum(d_scores) / max(1, len(d_scores)),
        "evaluation_errors": q_errs + a_errs + j_errs + b_errs + d_errs,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Compile modular evidence V2 DSPy modules")
    parser.add_argument("--bootstrap", action="store_true", help="Online BootstrapFewShot optimization")
    parser.add_argument("--random-search", action="store_true", help="Online BootstrapFewShotWithRandomSearch optimization")
    parser.add_argument("--mipro", action="store_true", help="Online MIPROv2 instruction + demo optimization")
    parser.add_argument("--all", action="store_true", help="Compile all 4 modules (Question, Judge, Alignment, Blueprint)")
    parser.add_argument("--evaluate", action="store_true", help="Online evaluation on held-out dev/test splits")
    parser.add_argument("--extended", action="store_true", help="Include extended domain-disjoint train split")
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_COMPILED_DIR)
    parser.add_argument("--metric-threshold", type=float, default=0.8)
    parser.add_argument("--max-bootstrapped", type=int, default=2)
    parser.add_argument("--max-labeled", type=int, default=2)
    args = parser.parse_args()
    lm = None
    if args.bootstrap or args.random_search or args.mipro or args.evaluate:
        from dotenv import load_dotenv
        from adaptive_questioning.evidence.provider import configured_lm
        root = Path(__file__).resolve().parents[2]
        load_dotenv(root.parent / ".env")
        load_dotenv(root / ".env", override=True)
        lm = configured_lm().copy(num_retries=3)

    strategy: CompileStrategy = (
        "mipro" if args.mipro else ("random_search" if args.random_search else ("bootstrap" if args.bootstrap else "labeled"))
    )
    if args.all:
        modules = compile_all_modules(
            lm, strategy=strategy, use_extended=args.extended or strategy != "labeled",
            metric_threshold=args.metric_threshold, max_bootstrapped_demos=args.max_bootstrapped,
            max_labeled_demos=args.max_labeled,
        )
        paths = save_all_compiled_modules(*modules, target_dir=args.out_dir)
        print("Saved:", *paths)
        if args.evaluate:
            print(json.dumps(evaluate_all_modules(*modules, lm=lm, split="test", judge_lm=lm), indent=2))
        return

    modules = (
        compile_with_bootstrap_few_shot(
            lm, metric_threshold=args.metric_threshold,
            max_bootstrapped_demos=args.max_bootstrapped,
            max_labeled_demos=args.max_labeled,
            use_extended=args.extended,
        )
        if args.bootstrap
        else compile_with_labeled_few_shot(use_extended=args.extended)
    )
    paths = save_compiled_modules(*modules, target_dir=args.out_dir)
    print("Saved:", *paths)
    if args.evaluate:
        print(json.dumps(evaluate_modules_on_dev(*modules, lm=lm, judge_lm=lm), indent=2))


if __name__ == "__main__":
    main()
