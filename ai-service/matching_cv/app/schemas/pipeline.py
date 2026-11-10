"""Pydantic schemas for the consolidated end-to-end pipeline."""
from typing import Any, Dict, List, Literal, Optional, Union
from pydantic import BaseModel, Field, PrivateAttr, model_validator

from matching_cv.app.schemas.gnn_inference import FitCategory
from matching_cv.app.schemas.hetero_graph import (
    GraphConstructionMode,
    HeteroGraphData,
)
from matching_cv.research.paper_aligned_gnn.schemas import PaperAlignedGraphData


class DocumentMetadata(BaseModel):
    """Metadata summary of a parsed document."""

    filename: str = Field(..., description="Uploaded document filename")
    file_type: str = Field(..., description="Detected file type ('pdf' or 'txt')")
    character_count: int = Field(default=0, ge=0, description="Cleaned character count")
    word_count: int = Field(default=0, ge=0, description="Cleaned word count")
    total_pages: Optional[int] = Field(default=None, description="PDF page count if applicable")
    text_sha256: str = Field(..., description="SHA-256 hash of cleaned text")


class PipelineDocumentSummary(BaseModel):
    """Pair of documents processed by the pipeline."""

    cv: DocumentMetadata
    jd: DocumentMetadata


class DocumentExtractionDetails(BaseModel):
    """Extraction metrics and optional granular item breakdown for a single document."""

    explicit_count: int = Field(default=0, ge=0)
    implicit_count: int = Field(default=0, ge=0)
    duplicate_count: int = Field(default=0, ge=0)
    rejected_implicit_count: int = Field(default=0, ge=0)
    explicit_skills: Optional[List[Dict[str, Any]]] = Field(
        default=None, description="Extracted explicit skill records if include_details=True"
    )
    accepted_implicit_skills: Optional[List[Dict[str, Any]]] = Field(
        default=None, description="Accepted implicit skills if include_details=True"
    )
    duplicate_implicit_skills: Optional[List[Dict[str, Any]]] = Field(
        default=None, description="Duplicate implicit skills if include_details=True"
    )
    rejected_implicit_skills: Optional[List[Dict[str, Any]]] = Field(
        default=None, description="Rejected implicit skills if include_details=True"
    )


class PipelineExtractionSummary(BaseModel):
    """Consolidated extraction summary across CV and JD."""

    cv: DocumentExtractionDetails
    jd: DocumentExtractionDetails
    total_unique_skills: int = Field(default=0, ge=0)
    duplicate_count: int = Field(default=0, ge=0)


class CandidatePairSummary(BaseModel):
    """SBERT Top-K candidate similarity pair summary."""

    source_skill_id: str
    source_label: str
    target_skill_id: str
    target_label: str
    cosine_similarity: float
    rank: int


class PipelineSemanticRepresentation(BaseModel):
    """Stage 3 SBERT semantic representation and retrieval summary."""

    top_k: int
    model_id: str
    model_revision: Optional[str] = None
    cv_skills_encoded: int = 0
    jd_skills_encoded: int = 0
    cv_evidences_encoded: int = 0
    jd_requirements_encoded: int = 0
    candidate_pairs_count: int = 0
    candidate_pairs: List[CandidatePairSummary] = Field(default_factory=list)
    cv_embeddings: Optional[List[Dict[str, Any]]] = Field(
        default=None, description="Full embedding records if include_embeddings=True"
    )
    jd_embeddings: Optional[List[Dict[str, Any]]] = Field(
        default=None, description="Full embedding records if include_embeddings=True"
    )


