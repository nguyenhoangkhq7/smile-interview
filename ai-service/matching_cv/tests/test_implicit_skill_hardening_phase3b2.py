"""Phase 3B.2 Hardening: Atomic Decomposition, Strategy Overclaim Gating & Adversarial Diagnostics."""
import pytest
from matching_cv.app.schemas.implicit_skill_extraction import (
    ImplicitEvidence,
    ImplicitEvidenceSnippet,
    ImplicitExtractedSkill,
)
from matching_cv.app.schemas.skill_extraction import ExtractedSkill, ExtractionResult, ExtractionStats
from matching_cv.app.services.extraction_adapter import ExtractionDataAdapter
from matching_cv.app.services.implicit_evidence_verifier import ImplicitEvidenceVerifier
from matching_cv.app.schemas.unified_skill_extraction import DocumentUnifiedResult, DocumentValidationResult


def test_issue_a_compound_full_support_deployment_automation_pipeline_optimization():
    """Issue A: 'Deployment Automation & Pipeline Optimization' on Full-Stack CV evidence."""
    cand = ImplicitExtractedSkill(
        skill_id="deploy-auto-pipe-opt",
        label="Deployment Automation & Pipeline Optimization",
        category="Engineering Practice",
        evidences=[
            ImplicitEvidence(
                inferred_from_raw="Set up CI/CD with GitHub Actions and Docker, reducing deployment time from 40 minutes to under 8.",
                snippets=[ImplicitEvidenceSnippet(text="Set up CI/CD with GitHub Actions and Docker, reducing deployment time from 40 minutes to under 8.", start=0, end=98)],
                reasoning="Configuring CI/CD pipelines automates deployment, and reducing deployment time from 40 to 8 minutes optimizes the pipeline.",
            )
        ],
    )

    accepted, rejected, verifications = ImplicitEvidenceVerifier.verify_candidates([cand], document_type="CV")

    assert len(accepted) == 2, f"Expected both components to be accepted, got: {[s.label for s in accepted]}"
    assert accepted[0].skill_id == "deployment-automation"
    assert accepted[0].label == "Deployment Automation"
    assert accepted[0].decomposed_from == "deploy-auto-pipe-opt"
    assert accepted[1].skill_id == "pipeline-optimization"
    assert accepted[1].label == "Pipeline Optimization"
    assert accepted[1].decomposed_from == "deploy-auto-pipe-opt"

    assert len(verifications) == 2
    assert all(v.is_accepted for v in verifications)
    assert all(v.support_status == "supported" for v in verifications)


def test_issue_b_compound_incomplete_retention_data_pipeline_reliability_monitoring():
    """Issue B: 'Data Pipeline Reliability & Monitoring' retains BOTH atomic components."""
    cand = ImplicitExtractedSkill(
        skill_id="data-pipe-rel-mon",
        label="Data Pipeline Reliability & Monitoring",
        category="Engineering Practice",
        evidences=[
            ImplicitEvidence(
                inferred_from_raw="Monitor end-to-end data pipelines and ensure high availability of ETL jobs.",
                snippets=[ImplicitEvidenceSnippet(text="Monitor end-to-end data pipelines and ensure high availability of ETL jobs.", start=0, end=79)],
                reasoning="Monitoring pipelines and ensuring high availability demonstrates pipeline reliability and monitoring.",
            )
        ],
    )

    accepted, rejected, verifications = ImplicitEvidenceVerifier.verify_candidates([cand], document_type="JD")

    assert len(accepted) == 2
    skill_ids = [s.skill_id for s in accepted]
    assert "data-pipeline-reliability" in skill_ids
    assert "monitoring" in skill_ids
    assert all(s.decomposed_from == "data-pipe-rel-mon" for s in accepted)


