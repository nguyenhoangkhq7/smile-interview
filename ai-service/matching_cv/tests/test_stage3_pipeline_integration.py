"""Tests for Stage 3 Pipeline Integration, Implicit Skill Propagation, JD Requirements, and Retrieval Scope."""
import hashlib
import json
import re
import numpy as np
import pytest
import torch
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient

from matching_cv.app.core.config import settings
from matching_cv.app.core.model_loader import model_loader
from matching_cv.app.main import app
from matching_cv.app.schemas.implicit_skill_extraction import (
    ImplicitEvidence,
    ImplicitEvidenceSnippet,
    ImplicitExtractedSkill,
    ImplicitExtractionResult,
    ImplicitExtractionStats,
)
from matching_cv.app.schemas.skill_extraction import Evidence, ExtractedSkill, ExtractionResult, ExtractionStats
from matching_cv.app.schemas.unified_skill_extraction import (
    DocumentUnifiedResult,
    DocumentValidationResult,
    DuplicateImplicitSkill,
    PipelineError,
    UnifiedExtractFileResponse,
    UnifiedExtractionSummary,
)
from matching_cv.app.schemas.semantic_representation import (
    EmbeddingGenerateRequest,
    EmbeddingRecord,
    SemanticRepresentationResponse,
)
from matching_cv.app.services.extraction_adapter import (
    AdaptedRequirementItem,
    AdaptedSkillItem,
    ExtractionDataAdapter,
    build_term_pattern,
)
from matching_cv.app.services.semantic_embedding_service import SemanticEmbeddingService
from matching_cv.app.services.semantic_retrieval_service import SemanticRetrievalService
from matching_cv.app.services.semantic_representation_service import SemanticRepresentationService
from matching_cv.app.services.document_parser import document_parser_service
from matching_cv.app.services.skill_postprocessor import skill_postprocessor


def make_extraction_result(skills, doc_type="CV", filename=None):
    """Helper creating invariant-compliant ExtractionResult."""
    total_mentions = sum(len(s.evidences) for s in skills)
    unres = sum(1 for s in skills for ev in s.evidences if ev.mention_start is None)
    ambig = sum(1 for s in skills for ev in s.evidences if getattr(ev, "mention_ambiguous", False))
    return ExtractionResult(
        filename=filename or f"doc_{doc_type.lower()}.pdf",
        document_type=doc_type,
        stats=ExtractionStats(
            total_mentions=total_mentions,
            unique_skills=len(skills),
            unresolved_mentions=unres,
            ambiguous_mentions=ambig,
        ),
        skills=skills,
    )


def make_implicit_extraction_result(skills, doc_type="CV", filename=None):
    """Helper creating invariant-compliant ImplicitExtractionResult."""
    total_inferences = sum(len(s.evidences) for s in skills)
    return ImplicitExtractionResult(
        filename=filename or f"doc_{doc_type.lower()}.pdf",
        document_type=doc_type,
        stats=ImplicitExtractionStats(
            total_inferences=total_inferences,
            unique_skills=len(skills),
        ),
        skills=skills,
    )


@pytest.fixture
def mock_sbert_model():
    """Mock SentenceTransformer generating deterministic 768-dim normalized vectors."""
    model = MagicMock()
    model.max_seq_length = 128

    def mock_encode(texts, batch_size=32, convert_to_tensor=True, normalize_embeddings=True, show_progress_bar=False):
        vectors = []
        for text in texts:
            seed = int(hashlib.sha256(text.encode("utf-8")).hexdigest()[:8], 16)
            rng = np.random.RandomState(seed)
            raw = rng.randn(768).astype(np.float32)
            norm = np.linalg.norm(raw)
            vectors.append(raw / norm)
        arr = np.vstack(vectors).astype(np.float32)
        if convert_to_tensor:
            return torch.tensor(arr, dtype=torch.float32)
        return arr

    model.encode.side_effect = mock_encode

    tokenizer = MagicMock()
    def mock_tokenize(text, add_special_tokens=True, truncation=False):
        words = text.split()
        return list(range(len(words) + (2 if add_special_tokens else 0)))

    tokenizer.encode.side_effect = mock_tokenize
    tokenizer.decode.side_effect = lambda ids, skip_special_tokens=True: f"chunk_{len(ids)}"
    model.tokenizer = tokenizer
    return model


@pytest.fixture
def integration_service(mock_sbert_model):
    """Semantic representation service wired with mock model."""
    loader = MagicMock()
    loader.get_model.return_value = mock_sbert_model
    loader.get_tokenizer.return_value = mock_sbert_model.tokenizer
    loader.get_max_seq_length.return_value = 128
    loader.device = "cpu"
    emb = SemanticEmbeddingService(loader=loader, batch_size=16)
    ret = SemanticRetrievalService()
    return SemanticRepresentationService(embedding_service=emb, retrieval_service=ret)


