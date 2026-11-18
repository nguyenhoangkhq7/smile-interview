"""
Pydantic v2 API Request & Response Schemas for Module 2 (Skill-Gap Detection) FastAPI Service.
"""

from typing import List, Optional
from pydantic import BaseModel, Field

from skill_gap.domain.models import (
    ExtractedCVSkill,
    ExtractedJDSkill,
    MatchResult,
    SkillGapReportSummary,
    SkillGapSummary,
)


class AnalyzeSkillGapRequest(BaseModel):
    """Input payload for Module 2 Skill-Gap Analysis."""

    analysis_id: Optional[str] = Field(
        default=None, description="Optional custom analysis identifier"
    )
    cv_text: str = Field(..., description="Raw candidate resume / CV text")
    jd_text: str = Field(..., description="Raw Job Description (JD) text")
    cv_skills: List[ExtractedCVSkill] = Field(
        default_factory=list, description="Extracted CV skills from Module 1"
    )
    jd_skills: List[ExtractedJDSkill] = Field(
        default_factory=list, description="Extracted JD skills from Module 1"
    )
    match_results: List[MatchResult] = Field(
        default_factory=list, description="Semantic match and GNN importance weights from Module 1"
    )


class AnalyzeWithReportResponse(BaseModel):
    """Skill Gap results and the analysis status used by the application."""

    analysis_id: str
    skills: List[SkillGapSummary]
    report: SkillGapReportSummary