class PipelineSemanticReasoning(BaseModel):
    """Sprint 2 Phase 1B semantic relationship reasoning summary."""

    model_id: Optional[str] = None
    prompt_version: Optional[str] = None
    critic_enabled: bool = False
    total_pairs_evaluated: int = 0
    eligible_relations_count: int = 0
    candidate_only_count: int = 0
    unrelated_count: int = 0
    uncertain_count: int = 0
    # Candidate Coverage and Budgeting fields (Pre-GNN Phase 2C)
    total_retrievable_pairs: int = Field(
        default=0, description="Total candidate pairs retrieved by Stage 3 SBERT before filtering"
    )
    total_unique_pairs: int = Field(
        default=0, description="Total unique deduplicated candidate pairs above min_cosine threshold"
    )
    selected_pairs: int = Field(
        default=0, description="Number of candidate pairs selected for reasoning within budget"
    )
    skipped_by_budget_pairs: int = Field(
        default=0, description="Number of unique candidate pairs skipped due to reasoning_max_pairs budget limit"
    )
    failed_pairs: int = Field(
        default=0, description="Number of candidate pairs that encountered evaluation failures"
    )
    cv_skills_covered: int = Field(
        default=0, description="Count of distinct CV skills represented in evaluated/selected pairs"
    )
    cv_skills_total: int = Field(
        default=0, description="Total count of distinct CV skills present in candidate retrievals"
    )
    cv_skill_coverage_pct: float = Field(
        default=0.0, description="Percentage of retrievable CV skills represented in candidate selection"
    )
    jd_skills_covered: int = Field(
        default=0, description="Count of distinct JD skills represented in evaluated/selected pairs"
    )
    jd_skills_total: int = Field(
        default=0, description="Total count of distinct JD skills present in candidate retrievals"
    )
    jd_skill_coverage_pct: float = Field(
        default=0.0, description="Percentage of retrievable JD skills represented in candidate selection"
    )
    selection_strategy: Optional[str] = Field(
        default=None, description="Candidate selection strategy: 'balanced_coverage' or 'global_top_cosine'"
    )
    reasoning_budget: Optional[int] = Field(
        default=None, description="Configured reasoning_max_pairs budget"
    )
    candidate_coverage_summary: Optional[Dict[str, Any]] = Field(
        default=None, description="Detailed audit of candidate retrieval recall vs reasoning coverage"
    )
    results: Optional[List[Dict[str, Any]]] = Field(
        default=None, description="Full reasoning results if include_details=True"
    )


class PipelineGraphSummary(BaseModel):
    """Stage 5 Graph construction and validation summary."""

    graph_id: str
    graph_mode: str
    edge_policy: str
    node_counts: Dict[str, int]
    edge_counts: Dict[str, int]
    integrity: Dict[str, Any]
    subgraph_checks: Optional[Dict[str, Any]] = None
    pyg_summary: Optional[Dict[str, Any]] = Field(
        default=None, description="PyG HeteroData tensor shape summary if include_graph=True"
    )
    graph_data: Optional[Union[PaperAlignedGraphData, HeteroGraphData, Dict[str, Any]]] = Field(
        default=None, description="Full in-memory graph data if include_graph=True"
    )


class StageDiagnostic(BaseModel):
    """Duration and execution status for an individual pipeline stage."""

    stage: str
    status: Literal["completed", "skipped", "failed"]
    duration_ms: float
    error: Optional[str] = None


class PipelineDiagnostics(BaseModel):
    """Comprehensive stage timings, execution trace, and errors."""

    stages: List[StageDiagnostic] = Field(default_factory=list)
    total_duration_ms: float = 0.0
    timings: Dict[str, float] = Field(default_factory=dict)
    errors: List[Dict[str, Any]] = Field(default_factory=list)


class PipelineFailureDetail(BaseModel):
    """Structured failure diagnosis returned when a stage fails."""

    stage: str
    error_code: str
    message: str
    retryable: bool
    run_id: str