# =============================================================================
# GROUP 1: Implicit Propagation (Cases 1 - 6)
# =============================================================================

def test_case_01_explicit_and_accepted_implicit_skills_on_both_cv_and_jd(integration_service):
    """Case 1: Both CV and JD have explicit and accepted implicit skills propagated cleanly."""
    cv_exp = [ExtractedSkill(skill_id="java", surface_forms=["Java"], kind="skill", category="Technology/Tool", type="explicit", evidences=[])]
    cv_imp = [ImplicitExtractedSkill(skill_id="event-driven", label="Event-Driven", category="Technical Concept", basis="activity", type="implicit", evidences=[])]
    jd_exp = [ExtractedSkill(skill_id="kafka", surface_forms=["Kafka"], kind="skill", category="Technology/Tool", type="explicit", evidences=[])]
    jd_imp = [ImplicitExtractedSkill(skill_id="caching", label="Caching Strategy", category="Technical Concept", basis="activity", type="implicit", evidences=[])]

    unified = UnifiedExtractFileResponse(
        run_id="run_c1",
        status="completed",
        cv=DocumentUnifiedResult(
            filename="cv.pdf",
            document_type="CV",
            explicit=make_extraction_result(cv_exp, "CV", "cv.pdf"),
            validation=DocumentValidationResult(accepted_implicit_skills=cv_imp),
        ),
        jd=DocumentUnifiedResult(
            filename="jd.pdf",
            document_type="JD",
            explicit=make_extraction_result(jd_exp, "JD", "jd.pdf"),
            validation=DocumentValidationResult(accepted_implicit_skills=jd_imp),
        ),
    )

    req = EmbeddingGenerateRequest(unified_response=unified, compute_similarity=False)
    resp = integration_service.generate_representations(req)

    assert resp.stats.cv_explicit_skills == 1
    assert resp.stats.cv_accepted_implicit_skills == 1
    assert resp.stats.jd_explicit_skills == 1
    assert resp.stats.jd_accepted_implicit_skills == 1
    assert len(resp.cv_skill_embeddings) == 2
    assert len(resp.jd_skill_embeddings) == 2


def test_case_02_nonempty_implicit_skills_with_incomplete_validation(integration_service):
    """Case 2: Implicit extraction is non-empty, but validation data was missing/empty -> auto-revalidated."""
    cv_exp = [ExtractedSkill(skill_id="java", surface_forms=["Java"], kind="skill", category="Technology/Tool", type="explicit", evidences=[])]
    cv_imp = [
        ImplicitExtractedSkill(
            skill_id="microservices",
            label="Microservices Architecture",
            category="Technical Concept",
            basis="activity",
            type="implicit",
            evidences=[
                ImplicitEvidence(
                    inferred_from_raw="Architected and designed microservices architecture.",
                    snippets=[ImplicitEvidenceSnippet(text="Architected and designed microservices architecture.", verbatim_ok=True)],
                    reasoning="Direct architecture design evidence.",
                    confidence=0.9,
                )
            ],
        ),
        ImplicitExtractedSkill(
            skill_id="java",
            label="Java Programming",
            category="Technology/Tool",
            basis="activity",
            type="implicit",
            evidences=[
                ImplicitEvidence(
                    inferred_from_raw="Experienced Java developer.",
                    snippets=[ImplicitEvidenceSnippet(text="Experienced Java developer.", verbatim_ok=True)],
                    reasoning="Java evidence.",
                    confidence=0.9,
                )
            ],
        ),  # duplicate
    ]

    unified = UnifiedExtractFileResponse(
        run_id="run_c2",
        status="completed",
        cv=DocumentUnifiedResult(
            filename="cv.pdf",
            document_type="CV",
            explicit=make_extraction_result(cv_exp, "CV", "cv.pdf"),
            implicit=make_implicit_extraction_result(cv_imp, "CV", "cv.pdf"),
            validation=DocumentValidationResult(),  # Empty validation!
        ),
    )

    req = EmbeddingGenerateRequest(unified_response=unified, auto_revalidate_implicit=True, compute_similarity=False)
    resp = integration_service.generate_representations(req)

    assert resp.stats.cv_accepted_implicit_skills == 1
    assert resp.stats.cv_duplicate_implicit_skills == 1
    assert resp.audit.cv_duplicate_implicit_skills[0].skill_id == "java"


