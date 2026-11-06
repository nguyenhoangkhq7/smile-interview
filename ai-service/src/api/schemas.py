"""
Pydantic v2 API Request & Response Schemas for Module 2 (Skill-Gap Detection) FastAPI Service.
"""

from typing import List, Optional
from pydantic import BaseModel, Field

from src.domain.models import (
    ExtractedCVSkill,
    ExtractedJDSkill,
    MatchResult,
    SkillGapResult,
)
from src.services.report_generator import StaticGapAuditReport


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


class AnalyzeSkillGapResponse(BaseModel):
    """
    Output payload from `POST /api/v1/skill-gap/analyze`.
    The `skills` field matches `StartInterviewRequestWrapper.skills` (`List[SkillGapInput]`)
    of Module 3 (`adaptive_questioning`) 100% without conversion.
    """

    analysis_id: str
    total_skills: int
    skills_requiring_probing: int
    skills: List[SkillGapResult]


class AnalyzeWithReportResponse(BaseModel):
    """Combined output payload from `POST /api/v1/skill-gap/analyze-with-report`."""

    analysis_id: str
    skills: List[SkillGapResult]
    report: StaticGapAuditReport
