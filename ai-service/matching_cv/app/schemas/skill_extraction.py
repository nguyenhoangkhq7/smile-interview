"""Pydantic schemas for explicit skill extraction output contract."""
import re
from typing import Any, Dict, List, Literal, Optional, Set
from pydantic import AliasChoices, BaseModel, Field, model_validator

# 6-category taxonomy
CategoryType = Literal[
    "Technology/Tool",
    "Technical Concept",
    "Engineering Practice",
    "Domain Knowledge",
    "Certification",
    "Technical Standard",
]

# Additive kind classification
KindType = Literal["skill", "domain", "context", "certification"]
KindSourceType = Literal["llm", "inferred", "invalid"]


def check_verbatim_mention(surface_form: str, sentence: str) -> bool:
    """Check if surface_form occurs in sentence (whitespace-tolerant, casefold)."""
    if not surface_form:
        return True
    norm_sf = re.sub(r"\s+", " ", surface_form).strip().casefold()
    norm_sent = re.sub(r"\s+", " ", sentence).strip().casefold()
    return norm_sf in norm_sent


# -----------------------------------------------------------------------------
# Raw Extraction (What the LLM must return)
# -----------------------------------------------------------------------------

class RawSkillMention(BaseModel):
    """Raw mention item as returned by the LLM."""

    surface_form: str = Field(
        ...,
        validation_alias=AliasChoices("surface_form", "mention"),
        description="Exact verbatim substring from the document",
    )
    category: Optional[str] = Field(
        default=None,
        description="Category string as returned by the LLM (not authoritative)",
    )
    kind: Optional[str] = Field(
        default=None,
        description="Additive kind: 'skill' | 'domain' | 'context' | 'certification', or raw string if LLM returned an invalid kind",
    )
    sentence: str = Field(
        ...,
        validation_alias=AliasChoices("sentence", "source_sentence"),
        description="Verbatim sentence containing the mention",
    )
    modifier_text: Optional[str] = Field(
        default=None,
        description="Verbatim qualifier, e.g. 'primary', 'basic', 'some'",
    )
    confidence: float = Field(
        default=1.0,
        ge=0.0,
        le=1.0,
        description="Confidence score between 0.0 and 1.0",
    )

    @property
    def mention(self) -> str:
        return self.surface_form

    @property
    def source_sentence(self) -> str:
        return self.sentence


class RawExtraction(BaseModel):
    """Container for raw extraction output returned by the LLM."""

    skills: List[RawSkillMention] = Field(
        default_factory=list,
        validation_alias=AliasChoices("skills", "explicit_skills"),
        description="List of raw extracted skill mentions",
    )

    @property
    def explicit_skills(self) -> List[RawSkillMention]:
        return self.skills


# -----------------------------------------------------------------------------
# Compact Extraction Schema (explicit_compact_v1)
# -----------------------------------------------------------------------------

class CompactSkillMention(BaseModel):
    """Compact raw skill item as returned by the LLM under explicit_compact_v1."""

    name: str = Field(..., description="Canonical or surface skill name")
    category: str = Field(
        default="Technology/Tool",
        description="Skill category (e.g. Technology/Tool, Engineering Practice, Domain Knowledge, Soft Skill, Productivity/Methodology, Other)",
    )
    mention: str = Field(
        ...,
        validation_alias=AliasChoices("mention", "surface_form"),
        description="Exact verbatim mention as written in the document",
    )


class CompactRawExtraction(BaseModel):
    """Container for raw compact extraction output under explicit_compact_v1."""

    skills: List[CompactSkillMention] = Field(
        default_factory=list,
        validation_alias=AliasChoices("skills", "explicit_skills"),
        description="List of compact extracted skill items",
    )
    schema_version: str = Field(default="explicit_compact_v1")

    @property
    def explicit_skills(self) -> List[CompactSkillMention]:
        return self.skills


# -----------------------------------------------------------------------------
# Final Output Contract (Per Document)
# -----------------------------------------------------------------------------