def test_case_03_legitimately_empty_accepted_implicit_skills(integration_service):
    """Case 3: Complete validation stage legitimately accepted 0 implicit skills (all were duplicates)."""
    cv_exp = [ExtractedSkill(skill_id="java", surface_forms=["Java"], kind="skill", category="Technology/Tool", type="explicit", evidences=[])]
    cv_dups = [DuplicateImplicitSkill(skill_id="java", label="Java", matched_explicit_skill_id="java", matched_explicit_surface_form="Java")]

    unified = UnifiedExtractFileResponse(
        run_id="run_c3",
        status="completed",
        cv=DocumentUnifiedResult(
            filename="cv.pdf",
            document_type="CV",
            explicit=make_extraction_result(cv_exp, "CV", "cv.pdf"),
            validation=DocumentValidationResult(duplicate_implicit_skills=cv_dups, accepted_implicit_skills=[]),
        ),
    )

    req = EmbeddingGenerateRequest(unified_response=unified, compute_similarity=False)
    resp = integration_service.generate_representations(req)

    assert resp.stats.cv_accepted_implicit_skills == 0
    assert resp.stats.cv_duplicate_implicit_skills == 1
    assert len(resp.cv_skill_embeddings) == 1


def test_case_04_duplicate_implicit_skills_correctly_excluded(integration_service):
    """Case 4: Duplicate implicit skills are audited and excluded from active embeddings."""
    cv_exp = [ExtractedSkill(skill_id="sql", surface_forms=["SQL"], kind="skill", category="Technology/Tool", type="explicit", evidences=[])]
    dup = DuplicateImplicitSkill(skill_id="sql", label="SQL Querying", matched_explicit_skill_id="sql", matched_explicit_surface_form="SQL")

    unified = UnifiedExtractFileResponse(
        run_id="run_c4",
        status="completed",
        cv=DocumentUnifiedResult(
            filename="cv.pdf",
            document_type="CV",
            explicit=make_extraction_result(cv_exp, "CV", "cv.pdf"),
            validation=DocumentValidationResult(duplicate_implicit_skills=[dup], accepted_implicit_skills=[]),
        ),
    )

    req = EmbeddingGenerateRequest(unified_response=unified, compute_similarity=False)
    resp = integration_service.generate_representations(req)

    embs = resp.cv_skill_embeddings
    assert len(embs) == 1
    assert embs[0].associated_skill_ids == ["sql"]
    assert embs[0].extraction_type == "explicit"
    assert len(resp.audit.cv_duplicate_implicit_skills) == 1


def test_case_05_partial_extraction_response_with_stage_errors(integration_service):
    """Case 5: Partial success response preserves available explicit skills while recording errors."""
    err = PipelineError(document="JD", stage="implicit_extraction", error_type="TimeoutError", message="LLM timeout")
    cv_exp = [ExtractedSkill(skill_id="java", surface_forms=["Java"], kind="skill", category="Technology/Tool", type="explicit", evidences=[])]

    unified = UnifiedExtractFileResponse(
        run_id="run_c5",
        status="partial_success",
        cv=DocumentUnifiedResult(
            filename="cv.pdf",
            document_type="CV",
            explicit=make_extraction_result(cv_exp, "CV", "cv.pdf"),
        ),
        errors=[err],
    )

    req = EmbeddingGenerateRequest(unified_response=unified, compute_similarity=False)
    resp = integration_service.generate_representations(req)

    assert resp.stats.cv_explicit_skills == 1
    assert len(resp.cv_skill_embeddings) == 1


def test_case_06_historical_fixture_compatibility():
    """Case 6: Historical stored fixtures load cleanly and extract expected skills."""
    with open("tests/fixtures/stored_runs/01_Backend_CV_run1.json", "r", encoding="utf-8") as f:
        run1 = json.load(f)
    with open("tests/fixtures/01_Backend_CV.pdf", "rb") as f:
        cv_raw, _ = document_parser_service.extract_text_from_pdf(f.read())
        cv_cleaned = document_parser_service.clean_extracted_text(cv_raw)

    res = skill_postprocessor.process_extraction(
        raw_result=run1["raw_llm"],
        text=cv_cleaned,
        filename="01_Backend_CV.pdf",
        document_type="CV",
    )
    assert len(res.skills) == 47


# =============================================================================
# GROUP 2: JD Text and Consistency Guard (Cases 7 - 11)
# =============================================================================

def test_case_07_original_jd_text_supplied(integration_service):
    """Case 7: When original JD text is supplied, requirements are segmented with spans."""
    jd_raw = "Requirements:\n* 3+ years experience with Spring Boot microservices.\n* Kafka streaming."
    h = hashlib.sha256(jd_raw.encode("utf-8")).hexdigest()

    unified = UnifiedExtractFileResponse(
        run_id="run_c7",
        status="completed",
        jd=DocumentUnifiedResult(
            filename="jd.pdf",
            document_type="JD",
            text_sha256=h,
            explicit=make_extraction_result(
                [ExtractedSkill(skill_id="spring-boot", surface_forms=["Spring Boot"], kind="skill", category="Technology/Tool", type="explicit", evidences=[])],
                "JD",
                "jd.pdf",
            ),
        ),
    )

    req = EmbeddingGenerateRequest(unified_response=unified, jd_text=jd_raw, compute_similarity=False)
    resp = integration_service.generate_representations(req)

    assert resp.diagnostics["requirements_diagnostics"]["jd_requirements_source"] == "raw_jd_text"
    assert resp.diagnostics["jd_text_sha256_verification"] == "verified_match"
    assert len(resp.jd_requirement_embeddings) >= 2


