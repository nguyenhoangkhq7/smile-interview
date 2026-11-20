"""Internal snapshots and public contracts for evidence interviewing V2."""
from datetime import datetime
from enum import Enum
from typing import Literal, TypedDict

from pydantic import BaseModel, ConfigDict, Field, model_validator

from skill_gap.domain.models import JobTask
from .policy_config import InterviewPolicy


class GroundedRequirement(TypedDict):
    skill_id: str
    description: str
    required_proficiency: float
    inferred: bool
    has_task: bool
    requirement_kind: Literal["REQUIRED", "OPTIONAL", "UNSPECIFIED"]
    jd_evidence_spans: list[str]


class Mode(str, Enum):
    CODING = "CODING"
    DEBUGGING = "DEBUGGING"
    DESIGN = "DESIGN"
    TECHNICAL_EXPLANATION = "TECHNICAL_EXPLANATION"
    BEHAVIORAL = "BEHAVIORAL"


class Assessment(str, Enum):
    NOT_ASSESSED = "NOT_ASSESSED"
    INSUFFICIENT = "INSUFFICIENT_EVIDENCE"
    NOT_DEMONSTRATED = "NOT_DEMONSTRATED"
    BELOW = "DEMONSTRATED_BELOW_TARGET"
    AT = "DEMONSTRATED_AT_TARGET"
    ABOVE = "DEMONSTRATED_ABOVE_TARGET"


class Action(str, Enum):
    INITIAL = "INITIAL"
    CLARIFY = "CLARIFY"
    FOLLOW_UP = "FOLLOW_UP"
    DEEPER = "PROBE_DEEPER"
    EASIER = "ASK_EASIER"
    VERIFY = "VERIFY_CONTRADICTION"


class InterviewConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    interaction_mode: Literal["TEXT", "VOICE"] = "TEXT"
    mode: Literal["MIXED", "FOCUSED"] = "MIXED"
    focused_question_mode: Mode | None = None
    max_questions: int = Field(default=10, ge=1, le=40)
    duration_seconds: int = Field(default=900, ge=60, le=7200)
    max_questions_per_objective: int = Field(default=8, ge=1, le=40)

    @model_validator(mode="before")
    @classmethod
    def infer_mode(cls, values: object) -> object:
        if isinstance(values, dict) and "mode" not in values and values.get("focused_question_mode") is not None:
            return {**values, "mode": "FOCUSED"}
        return values

    @model_validator(mode="after")
    def validate_mode(self):
        if (self.mode == "FOCUSED") != (self.focused_question_mode is not None):
            raise ValueError("FOCUSED requires a mode; MIXED must not specify one")
        return self


class InterviewSkillContext(BaseModel):
    """Skill data needed after the interview plan is ready."""

    model_config = ConfigDict(extra="forbid")

    jd_skill_id: str = Field(..., description="Identifier of the required skill in the JD")
    jd_skill_name: str = Field(default="", max_length=200)
    matched_cv_skill_name: str = Field(default="", max_length=200)
    semantic_alignment: str = Field(default="", max_length=60)
    context_job: str = Field(default="", max_length=300)
    cv_evidence_spans: list[str] = Field(default_factory=list)


class InterviewSkill(InterviewSkillContext):
    model_config = ConfigDict(extra="ignore")
    required_proficiency: float = Field(..., ge=1.0, le=5.0)
    priority: float = Field(default=0.0, ge=0.0, le=1.0)
    importance_weight: float = Field(default=0.0, ge=0.0, le=1.0)
    jd_evidence_spans: list[str] = Field(default_factory=list)
    job_tasks: list[JobTask] = Field(default_factory=list)


class CriterionDraft(BaseModel):
    description: str = Field(min_length=3)
    expected_evidence: str = Field(min_length=3)
    below_target: str = Field(min_length=3)
    at_target: str = Field(min_length=3)
    above_target: str = Field(min_length=3)
    essential: bool = True


class Criterion(CriterionDraft):
    criterion_id: str = ""


class SuitableMode(BaseModel):
    model_config = ConfigDict(extra="forbid")
    mode: Mode
    criterion_indices: list[int] = Field(default_factory=list)


