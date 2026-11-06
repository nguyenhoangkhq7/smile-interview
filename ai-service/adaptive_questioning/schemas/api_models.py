"""
FastAPI request/response schemas and Structured LLM Output schemas (DSPy-style declarative signatures).
"""

from typing import List, Optional, Union
from pydantic import BaseModel, Field

from adaptive_questioning.schemas.skill_gap_input import SkillGapInput
from adaptive_questioning.schemas.state import (
    AbductiveReasoning,
    ContextAnchor,
    MetamorphicTag,
    RubricLevel,
    SubSlot,
    TurnLog,
)


# ---------------------------------------------------------------------------
# Structured LLM Output Schemas (Step 2A & Step 2B)
# ---------------------------------------------------------------------------

class ProposedSubSlot(BaseModel):
    """Temporary probing sub-slot proposed at local turn k in {2, 3}."""

    slot_name: str = Field(..., description="Short snake_case or descriptive name of the sub-slot")
    description: str = Field(
        ..., description="Specific technical aspect to probe to resolve the hypothesis"
    )


class Step2AQuestionOutput(BaseModel):
    """Declarative Output Layer schema for Step 2A (Abductive CoT & 3-Layer Question Generator)."""

    surprising_fact_C: str = Field(
        ...,
        description="Observed Surprising Fact C_0 (at k=1) or C_{t-1} (at k>=2) from CV/dialogue discrepancy",
    )
    hypothesis_A: str = Field(
        ...,
        description="Abductive Hypothesis A_0 or A_{t-1} explaining the hidden cause of C",
    )
    new_sub_slot: Optional[ProposedSubSlot] = Field(
        default=None,
        description="Optional temporary Probing Sub-slot (only at k>=2, max 1 per turn, max 2 per skill)",
    )
    target_slot_id: str = Field(
        ...,
        description="ID of the active primary slot or sub-slot targeted by this question",
    )
    question: str = Field(
        ...,
        description="Single concrete Vietnamese technical question adhering to One-Question-One-Answer and Show-Don't-Tell",
    )


class Step2BJudgeOutput(BaseModel):
    """Declarative Output Layer schema for Step 2B (Reflective Metamorphic PBA Judge)."""

    extracted_slot_value: Optional[str] = Field(
        default=None,
        description="Specific technical evidence extracted from candidate answer x_t to fill the active slot",
    )
    reflective_insight: str = Field(
        ...,
        description="Concise 1-2 sentence evaluation against Rubric centroids [1.5, 3.0, 4.5] BEFORE assigning probabilities",
    )
    metamorphic_tag: MetamorphicTag = Field(
        ...,
        description="Metamorphic Relation classification (INVARIANT, MINOR_SHIFT, MODERATE_SHIFT, DECISIVE_SHIFT)",
    )
    raw_posterior_probs: List[float] = Field(
        ...,
        min_length=3,
        max_length=3,
        description="Proposed posterior probability vector [P(Low), P(Med), P(High)]",
    )
    consolidated_summary: str = Field(
        ...,
        description="Concise 1-sentence verified finding summarizing candidate's demonstrated competency for A_ctx memory consolidation",
    )


# ---------------------------------------------------------------------------
# FastAPI Endpoint Request & Response Schemas
# ---------------------------------------------------------------------------

class StartInterviewRequestWrapper(BaseModel):
    """Optional wrapper object containing the Module 2 JSON array."""

    skills: List[SkillGapInput] = Field(..., description="List of skill gap records from Module 2")


StartInterviewPayload = Union[List[SkillGapInput], StartInterviewRequestWrapper]


class StartInterviewResponse(BaseModel):
    """Response schema for POST /api/v1/interview/start."""

    session_id: str
    turn: int
    active_skill_id: Optional[str] = None
    initial_belief: List[float] = Field(default_factory=list)
    abductive_reasoning: Optional[AbductiveReasoning] = None
    question: Optional[str] = None
    is_finished: bool


class RespondInterviewRequest(BaseModel):
    """Request schema for POST /api/v1/interview/respond."""

    session_id: str
    candidate_response: str


class RespondInterviewResponse(BaseModel):
    """Response schema for POST /api/v1/interview/respond."""

    session_id: str
    turn: int
    evaluated_skill_id: str
    previous_belief: List[float]
    updated_belief: List[float]
    tv_delta: float
    metamorphic_tag: MetamorphicTag
    reflective_insight: str
    skill_verified: bool
    active_skill_id: Optional[str] = None
    next_question: Optional[str] = None
    completion_rate: float
    is_finished: bool


# ---------------------------------------------------------------------------
# Phase 4: Auditable HITL Report Schemas
# ---------------------------------------------------------------------------

class SkillAuditReportItem(BaseModel):
    """Phase 4 per-skill Auditable HITL evaluation record."""

    jd_skill_id: str
    matched_cv_skill_id: Optional[str] = None
    suggested_strategy: str
    initial_cv_proficiency: float = Field(..., description="Initial s_cv from Module 2")
    verified_proficiency: float = Field(
        ..., description="Expected proficiency s_hat_final = 1.5*P(Low) + 3.0*P(Med) + 4.5*P(High)"
    )
    required_jd_proficiency: float = Field(..., description="Target s_jd from Module 2")
    verified_skill_gap: float = Field(
        ..., description="max(0.0, s_jd - s_hat_final)"
    )
    map_rubric_level: RubricLevel = Field(
        ..., description="arg max_{l in {Low, Med, High}} P_T(l)"
    )
    is_verified: bool
    verification_reason: Optional[str] = None
    local_turns_spent: int
    prior_belief: List[float]
    final_belief: List[float]
    belief_trajectory: List[List[float]] = Field(
        ..., description="Full belief trajectory B_{0:T} for this skill"
    )
    metamorphic_tags: List[MetamorphicTag] = Field(
        default_factory=list, description="Sequence of Metamorphic Tags assigned across turns"
    )
    judge_justifications: List[str] = Field(
        default_factory=list, description="Sequence of Judge reflective insights across turns"
    )
    primary_slot_value: Optional[str] = None
    filled_sub_slots: List[SubSlot] = Field(
        default_factory=list, description="Sub-slots created and filled before GC"
    )
    consolidated_finding: Optional[str] = None


class HITLReportResponse(BaseModel):
    """Response schema for GET /api/v1/interview/report/{session_id}."""

    session_id: str
    is_finished: bool
    termination_reason: Optional[str] = None
    total_turns: int
    total_initial_primary_skills: int
    verified_primary_skills: int
    completion_rate: float
    evaluated_skills: List[SkillAuditReportItem]
    consolidated_context_anchors: List[ContextAnchor]
    turn_audit_trail: List[TurnLog]
    markdown_summary: str
