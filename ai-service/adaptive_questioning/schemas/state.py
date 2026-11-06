"""
Pydantic v2 state models for Pipeline V2.2 Adaptive Questioning sessions.
"""

from enum import Enum
from typing import Dict, List, Literal, Optional
from pydantic import BaseModel, Field

from adaptive_questioning.config import T_MAX
from adaptive_questioning.schemas.skill_gap_input import SkillGapInput


class MetamorphicTag(str, Enum):
    INVARIANT = "INVARIANT"
    MINOR_SHIFT = "MINOR_SHIFT"
    MODERATE_SHIFT = "MODERATE_SHIFT"
    DECISIVE_SHIFT = "DECISIVE_SHIFT"


class RubricLevel(str, Enum):
    LOW = "Low"
    MED = "Med"
    HIGH = "High"


class SubSlot(BaseModel):
    """Temporary probing sub-slot created dynamically during Abductive CoT (k >= 2)."""

    slot_id: str = Field(..., description="Unique identifier for the probing sub-slot")
    slot_name: str = Field(..., description="Short name of the probing dimension")
    description: str = Field(..., description="Description of the technical gap/hypothesis being probed")
    value: Optional[str] = Field(default=None, description="Extracted technical evidence from candidate answer")
    filled: bool = Field(default=False, description="Whether this sub-slot has been filled")


class ContextAnchor(BaseModel):
    """Context Anchor in A_ctx used for natural topic bridging and 1-line memory consolidation."""

    jd_skill_id: str = Field(..., description="Skill identifier")
    candidate_proficiency: float = Field(..., description="Initial or verified proficiency score")
    context_job: Optional[str] = Field(default=None, description="Associated job role and timeline")
    consolidated_summary: Optional[str] = Field(
        default=None, description="1-sentence verified finding appended upon skill completion"
    )
    source: Literal["INITIAL_NONE", "VERIFIED_CONSOLIDATION"] = Field(
        default="INITIAL_NONE", description="Origin of this context anchor"
    )


class AbductiveReasoning(BaseModel):
    """Abductive Chain-of-Thought (C -> A) reasoning trace."""

    surprising_fact_C: str = Field(
        ..., description="Observed discrepancy C_0 or C_{t-1} triggering the probe"
    )
    hypothesis_A: str = Field(
        ..., description="Inferred hidden cause / hypothesis A_0 or A_{t-1}"
    )


class TurnLog(BaseModel):
    """Audit record for a single dialogue turn."""

    turn: int = Field(..., description="Global turn index t (1-based)")
    local_turn: int = Field(..., description="Local turn index k (1..k_max) on the active skill")
    skill_id: str = Field(..., description="Evaluated primary skill ID d*")
    target_slot_id: str = Field(..., description="Target slot or sub-slot ID probed in this turn")
    abductive_reasoning: AbductiveReasoning = Field(
        ..., description="Abductive CoT (C -> A) generated at Step 2A"
    )
    question: str = Field(..., description="Adaptive question generated at Step 2A")
    candidate_response: Optional[str] = Field(
        default=None, description="Candidate response x_t submitted at Step 2B"
    )
    extracted_slot_value: Optional[str] = Field(
        default=None, description="Technical evidence extracted into the active slot"
    )
    reflective_insight: Optional[str] = Field(
        default=None, description="1-2 sentence Judge justification against Rubric centroids"
    )
    metamorphic_tag: Optional[MetamorphicTag] = Field(
        default=None, description="Metamorphic Relation classification bounding TV shift"
    )
    previous_belief: List[float] = Field(
        ..., description="Belief distribution P_{t-1} over [Low, Med, High]"
    )
    raw_posterior_belief: Optional[List[float]] = Field(
        default=None, description="Normalized raw posterior P_t^raw proposed by Judge"
    )
    updated_belief: Optional[List[float]] = Field(
        default=None, description="Calibrated posterior P_t after Simplex Convex Interpolation"
    )
    tv_raw: Optional[float] = Field(
        default=None, description="Raw Total Variation distance TV(P_t^raw, P_{t-1})"
    )
    alpha_t: Optional[float] = Field(
        default=None, description="Bounded convex interpolation weight alpha_t in [0, 1]"
    )
    tv_delta: Optional[float] = Field(
        default=None, description="Actual Total Variation shift TV(P_t, P_{t-1})"
    )
    skill_verified_after_turn: bool = Field(
        default=False, description="Whether primary skill d* reached VERIFIED after this turn"
    )
    verification_reason: Optional[str] = Field(
        default=None, description="Router condition that triggered verification"
    )


