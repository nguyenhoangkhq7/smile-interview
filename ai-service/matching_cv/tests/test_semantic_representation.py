"""Unit and integration tests for Stage 3 SBERT Semantic Representation & Retrieval."""
import concurrent.futures
import copy
import hashlib
import json
import numpy as np
import pytest
import torch
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient

from matching_cv.app.core.config import settings
from matching_cv.app.core.model_loader import ModelLoader, model_loader
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
    UnifiedExtractFileResponse,
    UnifiedExtractionSummary,
)
from matching_cv.app.schemas.semantic_representation import (
    EmbeddingGenerateRequest,
    EmbeddingRecord,
    SemanticRepresentationResponse,
    SimilarityMatrix,
)
from matching_cv.app.services.extraction_adapter import (
    AdaptedEvidenceItem,
    AdaptedRequirementItem,
    AdaptedSkillItem,
    ExtractionDataAdapter,
)
from matching_cv.app.services.semantic_embedding_service import SemanticEmbeddingService
from matching_cv.app.services.semantic_retrieval_service import SemanticRetrievalService
from matching_cv.app.services.semantic_representation_service import SemanticRepresentationService


@pytest.fixture
def mock_sbert_model():
    """
    Mock SentenceTransformer model producing deterministic 768-dim L2-normalized vectors
    based on the SHA-256 hash of the input text content.
    """
    model = MagicMock()
    model.max_seq_length = 128

    def mock_encode(texts, batch_size=32, convert_to_tensor=True, normalize_embeddings=True, show_progress_bar=False):
        vectors = []
        for text in texts:
            # Deterministic pseudo-vector seeded by text content hash
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

    # Mock tokenizer
    tokenizer = MagicMock()

    def mock_tokenize_encode(text, add_special_tokens=True, truncation=False):
        words = text.split()
        return list(range(len(words) + (2 if add_special_tokens else 0)))

    def mock_decode(token_ids, skip_special_tokens=True):
        return f"decoded_chunk_{len(token_ids)}"

    tokenizer.encode.side_effect = mock_tokenize_encode
    tokenizer.decode.side_effect = mock_decode
    model.tokenizer = tokenizer

    return model


@pytest.fixture
def mock_embedding_service(mock_sbert_model):
    """Embedding service wired with mock loader and mock model."""
    loader = MagicMock()
    loader.get_model.return_value = mock_sbert_model
    loader.get_tokenizer.return_value = mock_sbert_model.tokenizer
    loader.get_max_seq_length.return_value = 128
    loader.device = "cpu"
    return SemanticEmbeddingService(loader=loader, batch_size=16)


