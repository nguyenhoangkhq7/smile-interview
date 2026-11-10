"""Production Skill Importance Service (JSI-5.4 Phase B).

Integrates the JSI-4 V4 JD Skill Importance Estimator into production inference
as an independent, auditable capability completely decoupled from Coverage Calculation
and Hybrid Reranking.

Strict Production Invariants:
- GNN Isolation: Never writes w_j to graph tensors or mutates edge proficiency p_j.
- Hybrid Isolation: Never computes hybrid scores or coverage during independent importance evaluation.
- Deterministic Output: Sorted by importance weight w_j descending, then canonical skill ID ascending.
- Weight Validation: Every eligible competency satisfies 0.0 <= w_j <= 1.0 (rejects NaN/Inf).
- Privacy & PII: Logs and caches strictly omit verbatim document text and candidate PII.
- Non-Fatal Resilience: Inference failures return an explicit status without failing GNN matching.
"""
from __future__ import annotations

from enum import Enum
import logging
import math
import time
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field

from matching_cv.app.core.config import settings
from matching_cv.research.data.canonical_skill_normalizer import normalize_canonical_skill
from matching_cv.research.skill_importance.importance_service import (
    ESTIMATOR_VERSION,
    JSI4ImportanceRecord,
    JSI4ImportanceService,
    JDImportanceResponse,
    jsi4_importance_service,
)

logger = logging.getLogger(__name__)


class ImportanceStatus(str, Enum):
    """Explicit operational statuses for production skill importance inference."""
    SUCCESS = "SUCCESS"
    DISABLED = "DISABLED"
    NO_ELIGIBLE_SKILLS = "NO_ELIGIBLE_SKILLS"
    ESTIMATION_FAILED = "ESTIMATION_FAILED"
    INVALID_OUTPUT = "INVALID_OUTPUT"


class ProductionSkillImportanceRecord(BaseModel):
    """Production record for a single JD requirement competency."""

    skill_id: str = Field(..., description="Normalized canonical skill identifier")
    skill_name: str = Field(..., description="Human-readable display name")
    weight: float = Field(..., ge=0.0, le=1.0, description="Normalized JSI-4 importance weight w_j in [0.0, 1.0]")
    raw_score: Optional[float] = Field(default=None, description="Raw uncalibrated continuous ensemble score")
    modality: str = Field(default="MUST_HAVE", description="Deontic modality (MUST_HAVE, SHOULD_HAVE, etc.)")
    eligibility: str = Field(default="VALID_TECHNOLOGY", description="Competency eligibility classification")
    polarity: Literal["POSITIVE", "NEGATED", "EXCLUDED"] = Field(default="POSITIVE")
    is_eligible: bool = Field(default=True, description="True if entity is an eligible technical skill")
    group_type: Literal["SOLO", "OR", "AND"] = Field(default="SOLO", description="Logical group structure")
    requirement_group_id: Optional[str] = Field(default=None, description="Linked clause identifier for OR/AND groups")
    group_members: List[str] = Field(default_factory=list, description="IDs of other members in the logical group")
    explanation: Optional[str] = Field(default=None, description="Human-readable explanation of assigned weight")
    evidence: List[str] = Field(default_factory=list, description="Verbatim source sentence evidence")


class ProductionSkillImportanceOutput(BaseModel):
    """Standardized production contract for JD skill importance inference."""

    status: ImportanceStatus = Field(default=ImportanceStatus.SUCCESS, description="Operational status")
    estimator_version: str = Field(default=ESTIMATOR_VERSION, description="Estimator release version")
    total_skills_received: int = Field(default=0, description="Total input competencies processed")
    eligible_skills_count: int = Field(default=0, description="Number of eligible positive competencies")
    excluded_skills_count: int = Field(default=0, description="Number of ineligible or excluded entities")
    records: List[ProductionSkillImportanceRecord] = Field(
        default_factory=list,
        description="Deterministic list of eligible positive competencies with importance weights w_j",
    )
    excluded_records: List[ProductionSkillImportanceRecord] = Field(
        default_factory=list,
        description="Diagnostic records for excluded, negated, or non-technical entities",
    )
    execution_time_ms: float = Field(default=0.0, description="Inference latency in milliseconds")
    error_message: Optional[str] = Field(default=None, description="Sanitized diagnostic message if failed")
    cache_hit: bool = Field(default=False, description="True if result was served from in-memory cache")