class Evidence(BaseModel):
    """Evidence instance with character offsets into the cleaned document text.

    Note on verification:
    - verbatim_ok, offset_resolved, and mention offsets (mention_start, mention_end)
      are deterministic checks.
    - `kind` is an unverified LLM judgement.
    """

    surface_form: str = Field(
        default="",
        description="Text as written in the document",
    )
    kind: Optional[KindType] = Field(
        default=None,
        description="'skill' | 'domain' | 'context' | 'certification' (unverified LLM judgement), or None if invalid",
    )
    kind_raw: Optional[str] = Field(
        default=None,
        description="Raw kind string as received from LLM",
    )
    kind_source: KindSourceType = Field(
        default="inferred",
        description="'llm' | 'inferred' | 'invalid'",
    )
    sentence: str = Field(..., description="Verbatim sentence containing the evidence")
    start: Optional[int] = Field(
        default=None,
        ge=0,
        description="Char start offset into document text, or None if unresolved",
    )
    end: Optional[int] = Field(
        default=None,
        ge=0,
        description="Char end offset into document text, or None if unresolved",
    )
    offset_resolved: bool = Field(
        default=False,
        description="Deterministic check: True if character offsets were successfully resolved",
    )
    verbatim_ok: bool = Field(
        default=True,
        description="Deterministic check: True if surface_form occurs in sentence (whitespace-tolerant, casefold)",
    )
    modifier_text: Optional[str] = Field(
        default=None,
        description="Verbatim qualifier, e.g. 'primary', 'basic', 'some'",
    )
    section: Optional[str] = Field(
        default=None,
        description="Section name where evidence occurs, determined by section_tagger",
    )
    category: Optional[CategoryType] = Field(
        default=None,
        description="6-category taxonomy classification, set only when one of 6 known values, otherwise None",
    )
    category_raw: Optional[str] = Field(
        default=None,
        description="Raw category string as received from LLM",
    )
    mention_start: Optional[int] = Field(
        default=None,
        ge=0,
        description="Deterministic check: Char start offset of mention into document text, or None if unresolved",
    )
    mention_end: Optional[int] = Field(
        default=None,
        ge=0,
        description="Deterministic check: Char end offset of mention into document text, or None if unresolved",
    )
    mention_ambiguous: bool = Field(
        default=False,
        description="True if surface_form occurs more than once inside the evidence sentence",
    )

    @model_validator(mode="before")
    @classmethod
    def compute_verbatim_ok(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if "verbatim_ok" not in data and "sentence" in data:
                sf = data.get("surface_form") or ""
                sent = data.get("sentence") or ""
                if sf:
                    norm_sf = re.sub(r"\s+", " ", sf).strip().casefold()
                    norm_sent = re.sub(r"\s+", " ", sent).strip().casefold()
                    data["verbatim_ok"] = norm_sf in norm_sent
        return data

    @model_validator(mode="after")
    def validate_offsets(self) -> "Evidence":
        if self.start is not None or self.end is not None:
            if self.start is None or self.end is None:
                raise ValueError("Both start and end must be provided if either is present")
            if self.start >= self.end:
                raise ValueError(
                    f"Evidence start offset ({self.start}) must be strictly less than end offset ({self.end})"
                )
            self.offset_resolved = True
        else:
            self.offset_resolved = False

        if self.mention_start is not None or self.mention_end is not None:
            if self.mention_start is None or self.mention_end is None:
                raise ValueError("Both mention_start and mention_end must be provided if either is present")
            if self.mention_start >= self.mention_end:
                raise ValueError(
                    f"Evidence mention_start offset ({self.mention_start}) must be strictly less than mention_end offset ({self.mention_end})"
                )
            if self.start is None or self.end is None or not self.offset_resolved:
                raise ValueError("Mention offsets cannot be present when evidence offsets (start, end) are unresolved")
            if self.mention_start < self.start or self.mention_end > self.end:
                raise ValueError(
                    f"Mention span [{self.mention_start}, {self.mention_end}] must be inside evidence span [{self.start}, {self.end}]"
                )

        return self


class ExtractedSkill(BaseModel):
    """Extracted skill deduplicated at the document level.

    Note on skill_id:
    `skill_id` is a slug of the first surface form, NOT a canonical id.
    No alias table is applied in this gate.
    """

    skill_id: str = Field(
        ...,
        pattern=r"^([a-z0-9][a-z0-9\-\.]*|unmapped:[a-z0-9\-\.]+)$",
        description="Deterministic slug of the first surface form, NOT a canonical id e.g. 'kafka' or 'unmapped:<slug>'",
    )
    surface_forms: List[str] = Field(
        default_factory=list,
        description="Unique surface forms in order of first occurrence",
    )
    category: Optional[CategoryType] = Field(
        default=None,
        description="Additive category classification",
    )
    category_raw: Optional[str] = Field(
        default=None,
        description="Raw category string as received from LLM",
    )
    kind: Optional[KindType] = Field(
        default=None,
        description="'skill' | 'domain' | 'context' | 'certification', derived from first evidence (unverified LLM judgement)",
    )
    type: Literal["explicit"] = Field(
        default="explicit",
        description="Extraction type (explicit)",
    )
    confidence: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Confidence score 0..1, or None (no calibrated value exists; postprocessor sets None)",
    )
    sections: List[str] = Field(
        default_factory=list,
        description="Unique list of sections where this skill appears, in order of first occurrence (excluding None)",
    )
    evidences: List[Evidence] = Field(
        default_factory=list,
        description="List of evidence citations and character offsets",
    )

    @model_validator(mode="after")
    def derive_fields(self) -> "ExtractedSkill":
        # If surface_forms is empty but evidences exist, populate from evidences
        if not self.surface_forms and self.evidences:
            seen: Set[str] = set()
            forms: List[str] = []
            for ev in self.evidences:
                if ev.surface_form and ev.surface_form not in seen:
                    seen.add(ev.surface_form)
                    forms.append(ev.surface_form)
            self.surface_forms = forms

        # Derive kind from first evidence if not explicitly set
        if self.kind is None and self.evidences:
            self.kind = self.evidences[0].kind

        # Derive category and category_raw from first evidence if not explicitly set
        if self.category is None and self.evidences:
            self.category = self.evidences[0].category
        if self.category_raw is None and self.evidences:
            self.category_raw = self.evidences[0].category_raw

        return self