@pytest.fixture
def sample_unified_response() -> UnifiedExtractFileResponse:
    """Fixture producing a realistic UnifiedExtractFileResponse with CV and JD data."""
    shared_cv_sentence = "Built scalable microservices in Java and Spring Boot for payment systems."

    cv_explicit_skills = [
        ExtractedSkill(
            skill_id="java",
            surface_forms=["Java"],
            kind="skill",
            category="Technology/Tool",
            type="explicit",
            confidence=None,
            sections=["experience"],
            evidences=[
                Evidence(
                    surface_form="Java",
                    sentence=shared_cv_sentence,
                    start=0,
                    end=len(shared_cv_sentence),
                    mention_start=32,
                    mention_end=36,
                    section="experience",
                    kind="skill",
                    category="Technology/Tool",
                )
            ],
        ),
        ExtractedSkill(
            skill_id="spring-boot",
            surface_forms=["Spring Boot"],
            kind="skill",
            category="Technology/Tool",
            type="explicit",
            confidence=None,
            sections=["experience"],
            evidences=[
                Evidence(
                    surface_form="Spring Boot",
                    sentence=shared_cv_sentence,
                    start=0,
                    end=len(shared_cv_sentence),
                    mention_start=41,
                    mention_end=52,
                    section="experience",
                    kind="skill",
                    category="Technology/Tool",
                )
            ],
        ),
    ]

    cv_accepted_implicit = [
        ImplicitExtractedSkill(
            skill_id="event-driven-architecture",
            label="Event-Driven Architecture",
            category="Technical Concept",
            basis="activity",
            type="implicit",
            confidence=None,
            evidences=[
                ImplicitEvidence(
                    inferred_from_raw="Migrated synchronous REST APIs to Kafka topics... reducing peak latency",
                    snippets=[
                        ImplicitEvidenceSnippet(
                            text="Migrated synchronous REST APIs to Kafka topics",
                            start=100,
                            end=146,
                            section="experience",
                            verbatim_ok=True,
                        ),
                        ImplicitEvidenceSnippet(
                            text="reducing peak latency",
                            start=150,
                            end=171,
                            section="experience",
                            verbatim_ok=True,
                        ),
                    ],
                    reasoning="Asynchronous messaging implies event-driven patterns.",
                    basis="activity",
                    llm_confidence_raw=0.88,
                )
            ],
        )
    ]

    cv_duplicate_implicit = [
        DuplicateImplicitSkill(
            skill_id="java",
            label="Java Programming",
            category="Technology/Tool",
            matched_explicit_skill_id="java",
            matched_explicit_surface_form="Java",
            duplicate_reason="surface_form_match",
        )
    ]

    jd_explicit_skills = [
        ExtractedSkill(
            skill_id="spring-boot",
            surface_forms=["Spring Boot"],
            kind="skill",
            category="Technology/Tool",
            type="explicit",
            confidence=None,
            sections=["requirements"],
            evidences=[
                Evidence(
                    surface_form="Spring Boot",
                    sentence="Strong experience with Spring Boot microservices is required.",
                    start=0,
                    end=60,
                    mention_start=23,
                    mention_end=34,
                    section="requirements",
                    kind="skill",
                    category="Technology/Tool",
                )
            ],
        ),
        ExtractedSkill(
            skill_id="kafka",
            surface_forms=["Kafka"],
            kind="skill",
            category="Technology/Tool",
            type="explicit",
            confidence=None,
            sections=["requirements"],
            evidences=[
                Evidence(
                    surface_form="Kafka",
                    sentence="Hands-on experience with Kafka or RabbitMQ event streaming.",
                    start=0,
                    end=59,
                    mention_start=25,
                    mention_end=30,
                    section="requirements",
                    kind="skill",
                    category="Technology/Tool",
                )
            ],
        ),
    ]

    return UnifiedExtractFileResponse(
        run_id="test_run_12345678",
        status="completed",
        cv=DocumentUnifiedResult(
            filename="test_cv.pdf",
            document_type="CV",
            text_sha256="abc123sha256cv",
            explicit=ExtractionResult(
                filename="test_cv.pdf",
                document_type="CV",
                stats=ExtractionStats(total_mentions=2, unique_skills=2),
                skills=cv_explicit_skills,
            ),
            implicit=ImplicitExtractionResult(
                filename="test_cv.pdf",
                document_type="CV",
                stats=ImplicitExtractionStats(total_inferences=1, unique_skills=1, multi_fragment_evidences=1),
                skills=cv_accepted_implicit,
            ),
            validation=DocumentValidationResult(
                duplicate_implicit_skills=cv_duplicate_implicit,
                accepted_implicit_skills=cv_accepted_implicit,
            ),
        ),
        jd=DocumentUnifiedResult(
            filename="test_jd.pdf",
            document_type="JD",
            text_sha256="def456sha256jd",
            explicit=ExtractionResult(
                filename="test_jd.pdf",
                document_type="JD",
                stats=ExtractionStats(total_mentions=2, unique_skills=2),
                skills=jd_explicit_skills,
            ),
            implicit=None,
            validation=DocumentValidationResult(
                duplicate_implicit_skills=[],
                accepted_implicit_skills=[],
            ),
        ),
        summary=UnifiedExtractionSummary(
            cv_explicit_count=2,
            cv_implicit_count=1,
            jd_explicit_count=2,
            jd_implicit_count=0,
            duplicate_count=1,
            total_unique_skills=4,
        ),
    )


