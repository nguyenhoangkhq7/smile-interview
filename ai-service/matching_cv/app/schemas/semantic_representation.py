"""Pydantic schemas for Stage 3 SBERT Semantic Representation & Retrieval."""
from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, Field, model_validator

from matching_cv.app.schemas.unified_skill_extraction import (
    DuplicateImplicitSkill,
    UnifiedExtractFileResponse,
)


class EmbeddingRecord(BaseModel):
    """Semantic embedding record with distinct occurrence identity, reusable vector identity, and full provenance."""

    occurrence_id: str = Field(
        ...,
        description="Unique identifier for this specific document occurrence (e.g. occ_cv_evidence_doc1_idx0)",
    )
    vector_id: str = Field(
        ...,
        description="Content/model vector identifier for vector reuse across identical texts (e.g. vec_model_hash)",
    )
    embedding_id: str = Field(
        ...,
        description="Primary identifier for backward compatibility (matches occurrence_id)",
    )
    document_type: Literal["CV", "JD"] = Field(..., description="Originating document type ('CV' or 'JD')")
    source_identifier: str = Field(
        ...,
        description="Source identifier (filename, doc_id, or run_id)",
    )
    target_type: Literal["skill", "cv_evidence", "jd_requirement"] = Field(
        ...,
        description="Category of embedded entity",
    )
    source_text: str = Field(..., description="Exact string input passed to SBERT")
    associated_skill_ids: List[str] = Field(
        default_factory=list,
        description="Canonical skill IDs associated with this occurrence",
    )
    associated_skill_names: List[str] = Field(
        default_factory=list,
        description="Human-readable skill labels associated with this occurrence",
    )
    extraction_type: Optional[Literal["explicit", "implicit"]] = Field(
        default=None,
        description="Extraction type ('explicit' | 'implicit'), or None for generic requirements",
    )
    model_id: str = Field(..., description="HuggingFace model repository ID")
    model_revision: Optional[str] = Field(default=None, description="Resolved immutable model commit hash")
    embedding_dim: int = Field(default=768, description="Vector dimension")
    construction_strategy: str = Field(
        ...,
        description="Input text construction strategy, e.g. 'skill_name', 'skill_name_and_definition', 'cv_evidence_sentence', 'jd_requirement_sentence'",
    )
    text_hash: str = Field(..., description="SHA-256 hex digest of source_text")
    is_truncated: bool = Field(
        default=False,
        description="True if input text exceeded max_seq_length",
    )
    truncation_status: Literal["not_truncated", "segmented", "rejected"] = Field(
        default="not_truncated",
        description="Handling outcome for sequence length: 'not_truncated', 'segmented', or 'rejected'",
    )
    segment_info: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Segment tracking when text is split into sub-chunks (parent_id, chunk_index, total_chunks)",
    )
    token_count: int = Field(default=0, description="Total tokens in text before any truncation/segmentation")
    max_seq_length: int = Field(default=128, description="Model tokenizer max sequence length")
    vector: Optional[List[float]] = Field(
        default=None,
        description="L2-normalized embedding vector (included only if requested)",
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Detailed provenance: character offsets, section, verbatim_ok, confidence, basis, reasoning",
    )


class SemanticSimilarityPair(BaseModel):
    """Ranked semantic similarity candidate pair with full-precision and presentation scores."""

    source_id: str = Field(..., description="Query occurrence/embedding ID (typically CV)")
    target_id: str = Field(..., description="Target candidate occurrence/embedding ID (typically JD)")
    source_label: str = Field(..., description="Query label / text")
    target_label: str = Field(..., description="Target label / text")
    cosine_similarity: float = Field(
        ...,
        ge=-1.0,
        le=1.0,
        description="Presentation cosine similarity score (rounded to 4 decimal places)",
    )
    raw_score: float = Field(
        ...,
        description="Full-precision unrounded cosine similarity score used for deterministic ranking",
    )
    rank: int = Field(..., ge=1, description="1-indexed rank within candidate list")


class TopKRetrievalResult(BaseModel):
    """Top-K semantic candidates for a specific query item."""

    query_id: str = Field(..., description="Query embedding/occurrence ID")
    query_label: str = Field(..., description="Query text or skill label")
    candidates: List[SemanticSimilarityPair] = Field(
        default_factory=list,
        description="Deterministically ranked candidates using full-precision scores",
    )


