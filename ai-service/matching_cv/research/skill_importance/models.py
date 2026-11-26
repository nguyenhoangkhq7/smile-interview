"""Data contracts and schemas for Job2Skills-Inspired Skill Importance Estimator (JSI-v1)."""
from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, Field


SectionType = Literal[
    "requirements",
    "responsibilities",
    "nice_to_have",
    "about",
    "benefits",
    "header",
    "unknown",
]

TitleDetectionStatus = Literal["RESOLVED", "LOW_CONFIDENCE", "UNRESOLVED"]


class JDSectionSpan(BaseModel):
    """Represents a recognized structural section span within a Job Description."""

    section_type: SectionType = Field(
        ...,
        description="Classified section category: requirements | responsibilities | nice_to_have | about | benefits | header | unknown",
    )
    heading_text: str = Field(
        ...,
        description="Verbatim heading string extracted from the document",
    )
    start: int = Field(
        ...,
        ge=0,
        description="Character start offset of the section (from heading start)",
    )
    end: int = Field(
        ...,
        ge=0,
        description="Character end offset of the section (runs to next heading or EOF)",
    )
    confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Detection confidence of this heading classification",
    )
    detection_method: str = Field(
        ...,
        description="Method that matched the heading (e.g. 'alias_exact', 'pattern_numbered', 'regex_all_caps')",
    )


class JobTitleResult(BaseModel):
    """Result of deterministic Job Title extraction."""

    job_title: Optional[str] = Field(
        default=None,
        description="Extracted or inferred Job Title, or None if unresolved",
    )
    title_confidence: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Confidence in the extracted title",
    )
    detection_method: str = Field(
        ...,
        description="Method used for extraction (e.g. 'first_line_pattern', 'explicit_prefix', 'narrative_opening', 'unresolved')",
    )
    detection_status: TitleDetectionStatus = Field(
        ...,
        description="Resolution status: RESOLVED | LOW_CONFIDENCE | UNRESOLVED",
    )


class SkillSentenceOccurrence(BaseModel):
    """Discrete textual occurrence linking a skill entity to its containing sentence and section."""

    canonical_skill_id: str = Field(..., description="Canonical skill identifier")
    skill_display_name: str = Field(..., description="Canonical display name of the skill")
    skill_type: Literal["explicit", "implicit"] = Field(..., description="Skill extraction type")
    source_sentence: str = Field(..., description="Verbatim sentence containing or implying the skill")
    source_start: Optional[int] = Field(default=None, ge=0, description="Char start of sentence in cleaned JD text")
    source_end: Optional[int] = Field(default=None, ge=0, description="Char end of sentence in cleaned JD text")
    mention_start: Optional[int] = Field(default=None, ge=0, description="Char start of mention token in cleaned text")
    mention_end: Optional[int] = Field(default=None, ge=0, description="Char end of mention token in cleaned text")
    section_type: Optional[str] = Field(default=None, description="Section classification containing this occurrence")
    section_confidence: float = Field(default=0.0, ge=0.0, le=1.0, description="Confidence of the section assignment")
    modifier_text: Optional[str] = Field(default=None, description="Verbatim modifier qualifier if extracted")
    evidence_type: str = Field(default="explicit_mention", description="Origin: explicit_mention | implicit_snippet | implicit_inferred")


class SentenceSalienceResult(BaseModel):
    """Sentence-level salience estimation for a single occurrence."""

    raw_cosine: float = Field(..., description="Raw SBERT cosine similarity between skill and sentence in [-1, 1]")
    transformed_similarity: float = Field(..., ge=0.0, le=1.0, description="Linear monotonic mapping of cosine into [0, 1]")
    modality_category: str = Field(..., description="Deontic category: Mandatory | Operational | Preferred | Contextual | Negated")
    modality_score: float = Field(..., ge=0.0, le=1.0, description="Numeric modality weight (1.00, 0.75, 0.50, 0.25, 0.00)")
    is_negated: bool = Field(default=False, description="True if the skill is negated in the local clause ('not required')")
    sentence_salience: float = Field(..., ge=0.0, le=1.0, description="Combined sentence salience score")
    matched_clause: Optional[str] = Field(default=None, description="Local sub-clause evaluated for modality")