def test_issue_c_strategy_level_exposure_only_quarantined():
    """Issue C: 'Polyglot Persistence Strategy' with mere MongoDB exposure must be quarantined."""
    cand = ImplicitExtractedSkill(
        skill_id="polyglot-persistence-strategy",
        label="Polyglot Persistence Strategy",
        category="Technical Concept",
        evidences=[
            ImplicitEvidence(
                inferred_from_raw="MongoDB experience alongside relational databases.",
                snippets=[ImplicitEvidenceSnippet(text="MongoDB experience alongside relational databases.", start=0, end=47)],
                reasoning="Mentioning MongoDB and relational DB implies polyglot persistence strategy.",
            )
        ],
    )

    accepted, rejected, verifications = ImplicitEvidenceVerifier.verify_candidates([cand], document_type="JD")

    assert len(accepted) == 0, "Exposure to multiple databases must NOT grant Strategy-level competence"
    assert len(rejected) == 1
    assert verifications[0].support_status == "plausible"
    assert verifications[0].acceptance_decision == "quarantined"
    assert verifications[0].is_accepted is False
    assert "strategy" in verifications[0].assessment_reason.lower()


def test_strategy_level_with_genuine_responsibility_accepted():
    """Strategy competency with direct architectural trade-off responsibility is accepted."""
    cand = ImplicitExtractedSkill(
        skill_id="polyglot-persistence-strategy",
        label="Polyglot Persistence Strategy",
        category="Technical Concept",
        evidences=[
            ImplicitEvidence(
                inferred_from_raw="Evaluated architectural trade-offs between MongoDB and relational databases to design our polyglot persistence strategy.",
                snippets=[ImplicitEvidenceSnippet(text="Evaluated architectural trade-offs between MongoDB and relational databases to design our polyglot persistence strategy.", start=0, end=126)],
                reasoning="Active architectural trade-off evaluation and design substantiates persistence strategy.",
            )
        ],
    )

    accepted, rejected, verifications = ImplicitEvidenceVerifier.verify_candidates([cand], document_type="CV")

    assert len(accepted) == 1
    assert accepted[0].skill_id == "polyglot-persistence-strategy"
    assert verifications[0].is_accepted is True
    assert verifications[0].support_status == "supported"


def test_compound_partial_support_one_accepted_one_rejected():
    """Compound candidate where only one component is supported."""
    cand = ImplicitExtractedSkill(
        skill_id="incident-mgmt-post-mortem",
        label="Incident Management & Post-Mortem Analysis",
        category="Engineering Practice",
        evidences=[
            ImplicitEvidence(
                inferred_from_raw="Primary on-call engineer for tier-1 services, triaged outages and resolved production incidents.",
                snippets=[ImplicitEvidenceSnippet(text="Primary on-call engineer for tier-1 services, triaged outages and resolved production incidents.", start=0, end=97)],
                reasoning="On-call incident handling demonstrates incident management.",
            )
        ],
    )

    accepted, rejected, verifications = ImplicitEvidenceVerifier.verify_candidates([cand], document_type="CV")

    assert len(accepted) == 1
    assert accepted[0].skill_id == "incident-management"
    assert len(verifications) == 2
    # First verification is accepted Incident Management
    assert verifications[0].skill_id == "incident-management"
    assert verifications[0].is_accepted is True
    assert verifications[0].support_status == "supported"
    # Second verification is rejected Post-Mortem Analysis
    assert verifications[1].skill_id == "post-mortem-analysis"
    assert verifications[1].is_accepted is False
    assert verifications[1].support_status == "unsupported"


def test_compound_with_explicit_duplicate_component():
    """When one decomposed component duplicates an explicit skill, only the non-duplicate is accepted."""
    explicit_mock = ExtractionResult(
        skills=[
            ExtractedSkill(
                skill_id="deployment-automation",
                surface_forms=["Deployment Automation"],
                category="Engineering Practice",
            )
        ],
        stats=ExtractionStats(total_mentions=0, unique_skills=1),
    )

    cand = ImplicitExtractedSkill(
        skill_id="deploy-auto-pipe-opt",
        label="Deployment Automation & Pipeline Optimization",
        category="Engineering Practice",
        evidences=[
            ImplicitEvidence(
                inferred_from_raw="Set up CI/CD with GitHub Actions and Docker, reducing deployment time from 40 minutes to under 8.",
                snippets=[ImplicitEvidenceSnippet(text="Set up CI/CD with GitHub Actions and Docker, reducing deployment time from 40 minutes to under 8.", start=0, end=98)],
                reasoning="CI/CD automates deployment and pipeline changes optimize speed.",
            )
        ],
    )

    accepted, rejected, verifications = ImplicitEvidenceVerifier.verify_candidates(
        [cand], explicit_result=explicit_mock, document_type="CV"
    )

    assert len(accepted) == 1
    assert accepted[0].skill_id == "pipeline-optimization"
    assert any(v.skill_id == "deployment-automation" and not v.is_accepted for v in verifications)


