"""Pydantic schemas for implicit skill extraction output contract.

Implicit skills are skills NOT explicitly stated in the document but
inferable from context, e.g.:
  - Skills implied by described experience ("built high-traffic API" → scalability)
  - Soft skills evident from role descriptions ("led a team of 5" → leadership)
  - Prerequisite/related skills of mentioned technologies ("Kafka" → distributed systems)
"""
from typing import Any, Dict, List, Literal, Optional
from pydantic import AliasChoices, BaseModel, ConfigDict, Field, model_validator


# Re-use same 6-category taxonomy from explicit extraction
CategoryType = Literal[
    "Technology/Tool",
    "Technical Concept",
    "Engineering Practice",
    "Domain Knowledge",
    "Soft Skill",
    "Certification",
]

BasisType = Literal[
    "activity",
    "role",
    "jd_role_context",
]


# -----------------------------------------------------------------------------
# Raw Extraction (What the LLM must return)
# -----------------------------------------------------------------------------

class RawImplicitSkillMention(BaseModel):
    """Raw implicit skill item as returned by the LLM."""

    skill_label: str = Field(
        ...,
        validation_alias=AliasChoices("skill_label", "label", "skill"),
        description="Normalized skill name, e.g. 'leadership', 'system design', 'scalability'",
    )
    category: Optional[str] = Field(
        default=None,
        description="Category string as returned by the LLM (not authoritative)",
    )
    inferred_from: str = Field(
        ...,
        validation_alias=AliasChoices("inferred_from", "source_sentence", "source"),
        description="Verbatim sentence or phrase from the document that led to this inference",
    )
    reasoning: Optional[str] = Field(
        default=None,
        description="Short explanation of why this skill is implied by the source text",
    )
    confidence: float = Field(
        default=0.7,
        ge=0.0,
        le=1.0,
        description="LLM self-assessed confidence 0..1 for this inference",
    )


class RawImplicitExtraction(BaseModel):
    """Container for raw implicit extraction output returned by the LLM."""

    implicit_skills: List[RawImplicitSkillMention] = Field(
        default_factory=list,
        validation_alias=AliasChoices("implicit_skills", "skills"),
        description="List of raw inferred implicit skill mentions",
    )


# -----------------------------------------------------------------------------
# Final Output Contract
# -----------------------------------------------------------------------------

class ImplicitEvidenceSnippet(BaseModel):
    """A resolved fragment of an implicit evidence string."""

    text: str = Field(..., description="Fragment text as split from inferred_from")
    start: Optional[int] = Field(
        default=None,
        ge=0,
        description="Char start offset into cleaned text, None if unresolved",
    )
    end: Optional[int] = Field(
        default=None,
        ge=0,
        description="Char end offset into cleaned text, None if unresolved",
    )
    section: Optional[str] = Field(
        default=None,
        description="Section name resolved via section_tagger, None if unresolved",
    )
    verbatim_ok: bool = Field(
        default=False,
        description="True if fragment was verbatim resolved in cleaned text",
    )
    ellipsis_in_snippet: bool = Field(
        default=False,
        description="True if fragment contained ellipsis ('...' or '…')",
    )


class ImplicitEvidence(BaseModel):
    """Evidence for an implicit skill — the source sentence fragments and reasoning chain."""

    model_config = ConfigDict(populate_by_name=True)

    inferred_from_raw: str = Field(
        ...,
        validation_alias=AliasChoices(
            "inferred_from_raw", "inferred_from", "source_sentence", "source"
        ),
        description="Raw verbatim sentence or phrase from document returned by LLM",
    )
    snippets: List[ImplicitEvidenceSnippet] = Field(
        default_factory=list,
        description="Resolved fragments split on ellipses ('...' / '…')",
    )
    reasoning: Optional[str] = Field(
        default=None,
        description="Short explanation of how the source implies this skill",
    )
    basis: Optional[BasisType] = Field(
        default=None,
        description="Inference basis for V2 items ('activity' | 'role' | 'jd_role_context')",
    )
    basis_raw: Optional[str] = Field(
        default=None,
        description="Raw basis string returned by LLM",
    )
    basis_invalid_for_cv: bool = Field(
        default=False,
        description="Flagged True if basis is 'jd_role_context' on a CV document",
    )
    llm_confidence_raw: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=1.0,
        validation_alias=AliasChoices("llm_confidence_raw", "confidence"),
        description="LLM self-assessed confidence for this specific inference (not used for stats)",
    )

    @property
    def inferred_from(self) -> str:
        return self.inferred_from_raw

    @property
    def confidence(self) -> Optional[float]:
        return self.llm_confidence_raw


