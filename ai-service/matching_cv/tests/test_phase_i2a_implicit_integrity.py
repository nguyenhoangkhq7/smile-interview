"""
Tests for Phase I2-A Implicit Evidence Integrity & Eligibility Policy.

Validates the canonical verification boundary and agreement between
PaperAlignedGraphBuilder graph topology and StandardizedOutputBuilder public proficiency.
"""

import pytest
import unicodedata
from typing import List

from matching_cv.app.schemas.skill_extraction import ExtractedSkill, ExtractionResult, Evidence
from matching_cv.app.schemas.implicit_skill_extraction import (
    ImplicitEvidence,
    ImplicitExtractedSkill,
    ImplicitExtractionResult,
)
from matching_cv.app.schemas.unified_skill_extraction import (
    DocumentUnifiedResult,
    DocumentValidationResult,
    UnifiedExtractFileResponse,
)
from matching_cv.app.services.implicit_evidence_verifier import ImplicitEvidenceVerifier
from matching_cv.app.services.standardized_output_builder import (
    PublicOutputContext,
    build_proficiency_side,
    build_standardized_output,
)
from matching_cv.research.paper_aligned_gnn.graph_builder import PaperAlignedGraphBuilder
from matching_cv.research.paper_aligned_gnn.schemas import PaperAlignedGraphConfig, SkillInputItem


SAMPLE_CV_TEXT = """
Minh Tran
Backend Software Engineer
SUMMARY
Backend engineer with 4 years of experience building and scaling Java/Spring Boot microservices.
EXPERIENCE
• Designed and rolled out a Kafka-based event pipeline to decouple inventory updates from checkout.
• Wrote integration tests with Testcontainers and raised service test coverage from 46% to 82%.
"""

SAMPLE_JD_TEXT = """
Northbridge Payments
Backend Engineer (Java / Spring Boot)
KEY RESPONSIBILITIES
• Design, build, and maintain RESTful microservices in Java (Spring Boot) that power transaction processing.
• Collaborate with product managers to translate settlement and compliance requirements into technical designs.
REQUIREMENTS
• 2+ years of professional experience with Java and Spring Boot in a production environment.
• Attention to accessibility (WCAG) guidelines.
• Improve accessibility for all payment interfaces.
"""


def test_01_explicit_skills_with_valid_evidence():
    """Explicit skills with valid document evidence are retained."""
    spans, ok, status = ImplicitEvidenceVerifier.verify_implicit_evidence_anchoring(
        ["Backend engineer with 4 years of experience building and scaling Java/Spring Boot microservices."],
        SAMPLE_CV_TEXT
    )
    assert ok is True
    assert status == "VERIFIED_ANCHORED"
    assert len(spans) == 1


def test_02_implicit_skills_with_exact_verbatim_evidence():
    """Implicit skills with exact verbatim evidence sentences are verified."""
    spans, ok, status = ImplicitEvidenceVerifier.verify_implicit_evidence_anchoring(
        ["Designed and rolled out a Kafka-based event pipeline to decouple inventory updates from checkout."],
        SAMPLE_CV_TEXT
    )
    assert ok is True
    assert status == "VERIFIED_ANCHORED"
    assert len(spans) == 1


def test_03_implicit_skills_with_whitespace_normalized_evidence():
    """Implicit skills with irregular spaces and newlines are correctly resolved."""
    irregular_span = "Designed   and  rolled  out a \n Kafka-based event pipeline to decouple inventory updates from checkout."
    spans, ok, status = ImplicitEvidenceVerifier.verify_implicit_evidence_anchoring(
        [irregular_span],
        SAMPLE_CV_TEXT
    )
    assert ok is True
    assert status == "VERIFIED_ANCHORED"
    assert len(spans) == 1
    assert "Designed and rolled out a Kafka-based event pipeline" in spans[0]


def test_04_implicit_skills_with_paraphrased_ellipses_evidence():
    """Implicit skills with ellipses combining disjoint clauses are resolved to grounded sub-clauses."""
    ellipses_span = "Attention to accessibility (WCAG)... Improve accessibility"
    spans, ok, status = ImplicitEvidenceVerifier.verify_implicit_evidence_anchoring(
        [ellipses_span],
        SAMPLE_JD_TEXT
    )
    assert ok is True
    assert status == "VERIFIED_ANCHORED"
    assert len(spans) == 2
    assert "Attention to accessibility (WCAG)" in spans
    assert "Improve accessibility" in spans


