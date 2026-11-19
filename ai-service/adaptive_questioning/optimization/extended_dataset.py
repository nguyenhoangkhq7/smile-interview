"""Extended domain-disjoint DSPy datasets covering Question, Judge, Alignment, Blueprint, and Dialogue."""
from collections import Counter
import json
from pathlib import Path
from typing import Literal

import dspy

from adaptive_questioning.evidence.depth import DEPTH_DEFINITIONS
from adaptive_questioning.evidence.models import BlueprintDraft, Judgment, Question
from adaptive_questioning.evidence.provider import encode_context
from .dataset import get_gold_judge_examples, get_gold_question_examples

ExtendedSplit = Literal["all", "train", "dev", "val", "test"]
CORPORA_DIR = Path(__file__).resolve().with_name("corpora")


def _normalized_split(split: ExtendedSplit) -> str:
    if split not in {"all", "train", "dev", "val", "test"}:
        raise ValueError(f"Unknown dataset split: {split}")
    return "dev" if split == "val" else split


def _load_records(filename: str, split: ExtendedSplit) -> list[dict]:
    target = _normalized_split(split)
    records = json.loads((CORPORA_DIR / filename).read_text(encoding="utf-8"))
    if target == "all":
        return records
    return [record for record in records if record["split"] == target]


def _append_base(examples: list[dspy.Example], getter, split: ExtendedSplit, include_base: bool) -> list[dspy.Example]:
    target = _normalized_split(split)
    if not include_base or target == "test":
        return examples
    return getter(target) + examples


def get_extended_question_examples(
    split: ExtendedSplit = "all",
    *,
    include_base: bool = False,
) -> list[dspy.Example]:
    """Load curated Question examples across TEXT/VOICE, all 5 Modes, L1–L4, and all 6 Actions."""
    examples = [
        dspy.Example(
            context=encode_context(record["context"]),
            question=Question.model_validate(record["question"]),
        ).with_inputs("context")
        for record in _load_records("questions.json", split)
    ]
    return _append_base(examples, get_gold_question_examples, split, include_base)


def get_extended_judge_examples(
    split: ExtendedSplit = "all",
    *,
    include_base: bool = False,
) -> list[dspy.Example]:
    """Load curated Judgment examples including multiline line-range excerpts, coding checks, and extensions."""
    examples = [
        dspy.Example(
            context=encode_context(record["context"]),
            judgment=Judgment.model_validate(record["judgment"]),
        ).with_inputs("context")
        for record in _load_records("judgments.json", split)
    ]
    return _append_base(examples, get_gold_judge_examples, split, include_base)


def get_alignment_examples(split: ExtendedSplit = "all") -> list[dspy.Example]:
    """Load curated QuestionAlignment examples balanced across all 7 AlignmentVerdict labels."""
    return [
        dspy.Example(
            context=encode_context(record["context"]),
            verdict=record["verdict"],
        ).with_inputs("context")
        for record in _load_records("alignments.json", split)
    ]


def get_blueprint_examples(split: ExtendedSplit = "all") -> list[dspy.Example]:
    """Load curated Blueprint examples with input skills and extension-probe flags for validation."""
    return [
        dspy.Example(
            context=encode_context(record["context"]),
            blueprint=BlueprintDraft.model_validate(record["blueprint"]),
            skills=record["skills"],
            allow_extension_probes=record["allow_extension_probes"],
        ).with_inputs("context")
        for record in _load_records("blueprints.json", split)
    ]


def get_extended_dialogue_examples(split: ExtendedSplit = "all") -> list[tuple[dspy.Example, dspy.Example]]:
    """Load paired (Judgment -> next Question) dialogue turns across adaptive actions."""
    pairs: list[tuple[dspy.Example, dspy.Example]] = []
    for case in _load_records("dialogues.json", split):
        turn = case["turn"]
        shared = {
            "interaction_mode": case["interaction_mode"],
            "objective": case["objective"],
            "depth_definitions": DEPTH_DEFINITIONS,
        }
        judgment = Judgment.model_validate(case["judgment"])
        question = Question.model_validate(case["next_question"])
        assessment = {
            **shared,
            "turn": turn,
            "prior_observations": [],
            "prior_turns": [],
            "answer_lines": [{"line": i, "text": line} for i, line in enumerate(turn["answer"].splitlines(), start=1)],
        }
        contract: dict = {"mode": question.mode, "depth": question.depth, "criterion_ids": question.criterion_ids}
        if case["action"] == "CLARIFY":
            contract["evidence_scope"] = turn["question"]["evidence_scope"]
        generation = {
            **shared,
            "history": [{**turn, "judgment": judgment.model_dump(mode="json")}],
            "other_questions": [],
            "action": case["action"],
            "required_question_contract": contract,
        }
        pairs.append((
            dspy.Example(context=encode_context(assessment), judgment=judgment).with_inputs("context"),
            dspy.Example(context=encode_context(generation), question=question).with_inputs("context"),
        ))
    return pairs


def corpus_summary() -> dict[str, dict[str, int]]:
    """Return record counts per split for each extended corpus."""
    filenames = ("questions.json", "judgments.json", "alignments.json", "blueprints.json", "dialogues.json")
    return {
        name.removesuffix(".json"): dict(Counter(item["split"] for item in _load_records(name, "all")))
        for name in filenames
    }
