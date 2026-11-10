"""Orchestrator for Stage 3 SBERT Semantic Representation & Retrieval."""
import hashlib
import logging
import time
from typing import Any, Dict, List, Optional
import numpy as np

from matching_cv.app.core.config import settings
from matching_cv.app.core.model_loader import model_loader
from matching_cv.app.schemas.semantic_representation import (
    EmbeddingGenerateRequest,
    EmbeddingRecord,
    SemanticAudit,
    SemanticRepresentationResponse,
    SemanticStats,
    SimilarityMatrix,
    TopKRetrievalResult,
)
from matching_cv.app.services.document_parser import DocumentParserService
from matching_cv.app.services.extraction_adapter import ExtractionDataAdapter
from matching_cv.app.services.semantic_embedding_service import (
    SemanticEmbeddingService,
    semantic_embedding_service,
)
from matching_cv.app.services.semantic_retrieval_service import (
    SemanticRetrievalService,
    semantic_retrieval_service,
)

logger = logging.getLogger(__name__)


class SemanticRepresentationService:
    """End-to-end service generating SBERT embeddings and semantic candidate retrievals."""

    def __init__(
        self,
        embedding_service: Optional[SemanticEmbeddingService] = None,
        retrieval_service: Optional[SemanticRetrievalService] = None,
    ) -> None:
        self.embedding_service = embedding_service or semantic_embedding_service
        self.retrieval_service = retrieval_service or semantic_retrieval_service

    def generate_representations(
        self,
        request: EmbeddingGenerateRequest,
    ) -> SemanticRepresentationResponse:
        """Process unified extraction response and generate complete semantic representation."""
        t0 = time.perf_counter()
        resp = request.unified_response

        # Resolve document source identifiers
        cv_source_id = (
            resp.cv.filename if resp.cv and resp.cv.filename else f"cv_{resp.run_id[:8]}"
        )
        jd_source_id = (
            resp.jd.filename if resp.jd and resp.jd.filename else f"jd_{resp.run_id[:8]}"
        )

        # Resolve effective document texts from request or unified_response or raw_text
        effective_jd_text = request.jd_text
        if not effective_jd_text and getattr(resp, "jd_text", None):
            effective_jd_text = resp.jd_text
        elif not effective_jd_text and resp.jd and getattr(resp.jd, "raw_text", None):
            effective_jd_text = resp.jd.raw_text

        effective_cv_text = getattr(request, "cv_text", None)
        if not effective_cv_text and getattr(resp, "cv_text", None):
            effective_cv_text = resp.cv_text
        elif not effective_cv_text and resp.cv and getattr(resp.cv, "raw_text", None):
            effective_cv_text = resp.cv.raw_text

        # JD text SHA-256 consistency guard
        req_diagnostics_sha = "not_provided"
        if effective_jd_text and effective_jd_text.strip():
            raw_sha = hashlib.sha256(effective_jd_text.encode("utf-8")).hexdigest()
            cleaned_sha = hashlib.sha256(
                DocumentParserService.clean_extracted_text(effective_jd_text).encode("utf-8")
            ).hexdigest()
            if resp.jd and resp.jd.text_sha256:
                if resp.jd.text_sha256 not in (raw_sha, cleaned_sha):
                    raise ValueError(
                        f"SHA-256 mismatch between supplied jd_text ({raw_sha}) and "
                        f"unified_response.jd.text_sha256 ({resp.jd.text_sha256}). "
                        "The supplied JD text does not match the text used during skill extraction."
                    )
                req_diagnostics_sha = "verified_match"
            else:
                req_diagnostics_sha = "unverified_no_hash_in_response"

        # CV text SHA-256 consistency guard (if provided)
        cv_diagnostics_sha = "not_provided"
        if effective_cv_text and effective_cv_text.strip():
            cv_raw_sha = hashlib.sha256(effective_cv_text.encode("utf-8")).hexdigest()
            cv_cleaned_sha = hashlib.sha256(
                DocumentParserService.clean_extracted_text(effective_cv_text).encode("utf-8")
            ).hexdigest()
            if resp.cv and resp.cv.text_sha256:
                if resp.cv.text_sha256 not in (cv_raw_sha, cv_cleaned_sha):
                    raise ValueError(
                        f"SHA-256 mismatch between supplied cv_text ({cv_raw_sha}) and "
                        f"unified_response.cv.text_sha256 ({resp.cv.text_sha256}). "
                        "The supplied CV text does not match the text used during skill extraction."
                    )
                cv_diagnostics_sha = "verified_match"
            else:
                cv_diagnostics_sha = "unverified_no_hash_in_response"

        # 1. Adapt active skills & preserve duplicate audit (with auto-revalidation support)
        cv_res = ExtractionDataAdapter.extract_active_skills(
            resp.cv,
            auto_revalidate_implicit=request.auto_revalidate_implicit,
            run_id=resp.run_id,
        )
        cv_skills, cv_duplicates = cv_res.active_skills, cv_res.duplicate_audit

        jd_res = ExtractionDataAdapter.extract_active_skills(
            resp.jd,
            auto_revalidate_implicit=request.auto_revalidate_implicit,
            run_id=resp.run_id,
        )
        jd_skills, jd_duplicates = jd_res.active_skills, jd_res.duplicate_audit

        # 2. Extract CV sentence-level evidences
        cv_evidences = ExtractionDataAdapter.extract_evidence_items(
            resp.cv,
            "CV",
            cv_source_id,
            run_id=resp.run_id,
        )

        # 3. Segment JD requirements (using auto-resolved effective_jd_text)
        jd_requirements, req_diagnostics = ExtractionDataAdapter.segment_jd_requirements(
            resp.jd,
            effective_jd_text,
            jd_source_id,
        )

        # 4. Generate embeddings with pre-inference truncation validation
        cv_skill_records, cv_skill_vecs = self.embedding_service.encode_skills(
            cv_skills,
            "CV",
            cv_source_id,
            definition_dict=request.skill_definition_dict,
            include_vectors=request.include_vectors,
            on_overlength=request.on_overlength,
        )

        jd_skill_records, jd_skill_vecs = self.embedding_service.encode_skills(
            jd_skills,
            "JD",
            jd_source_id,
            definition_dict=request.skill_definition_dict,
            include_vectors=request.include_vectors,
            on_overlength=request.on_overlength,
        )

        cv_evidence_records, cv_evidence_vecs = self.embedding_service.encode_evidences(
            cv_evidences,
            include_vectors=request.include_vectors,
            on_overlength=request.on_overlength,
        )

        jd_req_records, jd_req_vecs = self.embedding_service.encode_requirements(
            jd_requirements,
            include_vectors=request.include_vectors,
            on_overlength=request.on_overlength,
        )

        all_records = (
            cv_skill_records
            + jd_skill_records
            + cv_evidence_records
            + jd_req_records
        )

        # Filter valid records for similarity computation (excluding rejected overlength records)
        valid_cv_skill_records = [r for r in cv_skill_records if r.truncation_status != "rejected"]
        valid_jd_skill_records = [r for r in jd_skill_records if r.truncation_status != "rejected"]
        valid_cv_ev_records = [r for r in cv_evidence_records if r.truncation_status != "rejected"]
        valid_jd_req_records = [r for r in jd_req_records if r.truncation_status != "rejected"]

        # Track unique encoded vectors (deduplicating across identical texts)
        encoded_hashes = {r.text_hash for r in all_records if r.truncation_status != "rejected"}
        unique_vectors_count = len(encoded_hashes)

        truncation_count = sum(1 for r in all_records if r.is_truncated)
        rejected_count = sum(1 for r in all_records if r.truncation_status == "rejected")
        segmented_count = sum(1 for r in all_records if r.truncation_status == "segmented")

        # 5. Compute similarity matrices & Top-K retrieval if requested
        matrices: Optional[Dict[str, SimilarityMatrix]] = None
        top_k_map: Optional[Dict[str, List[TopKRetrievalResult]]] = None

        # Determine retrieval scope filtered records
        filtered_cv_records = valid_cv_skill_records
        filtered_jd_records = valid_jd_skill_records

        if request.retrieval_scope == "skills_only":
            retrieval_cv_indices = [
                i
                for i, r in enumerate(valid_cv_skill_records)
                if (
                    (
                        r.metadata.get("kind") == "skill"
                        and r.metadata.get("competency_granularity") != "contextual_activity_or_product"
                    )
                    or (
                        r.extraction_type == "implicit"
                        and request.include_implicit_in_retrieval
                        and r.metadata.get("competency_granularity") != "contextual_activity_or_product"
                    )
                )
            ]
            retrieval_jd_indices = [
                i
                for i, r in enumerate(valid_jd_skill_records)
                if (
                    (
                        r.metadata.get("kind") == "skill"
                        and r.metadata.get("competency_granularity") != "contextual_activity_or_product"
                    )
                    or (
                        r.extraction_type == "implicit"
                        and request.include_implicit_in_retrieval
                        and r.metadata.get("competency_granularity") != "contextual_activity_or_product"
                    )
                )
            ]
            filtered_cv_records = [valid_cv_skill_records[i] for i in retrieval_cv_indices]
            filtered_jd_records = [valid_jd_skill_records[i] for i in retrieval_jd_indices]
            filtered_cv_vecs = (
                cv_skill_vecs[retrieval_cv_indices]
                if len(retrieval_cv_indices) > 0
                else np.empty((0, settings.STAGE3_EMBEDDING_DIM), dtype=np.float32)
            )
            filtered_jd_vecs = (
                jd_skill_vecs[retrieval_jd_indices]
                if len(retrieval_jd_indices) > 0
                else np.empty((0, settings.STAGE3_EMBEDDING_DIM), dtype=np.float32)
            )
        else:
            filtered_cv_vecs = cv_skill_vecs
            filtered_jd_vecs = jd_skill_vecs

        if request.compute_similarity:
            matrices = {}
            top_k_map = {}

            # Always compute and expose full entity matrix for downstream Stage 4 Graph Construction
            all_entities_matrix = self.retrieval_service.compute_cosine_matrix(
                cv_skill_vecs,
                jd_skill_vecs,
                valid_cv_skill_records,
                valid_jd_skill_records,
                expected_dim=settings.STAGE3_EMBEDDING_DIM,
            )
            matrices["cv_entities_vs_jd_entities"] = all_entities_matrix

            if request.retrieval_scope == "skills_only":
                skill_matrix = self.retrieval_service.compute_cosine_matrix(
                    filtered_cv_vecs,
                    filtered_jd_vecs,
                    filtered_cv_records,
                    filtered_jd_records,
                    expected_dim=settings.STAGE3_EMBEDDING_DIM,
                )
                matrices["cv_skills_vs_jd_skills"] = skill_matrix
                top_k_map["cv_skills_to_jd_skills"] = self.retrieval_service.retrieve_top_k(
                    filtered_cv_records,
                    filtered_jd_records,
                    skill_matrix,
                    top_k=request.top_k,
                )
            else:
                matrices["cv_skills_vs_jd_skills"] = all_entities_matrix
                top_k_map["cv_skills_to_jd_skills"] = self.retrieval_service.retrieve_top_k(
                    valid_cv_skill_records,
                    valid_jd_skill_records,
                    all_entities_matrix,
                    top_k=request.top_k,
                )

            # Matrix 2: CV Evidence vs JD Requirements
            ev_req_matrix = self.retrieval_service.compute_cosine_matrix(
                cv_evidence_vecs,
                jd_req_vecs,
                valid_cv_ev_records,
                valid_jd_req_records,
                expected_dim=settings.STAGE3_EMBEDDING_DIM,
            )
            matrices["cv_evidences_vs_jd_requirements"] = ev_req_matrix
            top_k_map["cv_evidences_to_jd_requirements"] = self.retrieval_service.retrieve_top_k(
                valid_cv_ev_records,
                valid_jd_req_records,
                ev_req_matrix,
                top_k=request.top_k,
            )

        duration_ms = round((time.perf_counter() - t0) * 1000, 2)

        stats = SemanticStats(
            cv_explicit_skills=len([s for s in cv_skills if s.extraction_type == "explicit"]),
            cv_accepted_implicit_skills=len([s for s in cv_skills if s.extraction_type == "implicit"]),
            cv_duplicate_implicit_skills=len(cv_duplicates),
            cv_distinct_evidences=len(cv_evidences),
            jd_explicit_skills=len([s for s in jd_skills if s.extraction_type == "explicit"]),
            jd_accepted_implicit_skills=len([s for s in jd_skills if s.extraction_type == "implicit"]),
            jd_duplicate_implicit_skills=len(jd_duplicates),
            jd_requirements=len(jd_requirements),
            total_embeddings_generated=len(all_records),
            unique_vectors_encoded=unique_vectors_count,
            truncation_count=truncation_count,
            rejected_overlength_count=rejected_count,
            segmented_count=segmented_count,
            encoding_duration_ms=duration_ms,
        )

        audit = SemanticAudit(
            cv_duplicate_implicit_skills=cv_duplicates,
            jd_duplicate_implicit_skills=jd_duplicates,
        )

        diagnostics: Dict[str, Any] = {
            "requirements_diagnostics": req_diagnostics,
            "jd_text_sha256_verification": req_diagnostics_sha,
            "cv_text_sha256_verification": cv_diagnostics_sha,
            "implicit_validation_diagnostics": {
                "cv": cv_res.validation_diagnostics,
                "jd": jd_res.validation_diagnostics,
                "auto_revalidate_implicit": request.auto_revalidate_implicit,
            },
            "retrieval_scope": request.retrieval_scope,
            "include_implicit_in_retrieval": request.include_implicit_in_retrieval,
            "retrieval_corpus_composition": {
                "total_cv_skill_entities": len(valid_cv_skill_records),
                "total_jd_skill_entities": len(valid_jd_skill_records),
                "retrieval_cv_skills_count": len(filtered_cv_records),
                "retrieval_jd_skills_count": len(filtered_jd_records),
                "excluded_cv_entities_count": len(valid_cv_skill_records) - len(filtered_cv_records),
                "excluded_jd_entities_count": len(valid_jd_skill_records) - len(filtered_jd_records),
            },
            "max_seq_length": self.embedding_service._get_max_seq_length(),
            "embedding_dimension": settings.STAGE3_EMBEDDING_DIM,
            "batch_size": self.embedding_service.batch_size,
            "include_vectors": request.include_vectors,
            "compute_similarity": request.compute_similarity,
            "top_k": request.top_k,
            "on_overlength_policy": request.on_overlength,
            "skill_definition_strategy": "provided_dict" if request.skill_definition_dict else "name_only_default",
            "semantic_matching_disclaimer": (
                "Cosine similarity indicates semantic closeness in SBERT embedding space; "
                "it is NOT a calibrated probability of skill equivalence or candidate qualification."
            ),
        }

        return SemanticRepresentationResponse(
            run_id=resp.run_id,
            model_id=self.embedding_service.model_name,
            model_revision=self.embedding_service.revision,
            device=self.embedding_service.loader.device,
            embedding_dim=settings.STAGE3_EMBEDDING_DIM,
            stats=stats,
            audit=audit,
            cv_skill_embeddings=cv_skill_records,
            jd_skill_embeddings=jd_skill_records,
            cv_evidence_embeddings=cv_evidence_records,
            jd_requirement_embeddings=jd_req_records,
            similarity_matrices=matrices,
            top_k_retrievals=top_k_map,
            diagnostics=diagnostics,
        )


semantic_representation_service = SemanticRepresentationService()
