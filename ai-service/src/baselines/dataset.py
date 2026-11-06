import json
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Dict, List, Optional, Union
from pydantic import BaseModel, Field

from src.baselines.base import BaselineInput
from src.domain.models import ExtractedCVSkill, ExtractedJDSkill, MatchResult


class DatasetPair(BaseModel):
    """
    Standardized schema for a single CV-JD evaluation sample.
    Encapsulates raw text representations, extracted skills, and upstream matching results
    from Module 1, exactly matching the signature consumed by SkillGapOrchestrator.run_pipeline.

    Fields:
        pair_id: Unique identifier for the pair (e.g. 'pair_001', 'devops_lead_01').
        cv_text: Complete raw candidate resume text.
        jd_text: Complete raw job description text.
        cv_skills: List of extracted candidate skills from Module 1.
        jd_skills: List of extracted job requirements from Module 1.
        match_results: Initial semantic matching scores (soft_match, w_j) from Module 1.
        metadata: Optional dictionary for domain, role title, annotator notes, etc.
    """

    pair_id: str
    cv_text: str
    jd_text: str
    cv_skills: List[ExtractedCVSkill]
    jd_skills: List[ExtractedJDSkill]
    match_results: List[MatchResult]
    metadata: Dict[str, Any] = Field(default_factory=dict)

    def to_baseline_input(self) -> BaselineInput:
        """Converts the pair into immutable BaselineInput format consumed by BaselineMethod.run()."""
        return BaselineInput(
            cv_text=self.cv_text,
            jd_text=self.jd_text,
            cv_skills=self.cv_skills,
            jd_skills=self.jd_skills,
            match_results=self.match_results,
        )


class DatasetSource(ABC):
    """
    Abstract interface for loading datasets (Single Responsibility & Open/Closed Principle).
    Future formats (e.g. real Module 1 output format, SQLite, database) can be plugged in
    behind this interface without modifying the evaluation runner.
    """

    @abstractmethod
    def load(self) -> List[DatasetPair]:
        """Loads and validates a collection of DatasetPair objects."""
        pass


class JSONDatasetSource(DatasetSource):
    """
    Loads dataset from a JSON file (list of objects or {"pairs": [...]}) or JSONL file.
    Validates each record against DatasetPair schema using Pydantic.
    """

    def __init__(self, file_path: Union[str, Path]) -> None:
        self.file_path = Path(file_path)

    def load(self) -> List[DatasetPair]:
        if not self.file_path.exists():
            raise FileNotFoundError(f"Dataset file not found: {self.file_path}")

        ext = self.file_path.suffix.lower()
        pairs: List[DatasetPair] = []

        if ext == ".jsonl":
            with open(self.file_path, "r", encoding="utf-8") as f:
                for idx, line in enumerate(f, start=1):
                    line = line.strip()
                    if not line:
                        continue
                    item = json.loads(line)
                    if isinstance(item, dict) and "pair_id" not in item:
                        item["pair_id"] = f"pair_{idx:03d}"
                    pair = DatasetPair.model_validate(item)
                    pairs.append(pair)
        else:
            with open(self.file_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            raw_list = data.get("pairs", data) if isinstance(data, dict) else data
            if not isinstance(raw_list, list):
                raise ValueError(
                    f"Invalid JSON format in {self.file_path}: expected list of pairs or dict with 'pairs' key."
                )

            for idx, item in enumerate(raw_list, start=1):
                if isinstance(item, dict) and "pair_id" not in item:
                    item["pair_id"] = f"pair_{idx:03d}"
                pair = DatasetPair.model_validate(item)
                pairs.append(pair)

        return pairs


class InMemoryDatasetSource(DatasetSource):
    """In-memory dataset source for programmatic execution and fast unit testing."""

    def __init__(self, pairs: List[DatasetPair]) -> None:
        self._pairs = pairs

    def load(self) -> List[DatasetPair]:
        return list(self._pairs)


def save_dataset_json(pairs: List[DatasetPair], path: Union[str, Path], indent: int = 2) -> None:
    """Helper to persist a list of DatasetPair objects to a JSON file."""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        data = [pair.model_dump(mode="json") for pair in pairs]
        json.dump(data, f, ensure_ascii=False, indent=indent)


def save_dataset_jsonl(pairs: List[DatasetPair], path: Union[str, Path]) -> None:
    """Helper to persist a list of DatasetPair objects to a JSONL file."""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        for pair in pairs:
            f.write(json.dumps(pair.model_dump(mode="json"), ensure_ascii=False) + "\n")
