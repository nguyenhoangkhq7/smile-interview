"""
Pydantic v2 Contracts for Module 1 (SBERT + GNN Semantic Skill Matching) and End-to-End Pipeline.
"""

from typing import List, Optional
from pydantic import BaseModel, Field

from skill_gap.domain.models import ExtractedCVSkill, ExtractedJDSkill, MatchResult


class MatchPipelineRequest(BaseModel):
    """Input payload for raw CV + JD text analysis."""

    analysis_id: Optional[str] = Field(
        default=None, description="Optional custom session/analysis identifier"
    )
    cv_text: str = Field(..., description="Raw or Markdown candidate resume / CV text")
    jd_text: str = Field(..., description="Raw or Markdown Job Description (JD) text")


class Module1Output(BaseModel):
    """
    Canonical output contract of Module 1 (SBERT + GNN), which serves as the exact
    input contract for Module 2 (`skill_gap`).
    """

    matcher_source: str = "EXTERNAL"
    cv_skills: List[ExtractedCVSkill] = Field(
        default_factory=list, description="Extracted CV skills with verbatim evidence spans"
    )
    jd_skills: List[ExtractedJDSkill] = Field(
        default_factory=list, description="Extracted JD required skills with verbatim evidence spans"
    )
    match_results: List[MatchResult] = Field(
        default_factory=list,
        description="Semantic similarity (soft_match) and GNN importance weights (w_j)",
    )