class ObjectiveDraft(BaseModel):
    requirement_id: str
    skill_id: str
    target_depth: int = Field(default=2, ge=1, le=4)
    depth_basis: str = "UNSPECIFIED"
    depth_rationale: str = ""
    depth_evidence_spans: list[str] = Field(default_factory=list)
    extension_depth: int | None = Field(default=None, ge=2, le=4)
    criteria: list[CriterionDraft] = Field(min_length=1, max_length=5)
    suitable_modes: list[SuitableMode] = Field(min_length=1)
    estimated_seconds: int = Field(default=120, ge=30, le=1800)


class BlueprintDraft(BaseModel):
    objectives: list[ObjectiveDraft] = Field(min_length=1, max_length=100)


class Objective(ObjectiveDraft):
    model_config = ConfigDict(extra="forbid")
    objective_id: str = ""
    claim: str = Field(min_length=3)
    requirement_kind: Literal["REQUIRED", "OPTIONAL", "UNSPECIFIED"] = "UNSPECIFIED"
    criteria: list[Criterion] = Field(min_length=1, max_length=5)
    jd_evidence_spans: list[str] = Field(default_factory=list)


class Blueprint(BaseModel):
    objectives: list[Objective] = Field(min_length=1, max_length=100)


class Observation(BaseModel):
    criterion_id: str
    response_excerpt: str = ""
    response_line_range: tuple[int, int] | None = Field(
        default=None, description="Optional inclusive 1-based range in answer_lines; server copies the original lines as evidence")
    observation: Literal["SUPPORTS", "CONTRADICTS", "UNCLEAR", "NO_EVIDENCE"]
    performance: Literal["BELOW", "AT_TARGET", "ABOVE", "UNDETERMINED"]
    rationale: str = Field(min_length=3)
    resolves_contradiction: bool = False
    unresolved_aspects: list[str] = Field(default_factory=list)


class _EvidenceBase(BaseModel):
    turn_id: str
    criterion_id: str
    response_excerpt: str = ""
    performance: Literal["BELOW", "AT_TARGET", "ABOVE", "UNDETERMINED"]
    rationale: str = Field(min_length=3)


class PublicEvidence(_EvidenceBase):
    depth_role: Literal["TARGET", "DIAGNOSTIC", "EXTENSION"] = "TARGET"
    observation: Literal["SUPPORTS", "CONTRADICTS", "UNCLEAR", "NO_EVIDENCE"] = "SUPPORTS"


class SessionCoaching(BaseModel):
    overall_summary: str = Field(min_length=5, max_length=1200)
    top_strengths: list[str] = Field(default_factory=list, max_length=6)
    priority_gaps: list[str] = Field(default_factory=list, max_length=6)
    actionable_study_steps: list[str] = Field(default_factory=list, max_length=6)


class PriorAttemptContext(BaseModel):
    objective_assessments: dict[str, str] = Field(default_factory=dict)
    mastered_skill_ids: set[str] = Field(default_factory=set)
    prior_question_stems: list[str] = Field(default_factory=list, max_length=20)


class RecordedEvidence(_EvidenceBase):
    model_config = ConfigDict(extra="forbid")
    observation: Literal["SUPPORTS", "CONTRADICTS", "UNCLEAR", "NO_EVIDENCE"]
    question_depth: int = Field(ge=1, le=4)
    evidence_scope: str = ""
    independent: bool = True
    explicit_inability: bool = False


class Judgment(BaseModel):
    observations: list[Observation]
    feedback: str
    explicit_inability: bool = False
    inability_excerpt: str = ""
    feedback_contains_hint: bool = False


class StoredQuestion(BaseModel):
    model_config = ConfigDict(extra="forbid")
    text: str = Field(min_length=10)
    criterion_ids: list[str] = Field(min_length=1)
    evidence_scope: str = ""


class Question(StoredQuestion):
    """Generator output with the metadata needed to validate the draft."""

    mode: Mode | None = None
    depth: int | None = Field(default=None, ge=1, le=4)


class CriterionProgress(BaseModel):
    turns_spent: int = 0
    clarification_spent: bool = False
    easier_spent: bool = False
    deeper_spent: bool = False
    stagnant_turns: int = 0
    unresolved_aspects: list[str] = Field(default_factory=list)
    stop_reason: str | None = None
    observed_cases: list[str] = Field(default_factory=list)


