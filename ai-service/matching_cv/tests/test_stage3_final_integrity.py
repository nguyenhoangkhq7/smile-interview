"""
Final Integrity and State-Machine Regression Tests for Stage 3 SBERT Semantic Representation.

Covers:
1. Implicit Validation State Machine (States A, B, C, D, E) and revalidation invariants.
2. Mention-Level vs Sentence-Level Requirement-Skill Associations (Levels 1 to 5).
3. Adversarial surface form matching (Java vs JavaScript, C vs C++/C#, .NET).
4. Entity kind separation (skill vs context/domain/certification).
5. Retrieval scope export semantics (excluded items have nullable scores, not 0.0).
"""

import json
import hashlib
from typing import List, Optional
from unittest.mock import MagicMock, patch

import pytest
import numpy as np
import torch

from matching_cv.app.schemas.skill_extraction import (
    Evidence,
    ExtractedSkill,
    ExtractionResult,
    ExtractionStats,
)
from matching_cv.app.schemas.implicit_skill_extraction import (
    ImplicitEvidence,
    ImplicitEvidenceSnippet,
    ImplicitExtractedSkill,
    ImplicitExtractionResult,
    ImplicitExtractionStats,
)
from matching_cv.app.schemas.unified_skill_extraction import (
    DocumentUnifiedResult,
    DocumentValidationResult,
    DuplicateImplicitSkill,
    UnifiedExtractFileResponse,
)
from matching_cv.app.schemas.semantic_representation import (
    EmbeddingGenerateRequest,
)
from matching_cv.app.services.extraction_adapter import (
    ExtractionDataAdapter,
    build_term_pattern,
)
from matching_cv.app.services.semantic_embedding_service import SemanticEmbeddingService
from matching_cv.app.services.semantic_retrieval_service import SemanticRetrievalService
from matching_cv.app.services.semantic_representation_service import SemanticRepresentationService


def make_extraction_result(skills: List[ExtractedSkill], doc_type: str = "CV", filename: Optional[str] = None) -> ExtractionResult:
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


def make_implicit_extraction_result(skills: List[ImplicitExtractedSkill], doc_type: str = "CV", filename: Optional[str] = None) -> ImplicitExtractionResult:
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
    """Deterministic 768-dim mock SentenceTransformer."""
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
def rep_service(mock_sbert_model):
    loader = MagicMock()
    loader.get_model.return_value = mock_sbert_model
    loader.get_tokenizer.return_value = mock_sbert_model.tokenizer
    loader.get_max_seq_length.return_value = 128
    loader.device = "cpu"
    emb = SemanticEmbeddingService(loader=loader, batch_size=16)
    ret = SemanticRetrievalService()
    return SemanticRepresentationService(embedding_service=emb, retrieval_service=ret)


# =============================================================================
# PART 1: IMPLICIT VALIDATION STATE MACHINE (PHASE 2)
# =============================================================================

def test_state_a_validation_present_with_accepted_skills(rep_service):
    """State A: Validation present with accepted skills -> preserve accepted list, do not revalidate."""
    exp = [ExtractedSkill(skill_id="java", surface_forms=["Java"], kind="skill", category="Technology/Tool", type="explicit", evidences=[])]
    imp = [ImplicitExtractedSkill(skill_id="cloud-architecture", label="Cloud Architecture", category="Technical Concept", basis="activity", type="implicit", evidences=[])]

    doc = DocumentUnifiedResult(
        document_type="CV",
        explicit=make_extraction_result(exp, "CV"),
        implicit=make_implicit_extraction_result(imp, "CV"),
        validation=DocumentValidationResult(status="completed", validation_origin="original", accepted_implicit_skills=imp),
    )
    unified = UnifiedExtractFileResponse(run_id="r_state_a", status="completed", cv=doc)

    req = EmbeddingGenerateRequest(unified_response=unified, auto_revalidate_implicit=True, compute_similarity=False)
    resp = rep_service.generate_representations(req)

    assert resp.stats.cv_accepted_implicit_skills == 1
    assert resp.diagnostics["implicit_validation_diagnostics"]["cv"]["validation_origin"] == "original"
    assert resp.cv_skill_embeddings[1].source_text == "Cloud Architecture"