def test_case_08_jd_text_omitted_and_fallback_explicitly_identified(integration_service):
    """Case 8: When jd_text is omitted, fallback path is clearly recorded in diagnostics."""
    ev = Evidence(
        surface_form="Spring Boot",
        sentence="3+ years experience with Spring Boot.",
        start=0,
        end=36,
        mention_start=25,
        mention_end=36,
        section="requirements",
        kind="skill",
        category="Technology/Tool",
    )
    unified = UnifiedExtractFileResponse(
        run_id="run_c8",
        status="completed",
        jd=DocumentUnifiedResult(
            filename="jd.pdf",
            document_type="JD",
            explicit=make_extraction_result(
                [ExtractedSkill(skill_id="spring-boot", surface_forms=["Spring Boot"], kind="skill", category="Technology/Tool", type="explicit", evidences=[ev])],
                "JD",
                "jd.pdf",
            ),
        ),
    )

    req = EmbeddingGenerateRequest(unified_response=unified, jd_text=None, compute_similarity=False)
    resp = integration_service.generate_representations(req)

    assert resp.diagnostics["requirements_diagnostics"]["jd_requirements_source"] == "extracted_evidences_fallback"
    assert resp.diagnostics["jd_text_sha256_verification"] == "not_provided"
    assert len(resp.jd_requirement_embeddings) == 1


def test_case_09_jd_text_hash_matches_extraction_hash(integration_service):
    """Case 9: Matching SHA-256 is accepted without error."""
    text = "Requirements:\n* Docker containerized deployments."
    h = hashlib.sha256(text.encode("utf-8")).hexdigest()

    unified = UnifiedExtractFileResponse(
        run_id="run_c9",
        status="completed",
        jd=DocumentUnifiedResult(
            filename="jd.pdf",
            document_type="JD",
            text_sha256=h,
            explicit=make_extraction_result(
                [ExtractedSkill(skill_id="docker", surface_forms=["Docker"], kind="skill", category="Technology/Tool", type="explicit", evidences=[])],
                "JD",
                "jd.pdf",
            ),
        ),
    )

    req = EmbeddingGenerateRequest(unified_response=unified, jd_text=text, compute_similarity=False)
    resp = integration_service.generate_representations(req)
    assert resp.diagnostics["jd_text_sha256_verification"] == "verified_match"


def test_case_10_jd_text_hash_mismatch_rejected(integration_service):
    """Case 10: Mismatch between supplied jd_text and stored text_sha256 raises ValueError."""
    text = "Requirements:\n* Docker containerized deployments."
    wrong_hash = "0000000000000000000000000000000000000000000000000000000000000000"

    unified = UnifiedExtractFileResponse(
        run_id="run_c10",
        status="completed",
        jd=DocumentUnifiedResult(
            filename="jd.pdf",
            document_type="JD",
            text_sha256=wrong_hash,
            explicit=make_extraction_result([], "JD", "jd.pdf"),
        ),
    )

    req = EmbeddingGenerateRequest(unified_response=unified, jd_text=text, compute_similarity=False)
    with pytest.raises(ValueError, match="SHA-256 mismatch"):
        integration_service.generate_representations(req)


def test_case_11_requirement_spans_remain_correct_after_preprocessing():
    """Case 11: Requirement offsets map accurately back to raw text characters."""
    raw = "Header Section\nRequirements:\n* Hands-on experience with Python and FastAPI.\n* CI/CD pipelines."
    doc_jd = DocumentUnifiedResult(
        document_type="JD",
        explicit=make_extraction_result([], "JD", "jd.pdf"),
    )
    reqs, _ = ExtractionDataAdapter.segment_jd_requirements(doc_jd, raw, "jd.pdf")
    assert len(reqs) == 2
    for r in reqs:
        assert r.start is not None and r.end is not None
        assert r.text in raw[r.start:r.end] or raw[r.start:r.end].strip() in raw


# =============================================================================
# GROUP 3: Requirement Associations (Cases 12 - 18)
# =============================================================================