class ImplicitExtractedSkill(BaseModel):
    """Inferred skill deduplicated at the document level.

    Note:
    - `skill_id` is a lowercase slug of `label`, NOT a canonical taxonomy id.
    - `confidence` is None (no calibrated value exists; kept as LLM self-report in evidences).
    - Unlike explicit skills, there are NO verbatim/offset constraints on the skill label itself.
    """

    skill_id: str = Field(
        ...,
        pattern=r"^([a-z0-9][a-z0-9\-\.]*|unmapped:[a-z0-9\-\.]+)$",
        description="Deterministic slug of the skill label, e.g. 'leadership' or 'system-design'",
    )
    label: str = Field(
        ...,
        description="Human-readable normalized skill name, e.g. 'Leadership', 'System Design'",
    )
    category: Optional[CategoryType] = Field(
        default=None,
        description="6-category taxonomy classification, None if LLM returned unknown category",
    )
    category_raw: Optional[str] = Field(
        default=None,
        description="Raw category string as received from LLM",
    )
    basis: Optional[BasisType] = Field(
        default=None,
        description="Inference basis for V2 items ('activity' | 'role' | 'jd_role_context')",
    )
    basis_raw: Optional[str] = Field(
        default=None,
        description="Raw basis string returned by LLM",
    )
    basis_invalid_for_cv: bool = Field(
        default=False,
        description="Flagged True if basis is 'jd_role_context' on a CV document",
    )
    type: Literal["implicit"] = Field(
        default="implicit",
        description="Extraction type (always 'implicit')",
    )
    confidence: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Confidence score 0..1, or None (no calibrated value; postprocessor sets None)",
    )
    decomposed_from: Optional[str] = Field(
        default=None,
        description="Original compound skill ID if decomposed from a compound candidate",
    )
    evidences: List[ImplicitEvidence] = Field(
        default_factory=list,
        description="List of source sentences and reasoning chains supporting this inference",
    )


class ImplicitExtractionStats(BaseModel):
    """Statistics for implicit extraction output."""

    total_inferences: int = Field(
        ..., ge=0, description="Total evidence inferences count (sum of len(evidences) per skill)"
    )
    unique_skills: int = Field(
        ..., ge=0, description="Count of unique inferred skills after deduplication"
    )
    unknown_category_count: int = Field(
        default=0,
        ge=0,
        description="Count of skills where category_raw is not in the known categories",
    )
    invalid_basis: int = Field(
        default=0,
        ge=0,
        description="Count of items where basis is not in the known basis types",
    )
    quarantined_mentions: int = Field(
        default=0,
        ge=0,
        description="Count of raw items quarantined due to structural errors",
    )
    non_verbatim_evidences: int = Field(
        default=0,
        ge=0,
        description="Count of evidences where at least one snippet has verbatim_ok False",
    )
    multi_fragment_evidences: int = Field(
        default=0,
        ge=0,
        description="Count of evidences split into more than 1 fragment snippet",
    )
    multi_section_evidences: int = Field(
        default=0,
        ge=0,
        description="Count of evidences whose snippets span more than 1 distinct section",
    )
    ellipsis_snippets: int = Field(
        default=0,
        ge=0,
        description="Count of snippets containing '...' or '…'",
    )
    basis_invalid_for_cv: int = Field(
        default=0,
        ge=0,
        description="Count of items where basis is 'jd_role_context' on a CV document",
    )

    @model_validator(mode="after")
    def check_consistency(self) -> "ImplicitExtractionStats":
        if self.unique_skills > self.total_inferences and self.total_inferences > 0:
            raise ValueError(
                f"unique_skills ({self.unique_skills}) cannot exceed total_inferences ({self.total_inferences})"
            )
        if self.multi_fragment_evidences > self.total_inferences:
            raise ValueError("multi_fragment_evidences cannot exceed total_inferences")
        if self.multi_section_evidences > self.multi_fragment_evidences:
            raise ValueError("multi_section_evidences cannot exceed multi_fragment_evidences")
        if self.non_verbatim_evidences > self.total_inferences:
            raise ValueError("non_verbatim_evidences cannot exceed total_inferences")
        if self.invalid_basis > self.total_inferences:
            raise ValueError("invalid_basis cannot exceed total_inferences")
        return self