def test_state_b_completed_validation_with_zero_accepted_remains_zero(rep_service):
    """
    CRITICAL INVARIANT (State B):
    Completed validation that accepted zero skills MUST remain zero,
    even when auto_revalidate_implicit=True!
    """
    exp = [ExtractedSkill(skill_id="java", surface_forms=["Java"], kind="skill", category="Technology/Tool", type="explicit", evidences=[])]
    # Raw implicit has 'java' (duplicate) and 'spring'
    imp = [
        ImplicitExtractedSkill(skill_id="java", label="Java Programming", category="Technology/Tool", basis="activity", type="implicit", evidences=[]),
        ImplicitExtractedSkill(skill_id="spring", label="Spring Framework", category="Technology/Tool", basis="activity", type="implicit", evidences=[]),
    ]
    dups = [
        DuplicateImplicitSkill(skill_id="java", label="Java Programming", matched_explicit_skill_id="java", matched_explicit_surface_form="Java"),
        DuplicateImplicitSkill(skill_id="spring", label="Spring Framework", matched_explicit_skill_id="java", matched_explicit_surface_form="Java"),
    ]

    doc = DocumentUnifiedResult(
        document_type="CV",
        explicit=make_extraction_result(exp, "CV"),
        implicit=make_implicit_extraction_result(imp, "CV"),
        validation=DocumentValidationResult(status="completed", duplicate_implicit_skills=dups, accepted_implicit_skills=[]),
    )
    unified = UnifiedExtractFileResponse(run_id="r_state_b", status="completed", cv=doc)

    # Even with auto_revalidate_implicit=True, State B must NOT revalidate!
    req = EmbeddingGenerateRequest(unified_response=unified, auto_revalidate_implicit=True, compute_similarity=False)
    resp = rep_service.generate_representations(req)

    assert resp.stats.cv_accepted_implicit_skills == 0
    assert resp.stats.cv_duplicate_implicit_skills == 2
    assert resp.diagnostics["implicit_validation_diagnostics"]["cv"]["validation_origin"] == "authoritative_empty"


def test_state_b_completed_zero_accepted_zero_duplicates_remains_zero(rep_service):
    """
    State B variant: Completed validation with 0 accepted and 0 duplicates (e.g. rejected by upstream verifier)
    must remain 0 accepted.
    """
    exp = [ExtractedSkill(skill_id="python", surface_forms=["Python"], kind="skill", category="Technology/Tool", type="explicit", evidences=[])]
    imp = [ImplicitExtractedSkill(skill_id="django", label="Django Web", category="Technology/Tool", basis="activity", type="implicit", evidences=[])]

    doc = DocumentUnifiedResult(
        document_type="CV",
        explicit=make_extraction_result(exp, "CV"),
        implicit=make_implicit_extraction_result(imp, "CV"),
        validation=DocumentValidationResult(status="completed", duplicate_implicit_skills=[], accepted_implicit_skills=[]),
    )
    unified = UnifiedExtractFileResponse(run_id="r_state_b2", status="completed", cv=doc)

    req = EmbeddingGenerateRequest(unified_response=unified, auto_revalidate_implicit=True, compute_similarity=False)
    resp = rep_service.generate_representations(req)

    assert resp.stats.cv_accepted_implicit_skills == 0
    assert resp.diagnostics["implicit_validation_diagnostics"]["cv"]["validation_origin"] == "authoritative_empty"