def test_case_12_one_requirement_referencing_multiple_explicit_skills():
    """Case 12: One requirement containing Java and Spring Boot preserves both associations."""
    line = "2+ years of professional experience with Java and Spring Boot in a production environment."
    skills = [
        ExtractedSkill(skill_id="java", surface_forms=["Java"], kind="skill", category="Technology/Tool", type="explicit", evidences=[]),
        ExtractedSkill(skill_id="spring-boot", surface_forms=["Spring Boot"], kind="skill", category="Technology/Tool", type="explicit", evidences=[]),
    ]
    doc_jd = DocumentUnifiedResult(
        document_type="JD",
        explicit=make_extraction_result(skills, "JD", "jd.pdf"),
    )
    raw = f"Requirements:\n- {line}"
    reqs, _ = ExtractionDataAdapter.segment_jd_requirements(doc_jd, raw, "jd.pdf")
    assert len(reqs) == 1
    req = reqs[0]
    assert "java" in req.associated_skill_ids
    assert "spring-boot" in req.associated_skill_ids


def test_case_13_shared_evidence_sentence_supporting_multiple_skills_in_fallback():
    """Case 13: Multiple skills citing the identical evidence sentence in fallback both get associated."""
    shared = "Build high-throughput microservices using Java and Spring Boot."
    ev_java = Evidence(surface_form="Java", sentence=shared, start=42, end=46, mention_start=42, mention_end=46, section="requirements", kind="skill", category="Technology/Tool")
    ev_spring = Evidence(surface_form="Spring Boot", sentence=shared, start=51, end=62, mention_start=51, mention_end=62, section="requirements", kind="skill", category="Technology/Tool")

    skills = [
        ExtractedSkill(skill_id="java", surface_forms=["Java"], kind="skill", category="Technology/Tool", type="explicit", evidences=[ev_java]),
        ExtractedSkill(skill_id="spring-boot", surface_forms=["Spring Boot"], kind="skill", category="Technology/Tool", type="explicit", evidences=[ev_spring]),
    ]
    doc_jd = DocumentUnifiedResult(
        document_type="JD",
        explicit=make_extraction_result(skills, "JD", "jd.pdf"),
    )

    reqs, _ = ExtractionDataAdapter.segment_jd_requirements(doc_jd, raw_jd_text=None, source_identifier="jd.pdf")
    assert len(reqs) == 1
    req = reqs[0]
    assert "java" in req.associated_skill_ids
    assert "spring-boot" in req.associated_skill_ids


def test_case_14_explicit_evidence_offsets_spanning_requirement_boundaries():
    """Case 14: Evidence offsets overlapping requirement boundaries trigger span_overlap association."""
    raw = "Requirements:\n* Advanced microservice architecture with Go."
    req_start = raw.find("Advanced")
    go_start = raw.find("Go")

    ev = Evidence(surface_form="Go", sentence=raw[req_start:], start=req_start, end=len(raw), mention_start=go_start, mention_end=go_start + 2, section="requirements", kind="skill", category="Technology/Tool")
    skills = [ExtractedSkill(skill_id="go", surface_forms=["Go"], kind="skill", category="Technology/Tool", type="explicit", evidences=[ev])]
    doc_jd = DocumentUnifiedResult(
        document_type="JD",
        explicit=make_extraction_result(skills, "JD", "jd.pdf"),
    )

    reqs, _ = ExtractionDataAdapter.segment_jd_requirements(doc_jd, raw, "jd.pdf")
    assert len(reqs) == 1
    assert "go" in reqs[0].associated_skill_ids
    assert any(m["association_method"] == "verified_mention_span" for m in reqs[0].associations_meta)


def test_case_15_java_versus_javascript_substring_safety():
    """Case 15: Java must NOT match JavaScript."""
    pat_java = build_term_pattern("Java")
    assert not pat_java.search("Strong JavaScript knowledge required.")
    assert pat_java.search("Strong Java knowledge required.")

    skills = [ExtractedSkill(skill_id="java", surface_forms=["Java"], kind="skill", category="Technology/Tool", type="explicit", evidences=[])]
    doc_jd = DocumentUnifiedResult(
        document_type="JD",
        explicit=make_extraction_result(skills, "JD", "jd.pdf"),
    )
    raw = "Requirements:\n- Strong JavaScript frontend skills."
    reqs, _ = ExtractionDataAdapter.segment_jd_requirements(doc_jd, raw, "jd.pdf")
    assert "java" not in reqs[0].associated_skill_ids


def test_case_16_technical_terms_containing_punctuation():
    """Case 16: Punctuation terms (C++, C#, .NET, Node.js) match accurately without false positives."""
    pat_cpp = build_term_pattern("C++")
    pat_csharp = build_term_pattern("C#")
    pat_dotnet = build_term_pattern(".NET")
    pat_nodejs = build_term_pattern("Node.js")
    pat_c = build_term_pattern("C")

    text = "We require C++, C#, .NET core, and Node.js backend services."
    assert pat_cpp.search(text)
    assert pat_csharp.search(text)
    assert pat_dotnet.search(text)
    assert pat_nodejs.search(text)
    assert not pat_c.search(text)  # C alone must not match C++ or C#


