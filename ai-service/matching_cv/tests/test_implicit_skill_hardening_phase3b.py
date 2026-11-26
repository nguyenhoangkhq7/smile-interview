"""Unit and regression tests for Phase 3B Evidence-Grounded Implicit Skill Hardening."""
import json
import pytest

from matching_cv.app.schemas.implicit_skill_extraction import ImplicitEvidence, ImplicitEvidenceSnippet, ImplicitExtractedSkill
from matching_cv.app.schemas.skill_extraction import ExtractedSkill, ExtractionResult, ExtractionStats
from matching_cv.app.services.implicit_evidence_verifier import ImplicitEvidenceVerifier
from matching_cv.app.services.skill_postprocessor import skill_postprocessor


@pytest.fixture
def regression_cases():
    with open("docs/verification/phase3b/regression_cases.json", "r", encoding="utf-8") as f:
        data = json.load(f)
    return data["cases"]


def test_regression_cases_matrix(regression_cases):
    """Execute all 15 regression cases and verify exact expected dispositions."""
    for case in regression_cases:
        cid = case["case_id"]
        doc_type = case["document_type"]
        cand = ImplicitExtractedSkill(
            skill_id=skill_postprocessor.slugify_skill(case["candidate_label"]),
            label=case["candidate_label"],
            category="Engineering Practice",
            basis="activity",
            evidences=[
                ImplicitEvidence(
                    inferred_from_raw=case["source_evidence"],
                    snippets=[ImplicitEvidenceSnippet(text=case["source_evidence"])],
                    reasoning=case["inference_rationale"],
                    llm_confidence_raw=0.85,
                )
            ],
        )

        accepted, rejected, verifications = ImplicitEvidenceVerifier.verify_candidates(
            [cand], explicit_result=None, document_type=doc_type
        )

        assert len(verifications) == 1, f"[{cid}] Expected 1 verification record"
        v = verifications[0]

        # Verify acceptance status
        assert v.is_accepted == case["expected_is_accepted"], (
            f"[{cid}] Expected is_accepted={case['expected_is_accepted']}, got {v.is_accepted}. Reason: {v.assessment_reason}"
        )
        if case["expected_is_accepted"]:
            assert len(accepted) == 1, f"[{cid}] Expected candidate to be accepted"
            assert len(rejected) == 0, f"[{cid}] Expected rejected list to be empty"
        else:
            assert len(accepted) == 0, f"[{cid}] Expected candidate to be rejected/quarantined"
            assert len(rejected) == 1, f"[{cid}] Expected candidate in rejected list"

        # Verify support status
        if case.get("expected_support_status"):
            assert v.support_status == case["expected_support_status"] or v.assessment == case["expected_support_status"], (
                f"[{cid}] Expected status {case['expected_support_status']}, got support_status={v.support_status}, assessment={v.assessment}"
            )

        # Verify acceptance decision
        if case.get("expected_acceptance_decision"):
            assert v.acceptance_decision == case["expected_acceptance_decision"], (
                f"[{cid}] Expected decision {case['expected_acceptance_decision']}, got {v.acceptance_decision}"
            )

        # Verify explanatory reason
        assert case["expected_reason_substr"].lower() in v.assessment_reason.lower(), (
            f"[{cid}] Expected '{case['expected_reason_substr']}' in '{v.assessment_reason}'"
        )


def test_compound_skill_decomposition_partial_support():
    """
    Test compound candidate: 'Incident Management & Post-Mortem Analysis'.
    Evidence supports Incident Management (on-call, outage triage), but NOT Post-Mortem Analysis.
    Should safely decompose: accept 'Incident Management', reject 'Post-Mortem Analysis'.
    """
    cand = ImplicitExtractedSkill(
        skill_id="incident-mgmt-post-mortem",
        label="Incident Management & Post-Mortem Analysis",
        category="Engineering Practice",
        basis="activity",
        evidences=[
            ImplicitEvidence(
                inferred_from_raw="Primary on-call engineer for tier-1 services, triaged outages and resolved production incidents.",
                snippets=[ImplicitEvidenceSnippet(text="Primary on-call engineer for tier-1 services, triaged outages and resolved production incidents.")],
                reasoning="Candidate resolved incidents and conducted incident management.",
                llm_confidence_raw=0.88,
            )
        ],
    )

    accepted, rejected, verifications = ImplicitEvidenceVerifier.verify_candidates([cand], document_type="CV")

    assert len(accepted) == 1
    assert len(rejected) == 0
    assert accepted[0].label == "Incident Management"
    assert accepted[0].skill_id == "incident-management"

    v = verifications[0]
    assert v.is_accepted is True
    assert v.proposed_label == "Incident Management"
    assert v.support_status == "supported"
    assert "decomposed" in v.assessment_reason.lower()
    assert "Post-Mortem Analysis" in str(v.original_evidence.get("decomposed_unsupported_parts"))