class ExtractionMeta(BaseModel):
    """Metadata describing the extraction execution and prompt provenance."""

    prompt_sha256: str = Field(
        ...,
        description="SHA-256 hex digest of the system prompt actually sent to the client",
    )
    prompt_variant: Optional[str] = Field(
        default=None,
        description="Prompt variant identifier (e.g. 'default')",
    )
    model_configured: str = Field(
        ...,
        description="LLM model configured for extraction",
    )
    temperature: float = Field(
        default=0.0,
        description="Sampling temperature configured for extraction",
    )
    schema_version: str = Field(
        default="1.0.0",
        description="Schema contract version",
    )
    extracted_at: str = Field(
        ...,
        description="ISO 8601 timestamp of extraction",
    )
    confidence_calibrated: bool = Field(
        default=False,
        description="False: LLM confidence values are uncalibrated self-assessments",
    )
    explicit_source: Optional[str] = Field(
        default=None,
        description="Source of explicit mentions: 'extraction_result' | 'caller_list' | None",
    )


class ImplicitExtractionResult(BaseModel):
    """Final contract for implicit skill extraction per document."""

    filename: Optional[str] = Field(
        default=None,
        description="Document filename if uploaded as file, or None for raw text",
    )
    document_type: Optional[Literal["CV", "JD"]] = Field(
        default=None,
        description="Document type ('CV' | 'JD')",
    )
    text_sha256: Optional[str] = Field(
        default=None,
        description="SHA-256 hex digest of the exact document text used for inference",
    )
    stats: ImplicitExtractionStats = Field(..., description="Summary statistics")
    skills: List[ImplicitExtractedSkill] = Field(
        default_factory=list,
        description="Deduplicated inferred implicit skills",
    )
    quarantined: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Raw items quarantined due to structural errors",
    )
    extraction_meta: Optional[ExtractionMeta] = Field(
        default=None,
        description="Provenance metadata for the extraction run",
    )

    @model_validator(mode="after")
    def validate_invariants(self) -> "ImplicitExtractionResult":
        # Invariant 1: skill_id unique within a document
        skill_ids = [s.skill_id for s in self.skills]
        if len(skill_ids) != len(set(skill_ids)):
            duplicates = {sid for sid in skill_ids if skill_ids.count(sid) > 1}
            raise ValueError(
                f"Invariant violated: duplicate skill_id found: {duplicates}"
            )

        # Invariant 2: stats.unique_skills == len(skills)
        if self.stats.unique_skills != len(self.skills):
            raise ValueError(
                f"Invariant violated: stats.unique_skills ({self.stats.unique_skills}) "
                f"!= len(skills) ({len(self.skills)})"
            )

        # Invariant 3: stats.total_inferences == sum(len(evidences))
        expected_total = sum(len(s.evidences) for s in self.skills)
        if self.stats.total_inferences != expected_total:
            raise ValueError(
                f"Invariant violated: stats.total_inferences ({self.stats.total_inferences}) "
                f"!= sum(len(evidences)) ({expected_total})"
            )

        # Invariant 4: stats.quarantined_mentions == len(quarantined)
        if self.stats.quarantined_mentions != len(self.quarantined):
            raise ValueError(
                f"Invariant violated: stats.quarantined_mentions ({self.stats.quarantined_mentions}) "
                f"!= len(quarantined) ({len(self.quarantined)})"
            )

        # Invariant 5: stats.non_verbatim_evidences == sum(1 for s in skills for ev in evidences if any(not snip.verbatim_ok for snip in ev.snippets))
        expected_non_verbatim = sum(
            1 for s in self.skills for ev in s.evidences if any(not snip.verbatim_ok for snip in ev.snippets)
        )
        if self.stats.non_verbatim_evidences != expected_non_verbatim:
            raise ValueError(
                f"Invariant violated: stats.non_verbatim_evidences ({self.stats.non_verbatim_evidences}) "
                f"!= actual non-verbatim evidences count ({expected_non_verbatim})"
            )

        # Invariant 6: stats.multi_fragment_evidences == sum(1 for s in skills for ev in evidences if len(ev.snippets) > 1)
        expected_multi_frag = sum(
            1 for s in self.skills for ev in s.evidences if len(ev.snippets) > 1
        )
        if self.stats.multi_fragment_evidences != expected_multi_frag:
            raise ValueError(
                f"Invariant violated: stats.multi_fragment_evidences ({self.stats.multi_fragment_evidences}) "
                f"!= actual multi-fragment evidences count ({expected_multi_frag})"
            )

        # Invariant 7: stats.multi_section_evidences == sum(1 for s in skills for ev in evidences if len({snip.section for snip in ev.snippets if snip.section is not None}) > 1)
        expected_multi_sec = sum(
            1 for s in self.skills for ev in s.evidences if len({snip.section for snip in ev.snippets if snip.section is not None}) > 1
        )
        if self.stats.multi_section_evidences != expected_multi_sec:
            raise ValueError(
                f"Invariant violated: stats.multi_section_evidences ({self.stats.multi_section_evidences}) "
                f"!= actual multi-section evidences count ({expected_multi_sec})"
            )

        # Invariant 8: stats.invalid_basis == sum(1 for s in skills for ev in evidences if ev.basis is None and ev.basis_raw is not None)
        expected_invalid_basis = sum(
            1 for s in self.skills for ev in s.evidences if ev.basis is None and ev.basis_raw is not None
        )
        if self.stats.invalid_basis != expected_invalid_basis:
            raise ValueError(
                f"Invariant violated: stats.invalid_basis ({self.stats.invalid_basis}) "
                f"!= actual invalid basis count ({expected_invalid_basis})"
            )

        # Invariant 9: stats.ellipsis_snippets == sum(1 for s in skills for ev in evidences for snip in ev.snippets if snip.ellipsis_in_snippet)
        expected_ellipsis_snippets = sum(
            1 for s in self.skills for ev in s.evidences for snip in ev.snippets if snip.ellipsis_in_snippet
        )
        if self.stats.ellipsis_snippets != expected_ellipsis_snippets:
            raise ValueError(
                f"Invariant violated: stats.ellipsis_snippets ({self.stats.ellipsis_snippets}) "
                f"!= actual ellipsis snippets count ({expected_ellipsis_snippets})"
            )

        # Invariant 10: stats.basis_invalid_for_cv == sum(1 for s in skills for ev in evidences if ev.basis_invalid_for_cv)
        expected_basis_invalid_for_cv = sum(
            1 for s in self.skills for ev in s.evidences if ev.basis_invalid_for_cv
        )
        if self.stats.basis_invalid_for_cv != expected_basis_invalid_for_cv:
            raise ValueError(
                f"Invariant violated: stats.basis_invalid_for_cv ({self.stats.basis_invalid_for_cv}) "
                f"!= actual basis_invalid_for_cv count ({expected_basis_invalid_for_cv})"
            )

        return self


