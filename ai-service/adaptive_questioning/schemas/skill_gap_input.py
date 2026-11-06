"""
Pydantic v2 models matching Module 2 (skill_gap) JSON output contract.
"""

from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field


class SemanticAlignmentType(str, Enum):
    MATCH = "MATCH"
    PARTIAL = "PARTIAL"
    MISSING = "MISSING"


class QuestionStrategyType(str, Enum):
    NONE = "NONE"
    COMPARE_SUBSTITUTE = "COMPARE_SUBSTITUTE"
    PROBE_DEPTH = "PROBE_DEPTH"
    LEARNING_AGILITY = "LEARNING_AGILITY"


class SkillGapInput(BaseModel):
    """Input data contract from Module 2 (`skill_gap`)."""

    model_config = ConfigDict(extra="ignore")

    jd_skill_id: str = Field(..., description="Identifier of the required skill in the JD")
    matched_cv_skill_id: Optional[str] = Field(
        default=None, description="Identifier of the matched skill in the CV"
    )
    semantic_alignment: SemanticAlignmentType = Field(
        default=SemanticAlignmentType.MATCH,
        description="Semantic alignment category (MATCH, PARTIAL, MISSING)",
    )
    is_substituted: bool = Field(
        default=False, description="Whether the skill is substituted by a partial match"
    )
    required_proficiency: float = Field(
        ..., ge=1.0, le=5.0, description="Target JD proficiency s_jd on a 5.0 scale"
    )
    candidate_proficiency: float = Field(
        ..., ge=0.0, le=5.0, description="Estimated CV proficiency s_cv on a 5.0 scale"
    )
    gap_magnitude: float = Field(
        default=0.0, ge=0.0, le=1.0, description="Normalized gap magnitude"
    )
    priority: float = Field(
        default=0.0, ge=0.0, le=1.0, description="Deterministic interview priority score"
    )
    suggested_strategy: QuestionStrategyType = Field(
        default=QuestionStrategyType.NONE,
        description="Suggested adaptive questioning strategy",
    )
    cv_evidence_spans: List[str] = Field(
        default_factory=list, description="Verbatim evidence spans extracted from CV"
    )
    context_job: Optional[str] = Field(
        default=None, description="Job title and timeline context from CV"
    )