def test_protected_atomic_compound_skills_not_decomposed():
    """Verify established atomic phrases containing '&' or '/' are NEVER decomposed."""
    protected_labels = [
        "CI/CD",
        "Infrastructure as Code",
        "Site Reliability Engineering",
        "Identity & Access Management",
        "Search & Discovery",
    ]
    for label in protected_labels:
        decomposed = ImplicitEvidenceVerifier.decompose_compound_label(label)
        assert decomposed is None, f"Protected atomic skill '{label}' must not be decomposed"


def test_explicit_redundancy_variant_gating():
    """
    Phase 5: If candidate is a superficial variant of an explicit skill (e.g. 'Terraform proficiency'
    when 'Terraform' is explicit), it must be rejected as redundant.
    """
    explicit_mock = ExtractionResult(
        skills=[
            ExtractedSkill(
                skill_id="terraform",
                canonical_name="Terraform",
                surface_forms=["Terraform", "terraform"],
                category="Technology/Tool",
            )
        ],
        stats=ExtractionStats(total_mentions=0, unique_skills=1),
    )

    cand = ImplicitExtractedSkill(
        skill_id="terraform-proficiency",
        label="Terraform proficiency",
        category="Engineering Practice",
        basis="activity",
        evidences=[
            ImplicitEvidence(
                inferred_from_raw="Used Terraform to manage cloud infrastructure modules.",
                snippets=[ImplicitEvidenceSnippet(text="Used Terraform to manage cloud infrastructure modules.")],
                reasoning="Worked with Terraform, indicating Terraform proficiency.",
            )
        ],
    )

    accepted, rejected, verifications = ImplicitEvidenceVerifier.verify_candidates(
        [cand], explicit_result=explicit_mock, document_type="CV"
    )

    assert len(accepted) == 0
    assert len(rejected) == 1
    assert verifications[0].is_accepted is False
    assert verifications[0].support_status == "unsupported"
    assert "superficial variant" in verifications[0].assessment_reason.lower()


def test_distinct_implicit_competency_preserved_alongside_explicit():
    """
    Phase 5: Legitimate distinct competencies (e.g. 'Infrastructure Provisioning Automation'
    when 'Terraform' is explicit) must be preserved and accepted.
    """
    explicit_mock = ExtractionResult(
        skills=[
            ExtractedSkill(
                skill_id="terraform",
                canonical_name="Terraform",
                surface_forms=["Terraform", "terraform"],
                category="Technology/Tool",
            )
        ],
        stats=ExtractionStats(total_mentions=0, unique_skills=1),
    )

    cand = ImplicitExtractedSkill(
        skill_id="infra-provisioning-automation",
        label="Infrastructure Provisioning Automation",
        category="Engineering Practice",
        basis="activity",
        evidences=[
            ImplicitEvidence(
                inferred_from_raw="Built modular Terraform configurations automating staging and production VPC rollouts.",
                snippets=[ImplicitEvidenceSnippet(text="Built modular Terraform configurations automating staging and production VPC rollouts.")],
                reasoning="Candidate built automated provisioning pipelines using IaC.",
            )
        ],
    )

    accepted, rejected, verifications = ImplicitEvidenceVerifier.verify_candidates(
        [cand], explicit_result=explicit_mock, document_type="CV"
    )

    assert len(accepted) == 1
    assert len(rejected) == 0
    assert verifications[0].is_accepted is True
    assert verifications[0].support_status == "supported"


def test_3_state_entailment_contract():
    """Verify all required fields of Phase 4 3-state entailment model are populated."""
    cand = ImplicitExtractedSkill(
        skill_id="ci-rollback-automation",
        label="Release Automation",
        category="Engineering Practice",
        basis="activity",
        evidences=[
            ImplicitEvidence(
                inferred_from_raw="Engineered automated release pipelines with automated rollback hooks and canary deployments.",
                snippets=[ImplicitEvidenceSnippet(text="Engineered automated release pipelines with automated rollback hooks and canary deployments.", start=10, end=102)],
                reasoning="Automated release with rollback demonstrates release automation.",
                llm_confidence_raw=0.92,
            )
        ],
    )

    accepted, rejected, verifications = ImplicitEvidenceVerifier.verify_candidates([cand], document_type="CV")
    assert len(verifications) == 1
    v = verifications[0]

    assert v.skill_name == "Release Automation"
    assert v.document_type == "CV"
    assert "Engineered automated release" in v.source_evidence
    assert len(v.evidence_offsets) == 1
    assert v.evidence_offsets[0]["start"] == 10
    assert v.support_status == "supported"
    assert v.acceptance_decision == "accepted"
    assert v.confidence_raw == 0.92
    assert v.confidence_normalized == 0.85 or v.confidence_normalized == 0.90
    assert v.validator_version == "2.0.0"
