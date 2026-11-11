"""Pydantic schemas for unified explicit and implicit skill extraction output contract."""
from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, Field

from matching_cv.app.schemas.implicit_skill_extraction import (
    ImplicitExtractedSkill,
    ImplicitExtractionResult,
)
from matching_cv.app.schemas.skill_extraction import ExtractionResult


class DuplicateImplicitSkill(BaseModel):
    """An implicit skill identified as duplicate of an explicit mention."""

    skill_id: str = Field(
        ...,
        description="Canonical slug identifier of the duplicate implicit skill",
    )
    label: str = Field(..., description="Normalized label of the duplicate implicit skill")
    category: Optional[str] = Field(
        default=None,
        description="Category classification of the duplicate implicit skill",
    )
    matched_explicit_skill_id: str = Field(
        ...,
        description="skill_id of the matching explicit skill that takes precedence",
    )
    matched_explicit_surface_form: str = Field(
        ...,
        description="Surface form of the matching explicit mention",
    )
    duplicate_reason: str = Field(
        default="exact_canonical_id",
        description="Reason: 'exact_canonical_id' | 'surface_form_match' | 'alias_match'",
    )
    original_inference: Optional[ImplicitExtractedSkill] = Field(
        default=None,
        description="Full original inferred skill with evidence for audit purposes",
    )


class ImplicitEvidenceVerification(BaseModel):
    """Audit record for evidence-grounded validity verification of an implicit skill (Layer B)."""

    skill_id: str = Field(..., description="Canonical ID of the verified implicit skill")
    original_label: str = Field(..., description="Original label inferred by LLM")
    proposed_label: Optional[str] = Field(
        default=None,
        description="Safe normalized or generalized label if modified",
    )
    assessment: Literal[
        "supported", "partially_supported", "unsupported", "insufficient_evidence", "plausible"
    ] = Field(
        ...,
        description="Decision state for evidence groundedness",
    )
    assessment_reason: str = Field(
        ...,
        description="Explanatory justification for the assessment",
    )
    is_accepted: bool = Field(
        ...,
        description="Whether this implicit skill is accepted into downstream representations",
    )
    confidence: Optional[float] = Field(
        default=None,
        description="Verifier assessment confidence",
    )
    verifier_type: str = Field(
        default="rule_based_deterministic",
        description="Identifier of verifier mechanism",
    )
    verifier_version: str = Field(
        default="2.0.0",
        description="Contract version of the verifier",
    )
    evidence_snippets: List[str] = Field(
        default_factory=list,
        description="Extracted textual snippets evaluated",
    )
    original_evidence: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Original evidence metadata",
    )
    skill_name: Optional[str] = Field(
        default=None,
        description="Skill label evaluated",
    )
    document_type: Optional[str] = Field(
        default=None,
        description="Document type ('CV' or 'JD')",
    )
    source_evidence: Optional[str] = Field(
        default=None,
        description="Full text of source evidence evaluated",
    )
    evidence_offsets: Optional[List[Dict[str, int]]] = Field(
        default_factory=list,
        description="Character offsets of evidence snippets in source document",
    )
    inference_rationale: Optional[str] = Field(
        default=None,
        description="Inference rationale from candidate extraction",
    )
    support_status: Optional[Literal["supported", "plausible", "unsupported"]] = Field(
        default=None,
        description="Phase 4 3-state entailment status: supported | plausible | unsupported",
    )
    support_reason: Optional[str] = Field(
        default=None,
        description="Detailed entailment rationale",
    )
    validator_version: Optional[str] = Field(
        default="2.0.0",
        description="Version of entailment validator",
    )
    confidence_raw: Optional[float] = Field(
        default=None,
        description="Raw confidence reported by extraction LLM",
    )
    confidence_normalized: Optional[float] = Field(
        default=None,
        description="Calibrated verifier confidence score",
    )
    acceptance_decision: Optional[Literal["accepted", "quarantined", "rejected"]] = Field(
        default=None,
        description="Gating decision: accepted | quarantined | rejected",
    )
    decomposed_from: Optional[str] = Field(
        default=None,
        description="Original compound skill ID if this verification is for a decomposed component",
    )
    decomposed_components: Optional[List[str]] = Field(
        default=None,
        description="All atomic sub-components if decomposed from compound skill",
    )