class SimilarityMatrix(BaseModel):
    """Complete cosine similarity matrix between two embedding groups."""

    source_ids: List[str] = Field(default_factory=list, description="Ordered source embedding IDs")
    target_ids: List[str] = Field(default_factory=list, description="Ordered target embedding IDs")
    source_labels: List[str] = Field(default_factory=list, description="Ordered source labels/texts")
    target_labels: List[str] = Field(default_factory=list, description="Ordered target labels/texts")
    matrix: List[List[float]] = Field(
        default_factory=list,
        description="2D array of cosine similarities rounded to 4 decimals for presentation",
    )
    raw_matrix: Optional[List[List[float]]] = Field(
        default=None,
        description="Optional full-precision unrounded cosine similarity matrix",
    )


class SemanticStats(BaseModel):
    """Statistical summary of semantic representation generation."""

    cv_explicit_skills: int = Field(default=0, ge=0)
    cv_accepted_implicit_skills: int = Field(default=0, ge=0)
    cv_duplicate_implicit_skills: int = Field(default=0, ge=0)
    cv_distinct_evidences: int = Field(default=0, ge=0)
    jd_explicit_skills: int = Field(default=0, ge=0)
    jd_accepted_implicit_skills: int = Field(default=0, ge=0)
    jd_duplicate_implicit_skills: int = Field(default=0, ge=0)
    jd_requirements: int = Field(default=0, ge=0)
    total_embeddings_generated: int = Field(default=0, ge=0)
    unique_vectors_encoded: int = Field(default=0, ge=0)
    truncation_count: int = Field(default=0, ge=0)
    rejected_overlength_count: int = Field(default=0, ge=0)
    segmented_count: int = Field(default=0, ge=0)
    encoding_duration_ms: float = Field(default=0.0, ge=0.0)


class SemanticAudit(BaseModel):
    """Audit data preserving rejected duplicate implicit skills."""

    cv_duplicate_implicit_skills: List[DuplicateImplicitSkill] = Field(
        default_factory=list,
        description="Duplicate implicit skills in CV excluded from active embeddings",
    )
    jd_duplicate_implicit_skills: List[DuplicateImplicitSkill] = Field(
        default_factory=list,
        description="Duplicate implicit skills in JD excluded from active embeddings",
    )


class SemanticRepresentationResponse(BaseModel):
    """Response containing SBERT semantic representation, diagnostics, and Top-K retrieval."""

    run_id: str = Field(..., description="Extraction run identifier")
    model_id: str = Field(..., description="SBERT model name used for embeddings")
    model_revision: Optional[str] = Field(default=None, description="Resolved immutable model commit hash")
    device: str = Field(..., description="Computation device used ('cpu' or 'cuda')")
    embedding_dim: int = Field(default=768, description="Vector embedding dimension")
    stats: SemanticStats = Field(default_factory=SemanticStats)
    audit: SemanticAudit = Field(default_factory=SemanticAudit)
    cv_skill_embeddings: List[EmbeddingRecord] = Field(default_factory=list)
    jd_skill_embeddings: List[EmbeddingRecord] = Field(default_factory=list)
    cv_evidence_embeddings: List[EmbeddingRecord] = Field(default_factory=list)
    jd_requirement_embeddings: List[EmbeddingRecord] = Field(default_factory=list)
    similarity_matrices: Optional[Dict[str, SimilarityMatrix]] = Field(
        default=None,
        description="Cosine similarity matrices: 'cv_skills_vs_jd_skills', 'cv_evidences_vs_jd_requirements'",
    )
    top_k_retrievals: Optional[Dict[str, List[TopKRetrievalResult]]] = Field(
        default=None,
        description="Top-K retrieval matches for CV skills and CV evidences",
    )
    diagnostics: Dict[str, Any] = Field(
        default_factory=dict,
        description="Runtime diagnostics, fallback notifications, and model details",
    )