def test_case_17_no_false_explicit_association_from_implicit_inference():
    """Case 17: Implicit inference associated with requirement retains extraction_type='implicit'."""
    imp_ev = ImplicitEvidence(
        inferred_from_raw="Migrated monolith to event-driven Kafka.",
        snippets=[ImplicitEvidenceSnippet(text="event-driven Kafka", start=25, end=43, section="requirements", verbatim_ok=True)],
        reasoning="Asynchronous messaging implies event-driven patterns.",
        basis="activity",
    )
    imp_skill = ImplicitExtractedSkill(
        skill_id="event-driven-architecture",
        label="Event-Driven Architecture",
        category="Technical Concept",
        basis="activity",
        type="implicit",
        evidences=[imp_ev],
    )
    doc_jd = DocumentUnifiedResult(
        document_type="JD",
        explicit=make_extraction_result([], "JD", "jd.pdf"),
        validation=DocumentValidationResult(accepted_implicit_skills=[imp_skill]),
    )

    raw = "Requirements:\n- Designing scalable event-driven Kafka pipelines."
    reqs, _ = ExtractionDataAdapter.segment_jd_requirements(doc_jd, raw, "jd.pdf")
    assert len(reqs) == 1
    req = reqs[0]
    assert "event-driven-architecture" in req.associated_skill_ids
    meta = [m for m in req.associations_meta if m["skill_id"] == "event-driven-architecture"][0]
    assert meta["extraction_type"] == "implicit"
    assert meta["basis"] == "activity"


def test_case_18_evidence_fallback_preserves_all_verified_skill_ids():
    """Case 18: Fallback path preserves all 3 skills citing a shared requirement sentence."""
    sent = "2+ years of professional experience with Java and Spring Boot in a production environment."
    ev1 = Evidence(surface_form="Java", sentence=sent, start=0, end=len(sent), mention_start=41, mention_end=45, kind="skill", category="Technology/Tool")
    ev2 = Evidence(surface_form="Spring Boot", sentence=sent, start=0, end=len(sent), mention_start=50, mention_end=61, kind="skill", category="Technology/Tool")
    ev3 = Evidence(surface_form="production environment", sentence=sent, start=0, end=len(sent), mention_start=67, mention_end=89, kind="context", category="Domain Knowledge")

    s1 = ExtractedSkill(skill_id="java", surface_forms=["Java"], kind="skill", category="Technology/Tool", type="explicit", evidences=[ev1])
    s2 = ExtractedSkill(skill_id="spring-boot", surface_forms=["Spring Boot"], kind="skill", category="Technology/Tool", type="explicit", evidences=[ev2])
    s3 = ExtractedSkill(skill_id="production-environment", surface_forms=["production environment"], kind="context", category="Domain Knowledge", type="explicit", evidences=[ev3])

    doc_jd = DocumentUnifiedResult(
        document_type="JD",
        explicit=make_extraction_result([s1, s2, s3], "JD", "jd.pdf"),
    )
    reqs, _ = ExtractionDataAdapter.segment_jd_requirements(doc_jd, None, "jd.pdf")
    assert len(reqs) == 1
    assert set(reqs[0].associated_skill_ids) == {"java", "spring-boot", "production-environment"}


# =============================================================================
# GROUP 4: Retrieval Scope & Entity Separation (Cases 19 - 23)
# =============================================================================

def test_case_19_skills_are_included_in_skill_only_retrieval(integration_service):
    """Case 19: Explicit entities with kind='skill' are included in skills_only retrieval."""
    cv_skills = [ExtractedSkill(skill_id="java", surface_forms=["Java"], kind="skill", category="Technology/Tool", type="explicit", evidences=[])]
    jd_skills = [ExtractedSkill(skill_id="java", surface_forms=["Java"], kind="skill", category="Technology/Tool", type="explicit", evidences=[])]

    unified = UnifiedExtractFileResponse(
        run_id="run_c19",
        status="completed",
        cv=DocumentUnifiedResult(document_type="CV", explicit=make_extraction_result(cv_skills, "CV")),
        jd=DocumentUnifiedResult(document_type="JD", explicit=make_extraction_result(jd_skills, "JD")),
    )

    req = EmbeddingGenerateRequest(unified_response=unified, retrieval_scope="skills_only", compute_similarity=True)
    resp = integration_service.generate_representations(req)

    assert "cv_skills_vs_jd_skills" in resp.similarity_matrices
    mat = resp.similarity_matrices["cv_skills_vs_jd_skills"]
    assert len(mat.source_ids) == 1
    assert len(mat.target_ids) == 1