# -----------------------------------------------------------------------------
# Test Case 1: Mock SBERT Determinism
# -----------------------------------------------------------------------------

def test_mock_sbert_is_deterministic_by_text(mock_sbert_model):
    """Verify mock SBERT yields identical vectors for identical text across batches and permutations."""
    text1 = "Python programming language"
    text2 = "Distributed systems with Kubernetes"

    # Encoded individually
    v1_single = mock_sbert_model.encode([text1], convert_to_tensor=False)[0]
    v2_single = mock_sbert_model.encode([text2], convert_to_tensor=False)[0]

    # Encoded together in batch
    batch_v = mock_sbert_model.encode([text1, text2], convert_to_tensor=False)
    np.testing.assert_allclose(v1_single, batch_v[0], atol=1e-6)
    np.testing.assert_allclose(v2_single, batch_v[1], atol=1e-6)

    # Permuted batch order preserves text-vector correspondence
    permuted_v = mock_sbert_model.encode([text2, text1], convert_to_tensor=False)
    np.testing.assert_allclose(v2_single, permuted_v[0], atol=1e-6)
    np.testing.assert_allclose(v1_single, permuted_v[1], atol=1e-6)

    # Distinct texts produce distinguishable vectors
    cosine_sim = float(np.dot(v1_single, v2_single))
    assert cosine_sim < 0.90


# -----------------------------------------------------------------------------
# Test Cases 2-6: Schema Adaptation & Deduplication Filtering
# -----------------------------------------------------------------------------

def test_explicit_extraction_schema_adaptation(sample_unified_response):
    """Test explicit extraction adaptation preserves display_name, category, kind, and sections."""
    skills, duplicates = ExtractionDataAdapter.extract_active_skills(sample_unified_response.cv)
    exp_skills = [s for s in skills if s.extraction_type == "explicit"]

    assert len(exp_skills) == 2
    java_skill = next(s for s in exp_skills if s.skill_id == "java")
    assert java_skill.display_name == "Java"
    assert java_skill.category == "Technology/Tool"
    assert java_skill.kind == "skill"
    assert java_skill.confidence is None
    assert "experience" in java_skill.sections


def test_implicit_extraction_schema_adaptation(sample_unified_response):
    """Test implicit extraction adaptation preserves label, category, basis, and null confidence."""
    skills, duplicates = ExtractionDataAdapter.extract_active_skills(sample_unified_response.cv)
    imp_skills = [s for s in skills if s.extraction_type == "implicit"]

    assert len(imp_skills) == 1
    eda = imp_skills[0]
    assert eda.skill_id == "event-driven-architecture"
    assert eda.display_name == "Event-Driven Architecture"
    assert eda.category == "Technical Concept"
    assert eda.basis == "activity"
    assert eda.confidence is None
    assert eda.kind is None


def test_accepted_implicit_skill_selection(sample_unified_response):
    """Test only accepted implicit skills are selected into active downstream records."""
    skills, _ = ExtractionDataAdapter.extract_active_skills(sample_unified_response.cv)
    skill_ids = [s.skill_id for s in skills]

    assert "event-driven-architecture" in skill_ids
    assert len(skills) == 3


def test_duplicate_implicit_skill_exclusion(sample_unified_response):
    """Test duplicate implicit skill is strictly excluded from active records."""
    skills, duplicates = ExtractionDataAdapter.extract_active_skills(sample_unified_response.cv)
    active_labels = [s.display_name for s in skills]

    assert "Java Programming" not in active_labels
    assert len(duplicates) == 1
    assert duplicates[0].skill_id == "java"
    assert duplicates[0].label == "Java Programming"