def test_05_implicit_skills_without_resolvable_evidence():
    """Implicit skills with pure hallucinated/interpretive rationale are rejected."""
    hallucinated_span = "The candidate has demonstrated profound mastery of distributed consensus algorithms like Raft."
    spans, ok, status = ImplicitEvidenceVerifier.verify_implicit_evidence_anchoring(
        [hallucinated_span],
        SAMPLE_CV_TEXT
    )
    assert ok is False
    assert status == "UNSUPPORTED_NO_ANCHORED_EVIDENCE"
    assert len(spans) == 0


def test_06_high_confidence_implicit_skills_without_evidence():
    """High confidence (e.g. 0.90) alone never substitutes for evidence; empty spans are rejected."""
    spans, ok, status = ImplicitEvidenceVerifier.verify_implicit_evidence_anchoring(
        [],
        SAMPLE_JD_TEXT
    )
    assert ok is False
    assert status == "NO_EVIDENCE_SPANS"
    assert len(spans) == 0


def test_06b_source_text_unavailable_quarantines_implicit_skill():
    """Fail-closed: If source text is missing or empty, implicit skills are strictly quarantined."""
    # When doc_text is None
    spans_none, ok_none, status_none = ImplicitEvidenceVerifier.verify_implicit_evidence_anchoring(
        ["Designed and rolled out a Kafka-based event pipeline"],
        None
    )
    assert ok_none is False
    assert status_none == "SOURCE_TEXT_UNAVAILABLE"
    assert len(spans_none) == 0

    # When doc_text is empty string
    spans_empty, ok_empty, status_empty = ImplicitEvidenceVerifier.verify_implicit_evidence_anchoring(
        ["Designed and rolled out a Kafka-based event pipeline"],
        "   "
    )
    assert ok_empty is False
    assert status_empty == "SOURCE_TEXT_UNAVAILABLE"
    assert len(spans_empty) == 0


def test_06c_empty_and_whitespace_only_evidence_spans():
    """Fail-closed: Empty list or whitespace-only strings return NO_EVIDENCE_SPANS."""
    spans_ws, ok_ws, status_ws = ImplicitEvidenceVerifier.verify_implicit_evidence_anchoring(
        ["   ", "\t\n  "],
        SAMPLE_CV_TEXT
    )
    assert ok_ws is False
    assert status_ws == "NO_EVIDENCE_SPANS"
    assert len(spans_ws) == 0


def test_07_duplicate_evidence_spans():
    """Duplicate evidence spans are cleanly deduplicated."""
    dup_spans = [
        "Collaborate with product managers to translate settlement and compliance requirements into technical designs.",
        "Collaborate with product managers to translate settlement and compliance requirements into technical designs."
    ]
    spans, ok, status = ImplicitEvidenceVerifier.verify_implicit_evidence_anchoring(
        dup_spans,
        SAMPLE_JD_TEXT
    )
    assert ok is True
    assert len(spans) == 1


def test_08_evidence_containing_unicode_punctuation():
    """Evidence containing unicode curly quotes, em-dashes, or non-breaking spaces matches correctly."""
    doc_with_unicode = 'We’re seeking a “rockstar” engineer—proficient with Java\u00a0microservices.'
    span_with_std_punct = "We're seeking a \"rockstar\" engineer-proficient with Java microservices."
    spans, ok, status = ImplicitEvidenceVerifier.verify_implicit_evidence_anchoring(
        [span_with_std_punct],
        doc_with_unicode
    )
    assert ok is True
    assert len(spans) == 1


def test_09_cv_and_jd_evidence_handling():
    """Both CV and JD evidence spans are appropriately handled against their respective documents."""
    cv_spans, cv_ok, _ = ImplicitEvidenceVerifier.verify_implicit_evidence_anchoring(
        ["Wrote integration tests with Testcontainers and raised service test coverage from 46% to 82%."],
        SAMPLE_CV_TEXT
    )
    assert cv_ok is True

    jd_spans, jd_ok, _ = ImplicitEvidenceVerifier.verify_implicit_evidence_anchoring(
        ["Collaborate with product managers to translate settlement and compliance requirements into technical designs."],
        SAMPLE_JD_TEXT
    )
    assert jd_ok is True


