from pydantic import BaseModel, Field
from typing import Optional, List


class CvJdMatchRequest(BaseModel):
    sessionId: str
    forceRefresh: bool = False
    fromSessionId: Optional[str] = ""
    cvText: Optional[str] = ""
    jdText: Optional[str] = ""
    roleTitle: Optional[str] = ""
    jobCategory: Optional[str] = "BACKEND"
    seniorityLevel: Optional[str] = "MID"


class EvidenceItemDto(BaseModel):
    criteria_id: Optional[int] = None
    criteria_name: str
    importance: str = "REQUIRED"
    jd_requirement: Optional[str] = None
    cv_evidence: Optional[str] = None
    status: str = "matched"
    reasoning: Optional[str] = None


class ScoreBreakdownDto(BaseModel):
    raw_must_have_score: int
    must_have_weight_ratio: float = 0.8
    raw_prefer_to_have_score: int
    prefer_to_have_weight_ratio: float = 0.2
    final_score: int


class ImprovementItemDto(BaseModel):
    criteria_name: str
    actionable_advice: str
    priority: str = "1"


class AssessmentResponseSchema(BaseModel):
    session_id: str
    job_category: str = "BACKEND"
    seniority_level: str = "MID"
    overall_match_score: int
    eligibility: str = "ELIGIBILITY"
    gate_evidence_items: List[EvidenceItemDto] = Field(default_factory=list)
    must_have_evidence_items: List[EvidenceItemDto] = Field(default_factory=list)
    prefer_to_have_evidence_items: List[EvidenceItemDto] = Field(default_factory=list)
    score_breakdown: ScoreBreakdownDto
    quick_wins: List[ImprovementItemDto] = Field(default_factory=list)
    skill_gaps: List[ImprovementItemDto] = Field(default_factory=list)
    cached: bool = False
