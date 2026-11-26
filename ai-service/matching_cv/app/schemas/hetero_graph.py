"""Pydantic schemas for Stage 4 Phase 1: Heterogeneous Graph Construction & GNN Data Readiness."""
from datetime import datetime, timezone
from typing import Any, Dict, List, Literal, Optional, Tuple, Union
from pydantic import BaseModel, Field

from matching_cv.app.schemas.semantic_reasoning import (
    BatchSkillPairReasoningResponse,
    GraphRelationStatus,
    SkillPairReasoningResult,
)
from matching_cv.app.schemas.semantic_representation import (
    EmbeddingRecord,
    SemanticRepresentationResponse,
)
from matching_cv.app.schemas.unified_skill_extraction import UnifiedExtractFileResponse

# Graph Node Types
NodeType = Literal["cv", "jd", "skill", "evidence", "requirement"]

# Graph Construction Modes
GraphConstructionMode = Literal["evidence_only", "similarity_enriched", "llm_enriched"]

# Edge Export Policies
EdgeExportPolicy = Literal[
    "trusted_structural_only",
    "eligible_llm_edges",
    "experimental_include_candidates",
]


class BaseGraphNode(BaseModel):
    """Abstract base schema for heterogeneous graph nodes."""

    node_id: str = Field(..., description="Unique immutable graph node identifier")
    node_type: NodeType = Field(..., description="Heterogeneous node type")
    source_identifier: str = Field(..., description="Originating document identifier or filename")
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Arbitrary provenance, debug, and extraction metadata",
    )


class CVNode(BaseGraphNode):
    """Candidate CV document node."""

    node_type: Literal["cv"] = "cv"
    document_id: str = Field(..., description="Source document identifier")
    run_id: str = Field(..., description="Extraction pipeline run identifier")
    source_type: Literal["CV"] = "CV"
    source_hash: Optional[str] = Field(default=None, description="SHA-256 hash of raw CV text")
    document_embedding: Optional[List[float]] = Field(
        default=None,
        description="Optional document-level embedding vector (never silently fabricated)",
    )


class JDNode(BaseGraphNode):
    """Job Description document node."""

    node_type: Literal["jd"] = "jd"
    document_id: str = Field(..., description="Source document identifier")
    run_id: str = Field(..., description="Extraction pipeline run identifier")
    source_type: Literal["JD"] = "JD"
    source_hash: Optional[str] = Field(default=None, description="SHA-256 hash of raw JD text")
    document_embedding: Optional[List[float]] = Field(
        default=None,
        description="Optional document-level embedding vector (never silently fabricated)",
    )


class SkillNode(BaseGraphNode):
    """Skill occurrence node preserving original occurrence identity without forced merging."""

    node_type: Literal["skill"] = "skill"
    skill_occurrence_id: str = Field(
        ...,
        description="Unique occurrence ID matching Stage 3 embedding record",
    )
    original_label: str = Field(..., description="Surface form or extracted skill text")
    canonical_skill_id: str = Field(..., description="Normalized or slug skill identifier")
    source_document: Literal["CV", "JD"] = Field(..., description="Document source origin")
    explicit_or_implicit: Literal["explicit", "implicit"] = Field(
        ...,
        description="Extraction provenance: explicit mention vs accepted implicit inference",
    )
    category: Optional[str] = Field(default=None, description="Domain or taxonomy category")
    confidence: Optional[float] = Field(default=None, description="Extraction or inference confidence")
    basis: Optional[str] = Field(default=None, description="Inference basis for implicit skills")
    embedding_ref: Optional[str] = Field(default=None, description="Reusable vector ID reference")
    embedding_vector: Optional[List[float]] = Field(
        default=None,
        description="768-dimensional L2-normalized SBERT embedding vector",
    )
    has_embedding: bool = Field(default=False, description="Whether 768D embedding vector is attached")
    evidence_status: str = Field(
        default="unsupported",
        description="Evidence linkage status: 'has_evidence' | 'unsupported'",
    )
    semantic_identity_status: str = Field(
        default="occurrence",
        description="Identity resolution state: 'occurrence' | 'resolved_candidate'",
    )


class EvidenceNode(BaseGraphNode):
    """Sentence-level CV evidence span node supporting a competency claim."""

    node_type: Literal["evidence"] = "evidence"
    evidence_id: str = Field(..., description="Unique evidence occurrence identifier")
    document_id: str = Field(..., description="CV source document identifier")
    text: str = Field(..., description="Exact unaltered evidence sentence text")
    source_span: Optional[Dict[str, int]] = Field(
        default=None,
        description="Character offset span: {'start': int, 'end': int}",
    )
    section: Optional[str] = Field(default=None, description="Document section where evidence occurs")
    verification_status: str = Field(
        default="context_verified",
        description="Evidence validation state: 'context_verified' | 'model_inferred' | 'unresolved'",
    )
    embedding_ref: Optional[str] = Field(default=None, description="Reusable vector ID reference")
    embedding_vector: Optional[List[float]] = Field(
        default=None,
        description="Optional 768-dimensional SBERT embedding of evidence sentence",
    )
    has_embedding: bool = Field(default=False, description="Whether embedding vector is attached")


