"""Pydantic contract for matching_cv output consumed by skill_gap."""

from typing import List, Optional

from pydantic import BaseModel, Field

from skill_gap.domain.models import ExtractedCVSkill, ExtractedJDSkill, MatchResult


class MatchPipelineRequest(BaseModel):
    analysis_id: Optional[str] = None
    cv_text: str
    jd_text: str


class Module1Output(BaseModel):
    matcher_source: str = "EXTERNAL"
    cv_skills: List[ExtractedCVSkill] = Field(default_factory=list)
    jd_skills: List[ExtractedJDSkill] = Field(default_factory=list)
    match_results: List[MatchResult] = Field(default_factory=list)
