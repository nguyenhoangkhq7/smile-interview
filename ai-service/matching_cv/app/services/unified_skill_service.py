"""Unified skill extraction service orchestrating explicit and implicit pipelines."""
import hashlib
import json
import logging
import re
import time
import uuid
from typing import Any, Dict, List, Literal, Optional, Set, Tuple

from fastapi import HTTPException, UploadFile, status

from matching_cv.app.schemas.implicit_skill_extraction import (
    ImplicitExtractedSkill,
    ImplicitExtractionResult,
)
from matching_cv.app.schemas.skill_extraction import ExtractionResult
from matching_cv.app.schemas.unified_skill_extraction import (
    DocumentUnifiedResult,
    DocumentValidationResult,
    DuplicateImplicitSkill,
    PipelineError,
    UnifiedExtractFileResponse,
    UnifiedExtractionSummary,
)
from matching_cv.app.services.document_parser import document_parser_service
from matching_cv.app.services.implicit_evidence_verifier import ImplicitEvidenceVerifier
from matching_cv.app.services.implicit_skill_postprocessor import implicit_skill_postprocessor
from matching_cv.app.services.llm_service import llm_service
from matching_cv.app.services.skill_postprocessor import skill_postprocessor

logger = logging.getLogger(__name__)


def normalize_skill_name(text: str) -> str:
    """Normalize skill name for robust string comparison (alphanumeric, casefolded)."""
    return re.sub(r"[^\w]+|_+", " ", text.casefold()).strip()