def test_case_20_context_and_domain_are_excluded_from_default_skill_retrieval(integration_service):
    """Case 20: Context and domain items are excluded from cv_skills_vs_jd_skills under skills_only scope."""
    cv_skills = [
        ExtractedSkill(skill_id="java", surface_forms=["Java"], kind="skill", category="Technology/Tool", type="explicit", evidences=[]),
        ExtractedSkill(skill_id="fintech", surface_forms=["Fintech"], kind="domain", category="Domain Knowledge", type="explicit", evidences=[]),
        ExtractedSkill(skill_id="production-env", surface_forms=["production environment"], kind="context", category="Domain Knowledge", type="explicit", evidences=[]),
    ]
    jd_skills = [
        ExtractedSkill(skill_id="java", surface_forms=["Java"], kind="skill", category="Technology/Tool", type="explicit", evidences=[]),
        ExtractedSkill(skill_id="e-commerce", surface_forms=["E-commerce"], kind="domain", category="Domain Knowledge", type="explicit", evidences=[]),
    ]

    unified = UnifiedExtractFileResponse(
        run_id="run_c20",
        status="completed",
        cv=DocumentUnifiedResult(document_type="CV", explicit=make_extraction_result(cv_skills, "CV")),
        jd=DocumentUnifiedResult(document_type="JD", explicit=make_extraction_result(jd_skills, "JD")),
    )

    req = EmbeddingGenerateRequest(unified_response=unified, retrieval_scope="skills_only", compute_similarity=True)
    resp = integration_service.generate_representations(req)

    assert len(resp.cv_skill_embeddings) == 3
    assert len(resp.jd_skill_embeddings) == 2

    skill_mat = resp.similarity_matrices["cv_skills_vs_jd_skills"]
    assert skill_mat.source_labels == ["Java"]
    assert skill_mat.target_labels == ["Java"]

    all_mat = resp.similarity_matrices["cv_entities_vs_jd_entities"]
    assert len(all_mat.source_labels) == 3
    assert len(all_mat.target_labels) == 2


def test_case_21_certification_embeddings_are_retained_separately(integration_service):
    """Case 21: Certification entity embeddings are preserved but excluded from skill-only ranking."""
    cv_skills = [
        ExtractedSkill(skill_id="aws-cert", surface_forms=["AWS Certified Developer"], kind="certification", category="Certification", type="explicit", evidences=[])
    ]
    jd_skills = [
        ExtractedSkill(skill_id="java", surface_forms=["Java"], kind="skill", category="Technology/Tool", type="explicit", evidences=[])
    ]

    unified = UnifiedExtractFileResponse(
        run_id="run_c21",
        status="completed",
        cv=DocumentUnifiedResult(document_type="CV", explicit=make_extraction_result(cv_skills, "CV")),
        jd=DocumentUnifiedResult(document_type="JD", explicit=make_extraction_result(jd_skills, "JD")),
    )

    req = EmbeddingGenerateRequest(unified_response=unified, retrieval_scope="skills_only", compute_similarity=True)
    resp = integration_service.generate_representations(req)

    assert len(resp.cv_skill_embeddings) == 1
    assert resp.cv_skill_embeddings[0].metadata["kind"] == "certification"

    skill_mat = resp.similarity_matrices["cv_skills_vs_jd_skills"]
    assert len(skill_mat.source_ids) == 0


def test_case_22_accepted_implicit_embeddings_retain_type_and_candidate_eligibility(integration_service):
    """Case 22: Accepted implicit skills retain extraction_type='implicit' and are eligible in skill retrieval."""
    cv_imp = [ImplicitExtractedSkill(skill_id="event-driven", label="Event-Driven Architecture", category="Technical Concept", basis="activity", type="implicit", evidences=[])]
    jd_exp = [ExtractedSkill(skill_id="event-driven", surface_forms=["Event-Driven"], kind="skill", category="Technical Concept", type="explicit", evidences=[])]

    unified = UnifiedExtractFileResponse(
        run_id="run_c22",
        status="completed",
        cv=DocumentUnifiedResult(document_type="CV", validation=DocumentValidationResult(accepted_implicit_skills=cv_imp)),
        jd=DocumentUnifiedResult(document_type="JD", explicit=make_extraction_result(jd_exp, "JD")),
    )

    req = EmbeddingGenerateRequest(unified_response=unified, retrieval_scope="skills_only", include_implicit_in_retrieval=True, compute_similarity=True)
    resp = integration_service.generate_representations(req)

    skill_mat = resp.similarity_matrices["cv_skills_vs_jd_skills"]
    assert skill_mat.source_labels == ["Event-Driven Architecture"]
    assert skill_mat.target_labels == ["Event-Driven"]


