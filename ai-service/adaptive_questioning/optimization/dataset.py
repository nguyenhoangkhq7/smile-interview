"""Recovered interview cases adapted to the current evidence-only DSPy signatures.

Source questions, answers and provenance live in examples.json. Only context and
the typed V2 output enter demonstrations; source metadata never becomes a label.
The original deterministic 14/6 split is retained, not a domain-disjoint benchmark.
"""
import json
from pathlib import Path
from typing import Literal

import dspy

from adaptive_questioning.evidence.depth import DEPTH_DEFINITIONS
from adaptive_questioning.evidence.models import Judgment, Objective, Question, Turn
from adaptive_questioning.evidence.provider import encode_context

Split = Literal["all", "train", "dev", "val"]
CORPUS_PATH = Path(__file__).with_name("examples.json")


def corpus_records(kind: str, split: Split = "all") -> list[dict]:
    if kind not in {"questions", "judgments"}:
        raise ValueError("Unknown example kind")
    if split not in {"all", "train", "dev", "val"}:
        raise ValueError("Unknown dataset split")
    records = json.loads(CORPUS_PATH.read_text(encoding="utf-8"))[kind]
    if split == "train":
        return records[:14]
    return records[14:] if split in {"dev", "val"} else records


def _normalize_turn(turn: dict) -> dict:
    cleaned = {k: v for k, v in turn.items() if k != "difficulty"}
    question = cleaned.get("question")
    if isinstance(question, dict):
        cleaned["question"] = {k: v for k, v in question.items() if k not in {"mode", "depth"}}
    return Turn.model_validate(cleaned).model_dump(mode="json")


def _context(record: dict) -> str:
    context = record["context"]
    context["depth_definitions"] = DEPTH_DEFINITIONS
    mode = context["turn"]["mode"] if "turn" in context else context["required_question_contract"]["mode"]
    obj = context["objective"]
    obj.update(requirement_id=obj["objective_id"] + "-requirement",
               depth_basis="CURATED_TASK", depth_rationale="Depth assigned from the task, not CV proficiency",
               suitable_modes=[{"mode": mode}])
    context["objective"] = Objective.model_validate(obj).model_dump(
        mode="json",
        exclude={
            "requirement_id", "objective_id", "depth_basis", "depth_rationale",
            "depth_evidence_spans", "requirement_kind", "jd_evidence_spans",
            "suitable_modes", "estimated_seconds",
        },
    )
    if "turn" in context:
        context["turn"] = _normalize_turn(context["turn"])
        context["answer_lines"] = [{"line": index, "text": line} for index, line in
                                   enumerate(context["turn"]["answer"].splitlines(), start=1)]
    if "cv_evidence" in context:
        # Historical context contains JD levels and interview bookkeeping as well
        # as CV text. Only the actual CV quote belongs in this runtime field.
        source_lines = record["source_context"].replace("\\n", "\n").splitlines()
        prefix = "- Bằng chứng nguyên văn từ CV:"
        context["cv_evidence"] = [line.split(prefix, 1)[1].strip().strip('"')
                                  for line in source_lines if prefix in line]
    return encode_context(context)


def get_gold_question_examples(split: Split = "all") -> list[dspy.Example]:
    return [dspy.Example(context=_context(record), question=Question.model_validate(record["question"]))
            .with_inputs("context") for record in corpus_records("questions", split)] + [
                question for _, question in dialogue_examples(split)]


def get_gold_judge_examples(split: Split = "all") -> list[dspy.Example]:
    return [dspy.Example(context=_context(record), judgment=Judgment.model_validate(record["judgment"]))
            .with_inputs("context") for record in corpus_records("judgments", split)] + [
                judge for judge, _ in dialogue_examples(split)]


def dialogue_examples(split: Split) -> list[tuple[dspy.Example, dspy.Example]]:
    """Keep both responses to an opening question on the same side of the split."""
    records = json.loads(CORPUS_PATH.with_name("dialogue_examples.json").read_text(encoding="utf-8"))
    pairs = []
    for case in records:
        if split != "all" and case["split"] != ("dev" if split == "val" else split):
            continue
        turn = _normalize_turn(case["turn"])
        objective = case["objective"]
        shared = dict(interaction_mode=case["interaction_mode"], objective=objective, depth_definitions=DEPTH_DEFINITIONS)
        judge = Judgment.model_validate(case["judgment"])
        question = Question.model_validate(case["next_question"])
        assessment = dict(shared, turn=turn, prior_observations=[], prior_turns=[],
                          answer_lines=[{"line": 1, "text": turn["answer"]}])
        generation = dict(shared, history=[dict(turn, judgment=judge.model_dump(mode="json"))],
                          other_questions=[], action=case["action"])
        contract = dict(mode=question.mode, depth=question.depth, criterion_ids=question.criterion_ids)
        if case["action"] == "CLARIFY":
            contract["evidence_scope"] = turn["question"]["evidence_scope"]
        generation["required_question_contract"] = contract
        pairs.append((dspy.Example(context=encode_context(assessment), judgment=judge).with_inputs("context"),
                      dspy.Example(context=encode_context(generation), question=question).with_inputs("context")))
    return pairs