class ObjectiveState(BaseModel):
    model_config = ConfigDict(extra="forbid")
    objective: Objective
    selected_mode: Mode | None = None
    excluded_reason: str | None = None
    lifecycle: Literal["PLANNED", "ACTIVE", "CLOSED", "EXCLUDED"] = "PLANNED"
    assessment: Assessment = Assessment.NOT_ASSESSED
    stop_reason: str | None = None
    turns_spent: int = 0
    evidence_history: list[RecordedEvidence] = Field(default_factory=list)
    assisted_criteria: list[str] = Field(default_factory=list)
    criterion_results: dict[str, RecordedEvidence] = Field(default_factory=dict)
    contradictions: list[str] = Field(default_factory=list)
    criterion_progress: dict[str, CriterionProgress] = Field(default_factory=dict)
    active_criterion_id: str | None = None
    probe_reason: str = "Initial evidence for an essential criterion"


class VerificationSources(BaseModel):
    model_config = ConfigDict(extra="forbid")
    cv: dict[str, str] = Field(default_factory=dict)
    jd: dict[str, str] = Field(default_factory=dict)


class VerificationFocus(BaseModel):
    model_config = ConfigDict(extra="forbid")
    cv_excerpt: str
    detail_to_verify: str
    jd_excerpt: str | None = None


class InterviewVerification(BaseModel):
    model_config = ConfigDict(extra="forbid")
    jd_by_objective: dict[str, str] = Field(default_factory=dict)
    focus_by_criterion: dict[str, VerificationFocus] = Field(default_factory=dict)