class ProductionSkillImportanceService:
    """Production service for independent JD skill importance estimation."""

    def __init__(self, backend_service: Optional[JSI4ImportanceService] = None) -> None:
        self.backend = backend_service or jsi4_importance_service

    def is_feature_enabled(self) -> bool:
        """Check whether production skill importance inference is active."""
        return bool(getattr(settings, "JSI_IMPORTANCE_ENABLED", False))

    def evaluate_jd_importance(
        self,
        jd_text: str,
        explicit_skills: Optional[List[Dict[str, Any]]] = None,
        implicit_skills: Optional[List[Dict[str, Any]]] = None,
        job_title: Optional[str] = None,
        jd_id: Optional[str] = None,
        force_enable: bool = False,
    ) -> ProductionSkillImportanceOutput:
        """
        Evaluate importance weights w_j for eligible JD competencies.

        Guarantees:
        - If feature flag is False and force_enable is False: returns status DISABLED immediately.
        - Enforces strict numeric bounds [0.0, 1.0], rejecting NaN / Inf / Negative.
        - Preserves canonical IDs and applies deterministic ordering (weight desc, id asc).
        - Segregates positive eligible technical skills from negated skills and collaborator actors.
        - Non-fatal exception handling: never raises unhandled exceptions to callers.
        """
        t0 = time.perf_counter()

        # Step 1: Feature Flag Check
        if not self.is_feature_enabled() and not force_enable:
            return ProductionSkillImportanceOutput(
                status=ImportanceStatus.DISABLED,
                estimator_version=ESTIMATOR_VERSION,
                total_skills_received=0,
                eligible_skills_count=0,
                excluded_skills_count=0,
                records=[],
                excluded_records=[],
                execution_time_ms=0.0,
                error_message="Skill importance estimation is disabled by configuration (JSI_IMPORTANCE_ENABLED=False).",
            )

        # Step 2: Input Validation Check
        if not jd_text or not jd_text.strip():
            return ProductionSkillImportanceOutput(
                status=ImportanceStatus.NO_ELIGIBLE_SKILLS,
                estimator_version=ESTIMATOR_VERSION,
                total_skills_received=0,
                eligible_skills_count=0,
                excluded_skills_count=0,
                records=[],
                excluded_records=[],
                execution_time_ms=round((time.perf_counter() - t0) * 1000.0, 3),
                error_message="Job Description text is empty.",
            )

        exp_list = explicit_skills or []
        imp_list = implicit_skills or []
        total_received = len(exp_list) + len(imp_list)

        if total_received == 0:
            return ProductionSkillImportanceOutput(
                status=ImportanceStatus.NO_ELIGIBLE_SKILLS,
                estimator_version=ESTIMATOR_VERSION,
                total_skills_received=0,
                eligible_skills_count=0,
                excluded_skills_count=0,
                records=[],
                excluded_records=[],
                execution_time_ms=round((time.perf_counter() - t0) * 1000.0, 3),
                error_message="No skills were extracted from the Job Description.",
            )

        # Step 3: Invoke Backend Estimator
        try:
            # Check cache state prior to invocation for observability
            cache_key = self.backend._compute_cache_key(jd_text, exp_list, imp_list, job_title)
            was_cached = cache_key in self.backend._cache

            raw_resp: JDImportanceResponse = self.backend.estimate_jd_importance(
                jd_text=jd_text,
                explicit_skills=exp_list,
                implicit_skills=imp_list,
                job_title=job_title,
                jd_id=jd_id,
            )

            # Step 4: Validate and Convert Records
            validated_records: List[ProductionSkillImportanceRecord] = []
            validated_excluded: List[ProductionSkillImportanceRecord] = []
            seen_canonical_ids: set[str] = set()

            for rec in raw_resp.importance_records:
                cid = normalize_canonical_skill(rec.canonical_skill_id) or rec.canonical_skill_id.strip().lower()
                if not cid or cid in seen_canonical_ids:
                    continue
                seen_canonical_ids.add(cid)

                # Weight validation: must be finite, non-null, within [0.0, 1.0]
                w = rec.importance_weight
                if w is None or not math.isfinite(w) or w < 0.0 or w > 1.0:
                    logger.warning(
                        f"ProductionSkillImportanceService: Rejecting invalid importance weight ({w}) for skill '{cid}'."
                    )
                    continue

                # Polarity and Eligibility validation
                if rec.polarity != "POSITIVE" or not rec.is_eligible_for_ranking:
                    # Move to excluded list rather than positive eligible
                    validated_excluded.append(
                        ProductionSkillImportanceRecord(
                            skill_id=cid,
                            skill_name=rec.skill_display_name,
                            weight=round(w, 4),
                            raw_score=rec.raw_importance_score,
                            modality=rec.modality,
                            eligibility=rec.eligibility,
                            polarity=rec.polarity,
                            is_eligible=False,
                            group_type=rec.group_type,
                            requirement_group_id=rec.requirement_group_id,
                            group_members=rec.group_members,
                            explanation=rec.diagnostic_notes or f"Excluded: polarity={rec.polarity}, eligibility={rec.eligibility}",
                            evidence=rec.evidence[:2],
                        )
                    )
                    continue

                # Generate human-readable importance explanation
                explanation = self._build_explanation(rec)

                validated_records.append(
                    ProductionSkillImportanceRecord(
                        skill_id=cid,
                        skill_name=rec.skill_display_name,
                        weight=round(w, 4),
                        raw_score=rec.raw_importance_score,
                        modality=rec.modality,
                        eligibility=rec.eligibility,
                        polarity="POSITIVE",
                        is_eligible=True,
                        group_type=rec.group_type,
                        requirement_group_id=rec.requirement_group_id,
                        group_members=rec.group_members,
                        explanation=explanation,
                        evidence=rec.evidence[:2],
                    )
                )

            # Convert backend excluded records
            for ex_rec in raw_resp.excluded_records:
                cid = normalize_canonical_skill(ex_rec.canonical_skill_id) or ex_rec.canonical_skill_id.strip().lower()
                w_val = ex_rec.importance_weight if (ex_rec.importance_weight is not None and math.isfinite(ex_rec.importance_weight)) else 0.0
                w_val = min(1.0, max(0.0, w_val))
                validated_excluded.append(
                    ProductionSkillImportanceRecord(
                        skill_id=cid,
                        skill_name=ex_rec.skill_display_name,
                        weight=round(w_val, 4),
                        raw_score=ex_rec.raw_importance_score,
                        modality=ex_rec.modality,
                        eligibility=ex_rec.eligibility,
                        polarity=ex_rec.polarity,
                        is_eligible=False,
                        group_type=ex_rec.group_type,
                        requirement_group_id=ex_rec.requirement_group_id,
                        group_members=ex_rec.group_members,
                        explanation=ex_rec.diagnostic_notes or f"Excluded ({ex_rec.eligibility}): {ex_rec.polarity}",
                        evidence=ex_rec.evidence[:2],
                    )
                )

            # Deterministic sorting: weight descending, then canonical skill_id ascending
            validated_records.sort(key=lambda r: (-r.weight, r.skill_id))
            validated_excluded.sort(key=lambda r: (r.skill_id,))

            elapsed_ms = round((time.perf_counter() - t0) * 1000.0, 3)

            status = ImportanceStatus.SUCCESS if validated_records else ImportanceStatus.NO_ELIGIBLE_SKILLS

            return ProductionSkillImportanceOutput(
                status=status,
                estimator_version=raw_resp.estimator_version or ESTIMATOR_VERSION,
                total_skills_received=total_received,
                eligible_skills_count=len(validated_records),
                excluded_skills_count=len(validated_excluded),
                records=validated_records,
                excluded_records=validated_excluded,
                execution_time_ms=elapsed_ms,
                cache_hit=was_cached,
            )

        except Exception as exc:
            elapsed_ms = round((time.perf_counter() - t0) * 1000.0, 3)
            # Log sanitized error without verbatim document text or PII
            jd_hash = jd_id or "unknown"
            logger.warning(
                f"ProductionSkillImportanceService: Non-fatal failure during estimation for JD ID {jd_hash}: {exc}",
                exc_info=False,
            )
            return ProductionSkillImportanceOutput(
                status=ImportanceStatus.ESTIMATION_FAILED,
                estimator_version=ESTIMATOR_VERSION,
                total_skills_received=total_received,
                eligible_skills_count=0,
                excluded_skills_count=0,
                records=[],
                excluded_records=[],
                execution_time_ms=elapsed_ms,
                error_message=f"Estimation failed non-fatally: {type(exc).__name__}",
                cache_hit=False,
            )

    @staticmethod
    def _build_explanation(rec: JSI4ImportanceRecord) -> str:
        """Construct human-readable diagnostic explanation for an assigned importance weight."""
        tier = "Critical Core" if (rec.importance_weight or 0) >= 0.80 else ("Important" if (rec.importance_weight or 0) >= 0.65 else "Supplementary")
        mod_desc = "Mandatory requirement" if rec.modality == "MUST_HAVE" else ("Preferred qualification" if rec.modality == "NICE_TO_HAVE" else "Standard requirement")
        group_desc = f" Part of disjunctive OR alternative group '{rec.requirement_group_id}'." if rec.group_type == "OR" else ""
        title_desc = " Explicitly anchored in Job Title." if rec.is_title_anchor else ""
        return (
            f"Assigned weight {rec.importance_weight:.4f} ({tier}). "
            f"{mod_desc} classified as {rec.eligibility}.{group_desc}{title_desc}"
        )


# Singleton production instance
production_skill_importance_service = ProductionSkillImportanceService()