class RequirementNode(BaseGraphNode):
    """JD requirement or qualification constraint node."""

    node_type: Literal["requirement"] = "requirement"
    requirement_id: str = Field(..., description="Unique requirement occurrence identifier")
    document_id: str = Field(..., description="JD source document identifier")
    text: str = Field(..., description="Exact unaltered requirement sentence text")
    requirement_type: Optional[str] = Field(
        default=None,
        description="Requirement category if explicitly identified",
    )
    required_or_preferred: Optional[str] = Field(
        default=None,
        description="Distinction: 'mandatory' | 'preferred' | None if not explicitly stated",
    )
    experience_constraint: Optional[str] = Field(
        default=None,
        description="Years of experience constraint if explicitly extracted, else None",
    )
    source_span: Optional[Dict[str, int]] = Field(
        default=None,
        description="Character offset span: {'start': int, 'end': int}",
    )
    section: Optional[str] = Field(default=None, description="Document section where requirement occurs")
    embedding_ref: Optional[str] = Field(default=None, description="Reusable vector ID reference")
    embedding_vector: Optional[List[float]] = Field(
        default=None,
        description="Optional 768-dimensional SBERT embedding of requirement sentence",
    )
    has_embedding: bool = Field(default=False, description="Whether embedding vector is attached")


class GraphEdge(BaseModel):
    """Typed directed heterogeneous graph relationship."""

    edge_type: str = Field(
        ...,
        description="Canonical relation name: 'has_skill', 'requires_skill', 'has_evidence', 'supported_by', 'has_requirement', 'mentions_skill', 'similar_to_candidate', 'equivalent_to', 'related_to', 'prerequisite_for', 'specialization_of', 'alternative_to'",
    )
    source_type: NodeType = Field(..., description="Heterogeneous source node type")
    target_type: NodeType = Field(..., description="Heterogeneous target node type")
    source_id: str = Field(..., description="Node ID of source endpoint")
    target_id: str = Field(..., description="Node ID of target endpoint")
    attributes: Dict[str, Any] = Field(
        default_factory=dict,
        description="Provenance, confidence, rank, similarity scores, or reasoning summary",
    )


class GraphIntegrityReport(BaseModel):
    """Detailed diagnostic audit of graph consistency, embedding validity, and provenance."""

    is_valid: bool = Field(..., description="True if no blocking integrity violations were found")
    node_integrity: Dict[str, Any] = Field(default_factory=dict)
    edge_integrity: Dict[str, Any] = Field(default_factory=dict)
    embedding_integrity: Dict[str, Any] = Field(default_factory=dict)
    provenance_integrity: Dict[str, Any] = Field(default_factory=dict)
    prerequisite_cycles: List[List[str]] = Field(
        default_factory=list,
        description="Detected cycles in directed prerequisite graph",
    )
    errors: List[str] = Field(default_factory=list, description="Blocking validation error messages")
    warnings: List[str] = Field(default_factory=list, description="Non-blocking warning messages")


class HeteroGraphData(BaseModel):
    """In-memory heterogeneous graph data container."""

    graph_id: str = Field(..., description="Unique graph instance identifier")
    run_id: str = Field(..., description="Source pipeline run identifier")
    mode: GraphConstructionMode = Field(..., description="Graph construction mode applied")
    edge_policy: EdgeExportPolicy = Field(..., description="Edge inclusion and gating policy")
    cv_nodes: Dict[str, CVNode] = Field(default_factory=dict)
    jd_nodes: Dict[str, JDNode] = Field(default_factory=dict)
    skill_nodes: Dict[str, SkillNode] = Field(default_factory=dict)
    evidence_nodes: Dict[str, EvidenceNode] = Field(default_factory=dict)
    requirement_nodes: Dict[str, RequirementNode] = Field(default_factory=dict)
    edges: List[GraphEdge] = Field(default_factory=list)
    rejected_audit: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Audit entries for rejected implicit skills, rejected LLM relations, or uncertain pairs",
    )
    diagnostics: Dict[str, Any] = Field(default_factory=dict)