class ExtractionStats(BaseModel):
    """Statistics on extracted mentions and unique skills."""

    total_mentions: int = Field(..., ge=0, description="Total evidence mentions count")
    unique_skills: int = Field(..., ge=0, description="Count of unique canonical skills")
    unresolved_evidences: int = Field(
        default=0,
        ge=0,
        description="Count of evidences where character offsets could not be resolved",
    )
    kind_conflicts: int = Field(
        default=0,
        ge=0,
        description="Count of skill_ids whose evidences carry different kinds",
    )
    non_verbatim_mentions: int = Field(
        default=0,
        ge=0,
        description="Count of evidences where verbatim_ok is False",
    )
    header_evidences: int = Field(
        default=0,
        ge=0,
        description=(
            "Count of resolved evidences located in section 'header'. "
            "Note: For documents without recognized section headings, the entire text falls into "
            "the fallback 'header' span, making this count equal to all resolved evidences. "
            "Thus, this stat is informative and only meaningful when section headings were found."
        ),
    )
    unresolved_mentions: int = Field(
        default=0,
        ge=0,
        description="Count of evidences where mention offsets could not be resolved (mention_start is None)",
    )
    ambiguous_mentions: int = Field(
        default=0,
        ge=0,
        description="Count of evidences where mention_ambiguous is True",
    )
    unknown_category_mentions: int = Field(
        default=0,
        ge=0,
        description="Count of evidences where category_raw is not in the 6 known categories",
    )
    invalid_kind_mentions: int = Field(
        default=0,
        ge=0,
        description="Count of evidences where kind is None (invalid kind received from LLM)",
    )
    quarantined_mentions: int = Field(
        default=0,
        ge=0,
        description="Count of raw items quarantined due to structural errors",
    )


