"""Maps completed pipeline stage outputs to the internal API response DTOs."""
import hashlib
from typing import List, Tuple

from matching_cv.app.schemas.pipeline import (
    CandidatePairSummary,
    DocumentExtractionDetails,
    DocumentMetadata,
    PipelineDocumentSummary,
    PipelineExtractionSummary,
    PipelineSemanticRepresentation,
)
from matching_cv.app.schemas.semantic_representation import SemanticRepresentationResponse
from matching_cv.app.schemas.unified_skill_extraction import UnifiedExtractFileResponse
from matching_cv.app.services.graph_builder import PINNED_SBERT_MODEL_ID, PINNED_SBERT_REVISION


class PipelineResponseMapper:
    """Pure mapping helpers for internal pipeline response data."""

    @staticmethod
    def document_summary(
        unified_response: UnifiedExtractFileResponse,
        *,
        cv_filename: str,
        jd_filename: str,
        cv_extension: str,
        jd_extension: str,
    ) -> Tuple[str, str, PipelineDocumentSummary]:
        cv_doc = unified_response.cv
        jd_doc = unified_response.jd
        cv_text = cv_doc.raw_text or "" if cv_doc else ""
        jd_text = jd_doc.raw_text or "" if jd_doc else ""

        summary = PipelineDocumentSummary(
            cv=DocumentMetadata(
                filename=cv_doc.filename if cv_doc and cv_doc.filename else cv_filename,
                file_type="pdf" if cv_extension == ".pdf" else "txt",
                character_count=len(cv_text),
                word_count=len(cv_text.split()),
                total_pages=None,
                text_sha256=(
                    cv_doc.text_sha256
                    if cv_doc and cv_doc.text_sha256
                    else hashlib.sha256(cv_text.encode()).hexdigest()
                ),
            ),
            jd=DocumentMetadata(
                filename=jd_doc.filename if jd_doc and jd_doc.filename else jd_filename,
                file_type="pdf" if jd_extension == ".pdf" else "txt",
                character_count=len(jd_text),
                word_count=len(jd_text.split()),
                total_pages=None,
                text_sha256=(
                    jd_doc.text_sha256
                    if jd_doc and jd_doc.text_sha256
                    else hashlib.sha256(jd_text.encode()).hexdigest()
                ),
            ),
        )
        return cv_text, jd_text, summary

    @staticmethod
    def extraction_summary(
        unified_response: UnifiedExtractFileResponse,
        *,
        include_details: bool,
    ) -> PipelineExtractionSummary:
        cv = unified_response.cv
        jd = unified_response.jd
        cv_validation = cv.validation if cv else None
        jd_validation = jd.validation if jd else None
        cv_explicit = cv.explicit if cv else None
        jd_explicit = jd.explicit if jd else None

        cv_explicit_skills = (
            [skill.model_dump() for skill in cv_explicit.skills]
            if include_details and cv_explicit
            else None
        )
        cv_accepted = (
            [skill.model_dump() for skill in cv_validation.accepted_implicit_skills]
            if include_details and cv_validation
            else None
        )
        cv_duplicates = (
            [skill.model_dump() for skill in cv_validation.duplicate_implicit_skills]
            if include_details and cv_validation
            else None
        )
        cv_rejected = (
            [skill.model_dump() for skill in cv_validation.rejected_implicit_skills]
            if include_details and cv_validation
            else None
        )

        jd_explicit_skills = (
            [skill.model_dump() for skill in jd_explicit.skills]
            if include_details and jd_explicit
            else None
        )
        jd_accepted = (
            [skill.model_dump() for skill in jd_validation.accepted_implicit_skills]
            if include_details and jd_validation
            else None
        )
        jd_duplicates = (
            [skill.model_dump() for skill in jd_validation.duplicate_implicit_skills]
            if include_details and jd_validation
            else None
        )
        jd_rejected = (
            [skill.model_dump() for skill in jd_validation.rejected_implicit_skills]
            if include_details and jd_validation
            else None
        )

        summary = unified_response.summary
        cv_explicit_count = (
            summary.cv_explicit_count
            if summary
            else len(cv_explicit.skills) if cv_explicit else 0
        )
        cv_implicit_count = (
            summary.cv_implicit_count
            if summary
            else len(cv_validation.accepted_implicit_skills) if cv_validation else 0
        )
        cv_duplicate_count = len(cv_validation.duplicate_implicit_skills) if cv_validation else 0
        cv_rejected_count = len(cv_validation.rejected_implicit_skills) if cv_validation else 0

        jd_explicit_count = (
            summary.jd_explicit_count
            if summary
            else len(jd_explicit.skills) if jd_explicit else 0
        )
        jd_implicit_count = (
            summary.jd_implicit_count
            if summary
            else len(jd_validation.accepted_implicit_skills) if jd_validation else 0
        )
        jd_duplicate_count = len(jd_validation.duplicate_implicit_skills) if jd_validation else 0
        jd_rejected_count = len(jd_validation.rejected_implicit_skills) if jd_validation else 0

        return PipelineExtractionSummary(
            cv=DocumentExtractionDetails(
                explicit_count=cv_explicit_count,
                implicit_count=cv_implicit_count,
                duplicate_count=cv_duplicate_count,
                rejected_implicit_count=cv_rejected_count,
                explicit_skills=cv_explicit_skills,
                accepted_implicit_skills=cv_accepted,
                duplicate_implicit_skills=cv_duplicates,
                rejected_implicit_skills=cv_rejected,
            ),
            jd=DocumentExtractionDetails(
                explicit_count=jd_explicit_count,
                implicit_count=jd_implicit_count,
                duplicate_count=jd_duplicate_count,
                rejected_implicit_count=jd_rejected_count,
                explicit_skills=jd_explicit_skills,
                accepted_implicit_skills=jd_accepted,
                duplicate_implicit_skills=jd_duplicates,
                rejected_implicit_skills=jd_rejected,
            ),
            total_unique_skills=(
                summary.total_unique_skills
                if summary
                else cv_explicit_count + cv_implicit_count + jd_explicit_count + jd_implicit_count
            ),
            duplicate_count=(
                summary.duplicate_count
                if summary
                else cv_duplicate_count + jd_duplicate_count
            ),
        )

    @staticmethod
    def semantic_representation_summary(
        response: SemanticRepresentationResponse,
        *,
        top_k: int,
        include_embeddings: bool,
    ) -> PipelineSemanticRepresentation:
        candidate_pairs: List[CandidatePairSummary] = []
        retrievals = (response.top_k_retrievals or {}).get("cv_skills_to_jd_skills") or []
        for retrieval in retrievals:
            for candidate in retrieval.candidates:
                candidate_pairs.append(
                    CandidatePairSummary(
                        source_skill_id=retrieval.query_id,
                        source_label=retrieval.query_label,
                        target_skill_id=candidate.target_id,
                        target_label=candidate.target_label,
                        cosine_similarity=round(float(candidate.cosine_similarity), 4),
                        rank=candidate.rank,
                    )
                )

        return PipelineSemanticRepresentation(
            top_k=top_k,
            model_id=PINNED_SBERT_MODEL_ID,
            model_revision=PINNED_SBERT_REVISION,
            cv_skills_encoded=len(response.cv_skill_embeddings),
            jd_skills_encoded=len(response.jd_skill_embeddings),
            cv_evidences_encoded=len(response.cv_evidence_embeddings),
            jd_requirements_encoded=len(response.jd_requirement_embeddings),
            candidate_pairs_count=len(candidate_pairs),
            candidate_pairs=candidate_pairs,
            cv_embeddings=(
                [embedding.model_dump() for embedding in response.cv_skill_embeddings]
                if include_embeddings
                else None
            ),
            jd_embeddings=(
                [embedding.model_dump() for embedding in response.jd_skill_embeddings]
                if include_embeddings
                else None
            ),
        )
