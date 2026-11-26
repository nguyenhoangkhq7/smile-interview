"""Targeted reproduction tests for Stage 3 production hardening and acceptance verification."""
import copy
import hashlib
import numpy as np
import pytest
from pydantic import ValidationError

from matching_cv.app.schemas.implicit_skill_extraction import (
    ImplicitEvidence,
    ImplicitEvidenceSnippet,
    ImplicitExtractedSkill,
    ImplicitExtractionResult,
    ImplicitExtractionStats,
)
from matching_cv.app.schemas.semantic_representation import (
    EmbeddingGenerateRequest,
    EmbeddingRecord,
)
from matching_cv.app.schemas.skill_extraction import Evidence, ExtractedSkill, ExtractionResult, ExtractionStats
from matching_cv.app.schemas.unified_skill_extraction import (
    DocumentUnifiedResult,
    DocumentValidationResult,
    DuplicateImplicitSkill,
    UnifiedExtractFileResponse,
)
from matching_cv.app.services.extraction_adapter import (
    AdaptedEvidenceOccurrence,
    AdaptedRequirementItem,
    AdaptedSkillItem,
    ExtractionDataAdapter,
)
from matching_cv.app.services.semantic_embedding_service import SemanticEmbeddingService
from matching_cv.app.services.semantic_representation_service import (
    SemanticRepresentationService,
    semantic_representation_service,
)
from matching_cv.app.services.semantic_retrieval_service import SemanticRetrievalService


def make_skill(skill_id: str, sf: str, doc_type: str = "CV") -> ExtractedSkill:
    sent = f"Proficient with {sf}."
    start = sent.find(sf)
    return ExtractedSkill(
        skill_id=skill_id,
        surface_forms=[sf],
        category="Technology/Tool",
        kind="skill",
        evidences=[
            Evidence(
                surface_form=sf,
                sentence=sent,
                start=0,
                end=len(sent),
                section="skills",
                mention_start=start,
                mention_end=start + len(sf),
                offset_resolved=True,
                verbatim_ok=True,
                mention_ambiguous=False,
                kind="skill",
                kind_raw="skill",
                kind_source="llm",
                category="Technology/Tool",
                category_raw="Technology/Tool",
            )
        ],
    )


def make_implicit_skill(skill_id: str, label: str) -> ImplicitExtractedSkill:
    return ImplicitExtractedSkill(
        skill_id=skill_id,
        label=label,
        category="Technology/Tool",
        evidences=[
            ImplicitEvidence(
                inferred_from_raw=f"Experience designing {label} architectures.",
                basis="activity",
                reasoning="Inferred from architecture design.",
                llm_confidence_raw=0.85,
            )
        ],
    )


# =====================================================================
# FIX A: COLLISION-RESISTANT OCCURRENCE IDENTIFIERS
# =====================================================================

def test_fix_a_explicit_and_implicit_same_skill_id_do_not_collide():
    """An explicit and an implicit skill sharing the exact same skill_id must have distinct occurrence_ids."""
    doc = DocumentUnifiedResult(
        document_type="CV",
        text_sha256="abc12345def67890",
        explicit=ExtractionResult(
            document_type="CV",
            stats=ExtractionStats(total_mentions=1, unique_skills=1, unresolved_mentions=0),
            skills=[make_skill("python", "Python", "CV")],
        ),
        validation=DocumentValidationResult(
            status="completed",
            accepted_implicit_skills=[make_implicit_skill("python", "Python")],
        ),
    )
    skills, _ = ExtractionDataAdapter.extract_active_skills(doc)
    assert len(skills) == 2
    exp_occ = skills[0].occurrence_id
    imp_occ = skills[1].occurrence_id
    assert exp_occ != imp_occ, f"Collision detected between explicit and implicit: {exp_occ}"
    assert "explicit" in exp_occ
    assert "implicit" in imp_occ


def test_fix_a_different_documents_same_skill_do_not_collide():
    """Two different CV documents with identical skills must produce distinct occurrence_ids."""
    doc1 = DocumentUnifiedResult(
        document_type="CV",
        text_sha256="11111111aaaaaaaa",
        explicit=ExtractionResult(
            document_type="CV",
            stats=ExtractionStats(total_mentions=1, unique_skills=1, unresolved_mentions=0),
            skills=[make_skill("java", "Java", "CV")],
        ),
    )
    doc2 = DocumentUnifiedResult(
        document_type="CV",
        text_sha256="22222222bbbbbbbb",
        explicit=ExtractionResult(
            document_type="CV",
            stats=ExtractionStats(total_mentions=1, unique_skills=1, unresolved_mentions=0),
            skills=[make_skill("java", "Java", "CV")],
        ),
    )
    skills1, _ = ExtractionDataAdapter.extract_active_skills(doc1)
    skills2, _ = ExtractionDataAdapter.extract_active_skills(doc2)
    assert skills1[0].occurrence_id != skills2[0].occurrence_id
    assert "11111111" in skills1[0].occurrence_id
    assert "22222222" in skills2[0].occurrence_id


