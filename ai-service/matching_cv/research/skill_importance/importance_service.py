"""JSI-4 Skill Importance Service Adapter (JSI-5.2 Phase B).

Wraps JSI4HardenedEstimator (Variant V4) to provide a standardized, auditable,
and decoupled service contract for extracting JD-specific skill importance w_j.

Strict Safety Invariants:
- Preserves canonical skill IDs via normalize_canonical_skill.
- Output importance weights strictly bounded in [0.10, 1.00].
- Preserves competency eligibility (separating technical skills from actors/hardware).
- Preserves deontic requirement modality and polarity (positive vs negated/excluded).
- Preserves disjunctive OR and conjunctive AND group metadata.
- Zero modifications to production GNN models, checkpoints, or edge proficiency p_j.
- Isolated in-memory cache keyed by (jd_text_sha256, sorted_skills_sha256, version).
"""
from __future__ import annotations

import hashlib
import logging
import time
from typing import Any, Dict, List, Literal, Optional, Sequence, Set, Tuple, Union
from pydantic import BaseModel, Field

from matching_cv.research.data.canonical_skill_normalizer import normalize_canonical_skill
from matching_cv.research.skill_importance.config import JSIConfig, default_jsi_config
from matching_cv.research.skill_importance.hardened_estimator import JSI4HardenedEstimator
from matching_cv.research.skill_importance.models import JDEstimationResult, SkillImportanceOutput

logger = logging.getLogger(__name__)

ESTIMATOR_VERSION = "JSI4_V4"


class JSI4ImportanceRecord(BaseModel):
    """Auditable importance record for a single JD requirement entity."""

    canonical_skill_id: str = Field(..., description="Normalized canonical skill identifier")
    skill_display_name: str = Field(..., description="Human-readable skill name")
    importance_weight: Optional[float] = Field(
        default=None,
        ge=0.10,
        le=1.00,
        description="JSI-4 normalized importance weight w_j in [0.10, 1.00]; None if excluded",
    )
    raw_importance_score: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Uncalibrated continuous raw ensemble score in [0.0, 1.0]",
    )
    eligibility: str = Field(
        ...,
        description="Competency classification (VALID_TECHNOLOGY, COLLABORATOR_ACTOR, HARDWARE_TARGET, etc.)",
    )
    is_eligible_for_ranking: bool = Field(
        ...,
        description="True if entity is an eligible technical skill; False if actor or excluded form factor",
    )
    modality: str = Field(
        default="MUST_HAVE",
        description="Requirement modality: MUST_HAVE | SHOULD_HAVE | NICE_TO_HAVE | CONTEXT_ONLY | NEGATED",
    )
    polarity: Literal["POSITIVE", "NEGATED", "EXCLUDED"] = Field(
        default="POSITIVE",
        description="Requirement polarity: POSITIVE | NEGATED | EXCLUDED",
    )
    group_type: Literal["SOLO", "OR", "AND"] = Field(
        default="SOLO",
        description="Logical group structure: SOLO | OR | AND",
    )
    requirement_group_id: Optional[str] = Field(
        default=None,
        description="Identifier linking members of an OR / AND clause",
    )
    group_members: List[str] = Field(
        default_factory=list,
        description="Canonical skill IDs of other members in the same logical group",
    )
    evidence: List[str] = Field(
        default_factory=list,
        description="Verbatim sentences from the JD mentioning or implying this requirement",
    )
    matched_clause: Optional[str] = Field(
        default=None,
        description="Specific syntactic clause evaluated for deontic modality",
    )
    source_sections: List[str] = Field(
        default_factory=list,
        description="Document sections where this requirement appeared",
    )
    extraction_type: Literal["explicit", "implicit"] = Field(
        default="explicit",
        description="Origin of extraction in Stage 2",
    )
    is_title_anchor: bool = Field(
        default=False,
        description="True if skill explicitly appeared in the Job Title",
    )
    diagnostic_notes: Optional[str] = Field(
        default=None,
        description="Diagnostic notes explaining exclusion or special processing",
    )


class JDImportanceResponse(BaseModel):
    """Standardized response contract for JD skill importance estimation."""

    estimator_version: str = Field(default=ESTIMATOR_VERSION, description="Estimator release version")
    jd_id: Optional[str] = Field(default=None, description="Job identifier if provided")
    jd_title: Optional[str] = Field(default=None, description="Extracted or declared Job Title")
    total_skills_received: int = Field(default=0, description="Total input skills processed")
    eligible_skills_count: int = Field(default=0, description="Number of eligible positive competencies")
    excluded_skills_count: int = Field(default=0, description="Number of ineligible or excluded entities")
    importance_records: List[JSI4ImportanceRecord] = Field(
        default_factory=list,
        description="Importance records for all eligible positive requirements",
    )
    excluded_records: List[JSI4ImportanceRecord] = Field(
        default_factory=list,
        description="Diagnostic records for excluded/ineligible/negated entities",
    )
    execution_time_ms: float = Field(default=0.0, description="Latency in milliseconds")
    status: Literal["SUCCESS", "EMPTY_INPUT", "NO_SKILLS", "ERROR"] = Field(
        default="SUCCESS",
        description="Execution status code",
    )