class VerificationFocusDraft(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    criterion_id: str = Field(min_length=1)
    cv_span_index: int = Field(ge=0, strict=True)
    jd_span_index: int | None = Field(default=None, ge=0, strict=True)
    detail_to_verify: str = Field(min_length=3, max_length=240)


class VerificationBatchDraft(BaseModel):
    model_config = ConfigDict(extra="forbid")
    focuses: list[VerificationFocusDraft]


class Turn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    turn_id: str
    objective_id: str
    skill_id: str
    mode: Mode
    action: Action
    question_depth: int = Field(ge=1, le=4)
    question: StoredQuestion
    answer: str | None = None
    judgment: Judgment | None = None
    introduction: str = ""


class Snapshot(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: Literal[2] = 2
    session_id: str
    state_version: int = 0
    config: InterviewConfig
    policy: InterviewPolicy = Field(default_factory=InterviewPolicy)
    skills: list[InterviewSkillContext]
    objectives: dict[str, ObjectiveState]
    queue: list[str]
    deadline_at: datetime
    verification: InterviewVerification | None = None
    pending_turn: Turn | None = None
    next_question_action: Action | None = None
    turns: list[Turn] = Field(default_factory=list)
    is_finished: bool = False
    termination_reason: str | None = None
    conversation: "ConversationState | None" = None
    opening_context: "InterviewOpening | None" = None
    coaching: SessionCoaching | None = None
    prior_question_stems: list[str] = Field(default_factory=list)


_RETIRED_OBJECTIVE_FIELDS = frozenset({
    "required_proficiency",
    "extension_criterion_ids",
    "inferred",
    "rubric_version",
    "rubric_fingerprint",
})
_RETIRED_SUITABLE_MODE_FIELDS = frozenset({"rationale"})


def _strip_retired_objective_fields(objective: object) -> object:
    if not isinstance(objective, dict):
        return objective
    cleaned = {k: v for k, v in objective.items() if k not in _RETIRED_OBJECTIVE_FIELDS}
    modes = cleaned.get("suitable_modes")
    if isinstance(modes, list):
        cleaned["suitable_modes"] = [
            {k: v for k, v in mode.items() if k not in _RETIRED_SUITABLE_MODE_FIELDS}
            if isinstance(mode, dict) else mode
            for mode in modes
        ]
    return cleaned


def _strip_retired_blueprint_fields(blueprint: object) -> object:
    if not isinstance(blueprint, dict):
        return blueprint
    objectives = blueprint.get("objectives")
    if not isinstance(objectives, list):
        return blueprint
    return {**blueprint, "objectives": [_strip_retired_objective_fields(obj) for obj in objectives]}


class StartRequest(BaseModel):
    session_id: str
    skills: list[InterviewSkill] = Field(min_length=1, max_length=100)
    config: InterviewConfig = Field(default_factory=InterviewConfig)
    blueprint: Blueprint | None = None
    opening: "InterviewOpening | None" = None
    prior_attempts: PriorAttemptContext | None = None
    verification_sources: VerificationSources | None = None

    @model_validator(mode="before")
    @classmethod
    def sanitize_legacy_blueprint(cls, values: object) -> object:
        """Drop retired rubric metadata from persisted blueprints while keeping strict validation elsewhere."""
        if isinstance(values, dict) and isinstance(values.get("blueprint"), dict):
            return {**values, "blueprint": _strip_retired_blueprint_fields(values["blueprint"])}
        return values


class BlueprintRequest(BaseModel):
    skills: list[InterviewSkill] = Field(min_length=1, max_length=100)
    opening: "InterviewOpening | None" = None


MAX_OPENING_SUMMARY_LENGTH = 2000
MAX_DIALOGUE_TEXT_LENGTH = 1500


class ConversationOpening(BaseModel):
    model_config = ConfigDict(extra="forbid")
    interviewer_name: str = Field(default="Minh", max_length=100)
    company: str = Field(default="", max_length=200)


class InterviewOpening(ConversationOpening):
    role_title: str = Field(default="vị trí ứng tuyển", max_length=200)
    candidate_name: str = Field(default="", max_length=150)
    jd_summary: str = Field(default="", max_length=MAX_OPENING_SUMMARY_LENGTH)
    cv_summary: str = Field(default="", max_length=MAX_OPENING_SUMMARY_LENGTH)
    attempt_number: int | None = Field(default=None, ge=1, le=1000)


class DialogueMessage(BaseModel):
    text: str = Field(min_length=15, max_length=MAX_DIALOGUE_TEXT_LENGTH)


class ConversationMessage(BaseModel):
    message_id: str
    text: str


class ConversationState(BaseModel):
    model_config = ConfigDict(extra="forbid")
    phase: Literal["OPENING", "SELF_INTRODUCTION", "INTERVIEW", "CLOSING", "FINISHED"]
    message: ConversationMessage
    opening: ConversationOpening
    expires_at: datetime
    introduction: str = ""
    opening_text: str = ""


class ConversationRequest(BaseModel):
    snapshot: Snapshot
    message_id: str
    expected_state_version: int
    action: Literal["NEXT", "SUBMIT_INTRODUCTION", "SKIP_INTRODUCTION"]
    introduction: str = Field(default="", max_length=10000)
    defer_question: bool = False


class TransitionRequest(BaseModel):
    snapshot: Snapshot
    turn_id: str
    expected_state_version: int
    candidate_response: str = Field(min_length=1, max_length=50000)
    defer_question: bool = False


class NextQuestionRequest(BaseModel):
    snapshot: Snapshot
    expected_state_version: int


class CriterionReport(BaseModel):
    criterion_id: str
    description: str
    assessment: Assessment


class ObjectiveReport(BaseModel):
    objective_id: str
    skill_id: str
    claim: str
    jd_evidence_spans: list[str]
    assessment: Assessment
    stop_reason: str | None
    strengths: list[str]
    weaknesses: list[str]
    study_recommendations: list[str] = Field(default_factory=list)
    evidence: list[PublicEvidence]
    criteria: list[CriterionReport] = Field(default_factory=list)


class Report(BaseModel):
    termination_reason: str | None
    objectives: list[ObjectiveReport]
    coaching: SessionCoaching | None = None


class PendingTurn(BaseModel):
    turn_id: str
    objective_id: str
    mode: Mode
    question: str
    introduction: str = ""


class PublicTurn(BaseModel):
    turn_id: str
    objective_id: str
    mode: Mode
    question: str
    answer: str | None
    feedback: str | None


class PublicSession(BaseModel):
    schema_version: Literal[2] = 2
    session_id: str
    state_version: int
    is_finished: bool
    deadline_at: datetime
    config: InterviewConfig
    pending_turn: PendingTurn | None
    awaiting_question: bool = False
    turns: list[PublicTurn]
    report: Report
    conversation: ConversationState | None = None


class TransitionResult(BaseModel):
    snapshot: Snapshot
    public: PublicSession