# -----------------------------------------------------------------------------
# Request & Response Wrappers
# -----------------------------------------------------------------------------

class ImplicitSkillExtractRequest(BaseModel):
    """Request payload for implicit skill extraction from raw text."""

    document_type: Literal["CV", "JD"] = Field(
        ...,
        description="Loại tài liệu cần phân tích ('CV' hoặc 'JD')",
        examples=["CV"],
    )
    text: str = Field(
        ...,
        min_length=20,
        description="Văn bản thô cần suy luận kỹ năng ẩn",
    )
    explicit_mentions: Optional[List[str]] = Field(
        default=None,
        description="Danh sách các kỹ năng tường minh đã trích xuất",
    )
    explicit_result: Optional[Any] = Field(
        default=None,
        description="Kết quả trích xuất kỹ năng tường minh (ExtractionResult hoặc stored run dict)",
    )


class ImplicitSkillExtractFileResponse(BaseModel):
    """Response payload for file upload implicit skill extraction."""

    cv: Optional[ImplicitExtractionResult] = Field(
        default=None,
        description="Kết quả trích xuất kỹ năng ẩn từ tệp CV (nếu có)",
    )
    jd: Optional[ImplicitExtractionResult] = Field(
        default=None,
        description="Kết quả trích xuất kỹ năng ẩn từ tệp JD (nếu có)",
    )


