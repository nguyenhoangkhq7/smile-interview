"""Internal snapshots and public contracts for evidence interviewing V2."""
from datetime import datetime
from enum import Enum
from typing import Literal, TypedDict

from pydantic import BaseModel, ConfigDict, Field, model_validator

from adaptive_questioning.schemas.skill_gap_input import SkillGapInput
from skill_gap.domain.models import JobTask
from .policy_config import InterviewPolicy

VERSION = "evidence-2.0"


class GroundedRequirement(TypedDict):
    requirement_id: str
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

    @model_validator(mode="after")
    def validate_mode(self):
        if (self.mode == "FOCUSED") != (self.focused_question_mode is not None):
            raise ValueError("FOCUSED requires a mode; MIXED must not specify one")
        return self


class InterviewSkill(SkillGapInput):
    importance_weight: float = Field(default=0, ge=0, le=1)
    jd_reasoning: str = ""
    jd_evidence_spans: list[str] = Field(default_factory=list)
    job_tasks: list[JobTask] = Field(default_factory=list)
    c_evidence: float = Field(default=0, ge=0, le=1)
    recency_flag: bool = False
    degraded: bool = False
    flags: list[str] = Field(default_factory=list)


class Criterion(BaseModel):
    criterion_id: str = ""
    description: str = Field(min_length=3)
    expected_evidence: str = Field(min_length=3)
    below_target: str = Field(min_length=3)
    at_target: str = Field(min_length=3)
    above_target: str = Field(min_length=3)
    essential: bool = True


class SuitableMode(BaseModel):
    mode: Mode
    rationale: str = Field(min_length=3)
    criterion_indices: list[int] = Field(default_factory=list)


class Objective(BaseModel):
    objective_id: str = ""
    requirement_id: str
    skill_id: str
    claim: str = Field(min_length=3)
    required_proficiency: float = Field(ge=1, le=5)
    target_depth: int = Field(default=2, ge=1, le=4)
    depth_basis: str = "LEGACY_UNSPECIFIED"
    depth_rationale: str = "Depth was not specified in the original V2 snapshot"
    depth_evidence_spans: list[str] = Field(default_factory=list)
    requirement_kind: Literal["REQUIRED", "OPTIONAL", "UNSPECIFIED"] = "UNSPECIFIED"
    extension_depth: int | None = Field(default=None, ge=2, le=4)
    extension_criterion_ids: list[str] = Field(default_factory=list)
    criteria: list[Criterion] = Field(min_length=1, max_length=5)
    suitable_modes: list[SuitableMode] = Field(min_length=1)
    estimated_seconds: int = Field(default=120, ge=30, le=1800)
    inferred: bool = False
    jd_evidence_spans: list[str] = Field(default_factory=list)
    rubric_version: Literal["evidence-2.0"] = VERSION
    rubric_fingerprint: str = ""


class Blueprint(BaseModel):
    objectives: list[Objective] = Field(min_length=1, max_length=100)


class Observation(BaseModel):
    criterion_id: str
    response_excerpt: str = ""
    observation: Literal["SUPPORTS", "CONTRADICTS", "UNCLEAR", "NO_EVIDENCE"]
    performance: Literal["BELOW", "AT_TARGET", "ABOVE", "UNDETERMINED"]
    rationale: str = Field(min_length=3)
    resolves_contradiction: bool = False
    unresolved_aspects: list[str] = Field(default_factory=list)


class PublicEvidence(Observation):
    turn_id: str


class RecordedEvidence(PublicEvidence):
    question_depth: int | None = None
    evidence_scope: str = ""
    independent: bool = True
    explicit_inability: bool = False


class Judgment(BaseModel):
    observations: list[Observation]
    feedback: str
    explicit_inability: bool = False
    inability_excerpt: str = ""
    feedback_contains_hint: bool = False
    raw_belief: list[float] = Field(min_length=3, max_length=3)
    tag: Literal["INVARIANT", "MINOR_SHIFT", "MODERATE_SHIFT", "DECISIVE_SHIFT"]