def test_preservation_of_duplicate_audit_data(sample_unified_response):
    """Test original duplicate audit data is preserved in SemanticAudit."""
    retrieval_service = SemanticRetrievalService()
    embedding_service = MagicMock()
    embedding_service.model_name = "test-model"
    embedding_service.revision = "test-rev"
    embedding_service.loader.device = "cpu"
    embedding_service._get_max_seq_length.return_value = 128
    embedding_service.batch_size = 16
    embedding_service.encode_skills.return_value = ([], np.empty((0, 768)))
    embedding_service.encode_evidences.return_value = ([], np.empty((0, 768)))
    embedding_service.encode_requirements.return_value = ([], np.empty((0, 768)))

    service = SemanticRepresentationService(
        embedding_service=embedding_service,
        retrieval_service=retrieval_service,
    )
    req = EmbeddingGenerateRequest(
        unified_response=sample_unified_response,
        compute_similarity=False,
    )
    res = service.generate_representations(req)

    assert len(res.audit.cv_duplicate_implicit_skills) == 1
    dup = res.audit.cv_duplicate_implicit_skills[0]
    assert dup.skill_id == "java"
    assert dup.matched_explicit_skill_id == "java"
    assert res.stats.cv_duplicate_implicit_skills == 1


# -----------------------------------------------------------------------------
# Test Cases 7-10: Evidence Identity & Provenance (FIX 2 & FIX 4)
# -----------------------------------------------------------------------------

def test_multiple_skills_sharing_one_evidence_sentence(sample_unified_response):
    """Test multiple skills sharing one evidence sentence are deduplicated with all associations preserved."""
    evidences = ExtractionDataAdapter.extract_evidence_items(
        sample_unified_response.cv,
        "CV",
        "test_cv.pdf",
    )
    shared_ev = next(
        (ev for ev in evidences if "Built scalable microservices in Java and Spring Boot" in ev.text),
        None,
    )
    assert shared_ev is not None
    assert "java" in shared_ev.associated_skill_ids
    assert "spring-boot" in shared_ev.associated_skill_ids
    assert "Java" in shared_ev.associated_skill_names
    assert "Spring Boot" in shared_ev.associated_skill_names
    assert len(shared_ev.evidences_meta) == 2


def test_repeated_evidence_across_documents_shares_vector_id_but_preserves_occurrence_id(mock_embedding_service):
    """
    FIX 2: Repeated identical evidence across documents reuses vector_id and avoids
    duplicate vector computation, while preserving occurrence-level identity and provenance.
    """
    sentence = "Designed and developed scalable microservice APIs."
    ev_cv = AdaptedEvidenceItem(
        occurrence_id="occ_cv_ev_10_60_abcdef",
        text=sentence,
        document_type="CV",
        source_identifier="cv_candidate.pdf",
        construction_strategy="cv_evidence_sentence",
        extraction_type="explicit",
        section="experience",
        start=10,
        end=60,
        offset_resolved=True,
    )
    ev_jd = AdaptedEvidenceItem(
        occurrence_id="occ_jd_ev_200_250_fedcba",
        text=sentence,
        document_type="JD",
        source_identifier="jd_backend.pdf",
        construction_strategy="jd_evidence_sentence",
        extraction_type="explicit",
        section="requirements",
        start=200,
        end=250,
        offset_resolved=True,
    )

    records, vectors = mock_embedding_service.encode_evidences([ev_cv, ev_jd], include_vectors=True)
    assert len(records) == 2

    # Occurrence identities must be distinct
    assert records[0].occurrence_id == "occ_cv_ev_10_60_abcdef"
    assert records[1].occurrence_id == "occ_jd_ev_200_250_fedcba"
    assert records[0].occurrence_id != records[1].occurrence_id

    # Reusable vector identity must be identical
    assert records[0].vector_id == records[1].vector_id
    assert records[0].text_hash == records[1].text_hash
    assert records[0].vector == records[1].vector

    # Distinct document and offset provenance is preserved
    assert records[0].document_type == "CV"
    assert records[1].document_type == "JD"
    assert records[0].metadata["start"] == 10
    assert records[1].metadata["start"] == 200