def test_fix_a_cv_and_jd_same_skill_do_not_collide():
    """The same skill in CV and JD must have distinct occurrence_ids."""
    doc_cv = DocumentUnifiedResult(
        document_type="CV",
        text_sha256="cv_hash_12345678",
        explicit=ExtractionResult(
            document_type="CV",
            stats=ExtractionStats(total_mentions=1, unique_skills=1, unresolved_mentions=0),
            skills=[make_skill("docker", "Docker", "CV")],
        ),
    )
    doc_jd = DocumentUnifiedResult(
        document_type="JD",
        text_sha256="jd_hash_87654321",
        explicit=ExtractionResult(
            document_type="JD",
            stats=ExtractionStats(total_mentions=1, unique_skills=1, unresolved_mentions=0),
            skills=[make_skill("docker", "Docker", "JD")],
        ),
    )
    cv_skills, _ = ExtractionDataAdapter.extract_active_skills(doc_cv)
    jd_skills, _ = ExtractionDataAdapter.extract_active_skills(doc_jd)
    assert cv_skills[0].occurrence_id != jd_skills[0].occurrence_id
    assert "cv_hash_" in cv_skills[0].occurrence_id
    assert "jd_hash_" in jd_skills[0].occurrence_id


# =====================================================================
# FIX B: VALIDATION STATE MACHINE MUST NEVER PROMOTE FAILED RESULTS
# =====================================================================

def test_fix_b_failed_validation_is_never_promoted_to_completed():
    """When validation.status == 'failed', nonempty accepted list must NOT be treated as completed."""
    doc = DocumentUnifiedResult(
        document_type="CV",
        implicit=ImplicitExtractionResult(
            document_type="CV",
            stats=ImplicitExtractionStats(total_inferences=1, unique_skills=1),
            skills=[make_implicit_skill("redis", "Redis")],
        ),
        validation=DocumentValidationResult(
            status="failed",
            accepted_implicit_skills=[make_implicit_skill("redis", "Redis")],
            duplicate_implicit_skills=[],
        ),
    )
    res = ExtractionDataAdapter.extract_active_skills(doc, auto_revalidate_implicit=False)
    # When auto_revalidate_implicit=False, failed validation must NOT accept skills as authoritative
    # And status must NOT be changed to 'completed'
    assert doc.validation.status == "failed"
    # Active skills must not include the unverified skills from failed validation
    assert len(res[0]) == 0


def test_fix_b_completed_zero_accepted_never_resurrects_even_with_auto_revalidate():
    """State B invariant: completed validation with 0 accepted skills stays 0 accepted."""
    doc = DocumentUnifiedResult(
        document_type="CV",
        explicit=ExtractionResult(
            document_type="CV",
            stats=ExtractionStats(total_mentions=1, unique_skills=1, unresolved_mentions=0),
            skills=[make_skill("sql", "SQL", "CV")],
        ),
        implicit=ImplicitExtractionResult(
            document_type="CV",
            stats=ImplicitExtractionStats(total_inferences=1, unique_skills=1),
            skills=[make_implicit_skill("sql", "SQL")],
        ),
        validation=DocumentValidationResult(
            status="completed",
            accepted_implicit_skills=[],
            duplicate_implicit_skills=[
                DuplicateImplicitSkill(
                    skill_id="sql",
                    label="SQL",
                    matched_explicit_skill_id="sql",
                    matched_explicit_surface_form="SQL",
                )
            ],
        ),
    )
    res = ExtractionDataAdapter.extract_active_skills(doc, auto_revalidate_implicit=True)
    # Must preserve 0 accepted implicit skills
    implicit_active = [s for s in res[0] if s.extraction_type == "implicit"]
    assert len(implicit_active) == 0


# =====================================================================
# FIX C: REQUIREMENT ASSOCIATION METADATA SAFETY
# =====================================================================

def test_fix_c_add_skill_association_default_is_conservative():
    """Omitting association_method must not default to verified_mention_span without mention offsets."""
    req = AdaptedRequirementItem(
        occurrence_id="occ_req_1",
        text="Experience with Java.",
        source_identifier="jd.pdf",
    )
    # Caller calls add_skill_association without method or mention offsets
    req.add_skill_association(skill_id="java", skill_name="Java")
    assert len(req.associations_meta) == 1
    meta = req.associations_meta[0]
    assert meta["association_method"] != "verified_mention_span"
    assert meta["verification_status"] != "verified_mention"