def deduplicate_explicit_implicit(
    explicit_result: Optional[ExtractionResult],
    implicit_result: Optional[ImplicitExtractionResult],
    validation_policy: str = "dedup_plus_evidence_verification",
    document_type: str = "CV",
) -> DocumentValidationResult:
    """
    Perform conservative explicit/implicit semantic deduplication and evidence validity verification.

    Layer A (Deduplication):
    - Explicit skills take precedence over semantically equivalent implicit skills.
    - If canonical skill_id matches exactly -> mark as duplicate (exact_canonical_id).
    - If normalized label matches normalized surface form -> mark as duplicate (surface_form_match).
    - If slug of label matches slug of any surface form -> mark as duplicate (surface_form_match).
    - Preserves distinct skills that are merely related through technology or parent/child links.

    Layer B (Evidence Validity Verification):
    - Evaluates groundedness of inferred skills in document evidence snippets/reasoning.
    - Prevents overclaiming specific regulatory standards (HIPAA, GDPR) from general domain context.
    - Prevents exaggerating client delivery into stakeholder management responsibilities.
    - Preserves legitimate technical engineering competencies.
    """
    if not implicit_result or not implicit_result.skills:
        return DocumentValidationResult(
            status="completed",
            validation_origin="original",
            validation_policy=validation_policy,
            duplicate_implicit_skills=[],
            accepted_implicit_skills=[],
            rejected_implicit_skills=[],
            evidence_verifications=[],
        )

    if not explicit_result or not explicit_result.skills:
        layer_a_accepted = list(implicit_result.skills)
        if validation_policy == "dedup_plus_evidence_verification":
            accepted_skills, rejected_skills, verifications = ImplicitEvidenceVerifier.verify_candidates(
                layer_a_accepted, explicit_result=None, document_type=document_type
            )
        else:
            accepted_skills = layer_a_accepted
            rejected_skills = []
            verifications = []

        return DocumentValidationResult(
            status="completed",
            validation_origin="original",
            validation_policy=validation_policy,
            duplicate_implicit_skills=[],
            accepted_implicit_skills=accepted_skills,
            rejected_implicit_skills=rejected_skills,
            evidence_verifications=verifications,
        )

    # Build lookup mappings from the explicit skills
    # 1. Exact canonical skill_ids: id.lower() -> (canonical_id, display_name)
    explicit_ids: Dict[str, Tuple[str, str]] = {}
    # 2. Normalized surface forms: norm_sf -> (canonical_id, surface_form)
    explicit_surface_forms: Dict[str, Tuple[str, str]] = {}
    # 3. Slugs of all surface forms: slug -> (canonical_id, surface_form)
    explicit_slugs: Dict[str, Tuple[str, str]] = {}

    for exp_skill in explicit_result.skills:
        first_sf = exp_skill.surface_forms[0] if exp_skill.surface_forms else exp_skill.skill_id
        explicit_ids[exp_skill.skill_id.lower()] = (exp_skill.skill_id, first_sf)

        for sf in exp_skill.surface_forms:
            norm_sf = normalize_skill_name(sf)
            if norm_sf:
                explicit_surface_forms[norm_sf] = (exp_skill.skill_id, sf)
            slug = skill_postprocessor.slugify_skill(sf)
            if slug:
                explicit_slugs[slug] = (exp_skill.skill_id, sf)

        for ev in exp_skill.evidences:
            if ev.surface_form:
                norm_sf = normalize_skill_name(ev.surface_form)
                if norm_sf:
                    explicit_surface_forms[norm_sf] = (exp_skill.skill_id, ev.surface_form)
                slug = skill_postprocessor.slugify_skill(ev.surface_form)
                if slug:
                    explicit_slugs[slug] = (exp_skill.skill_id, ev.surface_form)

    duplicate_list: List[DuplicateImplicitSkill] = []
    layer_a_accepted: List[ImplicitExtractedSkill] = []

    for imp_skill in implicit_result.skills:
        matched_info: Optional[Tuple[str, str, str]] = None  # (exp_id, exp_sf, reason)

        # Check 1: Canonical skill_id exact match
        imp_id_lower = imp_skill.skill_id.lower()
        if imp_id_lower in explicit_ids:
            exp_id, exp_sf = explicit_ids[imp_id_lower]
            matched_info = (exp_id, exp_sf, "exact_canonical_id")

        # Check 2: Normalized label match against explicit surface forms
        if not matched_info:
            norm_imp_label = normalize_skill_name(imp_skill.label)
            if norm_imp_label in explicit_surface_forms:
                exp_id, exp_sf = explicit_surface_forms[norm_imp_label]
                matched_info = (exp_id, exp_sf, "surface_form_match")

        # Check 3: Slugified label match against explicit slugs
        if not matched_info:
            imp_slug = skill_postprocessor.slugify_skill(imp_skill.label)
            if imp_slug in explicit_slugs:
                exp_id, exp_sf = explicit_slugs[imp_slug]
                matched_info = (exp_id, exp_sf, "surface_form_match")

        if matched_info:
            exp_id, exp_sf, reason = matched_info
            duplicate_list.append(
                DuplicateImplicitSkill(
                    skill_id=imp_skill.skill_id,
                    label=imp_skill.label,
                    category=imp_skill.category_raw or imp_skill.category,
                    matched_explicit_skill_id=exp_id,
                    matched_explicit_surface_form=exp_sf,
                    duplicate_reason=reason,
                    original_inference=imp_skill,
                )
            )
        else:
            layer_a_accepted.append(imp_skill)

    # Layer B: Evidence Validity Verification
    if validation_policy == "dedup_plus_evidence_verification":
        accepted_skills, rejected_skills, verifications = ImplicitEvidenceVerifier.verify_candidates(
            layer_a_accepted, explicit_result=explicit_result, document_type=document_type
        )
    else:
        accepted_skills = layer_a_accepted
        rejected_skills = []
        verifications = []

    return DocumentValidationResult(
        status="completed",
        validation_origin="original",
        validation_policy=validation_policy,
        duplicate_implicit_skills=duplicate_list,
        accepted_implicit_skills=accepted_skills,
        rejected_implicit_skills=rejected_skills,
        evidence_verifications=verifications,
    )