def test_evidence_provenance_retention(sample_unified_response, mock_embedding_service):
    """
    FIX 4: Retain section, character offsets, verbatim status, basis, reasoning, and uncalibrated confidence.
    """
    evidences = ExtractionDataAdapter.extract_evidence_items(sample_unified_response.cv, "CV", "test_cv.pdf")
    records, _ = mock_embedding_service.encode_evidences(evidences)

    implicit_rec = next(r for r in records if "Migrated synchronous REST APIs" in r.source_text)
    assert implicit_rec.metadata["section"] == "experience"
    assert implicit_rec.metadata["start"] == 100
    assert implicit_rec.metadata["end"] == 146
    assert implicit_rec.metadata["verbatim_ok"] is True
    assert implicit_rec.metadata["basis"] == "activity"
    assert implicit_rec.metadata["reasoning"] == "Asynchronous messaging implies event-driven patterns."
    assert implicit_rec.metadata["llm_confidence_raw"] == 0.88


# -----------------------------------------------------------------------------
# Test Cases 11-14: Silent Token Truncation Prevention (FIX 1)
# -----------------------------------------------------------------------------

def test_token_truncation_detection_before_inference(mock_embedding_service):
    """FIX 1: Pre-inference sequence length check reliably flags overlength text using model tokenizer."""
    short_text = "Java Spring Boot Microservices"
    long_text = "engineer " * 140  # 140 tokens > max_seq_length 128

    is_trunc_short, cnt_short, max_seq = mock_embedding_service.check_truncation(short_text)
    is_trunc_long, cnt_long, _ = mock_embedding_service.check_truncation(long_text)

    assert is_trunc_short is False
    assert cnt_short < 128
    assert is_trunc_long is True
    assert cnt_long > 128


def test_overlength_policy_error(mock_embedding_service):
    """FIX 1: Policy 'error' raises explicit ValueError on overlength input."""
    overlength_skill = AdaptedSkillItem(
        occurrence_id="occ_skill_long",
        skill_id="big-data",
        display_name="large " * 150,
        extraction_type="explicit",
    )
    with pytest.raises(ValueError, match="exceeds maximum sequence length"):
        mock_embedding_service.encode_skills([overlength_skill], "CV", "doc.pdf", on_overlength="error")


def test_overlength_policy_reject(mock_embedding_service):
    """FIX 1: Policy 'reject' marks record with vector=None, truncation_status='rejected', and avoids inference."""
    overlength_ev = AdaptedEvidenceItem(
        occurrence_id="occ_ev_long",
        text="overlength_token " * 150,
        document_type="CV",
        source_identifier="doc.pdf",
        construction_strategy="cv_evidence_sentence",
        extraction_type="explicit",
    )
    records, vectors = mock_embedding_service.encode_evidences([overlength_ev], on_overlength="reject")

    assert len(records) == 1
    rec = records[0]
    assert rec.is_truncated is True
    assert rec.truncation_status == "rejected"
    assert rec.vector is None
    # No vectors generated for rejected items
    assert vectors.shape[0] == 0


def test_overlength_policy_segment(mock_embedding_service):
    """FIX 1: Policy 'segment' splits text into valid sub-chunks, preserving segment_info."""
    overlength_ev = AdaptedEvidenceItem(
        occurrence_id="occ_ev_parent",
        text="word " * 260,  # ~260 words -> 3 chunks with 126 chunk size
        document_type="CV",
        source_identifier="doc.pdf",
        construction_strategy="cv_evidence_sentence",
        extraction_type="explicit",
    )
    records, vectors = mock_embedding_service.encode_evidences([overlength_ev], on_overlength="segment")

    assert len(records) > 1
    for r in records:
        assert r.is_truncated is True
        assert r.truncation_status == "segmented"
        assert r.segment_info is not None
        assert r.segment_info["parent_id"] == "occ_ev_parent"
        assert r.occurrence_id.startswith("occ_ev_parent_chunk_")
    assert vectors.shape[0] == len(records)


