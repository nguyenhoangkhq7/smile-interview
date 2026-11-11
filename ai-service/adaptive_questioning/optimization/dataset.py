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
from adaptive_questioning.evidence.models import Judgment, Objective, Question
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


def _context(record: dict) -> str:
    context = record["context"]
    context["depth_definitions"] = DEPTH_DEFINITIONS
    mode = context.get("mode", context.get("turn", {}).get("mode"))
    obj = context["objective"]
    obj.update(requirement_id=obj["objective_id"] + "-requirement",
               required_proficiency=record["source_required_proficiency"],
               depth_basis="CURATED_TASK", depth_rationale="Depth assigned from the task, not CV proficiency",
               inferred=True, suitable_modes=[{"mode": mode, "rationale": "Matches the curated interview task"}])
    context["objective"] = Objective.model_validate(obj).model_dump(mode="json")
    if "turn" in context:
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


def _question(record: dict) -> Question:
    reasoning = record.get("source_reasoning", {})
    payload = {
        "surprising_fact_C": reasoning.get("surprising_fact_C", ""),
        "hypothesis_A": reasoning.get("hypothesis_A", ""),
        **record["question"],
    }
    return Question.model_validate(payload)


def get_gold_question_examples(split: Split = "all") -> list[dspy.Example]:
    return [dspy.Example(context=_context(record), question=_question(record))
            .with_inputs("context") for record in corpus_records("questions", split)]


def get_gold_judge_examples(split: Split = "all") -> list[dspy.Example]:
    return [dspy.Example(context=_context(record), judgment=Judgment.model_validate(record["judgment"]))
            .with_inputs("context") for record in corpus_records("judgments", split)]