def test_fix_c_unresolved_requirement_does_not_inject_fake_skill_id():
    """An unresolved requirement must not have 'unresolved' in associated_skill_ids."""
    raw_jd = "Requirements:\n- Must be an energetic person with good humor."
    doc = DocumentUnifiedResult(
        document_type="JD",
        text_sha256=hashlib.sha256(raw_jd.encode()).hexdigest(),
        explicit=ExtractionResult(document_type="JD", stats=ExtractionStats(total_mentions=0, unique_skills=0, unresolved_mentions=0), skills=[]),
    )
    reqs, _ = ExtractionDataAdapter.segment_jd_requirements(doc, raw_jd, "jd.pdf")
    assert len(reqs) >= 1
    for r in reqs:
        assert "unresolved" not in r.associated_skill_ids
        assert len(r.associated_skill_ids) == 0


# =====================================================================
# FIX D: IMPLICIT EVIDENCE OFFSETS MUST NOT MASQUERADE AS MENTIONS
# =====================================================================

def test_fix_d_implicit_evidence_offsets_are_none_for_mentions():
    """Implicit associations must have mention_start=None and mention_end=None."""
    raw_jd = "Responsibilities:\n- Design high-throughput relational schemas."
    jd_hash = hashlib.sha256(raw_jd.encode()).hexdigest()
    doc = DocumentUnifiedResult(
        document_type="JD",
        text_sha256=jd_hash,
        explicit=ExtractionResult(document_type="JD", stats=ExtractionStats(total_mentions=0, unique_skills=0, unresolved_mentions=0), skills=[]),
        validation=DocumentValidationResult(
            status="completed",
            accepted_implicit_skills=[
                ImplicitExtractedSkill(
                    skill_id="database-partitioning",
                    label="Database Partitioning",
                    evidences=[
                        ImplicitEvidence(
                            inferred_from_raw="Design high-throughput relational schemas.",
                            snippets=[
                                ImplicitEvidenceSnippet(
                                    text="Design high-throughput relational schemas.",
                                    start=18,
                                    end=61,
                                    section="responsibilities",
                                )
                            ],
                            basis="activity",
                            reasoning="inferred from schema design",
                            llm_confidence_raw=0.85,
                        )
                    ],
                )
            ],
        ),
    )
    reqs, _ = ExtractionDataAdapter.segment_jd_requirements(doc, raw_jd, "jd.pdf")
    assert len(reqs) == 1
    req = reqs[0]
    assert len(req.associations_meta) == 1
    meta = req.associations_meta[0]
    assert meta["extraction_type"] == "implicit"
    assert meta["association_method"] == "implicit_evidence_supported"
    assert meta["mention_start"] is None
    assert meta["mention_end"] is None
    assert meta["evidence_reference"].get("snippet_start") == 18
    assert meta["evidence_reference"].get("snippet_end") == 61


# =====================================================================
# FIX E: SWAGGER AUTO-WRAPPER MUST NOT FABRICATE STATUS
# =====================================================================

def test_fix_e_wrapper_does_not_fabricate_completed_status():
    """If raw unwrapped input is missing 'status', it must not silently fabricate 'completed'."""
    raw_payload = {
        "cv": {"document_type": "CV", "filename": "cv.pdf"},
        "jd": {"document_type": "JD", "filename": "jd.pdf"},
        # run_id and status are missing!
    }
    with pytest.raises((ValidationError, ValueError)):
        EmbeddingGenerateRequest.model_validate(raw_payload)


def test_fix_e_wrapper_rejects_conflicting_wrapped_and_unwrapped():
    """If both unified_response and top-level cv/jd are provided, it must be rejected."""
    raw_payload = {
        "unified_response": {
            "run_id": "run-1",
            "status": "completed",
            "cv": {"document_type": "CV"},
        },
        "cv": {"document_type": "CV", "filename": "other.pdf"},
    }
    with pytest.raises((ValidationError, ValueError)):
        EmbeddingGenerateRequest.model_validate(raw_payload)


# =====================================================================
# FIX F: VECTOR ALIGNMENT SAFETY
# =====================================================================

def test_fix_f_vector_alignment_with_rejected_records():
    """Verify that vector rows match valid records exactly when rejections occur."""
    mock_records = [
        EmbeddingRecord(
            occurrence_id="occ_0",
            vector_id="vec_0",
            embedding_id="occ_0",
            document_type="CV",
            source_identifier="cv.pdf",
            target_type="skill",
            source_text="skill 0",
            construction_strategy="skill_name",
            text_hash="hash0",
            model_id="mock",
            embedding_dim=4,
            truncation_status="rejected",
        ),
        EmbeddingRecord(
            occurrence_id="occ_1",
            vector_id="vec_1",
            embedding_id="occ_1",
            document_type="CV",
            source_identifier="cv.pdf",
            target_type="skill",
            source_text="skill 1",
            construction_strategy="skill_name",
            text_hash="hash1",
            model_id="mock",
            embedding_dim=4,
            truncation_status="not_truncated",
        ),
    ]
    valid_records = [r for r in mock_records if r.truncation_status != "rejected"]
    vecs = np.array([[1.0, 0.0, 0.0, 0.0]], dtype=np.float32)
    # The matrix must have 1 row matching valid_records[0]
    matrix = SemanticRetrievalService.compute_cosine_matrix(vecs, vecs, valid_records, valid_records)
    assert matrix.source_ids == ["occ_1"]
    assert matrix.target_ids == ["occ_1"]