class Question(BaseModel):
    text: str = Field(min_length=10)
    criterion_ids: list[str] = Field(min_length=1)
    assistance: Literal["NONE", "CLARIFICATION", "HINT"] = "NONE"
    mode: Mode | None = None
    depth: int | None = Field(default=None, ge=1, le=4)
    evidence_scope: str = ""


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
    objective: Objective
    selected_mode: Mode | None = None
    excluded_reason: str | None = None
    lifecycle: Literal["PLANNED", "ACTIVE", "CLOSED", "EXCLUDED"] = "PLANNED"
    assessment: Assessment = Assessment.NOT_ASSESSED
    stop_reason: str | None = None
    turns_spent: int = 0
    clarification_spent: bool = False
    easier_spent: bool = False
    deeper_spent: bool = False
    inability_count: int = 0
    difficulty: float = 3
    current_question_depth: int = Field(default=2, ge=1, le=4)
    mode_selection_reason: str = ""
    evidence_history: list[RecordedEvidence] = Field(default_factory=list)
    assisted_criteria: list[str] = Field(default_factory=list)
    criterion_results: dict[str, RecordedEvidence] = Field(default_factory=dict)
    contradictions: list[str] = Field(default_factory=list)
    criterion_progress: dict[str, CriterionProgress] = Field(default_factory=dict)
    active_criterion_id: str | None = None
    probe_reason: str = "Initial evidence for an essential criterion"
    belief: list[float] = Field(default_factory=list)


class Turn(BaseModel):
    turn_id: str
    objective_id: str
    skill_id: str
    mode: Mode
    action: Action
    difficulty: float
    question_depth: int | None = Field(default=None, ge=1, le=4)
    question: Question
    answer: str | None = None
    judgment: Judgment | None = None
    introduction: str = ""


class Snapshot(BaseModel):
    schema_version: Literal[2] = 2
    engine_version: Literal["evidence-2.0"] = VERSION
    session_id: str
    state_version: int = 0
    config: InterviewConfig
    policy: InterviewPolicy = Field(default_factory=InterviewPolicy)
    skills: list[InterviewSkill]
    objectives: dict[str, ObjectiveState]
    queue: list[str]
    started_at: datetime
    deadline_at: datetime
    pending_turn: Turn | None = None
    turns: list[Turn] = Field(default_factory=list)
    is_finished: bool = False
    termination_reason: str | None = None


class StartRequest(BaseModel):
    session_id: str
    skills: list[InterviewSkill] = Field(min_length=1, max_length=100)
    config: InterviewConfig = Field(default_factory=InterviewConfig)
    blueprint: Blueprint | None = None
    policy: InterviewPolicy | None = None


class TransitionRequest(BaseModel):
    snapshot: Snapshot
    turn_id: str
    expected_state_version: int
    candidate_response: str = Field(min_length=1, max_length=50000)


class CriterionReport(BaseModel):
    criterion_id: str
    description: str
    assessment: Assessment
    turns_spent: int
    stop_reason: str | None = None


class ObjectiveReport(BaseModel):
    objective_id: str
    skill_id: str
    claim: str
    inferred: bool
    jd_evidence_spans: list[str]
    assessment: Assessment
    lifecycle: str
    stop_reason: str | None
    excluded_reason: str | None
    covered_criteria: list[str]
    missing_criteria: list[str]
    strengths: list[str]
    weaknesses: list[str]
    study_recommendations: list[str] = Field(default_factory=list)
    evidence: list[PublicEvidence]
    evidence_turn_ids: list[str]
    criteria: list[CriterionReport] = Field(default_factory=list)


class Report(BaseModel):
    schema_version: Literal[2] = 2
    state_version: int
    is_finished: bool
    termination_reason: str | None
    progress: float
    evidence_coverage: float
    target_attainment: float | None
    study_recommendations: list[str] = Field(default_factory=list)
    objectives: list[ObjectiveReport]


class PublicTurn(BaseModel):
    turn_id: str
    objective_id: str
    skill_id: str
    mode: Mode
    question: str
    answer: str | None
    feedback: str | None
    introduction: str = ""


class PublicSession(BaseModel):
    schema_version: Literal[2] = 2
    session_id: str
    state_version: int
    is_finished: bool
    deadline_at: datetime
    config: InterviewConfig
    pending_turn: PublicTurn | None
    turns: list[PublicTurn]
    report: Report


class TransitionResult(BaseModel):
    snapshot: Snapshot
    public: PublicSession