def test_downstream_active_skills_adapter_decomposed_contract():
    """Verify ExtractionDataAdapter handles decomposed implicit skills with proper occurrence IDs and metadata."""
    cand = ImplicitExtractedSkill(
        skill_id="deploy-auto-pipe-opt",
        label="Deployment Automation & Pipeline Optimization",
        category="Engineering Practice",
        evidences=[
            ImplicitEvidence(
                inferred_from_raw="Set up CI/CD with GitHub Actions and Docker, reducing deployment time from 40 minutes to under 8.",
                snippets=[ImplicitEvidenceSnippet(text="Set up CI/CD with GitHub Actions and Docker, reducing deployment time from 40 minutes to under 8.", start=0, end=98)],
            )
        ],
    )
    accepted, rejected, verifications = ImplicitEvidenceVerifier.verify_candidates([cand], document_type="CV")

    doc_res = DocumentUnifiedResult(
        filename="03_FullStack_CV.pdf",
        document_type="CV",
        text_sha256="12345678abcdef00",
        raw_text="Set up CI/CD with GitHub Actions and Docker, reducing deployment time from 40 minutes to under 8.",
        explicit=ExtractionResult(skills=[], stats=ExtractionStats(total_mentions=0, unique_skills=0)),
        validation=DocumentValidationResult(
            status="completed",
            accepted_implicit_skills=accepted,
            rejected_implicit_skills=rejected,
            evidence_verifications=verifications,
        ),
    )

    active_res = ExtractionDataAdapter.extract_active_skills(doc_res)
    assert len(active_res.active_skills) == 2
    item1 = active_res.active_skills[0]
    item2 = active_res.active_skills[1]

    assert item1.occurrence_id == "occ_cv_12345678_implicit_deployment-automation_0"
    assert item1.skill_id == "deployment-automation"
    assert item1.display_name == "Deployment Automation"
    assert item1.get_embedding_input()[0] == "Deployment Automation"

    assert item2.occurrence_id == "occ_cv_12345678_implicit_pipeline-optimization_1"
    assert item2.skill_id == "pipeline-optimization"
    assert item2.display_name == "Pipeline Optimization"
    assert item2.get_embedding_input()[0] == "Pipeline Optimization"


def test_adversarial_high_lexical_overlap_unsupported_strategy():
    """Adversarial: mentions 'cloud', 'architecture', 'infrastructure' without strategy responsibility."""
    cand = ImplicitExtractedSkill(
        skill_id="cloud-infrastructure-strategy",
        label="Cloud Infrastructure Strategy",
        category="Technical Concept",
        evidences=[
            ImplicitEvidence(
                inferred_from_raw="Deployed Docker containers to cloud infrastructure on AWS ECS.",
                snippets=[ImplicitEvidenceSnippet(text="Deployed Docker containers to cloud infrastructure on AWS ECS.", start=0, end=62)],
                reasoning="Candidate deployed to cloud, implying cloud infrastructure strategy.",
            )
        ],
    )
    accepted, rejected, verifications = ImplicitEvidenceVerifier.verify_candidates([cand], document_type="CV")
    assert len(accepted) == 0
    assert len(rejected) == 1
    assert verifications[0].is_accepted is False
    assert verifications[0].support_status in ("plausible", "unsupported")