class Stage4ReasoningRecording(BaseModel):
    """Authentic recorded LLM reasoning response for reproducible offline Stage 4 graph construction."""

    schema_version: Literal["stage4-reasoning-record-v1"] = "stage4-reasoning-record-v1"
    execution_source: Literal["live_llm", "recorded_replay"] = Field(
        ...,
        description="Source of the reasoning results: live_llm execution or recorded replay",
    )
    recording_version: str = Field(default="1.0.0", description="Recording format version")
    recorded_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
        description="Timestamp when reasoning was executed/recorded",
    )
    source_fixture: str = Field(..., description="Path or identifier of source fixture")
    source_fixture_sha256: str = Field(..., description="SHA-256 hash of source fixture file")
    stage3_input_sha256: Optional[str] = Field(default=None, description="SHA-256 hash of Stage 3 inputs/top-k")
    model_id: str = Field(..., description="LLM model identifier used (e.g. qwen/qwen3.7-flash)")
    prompt_version: str = Field(..., description="Prompt version used (e.g. sprint2-v2)")
    critic_enabled: bool = Field(default=True, description="Whether selective critic was active")
    total_pairs: int = Field(..., description="Total pairs in recording")
    evaluated_pairs: int = Field(default=0, description="Evaluated pairs count")
    critic_invocations: int = Field(default=0, description="Critic invocations count")
    contradictions_resolved: int = Field(default=0, description="Contradictions resolved count")
    results: List[SkillPairReasoningResult] = Field(..., description="List of authentic reasoning results")


class GraphBuildRequest(BaseModel):
    """Request payload for building a validated heterogeneous graph."""

    unified_response: Optional[UnifiedExtractFileResponse] = Field(
        default=None,
        description="Extracted skills used by the analyze pipeline",
    )
    stage3_response: Optional[Union[SemanticRepresentationResponse, Dict[str, Any]]] = Field(
        default=None,
        description="Skill embeddings used by the analyze pipeline",
    )
    reasoning_results: Optional[List[SkillPairReasoningResult]] = Field(
        default=None,
        description="Skill pair reasoning results from Sprint 2 LLM classifier",
    )
    reasoning_response: Optional[Union[BatchSkillPairReasoningResponse, Dict[str, Any]]] = Field(
        default=None,
        description="Reasoning results used by the analyze pipeline",
    )
    reasoning_recording: Optional[Union[Stage4ReasoningRecording, Dict[str, Any]]] = Field(
        default=None,
        description="Authentic recorded LLM reasoning response for reproducible graph construction",
    )
    raw_cv_text: Optional[str] = Field(default=None, description="Optional raw text of CV")
    raw_jd_text: Optional[str] = Field(default=None, description="Optional raw text of JD")
    graph_mode: GraphConstructionMode = Field(
        default="llm_enriched",
        description="Construction mode: 'evidence_only' (Mode A), 'similarity_enriched' (Mode B), 'llm_enriched' (Mode C)",
    )
    edge_policy: EdgeExportPolicy = Field(
        default="eligible_llm_edges",
        description="Edge gating policy: 'trusted_structural_only', 'eligible_llm_edges', 'experimental_include_candidates'",
    )
    include_diagnostics: bool = Field(
        default=True,
        description="Whether to include full integrity audit and diagnostics in response",
    )
    export_pyg: bool = Field(
        default=False,
        description="Whether to generate PyTorch Geometric HeteroData export metadata",
    )
    return_full_graph: bool = Field(
        default=False,
        description="Whether to return full graph node and edge dictionaries in response",
    )


class GraphBuildResponse(BaseModel):
    """Response payload summarizing graph construction, validation, and PyG export status."""

    graph_id: str = Field(..., description="Unique graph instance identifier")
    run_id: str = Field(..., description="Extraction pipeline run identifier")
    graph_mode: GraphConstructionMode = Field(..., description="Graph construction mode used")
    edge_policy: EdgeExportPolicy = Field(..., description="Edge inclusion policy used")
    node_counts: Dict[str, int] = Field(..., description="Counts of nodes by type and total")
    edge_counts: Dict[str, int] = Field(..., description="Counts of edges by relation type and total")
    validation_report: GraphIntegrityReport = Field(..., description="Graph integrity validation report")
    diagnostics: Dict[str, Any] = Field(default_factory=dict, description="Execution diagnostics and metadata")
    pyg_export_summary: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Summary of PyG HeteroData export if export_pyg was True",
    )
    graph_data: Optional[HeteroGraphData] = Field(
        default=None,
        description="Full serialized graph data (populated only if return_full_graph=True)",
    )
    created_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
        description="ISO 8601 creation timestamp",
    )


class GraphManifest(BaseModel):
    """Immutable reproducibility manifest for a Stage 4 graph build."""

    graph_id: str = Field(...)
    schema_version: str = Field(default="stage4-phase1-v1")
    branch: str = Field(...)
    git_commit: Optional[str] = Field(default=None)
    is_dirty: bool = Field(default=False)
    source_fixture_hashes: Dict[str, str] = Field(default_factory=dict)
    sbert_model: str = Field(...)
    sbert_revision: str = Field(...)
    llm_model: Optional[str] = Field(default=None)
    llm_prompt_version: Optional[str] = Field(default=None)
    graph_mode: str = Field(...)
    edge_policy: str = Field(...)
    runtime_dependency_versions: Dict[str, str] = Field(default_factory=dict)
    artifact_hashes: Dict[str, str] = Field(default_factory=dict)
    created_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
    )
