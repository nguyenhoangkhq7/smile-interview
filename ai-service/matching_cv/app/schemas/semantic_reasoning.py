"""Pydantic schemas for Sprint 2 Phase 1: Ontology-Free LLM Skill Semantic Reasoning."""
from datetime import datetime, timezone
from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, Field


IdentityDecision = Literal["equivalent", "distinct", "uncertain"]
RelationshipType = Literal[
    "related",
    "prerequisite",
    "specialization",
    "alternative",
    "unrelated",
    "uncertain",
]
DirectionType = Literal["a_to_b", "b_to_a", "bidirectional", "none"]
EvidenceBasis = Literal[
    "context_grounded",
    "model_knowledge",
    "exact_string_match",
    "insufficient_evidence",
]
VerificationStatus = Literal[
    "model_inferred",
    "context_verified",
    "deterministic_verified",
    "uncertain",
    "error",
]
GraphRelationStatus = Literal["eligible", "candidate_only", "rejected"]
ResolutionMethod = Literal[
    "exact_label_rule",
    "llm_direct",
    "llm_critic_refined",
    "derived_by_symmetry",
    "cache_dedup",
    "fallback_error",
]


class SkillRef(BaseModel):
    """Reference to a skill with identifier, display name, and provenance context."""

    skill_id: str = Field(..., description="Canonical slug or identifier of the skill")
    name: str = Field(..., description="Display surface form or label of the skill")
    context: Optional[str] = Field(
        default=None,
        description="Optional sentence or requirement context where skill appears",
    )
    source: Optional[str] = Field(
        default=None,
        description="Source document origin: 'CV' | 'JD' | 'explicit' | 'implicit'",
    )


class SkillPairReasoningInput(BaseModel):
    """Input payload representing a pair of skills to evaluate for semantic relationship."""

    pair_id: Optional[str] = Field(
        default=None,
        description="Deterministic identifier for reasoning pair traceability",
    )
    skill_a_id: str = Field(..., description="Identifier of first skill")
    skill_a_name: str = Field(..., description="Display name of first skill")
    skill_a_context: Optional[str] = Field(
        default=None,
        description="Optional context snippet for skill A from CV or JD",
    )
    skill_a_source: Optional[str] = Field(
        default=None,
        description="Document type for skill A: 'CV' or 'JD'",
    )

    skill_b_id: str = Field(..., description="Identifier of second skill")
    skill_b_name: str = Field(..., description="Display name of second skill")
    skill_b_context: Optional[str] = Field(
        default=None,
        description="Optional context snippet for skill B from CV or JD",
    )
    skill_b_source: Optional[str] = Field(
        default=None,
        description="Document type for skill B: 'CV' or 'JD'",
    )

    retrieval_cosine: Optional[float] = Field(
        default=None,
        description="Optional Stage 3 SBERT cosine similarity (used as metadata only)",
    )
    source_occurrence_ids: Optional[List[str]] = Field(
        default_factory=list,
        description="Original occurrence IDs from Stage 3 embedding inventory",
    )


class SkillPairReasoningResult(BaseModel):
    """Structured reasoning output for a single skill pair."""

    pair_id: Optional[str] = Field(
        default=None,
        description="Deterministic identifier for reasoning pair traceability",
    )
    skill_a: SkillRef = Field(..., description="First evaluated skill")
    skill_b: SkillRef = Field(..., description="Second evaluated skill")
    identity: IdentityDecision = Field(
        ...,
        description="Identity decision: 'equivalent' | 'distinct' | 'uncertain'",
    )
    relationship: Optional[RelationshipType] = Field(
        default=None,
        description="Semantic relationship type when distinct: 'related' | 'prerequisite' | 'specialization' | 'alternative' | 'unrelated' | 'uncertain'",
    )
    direction: Optional[DirectionType] = Field(
        default=None,
        description="Directionality of relationship: 'a_to_b' | 'b_to_a' | 'bidirectional' | 'none'",
    )
    reasoning_summary: str = Field(
        ...,
        description="Concise checkable rationale justifying the identity and relationship decisions",
    )
    evidence_basis: EvidenceBasis = Field(
        default="model_knowledge",
        description="Source basis of reasoning: 'context_grounded' | 'model_knowledge' | 'insufficient_evidence'",
    )
    verification_status: VerificationStatus = Field(
        default="model_inferred",
        description="Verification state: 'model_inferred' | 'context_verified' | 'uncertain' | 'error'",
    )
    requires_external_verification: bool = Field(
        default=False,
        description="Flag indicating human or external domain review is recommended",
    )
    model_id: str = Field(
        ...,
        description="LLM model identifier used for reasoning",
    )
    prompt_version: str = Field(
        default="sprint2-v1",
        description="Prompt template contract version",
    )
    retrieval_cosine: Optional[float] = Field(
        default=None,
        description="Stage 3 SBERT cosine score preserved as retrieval metadata",
    )
    source_occurrence_ids: Optional[List[str]] = Field(
        default_factory=list,
        description="Preserved occurrence IDs for provenance tracking",
    )
    latency_ms: Optional[float] = Field(
        default=None,
        description="Execution duration in milliseconds for this pair",
    )
    cached_from_symmetric: bool = Field(
        default=False,
        description="Whether this result was derived from an evaluated inverted pair",
    )
    error_status: Optional[str] = Field(
        default=None,
        description="Error description if reasoning failed or timed out",
    )
    graph_relation_status: GraphRelationStatus = Field(
        default="candidate_only",
        description="Stage 4 typed graph edge eligibility: 'eligible' | 'candidate_only' | 'rejected'",
    )
    resolution_method: ResolutionMethod = Field(
        default="llm_direct",
        description="Resolution mechanism: 'exact_label_rule' | 'llm_direct' | 'llm_critic_refined' | 'derived_by_symmetry' | 'cache_dedup' | 'fallback_error'",
    )
    initial_decision: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Original unrefined decision when modified by semantic critic",
    )
    critic_assessment: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Assessment details from semantic critic review pass",
    )
    contradiction_detected: bool = Field(
        default=False,
        description="Whether a label-rationale or semantic contradiction was detected",
    )


