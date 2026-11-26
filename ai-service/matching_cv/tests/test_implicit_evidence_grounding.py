"""Unit tests for Conservative Implicit Skill Evidence Grounding (Pre-GNN Phase 2C Fix 3)."""
import pytest

from matching_cv.app.schemas.implicit_skill_extraction import ImplicitEvidence, ImplicitEvidenceSnippet, ImplicitExtractedSkill
from matching_cv.app.services.implicit_evidence_verifier import ImplicitEvidenceVerifier


def test_implicit_evidence_grounding_rejects_unsupported_spatial_queries():
    """
    Example A: CV says candidate designed PostgreSQL schema and GraphQL API.
    Model claims knowledge of spatial queries without spatial/GIS evidence -> MUST be rejected.
    """
    candidate = ImplicitExtractedSkill(
        skill_id="spatial-queries",
        label="Spatial Queries",
        category="Technology/Tool",
        basis="activity",
        evidences=[
            ImplicitEvidence(
                inferred_from_raw="Designed relational database schema in PostgreSQL and built GraphQL APIs for order management.",
                snippets=[
                    ImplicitEvidenceSnippet(text="Designed relational database schema in PostgreSQL and built GraphQL APIs for order management.")
                ],
                reasoning="Candidate worked with PostgreSQL, so they must know spatial queries."
            )
        ]
    )

    accepted, rejected, verifications = ImplicitEvidenceVerifier.verify_candidates([candidate])
    assert len(accepted) == 0
    assert len(rejected) == 1
    assert rejected[0].skill_id == "spatial-queries"
    assert verifications[0].assessment == "insufficient_evidence"
    assert verifications[0].is_accepted is False
    assert "Spatial / Geospatial" in verifications[0].assessment_reason


def test_implicit_evidence_grounding_rejects_unsupported_eventual_consistency():
    """
    Example B: JD mentions booking/pricing and PostgreSQL.
    Model infers Eventual Consistency without distributed consistency evidence -> MUST be rejected.
    """
    candidate = ImplicitExtractedSkill(
        skill_id="eventual-consistency",
        label="Eventual Consistency",
        category="Technical Concept",
        basis="activity",
        evidences=[
            ImplicitEvidence(
                inferred_from_raw="Looking for an engineer to build hotel room booking and dynamic pricing backend using PostgreSQL.",
                snippets=[
                    ImplicitEvidenceSnippet(text="Looking for an engineer to build hotel room booking and dynamic pricing backend using PostgreSQL.")
                ],
                reasoning="Booking systems often deal with concurrent transactions and eventual consistency."
            )
        ]
    )

    accepted, rejected, verifications = ImplicitEvidenceVerifier.verify_candidates([candidate])
    assert len(accepted) == 0
    assert len(rejected) == 1
    assert rejected[0].skill_id == "eventual-consistency"
    assert verifications[0].assessment == "insufficient_evidence"
    assert verifications[0].is_accepted is False
    assert "Distributed Systems Consistency" in verifications[0].assessment_reason


def test_implicit_evidence_grounding_rejects_unsupported_community_management():
    """
    Example C: CV mentions open-source project.
    Model infers community management and issue triage without evidence -> MUST be rejected.
    """
    candidate = ImplicitExtractedSkill(
        skill_id="community-management",
        label="Community Management & Issue Triage",
        category="Engineering Practice",
        basis="activity",
        evidences=[
            ImplicitEvidence(
                inferred_from_raw="Published an open-source TypeScript utility library on GitHub with 200 stars.",
                snippets=[
                    ImplicitEvidenceSnippet(text="Published an open-source TypeScript utility library on GitHub with 200 stars.")
                ],
                reasoning="Having an open source repo implies managing a community and triaging incoming issues."
            )
        ]
    )

    accepted, rejected, verifications = ImplicitEvidenceVerifier.verify_candidates([candidate])
    assert len(accepted) == 0
    assert len(rejected) == 1
    assert rejected[0].skill_id == "community-management"
    assert verifications[0].assessment == "insufficient_evidence"
    assert verifications[0].is_accepted is False


def test_implicit_evidence_grounding_accepts_reasonably_inferred_competency():
    """
    Positive case: CV says candidate designed PostgreSQL schema and built GraphQL APIs.
    Model infers 'Database Schema Design' -> Reasonable technical competency without unevidenced extrapolation.
    """
    candidate = ImplicitExtractedSkill(
        skill_id="database-schema-design",
        label="Database Schema Design",
        category="Technical Concept",
        basis="activity",
        evidences=[
            ImplicitEvidence(
                inferred_from_raw="Designed relational database schema in PostgreSQL and built GraphQL APIs for order management.",
                snippets=[
                    ImplicitEvidenceSnippet(text="Designed relational database schema in PostgreSQL and built GraphQL APIs for order management.")
                ],
                reasoning="Directly evidenced by active relational schema design work."
            )
        ]
    )

    accepted, rejected, verifications = ImplicitEvidenceVerifier.verify_candidates([candidate])
    assert len(accepted) == 1
    assert len(rejected) == 0
    assert accepted[0].skill_id == "database-schema-design"
    assert verifications[0].assessment == "supported"
    assert verifications[0].is_accepted is True
    assert verifications[0].original_evidence.get("evidence_support_policy") in ("directly_supported", "reasonably_inferred")


def test_implicit_evidence_grounding_non_it_domain():
    """
    Non-IT Domain: Clinical healthcare.
    Outpatient clinical care supports 'Patient Consultation', but NOT 'Trauma Resuscitation & Emergency Surgery'.
    """
    cand_positive = ImplicitExtractedSkill(
        skill_id="patient-consultation",
        label="Patient Consultation",
        category="Domain Knowledge",
        basis="activity",
        evidences=[
            ImplicitEvidence(
                inferred_from_raw="Conducted daily outpatient clinical patient consultations and medical history taking.",
                snippets=[
                    ImplicitEvidenceSnippet(text="Conducted daily outpatient clinical patient consultations and medical history taking.")
                ],
                reasoning="General outpatient care directly demonstrates patient consultation."
            )
        ]
    )

    cand_negative = ImplicitExtractedSkill(
        skill_id="trauma-resuscitation",
        label="Trauma Resuscitation & Emergency Surgery",
        category="Domain Knowledge",
        basis="activity",
        evidences=[
            ImplicitEvidence(
                inferred_from_raw="Conducted daily outpatient clinical patient consultations and medical history taking.",
                snippets=[
                    ImplicitEvidenceSnippet(text="Conducted daily outpatient clinical patient consultations and medical history taking.")
                ],
                reasoning="Doctor worked in a clinic, so might handle critical emergency trauma."
            )
        ]
    )

    accepted, rejected, verifications = ImplicitEvidenceVerifier.verify_candidates([cand_positive, cand_negative])
    assert len(accepted) == 1
    assert accepted[0].skill_id == "patient-consultation"
    assert len(rejected) == 1
    assert rejected[0].skill_id == "trauma-resuscitation"
    assert verifications[1].assessment == "insufficient_evidence"