class PipelineMatchingResult(BaseModel):
    """Stage 6 GNN compatibility inference matching result."""

    model_name: str = Field(
        default="PaperAlignedHybridGNN",
        description="GNN architecture model name",
    )
    model_version: str = Field(
        default="paper-aligned-2025-v1",
        description="Research model release version",
    )
    graph_mode: str = Field(
        ...,
        description="Active graph mode evaluated",
    )
    checkpoint_sha256: str = Field(
        ...,
        description="SHA-256 integrity hash of active model checkpoint",
    )
    matching_score: float = Field(
        ...,
        ge=0.0,
        le=100.0,
        description="Bounded matching score on active score_scale ([0.0, 1.0] or [0.0, 100.0])",
    )
    raw_score: float = Field(
        ...,
        description="Raw continuous regression score from MLP head (unbounded; never silently clamped)",
    )
    raw_model_score: Optional[float] = Field(
        default=None,
        description="Canonical raw regression score from the GNN model head (synced with raw_score)",
    )
    predicted_target_name: str = Field(
        default="skill_score",
        description="Supervision target predicted by the loaded checkpoint (e.g. 'skill_score')",
    )
    score_version: str = Field(
        default="skill-target-regression-v1",
        description="Versioned scoring contract identifier",
    )
    calibrated_score: Optional[float] = Field(
        default=None,
        description="Empirically calibrated compatibility probability; None when uncalibrated",
    )
    calibration_status: str = Field(
        default="UNCALIBRATED",
        description="Calibration status ('UNCALIBRATED' when no validated probability calibration exists)",
    )
    bounded_display_score: float = Field(
        ...,
        ge=0.0,
        le=100.0,
        description="Explicitly bounded score for presentation purposes and backward compatibility",
    )
    fit_category: Optional[FitCategory] = Field(
        default=None,
        description="Optional categorical fit derived from documented post-processing thresholds, or FitCategory.UNCALIBRATED when uncalibrated",
    )
    score_scale: str = Field(
        default="0_1",
        description="Active score scale ('0_1' or '0_100')",
    )
    score_range: Dict[str, float] = Field(
        default_factory=lambda: {"min": 0.0, "max": 1.0},
        description="Theoretical bounds [min, max] of the canonical matching_score",
    )
    is_calibrated: bool = Field(
        default=False,
        description="Whether the score is a calibrated posterior probability (always False for GNN regression)",
    )
    score_type: str = Field(
        default="bounded_uncalibrated_regression",
        description="Mathematical score type description",
    )
    classification_thresholds: Optional[Dict[str, float]] = Field(
        default=None,
        description="Optional classification threshold boundaries applied; None when uncalibrated",
    )
    resume_skill_attention: Optional[Dict[str, float]] = Field(
        default=None,
        description="Final-layer Equation (2) modified GAT attention weights over resume skills (Figure 6)",
    )
    inference_latency_ms: Optional[float] = Field(
        default=None,
        description="GNN forward-pass duration in milliseconds",
    )
    probability_calibration_disclaimer: str = Field(
        default=(
            "Raw regression scores are uncalibrated continuous model outputs and must NOT be interpreted as posterior probabilities. "
            "Scores may legitimately be negative or exceed 1.0."
        ),
        description="Mandatory scientific reproducibility and statistical disclaimer",
    )

    @model_validator(mode="before")
    @classmethod
    def sync_scores(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if "matching_score" in data and "bounded_display_score" not in data:
                data["bounded_display_score"] = data["matching_score"]
            elif "bounded_display_score" in data and "matching_score" not in data:
                data["matching_score"] = data["bounded_display_score"]
            if data.get("raw_score") is not None and data.get("raw_model_score") is None:
                data["raw_model_score"] = data["raw_score"]
            elif data.get("raw_model_score") is not None and data.get("raw_score") is None:
                data["raw_score"] = data["raw_model_score"]
        return data


class PipelineAnalyzeResponse(BaseModel):
    """Complete consolidated response payload for POST /api/v1/pipeline/analyze."""

    run_id: str
    status: Literal["completed", "partial", "failed"]
    pipeline_version: str = "1.0.0"
    graph_mode: str = "similarity_enriched"
    documents: Optional[PipelineDocumentSummary] = None
    extraction: Optional[PipelineExtractionSummary] = None
    semantic_representation: Optional[PipelineSemanticRepresentation] = None
    semantic_reasoning: Optional[PipelineSemanticReasoning] = None
    graph: Optional[PipelineGraphSummary] = None
    matching_result: Optional[PipelineMatchingResult] = Field(
        default=None,
        description="Stage 6 GNN compatibility matching prediction and research model metadata",
    )
    matching_status: Optional[str] = Field(
        default=None,
        description="Status of GNN matching stage ('completed', 'skipped', 'unavailable', 'failed')",
    )
    diagnostics: PipelineDiagnostics
    failure: Optional[PipelineFailureDetail] = None

    # Non-serialized hand-off (never part of model_dump/JSON): in-memory Stage 1-6 objects needed to derive the
    # standardized public output without recomputation. Populated by PipelineOrchestrator on completed runs.
    _public_context: Optional[Any] = PrivateAttr(default=None)
