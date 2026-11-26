from abc import ABC, abstractmethod
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field

from skill_gap.domain.enums import SemanticAlignment
from skill_gap.domain.models import ExtractedCVSkill, ExtractedJDSkill, MatchResult


class BaselineOutputField(str, Enum):
    """
    Enumeration of output fields that can be produced by evaluation baselines.
    Used to track which outputs each baseline produces without filling missing ones with fake values.
    """
    ALIGNMENT = "semantic_alignment"
    P_JD = "required_proficiency"
    P_CV = "candidate_proficiency"
    GAP_MAGNITUDE = "gap_magnitude"
    PRIORITY = "priority"


class BaselineInput(BaseModel):
    """
    Immutable input contract for all baselines and evaluation runners.
    Matches exactly the 5 arguments received by SkillGapOrchestrator.run_pipeline:
    (cv_text, jd_text, cv_skills, jd_skills, match_results).
    """
    model_config = ConfigDict(frozen=True)

    cv_text: str
    jd_text: str
    cv_skills: List[ExtractedCVSkill]
    jd_skills: List[ExtractedJDSkill]
    match_results: List[MatchResult]


class BaselineSkillResult(BaseModel):
    """
    Standardized per-skill output structure for evaluation across all baselines.
    Any field that a baseline cannot compute MUST remain None (do not fabricate values).
    """
    jd_skill_id: str
    semantic_alignment: Optional[SemanticAlignment] = None
    required_proficiency: Optional[float] = Field(default=None, ge=1.0, le=5.0)
    candidate_proficiency: Optional[float] = Field(default=None, ge=1.0, le=5.0)
    gap_magnitude: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    priority: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class BaselineMethod(ABC):
    """
    Abstract base interface for all competitive baselines, reference checks,
    and pipeline adapters.
    Follows Liskov Substitution Principle (LSP): any baseline can be substituted into the runner.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique identifier of the baseline."""
        pass

    @property
    @abstractmethod
    def produces(self) -> frozenset[BaselineOutputField]:
        """Set of output fields actively produced by this baseline."""
        pass

    @property
    def requires_llm(self) -> bool:
        """Indicates whether this baseline requires an LLM call. Defaults to False."""
        return False

    @property
    def estimated_llm_calls_per_pair(self) -> int:
        """Estimated number of LLM invocations per input pair. Defaults to 0."""
        return 0

    @abstractmethod
    def run(self, input_data: BaselineInput) -> List[BaselineSkillResult]:
        """
        Execute baseline evaluation on the standardized input.
        Returns a list of BaselineSkillResult matching the skills in input_data.
        """
        pass