# -----------------------------------------------------------------------------
# Test Cases 15-16: JD Requirements Metadata & Verified Associations (FIX 5)
# -----------------------------------------------------------------------------

def test_jd_requirement_span_preservation_and_skill_isolation(sample_unified_response):
    """
    FIX 5: JD requirements preserve character offsets, associate skills only when verified
    verbatim in the requirement line, and do NOT classify requirements as 'explicit' skills.
    """
    raw_jd_text = (
        "Job Description\n"
        "Requirements:\n"
        "- Strong experience with Spring Boot microservices.\n"
        "- Ability to communicate effectively and collaborate across agile squads."
    )
    reqs, diag = ExtractionDataAdapter.segment_jd_requirements(
        sample_unified_response.jd,
        raw_jd_text=raw_jd_text,
        source_identifier="test_jd.pdf",
    )

    assert len(reqs) == 2
    spring_req = reqs[0]
    comm_req = reqs[1]

    # Offsets preserved
    assert spring_req.start is not None
    assert spring_req.end is not None
    assert spring_req.start < spring_req.end

    # Verified textual association
    assert "spring-boot" in spring_req.associated_skill_ids
    assert "Spring Boot" in spring_req.associated_skill_names

    # Non-technical requirement has NO invented skill association
    assert len(comm_req.associated_skill_ids) == 0


def test_jd_requirement_not_marked_explicit(mock_embedding_service):
    """FIX 5: Requirements encoded as jd_requirement have extraction_type=None, not 'explicit'."""
    req_item = AdaptedRequirementItem(
        occurrence_id="occ_jd_req_0",
        text="Experience with microservices architecture",
        source_identifier="test_jd.pdf",
        section="requirements",
        start=50,
        end=95,
        associated_skill_ids=["spring-boot"],
    )
    records, _ = mock_embedding_service.encode_requirements([req_item])
    assert records[0].extraction_type is None
    assert records[0].target_type == "jd_requirement"


# -----------------------------------------------------------------------------
# Test Cases 17-21: Full-Precision Ranking & Matrix Validation (FIX 3 & FIX 6)
# -----------------------------------------------------------------------------