class ExtractionMeta(BaseModel):
    """Metadata describing the extraction execution and prompt provenance."""

    prompt_sha256: str = Field(
        ...,
        description="SHA-256 hex digest of the system prompt actually sent to the client",
    )
    prompt_variant: Optional[str] = Field(
        default=None,
        description="Prompt variant identifier (e.g. 'default', 'V1', 'C1', 'C2', 'C3')",
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


class ExtractionResult(BaseModel):
    """Final contract for skill extraction per document."""

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
        description="SHA-256 hex digest of the exact document text indexed by evidences",
    )
    stats: ExtractionStats = Field(..., description="Summary statistics")
    skills: List[ExtractedSkill] = Field(
        default_factory=list,
        description="Deduplicated canonical skills",
    )
    quarantined: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Raw items quarantined due to structural errors with details",
    )
    extraction_meta: Optional[ExtractionMeta] = Field(
        default=None,
        description="Provenance metadata for the extraction run",
    )

    @model_validator(mode="after")
    def validate_invariants(self) -> "ExtractionResult":
        # Invariant 1: skill_id unique within a document
        skill_ids = [s.skill_id for s in self.skills]
        if len(skill_ids) != len(set(skill_ids)):
            duplicates = {sid for sid in skill_ids if skill_ids.count(sid) > 1}
            raise ValueError(
                f"Invariant violated: duplicate skill_id found within document: {duplicates}"
            )

        # Invariant 2: stats.total_mentions == sum(len(evidences))
        expected_total_mentions = sum(len(s.evidences) for s in self.skills)
        if self.stats.total_mentions != expected_total_mentions:
            raise ValueError(
                f"Invariant violated: stats.total_mentions ({self.stats.total_mentions}) "
                f"!= sum(len(evidences)) ({expected_total_mentions})"
            )

        # Invariant 3: stats.unique_skills == len(skills)
        if self.stats.unique_skills != len(self.skills):
            raise ValueError(
                f"Invariant violated: stats.unique_skills ({self.stats.unique_skills}) "
                f"!= len(skills) ({len(self.skills)})"
            )

        # Invariant 4: stats.unresolved_evidences == sum(1 for s in skills for ev in evidences if not ev.offset_resolved)
        expected_unresolved = sum(
            1 for s in self.skills for ev in s.evidences if not ev.offset_resolved
        )
        if self.stats.unresolved_evidences != expected_unresolved:
            raise ValueError(
                f"Invariant violated: stats.unresolved_evidences ({self.stats.unresolved_evidences}) "
                f"!= actual unresolved count ({expected_unresolved})"
            )

        # Invariant 5: stats.non_verbatim_mentions == sum(1 for s in skills for ev in evidences if not ev.verbatim_ok)
        expected_non_verbatim = sum(
            1 for s in self.skills for ev in s.evidences if not ev.verbatim_ok
        )
        if self.stats.non_verbatim_mentions != expected_non_verbatim:
            raise ValueError(
                f"Invariant violated: stats.non_verbatim_mentions ({self.stats.non_verbatim_mentions}) "
                f"!= actual non-verbatim count ({expected_non_verbatim})"
            )

        # Invariant 6: stats.kind_conflicts == number of skill_ids whose evidences carry different non-None kinds
        expected_kind_conflicts = sum(
            1 for s in self.skills if len({ev.kind for ev in s.evidences if ev.kind is not None}) > 1
        )
        if self.stats.kind_conflicts != expected_kind_conflicts:
            raise ValueError(
                f"Invariant violated: stats.kind_conflicts ({self.stats.kind_conflicts}) "
                f"!= actual conflicting skills count ({expected_kind_conflicts})"
            )

        # Invariant 7: stats.header_evidences == number of resolved evidences whose section == 'header'
        expected_header_evidences = sum(
            1 for s in self.skills for ev in s.evidences if ev.offset_resolved and ev.section == "header"
        )
        if self.stats.header_evidences != expected_header_evidences:
            raise ValueError(
                f"Invariant violated: stats.header_evidences ({self.stats.header_evidences}) "
                f"!= actual header evidences count ({expected_header_evidences})"
            )

        # Invariant 8: stats.unresolved_mentions == sum(1 for s in skills for ev in evidences if ev.mention_start is None)
        expected_unresolved_mentions = sum(
            1 for s in self.skills for ev in s.evidences if ev.mention_start is None
        )
        if self.stats.unresolved_mentions != expected_unresolved_mentions:
            raise ValueError(
                f"Invariant violated: stats.unresolved_mentions ({self.stats.unresolved_mentions}) "
                f"!= actual unresolved mentions count ({expected_unresolved_mentions})"
            )

        # Invariant 9: stats.ambiguous_mentions == sum(1 for s in skills for ev in evidences if ev.mention_ambiguous)
        expected_ambiguous_mentions = sum(
            1 for s in self.skills for ev in s.evidences if ev.mention_ambiguous
        )
        if self.stats.ambiguous_mentions != expected_ambiguous_mentions:
            raise ValueError(
                f"Invariant violated: stats.ambiguous_mentions ({self.stats.ambiguous_mentions}) "
                f"!= actual ambiguous mentions count ({expected_ambiguous_mentions})"
            )

        # Invariant 10: stats.unknown_category_mentions == sum(1 for s in skills for ev in evidences if ev.category_raw is not None and ev.category is None)
        expected_unknown_category = sum(
            1 for s in self.skills for ev in s.evidences if ev.category_raw is not None and ev.category is None
        )
        if self.stats.unknown_category_mentions != expected_unknown_category:
            raise ValueError(
                f"Invariant violated: stats.unknown_category_mentions ({self.stats.unknown_category_mentions}) "
                f"!= actual unknown category mentions count ({expected_unknown_category})"
            )

        # Invariant 11: stats.invalid_kind_mentions == sum(1 for s in skills for ev in evidences if ev.kind is None)
        expected_invalid_kind = sum(
            1 for s in self.skills for ev in s.evidences if ev.kind is None
        )
        if self.stats.invalid_kind_mentions != expected_invalid_kind:
            raise ValueError(
                f"Invariant violated: stats.invalid_kind_mentions ({self.stats.invalid_kind_mentions}) "
                f"!= actual invalid kind mentions count ({expected_invalid_kind})"
            )

        # Invariant 12: stats.quarantined_mentions == len(quarantined)
        expected_quarantined = len(self.quarantined)
        if self.stats.quarantined_mentions != expected_quarantined:
            raise ValueError(
                f"Invariant violated: stats.quarantined_mentions ({self.stats.quarantined_mentions}) "
                f"!= actual quarantined mentions count ({expected_quarantined})"
            )

        return self


# -----------------------------------------------------------------------------
# Request & Multi-file Response Wrappers
# -----------------------------------------------------------------------------

class SkillExtractRequest(BaseModel):
    """Request payload for explicit skill extraction from raw text."""

    document_type: Literal["CV", "JD"] = Field(
        ...,
        description="Loại tài liệu cần phân tích ('CV' hoặc 'JD')",
        examples=["CV"],
    )
    text: str = Field(
        ...,
        min_length=20,
        description="Văn bản thô cần trích xuất kỹ năng",
    )


class SkillExtractFileResponse(BaseModel):
    """Response payload for file upload skill extraction supporting CV and/or JD."""

    cv: Optional[ExtractionResult] = Field(
        default=None,
        description="Kết quả trích xuất kỹ năng từ tệp CV (nếu có)",
    )
    jd: Optional[ExtractionResult] = Field(
        default=None,
        description="Kết quả trích xuất kỹ năng từ tệp JD (nếu có)",
    )


# Backward-compatible alias
SkillExtractResponse = ExtractionResult