class DocumentValidationResult(BaseModel):
    """Validation and semantic deduplication outcomes for a document."""

    status: Optional[str] = Field(
        default=None,
        description="Validation execution status: 'completed' | 'missing' | 'inconsistent' | 'revalidated' | 'failed'",
    )
    validation_origin: Optional[str] = Field(
        default="original",
        description="Provenance of validation: 'original' | 'revalidated' | 'missing' | 'authoritative_empty' | 'not_applicable'",
    )
    validation_policy: Optional[str] = Field(
        default="dedup_plus_evidence_verification",
        description="Validation policy applied: 'dedup_only' | 'dedup_plus_evidence_verification'",
    )
    duplicate_implicit_skills: List[DuplicateImplicitSkill] = Field(
        default_factory=list,
        description="Inferred implicit skills flagged as duplicates of explicit skills",
    )
    accepted_implicit_skills: List[ImplicitExtractedSkill] = Field(
        default_factory=list,
        description="Inferred implicit skills accepted after deduplication and evidence verification",
    )
    rejected_implicit_skills: List[ImplicitExtractedSkill] = Field(
        default_factory=list,
        description="Inferred implicit skills rejected during evidence verification",
    )
    evidence_verifications: List[ImplicitEvidenceVerification] = Field(
        default_factory=list,
        description="Detailed evidence groundedness assessment records (Layer B)",
    )


class DocumentUnifiedResult(BaseModel):
    """Unified extraction results for a single document (CV or JD)."""

    filename: Optional[str] = Field(
        default=None,
        description="Uploaded document filename",
    )
    document_type: Literal["CV", "JD"] = Field(
        ...,
        description="Document type: 'CV' or 'JD'",
    )
    text_sha256: Optional[str] = Field(
        default=None,
        description="SHA-256 hex digest of the raw document text indexed across extractions",
    )
    raw_text: Optional[str] = Field(
        default=None,
        description="Full extracted raw text from the document (CV or JD)",
    )
    explicit: Optional[ExtractionResult] = Field(
        default=None,
        description="Full explicit skill extraction result",
    )
    implicit: Optional[ImplicitExtractionResult] = Field(
        default=None,
        description="Full implicit skill extraction result",
    )
    validation: DocumentValidationResult = Field(
        default_factory=DocumentValidationResult,
        description="Explicit/Implicit deduplication and validation outcome",
    )


class UnifiedExtractionSummary(BaseModel):
    """Aggregated statistics and execution metrics for the unified extraction request."""

    cv_explicit_count: int = Field(default=0, ge=0, description="Count of explicit skills in CV")
    cv_implicit_count: int = Field(default=0, ge=0, description="Count of accepted implicit skills in CV")
    jd_explicit_count: int = Field(default=0, ge=0, description="Count of explicit skills in JD")
    jd_implicit_count: int = Field(default=0, ge=0, description="Count of accepted implicit skills in JD")
    duplicate_count: int = Field(
        default=0, ge=0, description="Total duplicate implicit skills detected across documents"
    )
    total_unique_skills: int = Field(
        default=0, ge=0, description="Total distinct canonical skill IDs across all accepted skills"
    )
    execution_time_ms: float = Field(
        default=0.0, ge=0.0, description="Total end-to-end execution time in milliseconds"
    )
    timings_ms: Dict[str, float] = Field(
        default_factory=dict,
        description="Granular duration breakdown per stage in milliseconds",
    )


class PipelineError(BaseModel):
    """Structured error entry for an extraction stage."""

    document: Optional[Literal["CV", "JD"]] = Field(
        default=None, description="Document type affected ('CV' or 'JD'), or None if request-level"
    )
    stage: str = Field(
        ...,
        description="Stage where error occurred ('parse', 'explicit_extraction', 'implicit_extraction', 'validation')",
    )
    error_type: str = Field(..., description="Exception class or error category name")
    message: str = Field(..., description="Human-readable error description")


class UnifiedExtractFileResponse(BaseModel):
    """Unified response containing both explicit and implicit extraction for CV and/or JD."""

    run_id: str = Field(..., description="Unique extraction run identifier for correlation")
    status: Literal["completed", "partial_success", "failed"] = Field(
        ...,
        description="Overall pipeline status: 'completed' | 'partial_success' | 'failed'",
    )
    cv: Optional[DocumentUnifiedResult] = Field(
        default=None,
        description="Unified extraction result for CV (if uploaded)",
    )
    jd: Optional[DocumentUnifiedResult] = Field(
        default=None,
        description="Unified extraction result for JD (if uploaded)",
    )
    cv_text: Optional[str] = Field(
        default=None,
        description="Full extracted raw text of the CV document",
    )
    jd_text: Optional[str] = Field(
        default=None,
        description="Full extracted raw text of the JD document",
    )
    summary: UnifiedExtractionSummary = Field(
        default_factory=UnifiedExtractionSummary,
        description="Aggregated counts and timing metrics",
    )
    errors: List[PipelineError] = Field(
        default_factory=list,
        description="List of errors encountered during pipeline execution",
    )