def test_full_precision_ranking_near_equal_scores_no_collision():
    """
    FIX 3: Candidates with near-equal scores that would collide after 4-decimal rounding
    are deterministically ranked by full-precision scores without false alphabetical tie-breaks.
    """
    # Raw scores: candidate B has 0.85004, candidate A has 0.85001. Both round to 0.8500.
    # If rounded before ranking, candidate A ("Alpha") would beat candidate B ("Beta") alphabetically!
    # With full-precision ranking, candidate B (0.85004) MUST rank first.
    src_record = EmbeddingRecord(
        occurrence_id="occ_src_1",
        vector_id="vec_1",
        embedding_id="occ_src_1",
        document_type="CV",
        source_identifier="cv.pdf",
        target_type="skill",
        source_text="Query Skill",
        model_id="m",
        construction_strategy="s",
        text_hash="h_src",
    )
    cand_a = EmbeddingRecord(
        occurrence_id="occ_tgt_a",
        vector_id="vec_a",
        embedding_id="occ_tgt_a",
        document_type="JD",
        source_identifier="jd.pdf",
        target_type="skill",
        source_text="Alpha Candidate",
        model_id="m",
        construction_strategy="s",
        text_hash="h_a",
    )
    cand_b = EmbeddingRecord(
        occurrence_id="occ_tgt_b",
        vector_id="vec_b",
        embedding_id="occ_tgt_b",
        document_type="JD",
        source_identifier="jd.pdf",
        target_type="skill",
        source_text="Beta Candidate",
        model_id="m",
        construction_strategy="s",
        text_hash="h_b",
    )

    matrix = SimilarityMatrix(
        source_ids=["occ_src_1"],
        target_ids=["occ_tgt_a", "occ_tgt_b"],
        source_labels=["Query Skill"],
        target_labels=["Alpha Candidate", "Beta Candidate"],
        matrix=[[0.8500, 0.8500]],  # Collided 4-decimal rounded presentation
        raw_matrix=[[0.85001, 0.85004]],  # Unrounded full-precision scores
    )

    retrieval = SemanticRetrievalService.retrieve_top_k([src_record], [cand_a, cand_b], matrix, top_k=2)
    cands = retrieval[0].candidates

    # Beta Candidate must be rank 1 due to 0.85004 > 0.85001
    assert cands[0].target_id == "occ_tgt_b"
    assert cands[0].raw_score == 0.85004
    assert cands[0].cosine_similarity == 0.8500
    assert cands[0].rank == 1

    assert cands[1].target_id == "occ_tgt_a"
    assert cands[1].raw_score == 0.85001
    assert cands[1].cosine_similarity == 0.8500
    assert cands[1].rank == 2


def test_matrix_validation_shape_and_dimension_mismatch():
    """FIX 6: Cosine matrix calculation rejects 1D arrays and dimension mismatches."""
    r1 = [EmbeddingRecord(occurrence_id="1", vector_id="1", embedding_id="1", document_type="CV", source_identifier="f", target_type="skill", source_text="t1", model_id="m", construction_strategy="s", text_hash="h")]
    r2 = [EmbeddingRecord(occurrence_id="2", vector_id="2", embedding_id="2", document_type="JD", source_identifier="f", target_type="skill", source_text="t2", model_id="m", construction_strategy="s", text_hash="h")]

    # 1D array
    v_1d = np.array([1.0, 0.0], dtype=np.float32)
    v_2d = np.array([[1.0, 0.0]], dtype=np.float32)
    with pytest.raises(ValueError, match="must be a 2D array"):
        SemanticRetrievalService.compute_cosine_matrix(v_1d, v_2d, r1, r2)

    # Dimension mismatch between source and target
    v_dim2 = np.array([[1.0, 0.0]], dtype=np.float32)
    v_dim3 = np.array([[1.0, 0.0, 0.0]], dtype=np.float32)
    with pytest.raises(ValueError, match="dimension mismatch"):
        SemanticRetrievalService.compute_cosine_matrix(v_dim2, v_dim3, r1, r2)


def test_matrix_validation_nan_inf_and_unnormalized_vectors():
    """FIX 6: Cosine matrix calculation rejects NaN, Inf, zero norm, and non-normalized vectors."""
    r = [EmbeddingRecord(occurrence_id="1", vector_id="1", embedding_id="1", document_type="CV", source_identifier="f", target_type="skill", source_text="t1", model_id="m", construction_strategy="s", text_hash="h")]

    # NaN vector
    v_nan = np.array([[float("nan"), 1.0]], dtype=np.float32)
    v_ok = np.array([[1.0, 0.0]], dtype=np.float32)
    with pytest.raises(ValueError, match="contains non-finite values"):
        SemanticRetrievalService.compute_cosine_matrix(v_nan, v_ok, r, r)

    # Zero norm vector
    v_zero = np.array([[0.0, 0.0]], dtype=np.float32)
    with pytest.raises(ValueError, match="zero or near-zero norm"):
        SemanticRetrievalService.compute_cosine_matrix(v_zero, v_ok, r, r)

    # Non-L2-normalized vector (norm = 5.0)
    v_unnorm = np.array([[3.0, 4.0]], dtype=np.float32)
    with pytest.raises(ValueError, match="not L2-normalized"):
        SemanticRetrievalService.compute_cosine_matrix(v_unnorm, v_ok, r, r)