def test_cv_and_jd_text_retention_and_propagation():
    """Verify that cv_text and jd_text are retained on DocumentUnifiedResult and UnifiedExtractFileResponse."""
    raw_cv = "Experienced Python and FastAPI backend developer."
    raw_jd = "Looking for a Python developer with FastAPI and PostgreSQL experience."

    doc_cv = DocumentUnifiedResult(
        document_type="CV",
        filename="cv.pdf",
        text_sha256=hashlib.sha256(raw_cv.encode()).hexdigest(),
        raw_text=raw_cv,
    )
    doc_jd = DocumentUnifiedResult(
        document_type="JD",
        filename="jd.pdf",
        text_sha256=hashlib.sha256(raw_jd.encode()).hexdigest(),
        raw_text=raw_jd,
    )
    assert doc_cv.raw_text == raw_cv
    assert doc_jd.raw_text == raw_jd

    resp = UnifiedExtractFileResponse(
        run_id="run-text-test",
        status="completed",
        cv=doc_cv,
        jd=doc_jd,
        cv_text=raw_cv,
        jd_text=raw_jd,
    )
    assert resp.cv_text == raw_cv
    assert resp.jd_text == raw_jd

    # Test auto-wrapper with raw extraction payload containing cv_text and jd_text
    raw_payload = {
        "run_id": "run-wrapped-text",
        "status": "completed",
        "cv": doc_cv.model_dump(),
        "jd": doc_jd.model_dump(),
        "cv_text": raw_cv,
        "jd_text": raw_jd,
    }
    req = EmbeddingGenerateRequest.model_validate(raw_payload)
    assert req.cv_text == raw_cv
    assert req.jd_text == raw_jd
    assert req.unified_response.cv_text == raw_cv
    assert req.unified_response.jd_text == raw_jd


def test_sbert_auto_resolves_text_from_unified_response():
    """Verify that SBERT automatically retrieves full JD and CV text from unified_response when top-level request texts are omitted."""
    raw_cv = "Senior Software Engineer with 5 years in Python and Docker."
    raw_jd = """Willow Health
Requirements:
- 3+ years of experience with Python and Docker in production.
- Knowledge of relational databases."""
    cv_sha = hashlib.sha256(raw_cv.encode()).hexdigest()
    jd_sha = hashlib.sha256(raw_jd.encode()).hexdigest()

    doc_cv = DocumentUnifiedResult(
        document_type="CV",
        filename="cv.pdf",
        text_sha256=cv_sha,
        raw_text=raw_cv,
        explicit=ExtractionResult(
            filename="cv.pdf",
            document_type="CV",
            text_sha256=cv_sha,
            skills=[make_skill("python", "Python", "CV")],
            stats=ExtractionStats(total_mentions=1, unique_skills=1),
        ),
    )
    doc_jd = DocumentUnifiedResult(
        document_type="JD",
        filename="jd.pdf",
        text_sha256=jd_sha,
        raw_text=raw_jd,
        explicit=ExtractionResult(
            filename="jd.pdf",
            document_type="JD",
            text_sha256=jd_sha,
            skills=[make_skill("python", "Python", "JD")],
            stats=ExtractionStats(total_mentions=1, unique_skills=1),
        ),
    )
    unified = UnifiedExtractFileResponse(
        run_id="run-auto-text",
        status="completed",
        cv=doc_cv,
        jd=doc_jd,
        cv_text=raw_cv,
        jd_text=raw_jd,
    )

    # Note: request.jd_text and request.cv_text are deliberately NOT passed here!
    req = EmbeddingGenerateRequest(
        unified_response=unified,
        jd_text=None,
        cv_text=None,
        include_vectors=False,
    )
    result = semantic_representation_service.generate_representations(req)

    # SBERT must have auto-resolved jd_text from unified_response.jd_text / jd.raw_text
    assert result.diagnostics["requirements_diagnostics"]["jd_requirements_source"] == "raw_jd_text"
    assert result.diagnostics["jd_text_sha256_verification"] == "verified_match"
    assert result.diagnostics["cv_text_sha256_verification"] == "verified_match"
    # Should have segmented actual requirements from raw_jd_text
    assert len(result.jd_requirement_embeddings) > 0