class UnifiedSkillService:
    """Orchestration service for unified explicit and implicit skill extraction."""

    async def _process_single_document(
        self,
        upload_file: UploadFile,
        document_type: Literal["CV", "JD"],
        run_id: str,
        timings: Dict[str, float],
    ) -> Tuple[Optional[DocumentUnifiedResult], List[PipelineError]]:
        """
        Execute full extraction pipeline on a single document:
        1. Parse document once.
        2. Extract explicit skills on raw text.
        3. Extract implicit skills on raw text with explicit context.
        4. Deduplicate implicit skills against explicit skills.
        """
        errors: List[PipelineError] = []
        doc_prefix = document_type.lower()

        # Phase 1: Parse Document
        t_parse_start = time.perf_counter()
        try:
            doc_data = await document_parser_service.parse_file(upload_file)
        except HTTPException as http_exc:
            # Let format validation / 400 errors bubble up if requested
            raise http_exc
        except Exception as exc:
            logger.error(
                f"[{run_id}] Failed parsing {document_type} file '{upload_file.filename}': {exc}",
                exc_info=True,
            )
            errors.append(
                PipelineError(
                    document=document_type,
                    stage="parse",
                    error_type=type(exc).__name__,
                    message=str(exc),
                )
            )
            return None, errors

        parse_duration = (time.perf_counter() - t_parse_start) * 1000
        timings[f"parse_{doc_prefix}_ms"] = round(parse_duration, 2)

        from matching_cv.app.services.extraction_recovery import (
            explicit_recovery_diag_var,
            implicit_recovery_diag_var,
            last_recovery_diag_var,
            request_stage_context_var,
        )
        explicit_recovery_diag_var.set(None)
        implicit_recovery_diag_var.set(None)
        last_recovery_diag_var.set(None)
        request_stage_context_var.set(None)

        raw_text = doc_data.raw_text
        if len(raw_text.strip()) < 20:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"Nội dung văn bản từ tệp '{doc_data.filename}' quá ngắn "
                    "(dưới 20 ký tự) để có thể phân tích và trích xuất kỹ năng."
                ),
            )

        text_sha256 = hashlib.sha256(raw_text.encode("utf-8")).hexdigest()

        # Phase 2: Explicit Skill Extraction
        t_exp_start = time.perf_counter()
        explicit_result: Optional[ExtractionResult] = None
        try:
            raw_explicit = await llm_service.extract_explicit_skills(
                text=raw_text,
                document_type=document_type,
            )
            explicit_result = skill_postprocessor.process_extraction(
                raw_result=raw_explicit,
                text=raw_text,
                filename=doc_data.filename,
                document_type=document_type,
            )
        except Exception as exc:
            logger.error(
                f"[{run_id}] Explicit extraction failed for {document_type}: {exc}",
                exc_info=True,
            )
            errors.append(
                PipelineError(
                    document=document_type,
                    stage="explicit_extraction",
                    error_type=type(exc).__name__,
                    message=str(exc),
                )
            )

        exp_duration = (time.perf_counter() - t_exp_start) * 1000
        timings[f"{doc_prefix}_explicit_ms"] = round(exp_duration, 2)

        # Phase 3: Implicit Skill Extraction (contextualized with explicit result)
        t_imp_start = time.perf_counter()
        implicit_result: Optional[ImplicitExtractionResult] = None
        try:
            raw_implicit = await llm_service.extract_implicit_skills(
                text=raw_text,
                document_type=document_type,
                explicit_result=explicit_result,
            )
            implicit_result = implicit_skill_postprocessor.process_extraction(
                raw_result=raw_implicit,
                text=raw_text,
                filename=doc_data.filename,
                document_type=document_type,
            )
        except Exception as exc:
            logger.error(
                f"[{run_id}] Implicit extraction failed for {document_type}: {exc}",
                exc_info=True,
            )
            errors.append(
                PipelineError(
                    document=document_type,
                    stage="implicit_extraction",
                    error_type=type(exc).__name__,
                    message=str(exc),
                )
            )

        imp_duration = (time.perf_counter() - t_imp_start) * 1000
        timings[f"{doc_prefix}_implicit_ms"] = round(imp_duration, 2)

        # Phase 4: Validation & Deduplication
        t_val_start = time.perf_counter()
        validation_result: DocumentValidationResult
        try:
            validation_result = deduplicate_explicit_implicit(
                explicit_result=explicit_result,
                implicit_result=implicit_result,
                document_type=document_type,
            )
        except Exception as exc:
            logger.error(
                f"[{run_id}] Validation/deduplication failed for {document_type}: {exc}",
                exc_info=True,
            )
            errors.append(
                PipelineError(
                    document=document_type,
                    stage="validation",
                    error_type=type(exc).__name__,
                    message=str(exc),
                )
            )
            validation_result = DocumentValidationResult()

        val_duration = (time.perf_counter() - t_val_start) * 1000
        timings[f"{doc_prefix}_validation_ms"] = round(val_duration, 2)

        doc_result = DocumentUnifiedResult(
            filename=doc_data.filename,
            document_type=document_type,
            text_sha256=text_sha256,
            raw_text=raw_text,
            explicit=explicit_result,
            implicit=implicit_result,
            validation=validation_result,
        )

        return doc_result, errors

    async def extract_unified_from_files(
        self,
        cv_file: Optional[UploadFile] = None,
        jd_file: Optional[UploadFile] = None,
        file: Optional[UploadFile] = None,
        document_type: Optional[str] = None,
    ) -> UnifiedExtractFileResponse:
        """
        Main entry point for unified extraction. Processes CV and/or JD files.
        """
        run_id = str(uuid.uuid4())
        start_time = time.perf_counter()
        timings: Dict[str, float] = {}
        all_errors: List[PipelineError] = []

        logger.info(f"[{run_id}] Starting unified extraction request...")

        # Resolve files with backward compatibility for legacy 'file' parameter
        effective_cv = cv_file if (cv_file is not None and cv_file.filename) else None
        effective_jd = jd_file if (jd_file is not None and jd_file.filename) else None

        if effective_cv is None and effective_jd is None and file is not None and file.filename:
            doc_type_normalized = (document_type or "CV").strip().upper()
            if "JD" in doc_type_normalized:
                effective_jd = file
            else:
                effective_cv = file

        if effective_cv is None and effective_jd is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    "Vui lòng tải lên ít nhất một tệp tin thông qua tham số "
                    "'cv_file' (file CV) hoặc 'jd_file' (file JD)."
                ),
            )

        cv_result: Optional[DocumentUnifiedResult] = None
        jd_result: Optional[DocumentUnifiedResult] = None

        # Execute CV pipeline if present
        if effective_cv is not None:
            cv_res, cv_errs = await self._process_single_document(
                upload_file=effective_cv,
                document_type="CV",
                run_id=run_id,
                timings=timings,
            )
            cv_result = cv_res
            all_errors.extend(cv_errs)

        # Execute JD pipeline if present
        if effective_jd is not None:
            jd_res, jd_errs = await self._process_single_document(
                upload_file=effective_jd,
                document_type="JD",
                run_id=run_id,
                timings=timings,
            )
            jd_result = jd_res
            all_errors.extend(jd_errs)

        total_duration = (time.perf_counter() - start_time) * 1000
        timings["total_execution_ms"] = round(total_duration, 2)

        # Compute summary counts
        cv_exp_count = len(cv_result.explicit.skills) if (cv_result and cv_result.explicit) else 0
        cv_imp_count = (
            len(cv_result.validation.accepted_implicit_skills) if cv_result else 0
        )
        jd_exp_count = len(jd_result.explicit.skills) if (jd_result and jd_result.explicit) else 0
        jd_imp_count = (
            len(jd_result.validation.accepted_implicit_skills) if jd_result else 0
        )

        dup_count = 0
        if cv_result:
            dup_count += len(cv_result.validation.duplicate_implicit_skills)
        if jd_result:
            dup_count += len(jd_result.validation.duplicate_implicit_skills)

        # Compute distinct canonical skills across the entire request
        unique_canonical_ids: Set[str] = set()
        if cv_result and cv_result.explicit:
            for s in cv_result.explicit.skills:
                unique_canonical_ids.add(s.skill_id)
        if cv_result and cv_result.validation:
            for s in cv_result.validation.accepted_implicit_skills:
                unique_canonical_ids.add(s.skill_id)
        if jd_result and jd_result.explicit:
            for s in jd_result.explicit.skills:
                unique_canonical_ids.add(s.skill_id)
        if jd_result and jd_result.validation:
            for s in jd_result.validation.accepted_implicit_skills:
                unique_canonical_ids.add(s.skill_id)

        # Determine pipeline status
        requested_docs = (1 if effective_cv is not None else 0) + (1 if effective_jd is not None else 0)
        succeeded_docs = 0
        if cv_result is not None and cv_result.explicit is not None:
            succeeded_docs += 1
        if jd_result is not None and jd_result.explicit is not None:
            succeeded_docs += 1

        if not all_errors and succeeded_docs == requested_docs:
            status_val: Literal["completed", "partial_success", "failed"] = "completed"
        elif succeeded_docs > 0:
            status_val = "partial_success"
        else:
            status_val = "failed"

        summary = UnifiedExtractionSummary(
            cv_explicit_count=cv_exp_count,
            cv_implicit_count=cv_imp_count,
            jd_explicit_count=jd_exp_count,
            jd_implicit_count=jd_imp_count,
            duplicate_count=dup_count,
            total_unique_skills=len(unique_canonical_ids),
            execution_time_ms=round(total_duration, 2),
            timings_ms=timings,
        )

        logger.info(
            f"[{run_id}] Unified extraction finished: status='{status_val}', "
            f"CV explicit={cv_exp_count}, implicit={cv_imp_count}; "
            f"JD explicit={jd_exp_count}, implicit={jd_imp_count}; "
            f"duplicates={dup_count}, unique={len(unique_canonical_ids)}, "
            f"duration={total_duration:.1f}ms, errors={len(all_errors)}"
        )

        cv_text = cv_result.raw_text if cv_result else None
        jd_text = jd_result.raw_text if jd_result else None

        return UnifiedExtractFileResponse(
            run_id=run_id,
            status=status_val,
            cv=cv_result,
            jd=jd_result,
            cv_text=cv_text,
            jd_text=jd_text,
            summary=summary,
            errors=all_errors,
        )


unified_skill_service = UnifiedSkillService()