def test_matrix_validation_empty_inputs_return_cleanly():
    """FIX 6: Clean handling when one or both sides are empty."""
    r = [EmbeddingRecord(occurrence_id="1", vector_id="1", embedding_id="1", document_type="CV", source_identifier="f", target_type="skill", source_text="t1", model_id="m", construction_strategy="s", text_hash="h")]
    v = np.array([[1.0, 0.0]], dtype=np.float32)
    empty_v = np.empty((0, 2), dtype=np.float32)

    # Empty target
    mat = SemanticRetrievalService.compute_cosine_matrix(v, empty_v, r, [])
    assert mat.matrix == [[]]
    assert len(mat.source_ids) == 1
    assert len(mat.target_ids) == 0

    # Both empty
    mat_both = SemanticRetrievalService.compute_cosine_matrix(empty_v, empty_v, [], [])
    assert mat_both.matrix == []
    assert mat_both.source_ids == []


# -----------------------------------------------------------------------------
# Test Cases 22-25: Integration, Revision Pinning & API Endpoints
# -----------------------------------------------------------------------------

def test_pinned_model_revision_metadata():
    """FIX 7: Verify Stage 3 model revision is configured with pinned immutable commit hash."""
    assert settings.STAGE3_MODEL_REVISION == "4328cf26390c98c5e3c738b4460a05b95f4911f5"






# -----------------------------------------------------------------------------
# Test Case 26: Real SBERT Model Integration Test
# -----------------------------------------------------------------------------

@pytest.mark.integration
def test_real_sbert_multilingual_model_integration(sample_unified_response):
    """
    Integration test running the actual paraphrase-multilingual-mpnet-base-v2 model
    at pinned revision 4328cf26390c98c5e3c738b4460a05b95f4911f5 end-to-end.
    """
    model_name = settings.STAGE3_MODEL_NAME
    revision = settings.STAGE3_MODEL_REVISION

    model = model_loader.get_model(model_name, revision=revision)
    assert model is not None
    dim = model_loader.get_model_dimension(model_name, revision=revision)
    assert dim == 768

    embedding_service = SemanticEmbeddingService(loader=model_loader, model_name=model_name, revision=revision)
    retrieval_service = SemanticRetrievalService()
    service = SemanticRepresentationService(embedding_service=embedding_service, retrieval_service=retrieval_service)

    real_jd_text = "Requirements:\n- Senior Java backend engineer with Spring Boot and Kafka experience."
    sample_unified_response.jd.text_sha256 = hashlib.sha256(real_jd_text.encode("utf-8")).hexdigest()

    req = EmbeddingGenerateRequest(
        unified_response=sample_unified_response,
        jd_text=real_jd_text,
        include_vectors=False,
        top_k=3,
        compute_similarity=True,
        on_overlength="reject",
    )

    response = service.generate_representations(req)
    assert response.embedding_dim == 768
    assert response.stats.total_embeddings_generated > 0
    assert response.stats.unique_vectors_encoded > 0
    assert response.similarity_matrices is not None
    assert "cv_skills_vs_jd_skills" in response.similarity_matrices
    skill_mat = response.similarity_matrices["cv_skills_vs_jd_skills"]
    assert len(skill_mat.matrix) > 0
    assert len(skill_mat.matrix[0]) > 0

    # Check top retrieval candidates
    assert response.top_k_retrievals is not None
    top_cands = response.top_k_retrievals["cv_skills_to_jd_skills"]
    assert len(top_cands) > 0
    for query_item in top_cands:
        for cand in query_item.candidates:
            assert cand.raw_score is not None
            assert -1.0 <= cand.raw_score <= 1.0
            assert cand.cosine_similarity == round(cand.raw_score, 4)