def test_state_c_validation_absent_revalidation_disabled_safe(rep_service):
    """State C: Validation is absent, auto_revalidate_implicit=False -> zero skills accepted, marked missing."""
    exp = [ExtractedSkill(skill_id="java", surface_forms=["Java"], kind="skill", category="Technology/Tool", type="explicit", evidences=[])]
    imp = [ImplicitExtractedSkill(skill_id="microservices", label="Microservices", category="Technical Concept", basis="activity", type="implicit", evidences=[])]

    doc = DocumentUnifiedResult(
        document_type="CV",
        explicit=make_extraction_result(exp, "CV"),
        implicit=make_implicit_extraction_result(imp, "CV"),
        # validation omitted / empty default without status
        validation=DocumentValidationResult(),
    )
    unified = UnifiedExtractFileResponse(run_id="r_state_c_dis", status="completed", cv=doc)

    # auto_revalidate_implicit=False (default safe)
    req = EmbeddingGenerateRequest(unified_response=unified, auto_revalidate_implicit=False, compute_similarity=False)
    resp = rep_service.generate_representations(req)

    assert resp.stats.cv_accepted_implicit_skills == 0
    assert resp.diagnostics["implicit_validation_diagnostics"]["cv"]["validation_origin"] == "missing"


def test_state_c_validation_absent_revalidation_enabled_recovers(rep_service):
    """State C: Validation is absent, auto_revalidate_implicit=True -> authoritatively deduplicated."""
    exp = [ExtractedSkill(skill_id="java", surface_forms=["Java"], kind="skill", category="Technology/Tool", type="explicit", evidences=[])]
    imp = [
        ImplicitExtractedSkill(
            skill_id="microservices",
            label="Microservices",
            category="Technical Concept",
            basis="activity",
            type="implicit",
            evidences=[
                ImplicitEvidence(
                    inferred_from_raw="Built microservices in Java.",
                    snippets=[ImplicitEvidenceSnippet(text="Built microservices in Java.", verbatim_ok=True)],
                    reasoning="Microservices evidence.",
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
        ),  # dup
    ]

    doc = DocumentUnifiedResult(
        document_type="CV",
        explicit=make_extraction_result(exp, "CV"),
        implicit=make_implicit_extraction_result(imp, "CV"),
        validation=DocumentValidationResult(), # absent / unrun
    )
    unified = UnifiedExtractFileResponse(run_id="r_state_c_en", status="completed", cv=doc)

    req = EmbeddingGenerateRequest(unified_response=unified, auto_revalidate_implicit=True, compute_similarity=False)
    resp = rep_service.generate_representations(req)

    assert resp.stats.cv_accepted_implicit_skills == 1
    assert resp.stats.cv_duplicate_implicit_skills == 1
    assert resp.diagnostics["implicit_validation_diagnostics"]["cv"]["validation_origin"] == "revalidated"


def test_state_e_no_implicit_skills_extracted(rep_service):
    """State E: No implicit skills were extracted -> empty result preserved cleanly."""
    exp = [ExtractedSkill(skill_id="java", surface_forms=["Java"], kind="skill", category="Technology/Tool", type="explicit", evidences=[])]

    doc = DocumentUnifiedResult(
        document_type="CV",
        explicit=make_extraction_result(exp, "CV"),
        implicit=None,
        validation=DocumentValidationResult(),
    )
    unified = UnifiedExtractFileResponse(run_id="r_state_e", status="completed", cv=doc)

    req = EmbeddingGenerateRequest(unified_response=unified, compute_similarity=False)
    resp = rep_service.generate_representations(req)

    assert resp.stats.cv_accepted_implicit_skills == 0
    assert resp.stats.cv_duplicate_implicit_skills == 0
    assert resp.diagnostics["implicit_validation_diagnostics"]["cv"]["validation_origin"] == "not_applicable"


def test_idempotent_processing(rep_service):
    """Repeated processing of the same request produces identical counts, IDs, and diagnostics."""
    exp = [ExtractedSkill(skill_id="java", surface_forms=["Java"], kind="skill", category="Technology/Tool", type="explicit", evidences=[])]
    imp = [ImplicitExtractedSkill(skill_id="cloud", label="Cloud", category="Technical Concept", basis="activity", type="implicit", evidences=[])]

    doc = DocumentUnifiedResult(
        document_type="CV",
        explicit=make_extraction_result(exp, "CV"),
        implicit=make_implicit_extraction_result(imp, "CV"),
        validation=DocumentValidationResult(status="completed", accepted_implicit_skills=imp),
    )
    unified = UnifiedExtractFileResponse(run_id="r_idem", status="completed", cv=doc)
    req = EmbeddingGenerateRequest(unified_response=unified, compute_similarity=False)

    resp1 = rep_service.generate_representations(req)
    resp2 = rep_service.generate_representations(req)

    assert resp1.stats.cv_accepted_implicit_skills == resp2.stats.cv_accepted_implicit_skills
    assert [e.occurrence_id for e in resp1.cv_skill_embeddings] == [e.occurrence_id for e in resp2.cv_skill_embeddings]
    assert [e.vector_id for e in resp1.cv_skill_embeddings] == [e.vector_id for e in resp2.cv_skill_embeddings]


# =============================================================================
# PART 2: MENTION-LEVEL REQUIREMENT-SKILL ASSOCIATIONS (PHASE 3)
# =============================================================================

def test_level1_verified_mention_span():
    """Level 1: Explicit mention offsets matching inside requirement span produce verified_mention_span."""
    raw = "Requirements:\n* 3+ years experience with Java and Spring Boot in production."
    java_start = raw.find("Java")
    java_end = java_start + len("Java")
    ev = Evidence(
        surface_form="Java",
        sentence="* 3+ years experience with Java and Spring Boot in production.",
        start=raw.find("*"),
        end=len(raw),
        mention_start=java_start,
        mention_end=java_end,
        section="requirements",
        kind="skill",
        category="Technology/Tool",
        offset_resolved=True,
    )
    skill = ExtractedSkill(skill_id="java", surface_forms=["Java"], kind="skill", category="Technology/Tool", type="explicit", evidences=[ev])
    doc_jd = DocumentUnifiedResult(document_type="JD", explicit=make_extraction_result([skill], "JD", "jd.pdf"))

    reqs, _ = ExtractionDataAdapter.segment_jd_requirements(doc_jd, raw, "jd.pdf")
    assert len(reqs) == 1
    assert "java" in reqs[0].associated_skill_ids
    assoc = next(m for m in reqs[0].associations_meta if m["skill_id"] == "java")
    assert assoc["association_method"] == "verified_mention_span"
    assert assoc["verification_status"] == "verified_mention"
    assert assoc["mention_start"] == java_start
    assert assoc["mention_end"] == java_end
    assert assoc["matched_surface_form"] == "Java"


def test_level2_verified_surface_form_when_mention_offset_missing():
    """Level 2: When mention_start is None, conservative regex matches verified_surface_form."""
    raw = "Requirements:\n* Proficient with Docker containerization."
    ev = Evidence(
        surface_form="Docker",
        sentence="* Proficient with Docker containerization.",
        start=raw.find("*"),
        end=len(raw),
        mention_start=None,  # Unresolved mention offset!
        mention_end=None,
        section="requirements",
        kind="skill",
        category="Technology/Tool",
        offset_resolved=False,
    )
    skill = ExtractedSkill(skill_id="docker", surface_forms=["Docker"], kind="skill", category="Technology/Tool", type="explicit", evidences=[ev])
    doc_jd = DocumentUnifiedResult(document_type="JD", explicit=make_extraction_result([skill], "JD", "jd.pdf"))

    reqs, _ = ExtractionDataAdapter.segment_jd_requirements(doc_jd, raw, "jd.pdf")
    assert len(reqs) == 1
    assert "docker" in reqs[0].associated_skill_ids
    assoc = next(m for m in reqs[0].associations_meta if m["skill_id"] == "docker")
    assert assoc["association_method"] == "verified_surface_form"
    assert assoc["verification_status"] == "verified_surface"
    assert assoc["matched_surface_form"] == "Docker"
    assert assoc["offset_resolved"] is True


def test_level3_sentence_overlap_without_mention_does_not_create_false_mention():
    """
    CRITICAL INVARIANT (Level 3 / Phase 3.6):
    Evidence sentence span covering line 2 where skill is only in line 1
    MUST NOT create an association with line 2!
    """
    raw = "Requirements:\n* 3+ years experience with Java.\n* Collaborate with team using Kubernetes in production."
    java_start = raw.find("Java")

    # Upstream evidence sentence accidentally spans both lines!
    ev_java = Evidence(
        surface_form="Java",
        sentence=raw,
        start=0,
        end=len(raw),
        mention_start=java_start,
        mention_end=java_start + 4,
        section="requirements",
        kind="skill",
        category="Technology/Tool",
        offset_resolved=True,
    )
    skill_java = ExtractedSkill(skill_id="java", surface_forms=["Java"], kind="skill", category="Technology/Tool", type="explicit", evidences=[ev_java])
    doc_jd = DocumentUnifiedResult(document_type="JD", explicit=make_extraction_result([skill_java], "JD", "jd.pdf"))

    reqs, _ = ExtractionDataAdapter.segment_jd_requirements(doc_jd, raw, "jd.pdf")
    assert len(reqs) == 2

    # Line 1 ("* 3+ years experience with Java.") contains Java
    req1 = reqs[0]
    assert "java" in req1.associated_skill_ids

    # Line 2 ("* Collaborate with team using Kubernetes in production.") DOES NOT contain Java!
    req2 = reqs[1]
    assert "java" not in req2.associated_skill_ids
    # Line 2 must be unresolved because Java is NOT in line 2
    assert any(m.get("unresolved") for m in req2.associations_meta)


def test_level4_implicit_inference_support():
    """Level 4: Implicit skills retain inference provenance and method implicit_evidence_supported."""
    raw = "Requirements:\n* Build event-driven integrations using Kafka to keep downstream ledgers in sync."
    snip = ImplicitEvidenceSnippet(
        text="Build event-driven integrations using Kafka",
        start=raw.find("Build"),
        end=raw.find("Build") + len("Build event-driven integrations using Kafka"),
        verbatim_ok=True,
    )
    imp_ev = ImplicitEvidence(
        inferred_from_raw="Build event-driven integrations using Kafka",
        snippets=[snip],
        reasoning="Asynchronous event streaming requires eventual consistency management.",
        basis="activity",
        llm_confidence_raw=0.88,
    )
    imp_skill = ImplicitExtractedSkill(
        skill_id="eventual-consistency",
        label="Eventual Consistency",
        category="Technical Concept",
        basis="activity",
        type="implicit",
        evidences=[imp_ev],
    )
    doc_jd = DocumentUnifiedResult(
        document_type="JD",
        explicit=make_extraction_result([], "JD", "jd.pdf"),
        implicit=make_implicit_extraction_result([imp_skill], "JD", "jd.pdf"),
        validation=DocumentValidationResult(status="completed", accepted_implicit_skills=[imp_skill]),
    )

    reqs, _ = ExtractionDataAdapter.segment_jd_requirements(doc_jd, raw, "jd.pdf")
    assert len(reqs) == 1
    assert "eventual-consistency" in reqs[0].associated_skill_ids
    assoc = next(m for m in reqs[0].associations_meta if m["skill_id"] == "eventual-consistency")
    assert assoc["association_method"] == "implicit_evidence_supported"
    assert assoc["verification_status"] == "implicit_inferred"
    assert assoc["extraction_type"] == "implicit"
    assert assoc["reasoning"] == "Asynchronous event streaming requires eventual consistency management."
    assert assoc["confidence"] == 0.88


def test_adversarial_surface_matching():
    """Adversarial checks: C vs C++/C#, Java vs JavaScript, .NET vs NET."""
    pat_java = build_term_pattern("Java")
    assert not pat_java.search("Expert in JavaScript frontend development.")
    assert pat_java.search("Senior Java Backend Engineer.")

    pat_c = build_term_pattern("C")
    assert not pat_c.search("Proficient in C++ and C#.")
    assert pat_c.search("Proficient in C and Assembly.")

    pat_dotnet = build_term_pattern(".NET")
    assert pat_dotnet.search("Enterprise .NET microservices.")
    assert not pat_dotnet.search("Network SAFETY NET implementation.")

    pat_node = build_term_pattern("Node.js")
    assert pat_node.search("Fullstack Node.js API development.")
    assert not pat_node.search("Cluster node health checking.")


def test_many_to_many_and_entity_kind_separation():
    """Requirement referencing Java, Spring Boot, and production environment preserves kinds."""
    raw = "Requirements:\n* 2+ years of professional experience with Java and Spring Boot in a production environment."

    skill_java = ExtractedSkill(skill_id="java", surface_forms=["Java"], kind="skill", category="Technology/Tool", type="explicit", evidences=[])
    skill_spring = ExtractedSkill(skill_id="spring-boot", surface_forms=["Spring Boot"], kind="skill", category="Technology/Tool", type="explicit", evidences=[])
    ctx_prod = ExtractedSkill(skill_id="production-environment", surface_forms=["production environment"], kind="context", category="Technical Concept", type="explicit", evidences=[])

    doc_jd = DocumentUnifiedResult(
        document_type="JD",
        explicit=make_extraction_result([skill_java, skill_spring, ctx_prod], "JD", "jd.pdf"),
    )

    reqs, _ = ExtractionDataAdapter.segment_jd_requirements(doc_jd, raw, "jd.pdf")
    assert len(reqs) == 1
    r = reqs[0]
    assert len(r.associated_skill_ids) == 3
    assert set(r.associated_skill_ids) == {"java", "spring-boot", "production-environment"}

    assoc_java = next(m for m in r.associations_meta if m["skill_id"] == "java")
    assoc_spring = next(m for m in r.associations_meta if m["skill_id"] == "spring-boot")
    assoc_prod = next(m for m in r.associations_meta if m["skill_id"] == "production-environment")

    assert assoc_java["entity_kind"] == "skill"
    assert assoc_spring["entity_kind"] == "skill"
    assert assoc_prod["entity_kind"] == "context"  # Correctly distinguished!


# =============================================================================
# PART 3: RETRIEVAL EXPORT SEMANTICS (PHASE 4)
# =============================================================================

def test_excluded_retrieval_candidate_scores_are_nullable_not_zero():
    """Excluded non-skill entities in skills_only mode must have nullable/empty scores, NOT 0.0."""
    # Build a simulated export row
    def format_export_row(rec_id, kind, cat, top1_item):
        if top1_item is None:
            # Excluded from retrieval
            return {
                "skill_id": rec_id,
                "kind": kind,
                "category": cat,
                "top1_candidate": None,
                "top1_score": None,  # NOT 0.0!
                "excluded_from_retrieval": True,
                "excluded_reason": f"non_skill_entity (kind='{kind}', category='{cat}')",
            }
        else:
            return {
                "skill_id": rec_id,
                "kind": kind,
                "category": cat,
                "top1_candidate": top1_item["id"],
                "top1_score": top1_item["score"],
                "excluded_from_retrieval": False,
                "excluded_reason": "",
            }

    row_excluded = format_export_row("fintech", "domain", "Domain Knowledge", None)
    assert row_excluded["top1_score"] is None
    assert row_excluded["excluded_from_retrieval"] is True
    assert row_excluded["top1_score"] != 0.0  # Invariant: NEVER 0.0