class EmbeddingGenerateRequest(BaseModel):
    """Request payload for SBERT semantic embedding generation."""

    unified_response: UnifiedExtractFileResponse = Field(
        ...,
        description="Extracted skills used by the analyze pipeline",
    )
    cv_text: Optional[str] = Field(
        default=None,
        description="Optional full raw CV text",
    )
    jd_text: Optional[str] = Field(
        default=None,
        description="Optional full raw JD text to enable complete requirement segmentation",
    )
    include_vectors: bool = Field(
        default=False,
        description="Whether to serialize and return 768-dim float vectors in response",
    )
    top_k: int = Field(
        default=5,
        ge=1,
        le=50,
        description="Top-K candidates to return per query item",
    )
    compute_similarity: bool = Field(
        default=True,
        description="Whether to compute cosine similarity matrices and Top-K retrievals",
    )
    skill_definition_dict: Optional[Dict[str, str]] = Field(
        default=None,
        description="Optional pre-versioned skill definitions map: {skill_name: definition_text}",
    )
    on_overlength: Literal["error", "reject", "segment"] = Field(
        default="error",
        description="Handling policy when text exceeds max_seq_length: 'error' (raise exception), 'reject' (record vector=None), 'segment' (split into sub-chunks)",
    )
    retrieval_scope: Literal["skills_only", "all_entities"] = Field(
        default="skills_only",
        description="Corpus scope for skill-to-skill retrieval: 'skills_only' (default, candidates filtered to kind='skill' and accepted implicit skills, excluding context, domain, certification) or 'all_entities' (unfiltered legacy mode).",
    )
    include_implicit_in_retrieval: bool = Field(
        default=True,
        description="Whether to include accepted implicit skills as candidates in skill retrieval.",
    )
    auto_revalidate_implicit: bool = Field(
        default=False,
        description="Whether to automatically run authoritative deduplication to recover accepted implicit skills ONLY if validation data was omitted or missing. A completed validation that accepted zero skills is NEVER revalidated.",
    )
    model_config = {
        "json_schema_extra": {
            "example": {
                "unified_response": {
                    "run_id": "988fee55-1234-5678-abcd-000000000000",
                    "status": "completed",
                    "cv": {
                        "filename": "01_Backend_CV.pdf",
                        "document_type": "CV",
                        "text_sha256": "988fee55629f163567d17c91357c9d6505d1dff10f52071ad4c7e7d2b45ec3e4",
                        "stats": {},
                        "skills": [],
                    },
                    "jd": {
                        "filename": "01_Backend_JD.pdf",
                        "document_type": "JD",
                        "text_sha256": "43d4a49764a9d51c54a7adf6e14ead0212c18c943acc5a3a7df6c9b4dcea5872",
                        "stats": {},
                        "skills": [],
                    },
                },
                "jd_text": "2+ years of professional experience with Java and Spring Boot in a production environment.",
                "include_vectors": False,
                "top_k": 5,
                "compute_similarity": True,
                "retrieval_scope": "skills_only",
                "auto_revalidate_implicit": False,
            }
        }
    }

    @model_validator(mode="before")
    @classmethod
    def wrap_raw_unified_response(cls, data: Any) -> Any:
        if isinstance(data, dict):
            has_unified = "unified_response" in data
            has_raw = "cv" in data or "jd" in data

            # Reject ambiguous input containing both wrapped unified_response and top-level cv/jd
            if has_unified and has_raw:
                raise ValueError(
                    "Conflicting request payload: cannot provide both 'unified_response' and root-level 'cv'/'jd'."
                )

            if not has_unified and has_raw:
                req_fields = {
                    "cv_text",
                    "jd_text",
                    "include_vectors",
                    "top_k",
                    "compute_similarity",
                    "skill_definition_dict",
                    "on_overlength",
                    "retrieval_scope",
                    "include_implicit_in_retrieval",
                    "auto_revalidate_implicit",
                }
                unified_part = {
                    k: v for k, v in data.items()
                    if (k not in req_fields or k in ("cv_text", "jd_text", "status", "run_id"))
                }

                # Invariant: Never fabricate execution metadata or completed status!
                if "status" not in unified_part:
                    raise ValueError(
                        "Raw extraction payload is missing required 'status' field (e.g. 'completed', 'partial_success', 'failed')."
                    )
                if "run_id" not in unified_part:
                    raise ValueError(
                        "Raw extraction payload is missing required 'run_id' field."
                    )

                req_part = {k: v for k, v in data.items() if k in req_fields}
                req_part["unified_response"] = unified_part
                return req_part
        return data