class SkillBeliefState(BaseModel):
    """Belief trajectory and slot state for a single primary skill in Q_primary."""

    jd_skill_id: str
    matched_cv_skill_id: Optional[str] = None
    semantic_alignment: str = "MATCH"
    is_substituted: bool = False
    required_proficiency: float = Field(..., description="Target difficulty anchor r_target = s_jd")
    candidate_proficiency: float = Field(..., description="Initial CV proficiency s_cv")
    gap_magnitude: float = 0.0
    priority: float = 0.0
    suggested_strategy: str = "PROBE_DEPTH"
    cv_evidence_spans: List[str] = Field(default_factory=list)
    context_job: Optional[str] = None

    prior_belief: List[float] = Field(..., description="Prior belief B_0 = [P_0(Low), P_0(Med), P_0(High)]")
    current_belief: List[float] = Field(..., description="Current posterior belief P_t")
    belief_trajectory: List[List[float]] = Field(
        default_factory=list, description="Sequence of belief vectors B_{0:t}"
    )

    local_turn_k: int = Field(default=0, description="Number of questions asked for this skill")
    primary_slot_value: Optional[str] = Field(
        default=None, description="Evidence collected for the primary competency slot"
    )
    active_sub_slots: List[SubSlot] = Field(
        default_factory=list,
        description="Active temporary probing sub-slots (purged on verification via GC)",
    )
    archived_sub_slots: List[SubSlot] = Field(
        default_factory=list,
        description="Audit archive of sub-slots preserved for Phase 4 HITL reporting after GC",
    )

    is_verified: bool = Field(default=False, description="Whether skill has been verified")
    verification_reason: Optional[str] = Field(
        default=None, description="Reason for verification (Condition 1, 2, or 3)"
    )
    consolidated_finding: Optional[str] = Field(
        default=None, description="1-sentence consolidated finding moved to A_ctx"
    )


class InterviewSessionState(BaseModel):
    """Complete state of an adaptive questioning session."""

    session_id: str
    turn_t: int = Field(default=0, description="Current global turn counter t")
    total_initial_d: int = Field(
        ..., description="Constant denominator D = |Q_primary| fixed at Phase 1"
    )
    d_verified: int = Field(default=0, description="Count of verified primary skills D_verified")
    t_max: int = Field(default=T_MAX, description="Maximum allowed global turns T_max")

    primary_queue: List[str] = Field(
        default_factory=list, description="Active queue Q_primary of unverified skill IDs"
    )
    initial_primary_order: List[str] = Field(
        default_factory=list, description="Initial priority-sorted order of primary skills"
    )
    active_skill_id: Optional[str] = Field(
        default=None, description="Currently probed primary skill d*"
    )

    skills: Dict[str, SkillBeliefState] = Field(
        default_factory=dict, description="Map of primary skill_id -> SkillBeliefState"
    )
    all_input_skills: List[SkillGapInput] = Field(
        default_factory=list, description="All input skill gap records from Module 2"
    )
    context_anchors: List[ContextAnchor] = Field(
        default_factory=list, description="Bridging context and consolidated findings A_ctx"
    )

    pending_turn_log: Optional[TurnLog] = Field(
        default=None, description="Current open turn awaiting candidate response"
    )
    turn_history: List[TurnLog] = Field(
        default_factory=list, description="Completed turn logs across the interview"
    )

    is_finished: bool = Field(default=False, description="Whether the interview has terminated")
    termination_reason: Optional[str] = Field(
        default=None, description="Reason why the interview terminated"
    )