def test_adversarial_low_lexical_overlap_supported_competency():
    """Adversarial: low lexical overlap (paraphrase action) but substantiated competency."""
    cand = ImplicitExtractedSkill(
        skill_id="performance-optimization",
        label="Performance Optimization",
        category="Engineering Practice",
        evidences=[
            ImplicitEvidence(
                inferred_from_raw="Profiled memory allocations and eliminated unnecessary object creation, cutting p99 response times by 35%.",
                snippets=[ImplicitEvidenceSnippet(text="Profiled memory allocations and eliminated unnecessary object creation, cutting p99 response times by 35%.", start=0, end=104)],
                reasoning="Profiling and cutting response times is empirical performance optimization.",
            )
        ],
    )
    accepted, rejected, verifications = ImplicitEvidenceVerifier.verify_candidates([cand], document_type="CV")
    assert len(accepted) == 1
    assert accepted[0].skill_id == "performance-optimization"
    assert verifications[0].is_accepted is True
    assert verifications[0].support_status == "supported"


def test_adversarial_protected_atomic_compound_skills():
    """Protected compound phrases are not split into meaningless sub-components."""
    protected = ["CI/CD", "Infrastructure as Code", "Site Reliability Engineering", "Identity & Access Management"]
    for p in protected:
        decomposed = ImplicitEvidenceVerifier.decompose_compound_label(p)
        assert decomposed is None, f"Atomic phrase '{p}' must not be decomposed"


def test_adversarial_unfamiliar_technical_domain():
    """Unfamiliar technical domain with speculative extrapolation is rejected."""
    cand = ImplicitExtractedSkill(
        skill_id="quantum-algorithm-synthesis",
        label="Quantum Algorithm Synthesis",
        category="Technical Concept",
        evidences=[
            ImplicitEvidence(
                inferred_from_raw="Verified SHA-256 hash checksums of downloaded binary artifacts.",
                snippets=[ImplicitEvidenceSnippet(text="Verified SHA-256 hash checksums of downloaded binary artifacts.", start=0, end=66)],
                reasoning="Hash checking touches cryptography, implying quantum synthesis.",
            )
        ],
    )
    accepted, rejected, verifications = ImplicitEvidenceVerifier.verify_candidates([cand], document_type="CV")
    assert len(accepted) == 0
    assert len(rejected) == 1
    assert verifications[0].is_accepted is False
    assert verifications[0].support_status == "unsupported"


def test_adversarial_jd_implicit_requirement_supported():
    """JD requirement with clear necessary responsibility is accepted without exact lexical match."""
    cand = ImplicitExtractedSkill(
        skill_id="root-cause-analysis",
        label="Root Cause Analysis",
        category="Engineering Practice",
        evidences=[
            ImplicitEvidence(
                inferred_from_raw="Investigate recurring production outages, determine root causes, and implement preventive measures to prevent recurrence.",
                snippets=[ImplicitEvidenceSnippet(text="Investigate recurring production outages, determine root causes, and implement preventive measures to prevent recurrence.", start=0, end=114)],
                reasoning="Determining root causes and preventive actions is necessary root cause analysis.",
            )
        ],
    )
    accepted, rejected, verifications = ImplicitEvidenceVerifier.verify_candidates([cand], document_type="JD")
    assert len(accepted) == 1
    assert accepted[0].skill_id == "root-cause-analysis"
    assert verifications[0].is_accepted is True
    assert verifications[0].support_status == "supported"


def test_adversarial_role_seniority_exaggeration_rejected():
    """Junior task (reviewing one PR) claiming departmental leadership is rejected."""
    cand = ImplicitExtractedSkill(
        skill_id="engineering-department-leadership",
        label="Engineering Department Leadership",
        category="Soft Skill",
        evidences=[
            ImplicitEvidence(
                inferred_from_raw="Assisted onboarding one junior developer by reviewing their first pull request.",
                snippets=[ImplicitEvidenceSnippet(text="Assisted onboarding one junior developer by reviewing their first pull request.", start=0, end=75)],
                reasoning="Reviewing a pull request implies departmental leadership.",
            )
        ],
    )
    accepted, rejected, verifications = ImplicitEvidenceVerifier.verify_candidates([cand], document_type="CV")
    assert len(accepted) == 0
    assert len(rejected) == 1
    assert verifications[0].is_accepted is False
    assert verifications[0].support_status == "unsupported"
