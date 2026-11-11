"""Versioned public response contract for the CV-JD pipeline (``standardized-output-v1``).

This module defines the ONLY default public response for:
  * ``POST /api/v1/pipeline/analyze``

It is deliberately separate from the internal ``PipelineAnalyzeResponse`` DTO, which contains
pipeline diagnostics that are not part of the public contract.

Field order is part of the contract: Pydantic v2 serialises fields in declaration order, so
``match_score`` is always the first JSON key. Nullable fields are always present (never omitted).

Semantics are documented in ``docs/unified_pipeline_api.md``.
"""
from __future__ import annotations

from typing import List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

STANDARDIZED_OUTPUT_SCHEMA_VERSION = "standardized-output-v1"
STANDARDIZED_OUTPUT_VERSION_HEADER = "X-Output-Schema-Version"

PublicStatus = Literal[
    "MODEL_READY",  # verified trained checkpoint produced `match_score`
    "COMPLETED",  # backwards-compatible alias for MODEL_READY
    "MODEL_NOT_TRAINED",  # no verified trained PaperAlignedHybridGNN checkpoint -> match_score is null
    "MODEL_INCOMPATIBLE",  # a checkpoint exists but was rejected (architecture mismatch) -> match_score is null
    "INFERENCE_FAILED",  # GNN inference raised an unexpected error -> match_score is null
]

SkillType = Literal["explicit", "implicit"]


class SkillGapRow(BaseModel):
    """One row per unique retained JD competency. Exactly four fields."""

    model_config = ConfigDict(extra="forbid")

    jd_skill_id: str = Field(..., description="Normalized canonical ID of the retained JD skill")
    w_j: Optional[float] = Field(
        default=None,
        description=(
            "JD-skill importance for Skill Gap Analysis. Null when no eligible weight is available."
        ),
    )
    matched_cv_skill_id: Optional[str] = Field(
        default=None,
        description=(
            "Canonical ID of the candidate retained CV skill: the verified-identity CV skill when the JD skill "
            "is a shared graph node, otherwise the top JD-to-CV SBERT cosine candidate with cosine >= threshold. "
            "Null when no eligible CV skill satisfies the policy. This is an evidence candidate, NOT proof of "
            "skill satisfaction or requirement fulfillment."
        ),
    )
    soft_match: Optional[float] = Field(
        default=None,
        description=(
            "Raw SBERT cosine similarity in [-1, 1] between the selected JD/CV skill pair (no rescaling, no "
            "clipping, rounded to 6 decimals). Null when matched_cv_skill_id is null or no embedding exists. "
            "Pure vector similarity in embedding space; NOT a GNN score, NOT a proficiency score, and NOT an "
            "extraction confidence."
        ),
    )


class ProficiencySkill(BaseModel):
    """One retained skill of one document side."""

    model_config = ConfigDict(extra="forbid")

    skill_id: str = Field(..., description="Normalized canonical skill ID (side-specific identity)")
    skill_name: Optional[str] = Field(
        default=None,
        description="Human-readable display name",
    )
    type: SkillType = Field(..., description="Original extraction classification: 'explicit' or 'implicit'")
    confidence: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Source extraction confidence in [0,1] when one exists upstream; otherwise null",
    )
    w_j: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="JD-skill importance weight w_j in [0.0, 1.0]. Populated for JD skills when importance is enabled; None for CV skills.",
    )
    evidence_spans: List[str] = Field(
        default_factory=list,
        description="Verbatim evidence sentences verified to occur in the source document text (deduplicated)",
    )
    importance_status: Optional[str] = Field(
        default=None,
        description="Status of skill importance estimation (e.g. SUCCESS, DISABLED, ESTIMATION_FAILED)",
    )
    importance_estimator_version: Optional[str] = Field(
        default=None,
        description="Estimator release version (e.g. jsi4_v4_ensemble)",
    )


class ProficiencyInput(BaseModel):
    """CV and JD skill collections; never mixed."""

    model_config = ConfigDict(extra="forbid")

    cv_skills: List[ProficiencySkill] = Field(default_factory=list)
    jd_skills: List[ProficiencySkill] = Field(default_factory=list)


class StandardizedPipelineOutput(BaseModel):
    """Default public response (exactly six top-level fields, fixed order)."""

    model_config = ConfigDict(extra="forbid")

    match_score: Optional[float] = Field(
        default=None,
        description=(
            "Actual output of a verified trained PaperAlignedHybridGNN checkpoint (the model's "
            "`matching_score`, scale documented in score_scale of the internal result). "
            "Null until such a checkpoint exists. Never a heuristic or cosine average."
        ),
    )
    status: PublicStatus = Field(..., description="Why match_score is or is not present")
    cv_text: str = Field(..., description="Stage 1 cleaned CV text (whitespace normalization already applied)")
    jd_text: str = Field(..., description="Stage 1 cleaned JD text (whitespace normalization already applied)")
    skill_gap_input: List[SkillGapRow] = Field(
        default_factory=list,
        description=(
            "Handoff input payload for future Skill Gap Analysis module (retained JD requirements paired with "
            "verified identity or best SBERT retrieval candidate). This is raw pipeline evidence, NOT the final "
            "computed skill gap evaluation."
        ),
    )
    proficiency_input: ProficiencyInput = Field(
        default_factory=ProficiencyInput,
        description=(
            "Handoff input payload for future Proficiency Assessment module (segregated collections of retained "
            "CV and JD skills with extraction types, confidences, and verbatim evidence spans)."
        ),
    )


class PublicErrorResponse(BaseModel):
    """Error envelope for requests that fail before a standardized output can be produced (HTTP 4xx/5xx)."""

    model_config = ConfigDict(extra="forbid")

    status: Literal["failed"] = "failed"
    run_id: Optional[str] = None
    stage: str
    error_code: str
    message: str
    retryable: bool = False