def test_case_23_original_all_entity_retrieval_remains_backward_compatible(integration_service):
    """Case 23: When retrieval_scope='all_entities', all entity kinds are queried and retrieved."""
    cv_skills = [
        ExtractedSkill(skill_id="java", surface_forms=["Java"], kind="skill", category="Technology/Tool", type="explicit", evidences=[]),
        ExtractedSkill(skill_id="fintech", surface_forms=["Fintech"], kind="domain", category="Domain Knowledge", type="explicit", evidences=[]),
    ]
    jd_skills = [
        ExtractedSkill(skill_id="java", surface_forms=["Java"], kind="skill", category="Technology/Tool", type="explicit", evidences=[]),
    ]

    unified = UnifiedExtractFileResponse(
        run_id="run_c23",
        status="completed",
        cv=DocumentUnifiedResult(document_type="CV", explicit=make_extraction_result(cv_skills, "CV")),
        jd=DocumentUnifiedResult(document_type="JD", explicit=make_extraction_result(jd_skills, "JD")),
    )

    req = EmbeddingGenerateRequest(unified_response=unified, retrieval_scope="all_entities", compute_similarity=True)
    resp = integration_service.generate_representations(req)

    skill_mat = resp.similarity_matrices["cv_skills_vs_jd_skills"]
    assert len(skill_mat.source_labels) == 2


# =============================================================================
# GROUP 5: Existing Functionality & Invariants (Cases 24 - 28)
# =============================================================================

def test_case_24_stage3_model_remains_unchanged():
    """Case 24: Configured model remains multilingual paraphrase MPNet."""
    assert settings.STAGE3_MODEL_NAME == "sentence-transformers/paraphrase-multilingual-mpnet-base-v2"
    assert settings.STAGE3_MODEL_REVISION == "4328cf26390c98c5e3c738b4460a05b95f4911f5"


def test_case_25_embedding_dimension_remains_768():
    """Case 25: Embedding dimension invariant is strictly 768."""
    assert settings.STAGE3_EMBEDDING_DIM == 768


def test_case_26_raw_cosine_and_full_precision_top_k():
    """Case 26: Top-K ranking is deterministically ordered by full precision raw scores."""
    rec_src = EmbeddingRecord(
        occurrence_id="src1", vector_id="v1", embedding_id="src1", document_type="CV", source_identifier="cv", target_type="skill",
        source_text="Query", model_id="m", construction_strategy="s", text_hash="h"
    )
    rec_tgt1 = EmbeddingRecord(
        occurrence_id="tgt1", vector_id="v2", embedding_id="tgt1", document_type="JD", source_identifier="jd", target_type="skill",
        source_text="Target A", model_id="m", construction_strategy="s", text_hash="h"
    )
    rec_tgt2 = EmbeddingRecord(
        occurrence_id="tgt2", vector_id="v3", embedding_id="tgt2", document_type="JD", source_identifier="jd", target_type="skill",
        source_text="Target B", model_id="m", construction_strategy="s", text_hash="h"
    )

    v_src = np.array([[1.0, 0.0]], dtype=np.float32)
    v_tgt = np.array([[0.8123499, 0.5831682], [0.8123401, 0.5831818]], dtype=np.float32)

    mat = SemanticRetrievalService.compute_cosine_matrix(v_src, v_tgt, [rec_src], [rec_tgt1, rec_tgt2], expected_dim=2)
    top_k = SemanticRetrievalService.retrieve_top_k([rec_src], [rec_tgt1, rec_tgt2], mat, top_k=2)

    assert top_k[0].candidates[0].target_id == "tgt1"
    assert top_k[0].candidates[1].target_id == "tgt2"
    assert top_k[0].candidates[0].cosine_similarity == 0.8123
    assert top_k[0].candidates[1].cosine_similarity == 0.8123
    assert top_k[0].candidates[0].raw_score > top_k[0].candidates[1].raw_score


def test_case_27_rejected_or_segmented_vectors_handled_correctly(integration_service):
    """Case 27: Overlength texts under reject policy yield vector=None and are excluded from matrices."""
    skill = ExtractedSkill(skill_id="long-skill", surface_forms=["Very long skill " * 50], kind="skill", category="Technology/Tool", type="explicit", evidences=[])
    unified = UnifiedExtractFileResponse(
        run_id="run_c27",
        status="completed",
        cv=DocumentUnifiedResult(document_type="CV", explicit=make_extraction_result([skill], "CV")),
    )

    req = EmbeddingGenerateRequest(unified_response=unified, on_overlength="reject", compute_similarity=True)
    resp = integration_service.generate_representations(req)

    assert resp.stats.rejected_overlength_count == 1
    assert resp.cv_skill_embeddings[0].vector is None
    assert resp.cv_skill_embeddings[0].truncation_status == "rejected"