class SegmentSalienceResult(BaseModel):
    """Segment-level (section) salience estimation for a skill."""

    section_type: Optional[str] = Field(default=None, description="Best containing section, or None if unavailable")
    section_prior_weight: Optional[float] = Field(default=None, description="Assigned section prior weight, or None if unavailable")
    section_confidence: float = Field(default=0.0, ge=0.0, le=1.0, description="Confidence in section classification")
    is_available: bool = Field(..., description="True if valid section classification was available, False if unresolved")
    segment_salience: Optional[float] = Field(default=None, description="Segment salience score, or None if unavailable")
    multi_occurrence_strategy: str = Field(default="max_pooling", description="Strategy used across multiple sections")


class JobSalienceResult(BaseModel):
    """Job-level salience estimation for a skill."""

    title_similarity: Optional[float] = Field(default=None, description="Similarity to Job Title, or None if title unavailable")
    requirements_similarity: float = Field(..., description="Similarity to full requirements centroid vector")
    loo_requirements_similarity: Optional[float] = Field(
        default=None,
        description="Leave-One-Out similarity excluding this skill's own evidence sentences",
    )
    is_title_available: bool = Field(..., description="True if Job Title was resolved and used")
    job_salience: float = Field(..., ge=0.0, le=1.0, description="Combined job salience score")


class SkillImportanceScore(BaseModel):
    """Auditable importance score components and aggregated weight w_j."""

    sentence_salience: float = Field(..., ge=0.0, le=1.0, description="Aggregated sentence-level salience")
    segment_salience: Optional[float] = Field(
        default=None,
        description="Segment-level salience, or None if section was unavailable",
    )
    job_salience: float = Field(..., ge=0.0, le=1.0, description="Job-level salience")
    importance_score_raw: float = Field(..., ge=0.0, le=1.0, description="Raw ensemble importance over available dimensions")
    w_j: float = Field(..., ge=0.10, le=1.00, description="Final normalized importance weight mapped into [0.10, 1.00]")
    available_dimensions: List[str] = Field(..., description="List of dimensions used: ['sentence', 'segment', 'job']")
    normalization_method: str = Field(
        default="provisional_fixed_monotonic",
        description="Method used to produce w_j: 'provisional_fixed_monotonic'",
    )


class SkillImportanceProvenance(BaseModel):
    """Audit metadata tracing provenance of scoring."""

    source_sentences: List[str] = Field(default_factory=list, description="All verbatim sentences associated with this skill")
    source_sections: List[str] = Field(default_factory=list, description="All unique sections where this skill occurred")
    job_title: Optional[str] = Field(default=None, description="Job title used for scoring, or None if unavailable")
    scoring_version: str = Field(default="jsi-v1", description="Model and heuristic scoring version")
    dimension_breakdown: Optional[Dict[str, Any]] = Field(default=None, description="Detailed sub-scores for offline analysis")


class SkillImportanceOutput(BaseModel):
    """Complete auditable research output contract for a single JD skill entity."""

    canonical_skill_id: str = Field(..., description="Canonical skill identifier")
    skill_display_name: str = Field(..., description="Canonical display name")
    type: Literal["explicit", "implicit"] = Field(..., description="Extraction type")
    importance: SkillImportanceScore = Field(..., description="Importance scores and w_j")
    provenance: SkillImportanceProvenance = Field(..., description="Traceability provenance")


class JDEstimationResult(BaseModel):
    """Aggregate result of running JD Skill Importance Estimator on a document."""

    job_title_result: JobTitleResult = Field(..., description="Extracted job title information")
    sections: List[JDSectionSpan] = Field(default_factory=list, description="Parsed document sections")
    skills: List[SkillImportanceOutput] = Field(default_factory=list, description="Scored skills with importance")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Execution and summary metadata")