def test_10_agreement_between_gnn_graph_membership_and_public_output():
    """
    Guarantees strict agreement between PaperAlignedGraphBuilder and StandardizedOutputBuilder.
    An ungrounded implicit skill ('distributed-system-design') MUST NOT enter the graph topology
    AND MUST NOT enter the public proficiency output.
    """
    # 1. Build DocumentUnifiedResult with 1 explicit and 2 implicit skills
    # - "requirements-translation" (implicit, with verbatim evidence)
    # - "distributed-system-design" (implicit, with empty evidence spans)
    jd_exp = [
        ExtractedSkill(
            skill_id="java",
            skill_name="Java",
            category="Technology/Tool",
            evidence_sentence="2+ years of professional experience with Java",
            evidences=[],
        )
    ]
    jd_imp = [
        ImplicitExtractedSkill(
            skill_id="requirements-translation",
            label="Requirements Translation",
            category="Engineering Practice",
            confidence=0.88,
            evidences=[
                ImplicitEvidence(
                    inferred_from_raw="Collaborate with product managers to translate settlement and compliance requirements into technical designs.",
                    reasoning="Translating compliance requirements",
                )
            ],
        ),
        ImplicitExtractedSkill(
            skill_id="distributed-system-design",
            label="Distributed System Design",
            category="Engineering Practice",
            confidence=0.90,
            evidences=[],
        ),
    ]

    jd_doc = DocumentUnifiedResult.model_construct(
        document_type="JD",
        filename="test_jd.txt",
        text_sha256="test_jd_sha",
        raw_text=SAMPLE_JD_TEXT,
        explicit=ExtractionResult.model_construct(
            document_type="JD", filename="test_jd.txt", text_sha256="test_jd_sha", skills=jd_exp
        ),
        implicit=ImplicitExtractionResult.model_construct(
            document_type="JD", filename="test_jd.txt", text_sha256="test_jd_sha", skills=jd_imp
        ),
        validation=DocumentValidationResult.model_construct(
            status="completed",
            accepted_implicit_skills=jd_imp,
            duplicate_implicit_skills=[],
            rejected_implicit_skills=[],
            evidence_verifications=[],
        ),
    )

    unified = UnifiedExtractFileResponse.model_construct(
        run_id="test_agreement_run",
        status="completed",
        cv=None,
        jd=jd_doc,
        summary=None,
        errors=[],
    )

    builder = PaperAlignedGraphBuilder(PaperAlignedGraphConfig(filter_unsupported_implicit=True))
    graph_data, report = builder.build_graph(unified_response=unified, stage3_response=None)

    # Verify Graph Nodes
    graph_skill_ids = [n.canonical_skill_id for n in graph_data.skill_nodes.values()]
    assert "java" in graph_skill_ids, "Explicit skill 'java' must be in the graph"
    assert "requirements-translation" in graph_skill_ids, "Supported implicit skill must be in the graph"
    assert "distributed-system-design" not in graph_skill_ids, (
        "Unsupported implicit skill 'distributed-system-design' MUST NOT enter the graph"
    )

    # Verify Public Proficiency Output
    lineage = graph_data.diagnostics.get("competency_lineage", [])
    retained_occ = {r["occurrence_id"] for r in lineage if r["retention_decision"] == "RETAINED"}
    retained_canon = {n.canonical_skill_id for n in graph_data.skill_nodes.values()}

    public_skills, dbg = build_proficiency_side(
        doc_result=jd_doc,
        doc_text=SAMPLE_JD_TEXT,
        side="JD",
        run_id="test_agreement_run",
        retained_occurrences=retained_occ,
        retained_canonicals=retained_canon,
    )

    public_skill_ids = [s.skill_id for s in public_skills]
    assert "java" in public_skill_ids, "Explicit skill 'java' must be in public proficiency"
    assert "requirements-translation" in public_skill_ids, "Supported implicit skill must be in public proficiency"
    assert "distributed-system-design" not in public_skill_ids, (
        "Unsupported implicit skill 'distributed-system-design' MUST NOT enter public proficiency"
    )

    # Verify zero implicit skills in public output have empty evidence spans
    for s in public_skills:
        if s.type == "implicit":
            assert len(s.evidence_spans) > 0, (
                f"Implicit skill '{s.skill_id}' in public output has empty evidence spans!"
            )