class JSI4ImportanceService:
    """Service adapter executing JSI-4 V4 importance estimation with caching and validation."""

    def __init__(
        self,
        estimator: Optional[JSI4HardenedEstimator] = None,
        config: Optional[JSIConfig] = None,
        enable_cache: bool = True,
        max_cache_size: int = 128,
    ) -> None:
        self.config = config or default_jsi_config
        self.estimator = estimator or JSI4HardenedEstimator(self.config)
        self.enable_cache = enable_cache
        self.max_cache_size = max_cache_size
        self._cache: Dict[str, JDImportanceResponse] = {}

    def clear_cache(self) -> None:
        """Clear in-memory cache entries."""
        self._cache.clear()

    def _compute_cache_key(
        self,
        jd_text: str,
        explicit_skills: List[Dict[str, Any]],
        implicit_skills: List[Dict[str, Any]],
        job_title: Optional[str],
    ) -> str:
        """Construct secure, content-addressed cache key."""
        jd_sha = hashlib.sha256(jd_text.encode("utf-8")).hexdigest()
        exp_ids = sorted(str(s.get("canonical_skill_id") or s.get("name") or "") for s in explicit_skills)
        imp_ids = sorted(str(s.get("canonical_skill_id") or s.get("name") or "") for s in implicit_skills)
        skills_sha = hashlib.sha256(f"{exp_ids}|{imp_ids}".encode("utf-8")).hexdigest()
        title_str = (job_title or "").strip().lower()
        return f"{ESTIMATOR_VERSION}::{jd_sha[:16]}::{skills_sha[:16]}::{title_str}"

    def estimate_jd_importance(
        self,
        jd_text: str,
        explicit_skills: Optional[List[Dict[str, Any]]] = None,
        implicit_skills: Optional[List[Dict[str, Any]]] = None,
        job_title: Optional[str] = None,
        filename: Optional[str] = None,
        jd_id: Optional[str] = None,
    ) -> JDImportanceResponse:
        """
        Extract importance weights w_j for all eligible skills in the Job Description.

        Handles empty inputs, deduplicates by canonical ID, maps modality and groups,
        and cleanly separates eligible positive requirements from excluded entities.
        """
        t0 = time.perf_counter()

        exp_list = explicit_skills or []
        imp_list = implicit_skills or []

        # Defense 1: Handle empty JD text
        if not jd_text or not jd_text.strip():
            logger.info("JSI4ImportanceService: Empty or whitespace JD text received.")
            return JDImportanceResponse(
                estimator_version=ESTIMATOR_VERSION,
                jd_id=jd_id,
                jd_title=job_title,
                total_skills_received=len(exp_list) + len(imp_list),
                eligible_skills_count=0,
                excluded_skills_count=0,
                importance_records=[],
                excluded_records=[],
                execution_time_ms=round((time.perf_counter() - t0) * 1000.0, 3),
                status="EMPTY_INPUT",
            )

        # Defense 2: Handle empty skills
        if not exp_list and not imp_list:
            logger.info("JSI4ImportanceService: Zero input skills received.")
            return JDImportanceResponse(
                estimator_version=ESTIMATOR_VERSION,
                jd_id=jd_id,
                jd_title=job_title,
                total_skills_received=0,
                eligible_skills_count=0,
                excluded_skills_count=0,
                importance_records=[],
                excluded_records=[],
                execution_time_ms=round((time.perf_counter() - t0) * 1000.0, 3),
                status="NO_SKILLS",
            )

        # Check Cache
        if self.enable_cache:
            cache_key = self._compute_cache_key(jd_text, exp_list, imp_list, job_title)
            if cache_key in self._cache:
                cached_resp = self._cache[cache_key]
                logger.debug(f"JSI4ImportanceService: Cache hit for key {cache_key}")
                # Return copy with updated query-specific metadata
                return cached_resp.model_copy(update={"jd_id": jd_id or cached_resp.jd_id})

        # Run JSI-4 V4 Hardened Estimator
        est_result: JDEstimationResult = self.estimator.estimate_importance(
            jd_text=jd_text,
            explicit_skills=exp_list,
            implicit_skills=imp_list,
            filename=filename,
            job_title=job_title,
            remediate_layout=True,
            variant="V4_hardened",
        )

        detected_title = est_result.job_title_result.job_title or job_title

        eligible_records: List[JSI4ImportanceRecord] = []
        excluded_records: List[JSI4ImportanceRecord] = []

        seen_canonical_ids: Set[str] = set()

        for skill_out in est_result.skills:
            raw_cid = skill_out.canonical_skill_id
            norm_cid = normalize_canonical_skill(raw_cid) or raw_cid.strip().lower()

            # Prevent duplicate counting within the same JD
            if norm_cid in seen_canonical_ids:
                continue
            seen_canonical_ids.add(norm_cid)

            disp_name = skill_out.skill_display_name
            stype = skill_out.type

            dim_bd = skill_out.provenance.dimension_breakdown or {}
            sent_bd = dim_bd.get("sentence") or {}
            elig_bd = dim_bd.get("eligibility") or {}
            grp_bd = dim_bd.get("requirement_group") or {}

            # Extract eligibility
            elig_class = elig_bd.get("eligibility_class", "VALID_TECHNOLOGY")
            is_eligible = elig_bd.get("is_eligible_for_ranking", True)

            # Extract modality
            raw_mod = sent_bd.get("modality_category", "Mandatory")
            mod_str = self._standardize_modality(raw_mod)

            # Extract polarity
            is_neg = sent_bd.get("is_negated", False)
            if is_neg:
                polarity = "NEGATED"
            elif not is_eligible:
                polarity = "EXCLUDED"
            else:
                polarity = "POSITIVE"

            # Extract group info
            grp_type = "SOLO"
            grp_id = None
            grp_members = []
            if grp_bd:
                grp_type_raw = grp_bd.get("operator") or grp_bd.get("group_type", "SOLO")
                if grp_type_raw in ("OR", "AND"):
                    grp_type = grp_type_raw
                    grp_id = grp_bd.get("group_id")
                    grp_members = grp_bd.get("members", [])

            is_anchor = dim_bd.get("is_title_anchor", False)

            # Build record
            if polarity == "POSITIVE" and is_eligible:
                w_val = float(skill_out.importance.w_j)
                w_val = max(0.10, min(1.00, round(w_val, 4)))
                raw_score = float(skill_out.importance.importance_score_raw)

                rec = JSI4ImportanceRecord(
                    canonical_skill_id=norm_cid,
                    skill_display_name=disp_name,
                    importance_weight=w_val,
                    raw_importance_score=round(raw_score, 4),
                    eligibility=elig_class,
                    is_eligible_for_ranking=True,
                    modality=mod_str,
                    polarity="POSITIVE",
                    group_type=grp_type,
                    requirement_group_id=grp_id,
                    group_members=grp_members,
                    evidence=skill_out.provenance.source_sentences,
                    matched_clause=sent_bd.get("matched_clause"),
                    source_sections=skill_out.provenance.source_sections,
                    extraction_type=stype,
                    is_title_anchor=is_anchor,
                    diagnostic_notes=None,
                )
                eligible_records.append(rec)
            else:
                # Excluded / Ineligible / Negated requirement
                diag_msg = (
                    f"Excluded from positive ranking: eligibility={elig_class}, "
                    f"polarity={polarity}, reason={elig_bd.get('evidence_snippet', 'ineligible entity')}"
                )
                rec = JSI4ImportanceRecord(
                    canonical_skill_id=norm_cid,
                    skill_display_name=disp_name,
                    importance_weight=None,  # Do not invent missing weights for excluded entities
                    raw_importance_score=0.0,
                    eligibility=elig_class,
                    is_eligible_for_ranking=False,
                    modality=mod_str,
                    polarity=polarity,
                    group_type=grp_type,
                    requirement_group_id=grp_id,
                    group_members=grp_members,
                    evidence=skill_out.provenance.source_sentences,
                    matched_clause=sent_bd.get("matched_clause"),
                    source_sections=skill_out.provenance.source_sections,
                    extraction_type=stype,
                    is_title_anchor=is_anchor,
                    diagnostic_notes=diag_msg,
                )
                excluded_records.append(rec)

        # Sort eligible records descending by importance weight
        eligible_records.sort(key=lambda r: r.importance_weight if r.importance_weight is not None else 0.0, reverse=True)

        resp = JDImportanceResponse(
            estimator_version=ESTIMATOR_VERSION,
            jd_id=jd_id,
            jd_title=detected_title,
            total_skills_received=len(seen_canonical_ids),
            eligible_skills_count=len(eligible_records),
            excluded_skills_count=len(excluded_records),
            importance_records=eligible_records,
            excluded_records=excluded_records,
            execution_time_ms=round((time.perf_counter() - t0) * 1000.0, 3),
            status="SUCCESS",
        )

        # Update cache
        if self.enable_cache:
            cache_key = self._compute_cache_key(jd_text, exp_list, imp_list, job_title)
            if len(self._cache) >= self.max_cache_size:
                # Simple FIFO eviction
                self._cache.pop(next(iter(self._cache)))
            self._cache[cache_key] = resp

        return resp

    @staticmethod
    def _standardize_modality(raw_mod: str) -> str:
        """Map raw linguistic modality string into standardized category."""
        m = (raw_mod or "").strip().lower()
        if "mandatory" in m or "must" in m or "essential" in m or "required" in m:
            return "MUST_HAVE"
        if "operational" in m or "should" in m:
            return "SHOULD_HAVE"
        if "preferred" in m or "nice" in m or "plus" in m or "beneficial" in m:
            return "NICE_TO_HAVE"
        if "context" in m or "environment" in m or "domain" in m:
            return "CONTEXT_ONLY"
        if "negat" in m or "not" in m:
            return "NEGATED"
        return "MUST_HAVE"


# Singleton instance
jsi4_importance_service = JSI4ImportanceService()