class BatchSkillPairReasoningRequest(BaseModel):
    """Batch request payload to evaluate multiple candidate skill pairs."""

    pairs: List[SkillPairReasoningInput] = Field(
        ...,
        min_length=1,
        description="List of skill pairs to evaluate",
    )
    concurrency: int = Field(
        default=5,
        ge=1,
        le=20,
        description="Maximum concurrent asynchronous LLM requests",
    )
    timeout_seconds: float = Field(
        default=30.0,
        ge=0.01,
        le=120.0,
        description="Per-pair timeout in seconds",
    )
    include_cosine_in_prompt: bool = Field(
        default=False,
        description="Whether to provide SBERT cosine to LLM prompt (default False to prevent bias)",
    )
    enable_critic: bool = Field(
        default=False,
        description="Whether to enable selective semantic critic pass for contradiction review",
    )
    prompt_version: str = Field(
        default="sprint2-v2",
        description="Prompt template contract version ('sprint2-v1' or 'sprint2-v2')",
    )


class BatchSkillPairReasoningResponse(BaseModel):
    """Batch response payload containing evaluated skill pairs and execution metrics."""

    run_id: str = Field(..., description="Unique execution run identifier")
    results: List[SkillPairReasoningResult] = Field(
        default_factory=list,
        description="Evaluated skill pair reasoning records",
    )
    total_pairs: int = Field(..., description="Total pairs requested")
    evaluated_pairs: int = Field(..., description="Number of unique LLM calls performed")
    cached_dedup_pairs: int = Field(
        ...,
        description="Number of pairs resolved via deduplication or symmetry cache",
    )
    failed_pairs: int = Field(..., description="Number of pairs that encountered errors")
    critic_invocations: int = Field(
        default=0,
        description="Number of semantic critic reviews triggered",
    )
    contradictions_resolved: int = Field(
        default=0,
        description="Number of contradictory decisions detected and resolved",
    )
    model_id: str = Field(..., description="LLM model configured")
    prompt_version: str = Field(default="sprint2-v2", description="Prompt template version")
    duration_ms: float = Field(..., description="Total batch execution latency in milliseconds")
    coverage_metrics: Optional[Dict[str, Any]] = Field(
        default=None, description="Detailed candidate retrieval recall and LLM evaluation coverage metrics"
    )
    created_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
        description="ISO 8601 timestamp of execution",
    )


class Stage3TopKReasoningRequest(BaseModel):
    """Request to adapt and reason on Stage 3 SBERT Top-K retrieval results."""

    stage3_response: Dict[str, Any] = Field(
        ...,
        description="Embedding results used by the analyze pipeline",
    )
    max_pairs: int = Field(
        default=25,
        ge=1,
        le=100,
        description="Maximum Top-K pairs to evaluate",
    )
    min_cosine: float = Field(
        default=0.3,
        ge=-1.0,
        le=1.0,
        description="Minimum cosine similarity threshold to qualify as a candidate pair",
    )
    selection_strategy: Literal["balanced_coverage", "global_top_cosine"] = Field(
        default="balanced_coverage",
        description="Candidate selection strategy: 'balanced_coverage' (round-robin per CV skill) or 'global_top_cosine' (global top-N)",
    )
    concurrency: int = Field(
        default=5,
        ge=1,
        le=20,
        description="Maximum concurrent LLM calls",
    )
    timeout_seconds: float = Field(
        default=30.0,
        ge=0.01,
        le=120.0,
        description="Per-pair timeout in seconds",
    )
    enable_critic: bool = Field(
        default=False,
        description="Whether to enable selective semantic critic pass",
    )
    prompt_version: str = Field(
        default="sprint2-v2",
        description="Prompt template contract version ('sprint2-v1' or 'sprint2-v2')",
    )