# -----------------------------------------------------------------------------
# Raw Extraction V2 & Verifier Schemas
# -----------------------------------------------------------------------------

class RawImplicitSkillMentionV2(BaseModel):
    """Raw implicit skill item as returned by the V2 LLM prompt."""

    label: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("label", "skill_label", "skill"),
        description="Generic skill name (2-5 words)",
    )
    basis: Optional[str] = Field(
        default=None,
        description="Basis of inference: 'activity' | 'role' | 'jd_role_context'",
    )
    evidence: Optional[Any] = Field(
        default=None,
        validation_alias=AliasChoices("evidence", "snippets"),
        description="List of verbatim snippet substrings from the document",
    )


class RawImplicitExtractionV2(BaseModel):
    """Container for raw V2 implicit extraction output returned by LLM."""

    implicit_skills: List[Dict[str, Any]] = Field(
        default_factory=list,
        validation_alias=AliasChoices("implicit_skills", "skills"),
        description="List of raw inferred implicit skills",
    )


VerdictType = Literal[
    "entailed",
    "plausible",
    "unsupported",
    "normal_for_role",
    "possible",
    "invalid",
    "invalid_for_basis",
]


class CandidateVerification(BaseModel):
    """Result of candidate verification against document text and explicit mentions."""

    label: str = Field(..., description="Candidate skill label")
    basis: Optional[str] = Field(
        default=None,
        description="Inference basis of the candidate: 'activity' | 'role' | 'jd_role_context'",
    )
    verdict: VerdictType = Field(..., description="Verification verdict")
    covered_by: Optional[str] = Field(
        default=None,
        description="Explicit mention that covers or duplicates this skill, or None",
    )
    note: Optional[str] = Field(
        default=None,
        description="One-sentence verification reasoning note",
    )
    model_used: Optional[str] = Field(
        default=None,
        description="Model identifier actually used by the verifier",
    )

    def __getitem__(self, item: str) -> Any:
        return getattr(self, item)


class VerifierResponse(BaseModel):
    """Response returned by candidate verifier."""

    verifications: List[CandidateVerification] = Field(
        default_factory=list,
        description="List of candidate verifications",
    )


class CandidateVerificationRequest(BaseModel):
    """Request schema for candidate verification endpoint."""

    text: str = Field(..., min_length=1, description="Document text")
    candidates: List[Any] = Field(..., description="Candidate implicit skills")
    explicit_mentions: Optional[List[str]] = Field(
        default=None,
        description="Explicit mentions list",
    )
    explicit_result: Optional[Any] = Field(
        default=None,
        description="Explicit extraction result or stored run",
    )

