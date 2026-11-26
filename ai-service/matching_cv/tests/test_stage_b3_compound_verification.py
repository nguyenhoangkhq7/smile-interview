"""Stage B.3 Unit Tests: Compound Sub-component Verification Grounding.

Ensures decomposed compound labels route through the exact same semantic anchor
evaluation, thresholds, generic stem rules, and overclaim checks as atomic labels.
"""
from pathlib import Path
import pytest

from matching_cv.app.schemas.implicit_skill_extraction import (
    ImplicitEvidence,
    ImplicitEvidenceSnippet,
    ImplicitExtractedSkill,
)
from matching_cv.app.services.document_parser import document_parser_service
from matching_cv.app.services.implicit_evidence_verifier import ImplicitEvidenceVerifier


def test_stage_b3_compound_test_strategy_rejected_on_northbridge_bullet():
    """(a) 'Test Strategy and Coverage Improvement' on verbatim Northbridge CV bullet:
    'Test Strategy' must be REJECTED, 'Coverage Improvement' must be ACCEPTED.
    """
    fixtures_dir = Path(__file__).resolve().parent / "fixtures"
    cv_path = fixtures_dir / "01_Backend_CV.pdf"
    assert cv_path.exists(), f"CV fixture not found at {cv_path}"

    with open(cv_path, "rb") as f:
        cv_raw, _ = document_parser_service.extract_text_from_pdf(f.read())
        cv_text = document_parser_service.clean_extracted_text(cv_raw)

    lines = cv_text.splitlines()
    matching_idx = next(
        i for i, l in enumerate(lines)
        if "Testcontainers" in l and "raised service test coverage" in l
    )
    nb_bullet = lines[matching_idx] + " " + lines[matching_idx + 1]

    cand = ImplicitExtractedSkill(
        skill_id="test-strategy-and-coverage-improvement",
        label="Test Strategy and Coverage Improvement",
        category="Engineering Practice",
        evidences=[
            ImplicitEvidence(
                inferred_from_raw=nb_bullet,
                snippets=[
                    ImplicitEvidenceSnippet(
                        text=nb_bullet,
                        start=0,
                        end=len(nb_bullet),
                        section="experience",
                        verbatim_ok=True,
                    )
                ],
                reasoning="Wrote integration tests and raised test coverage.",
                llm_confidence_raw=0.85,
            )
        ],
    )

    accepted, rejected, verifications = ImplicitEvidenceVerifier.verify_candidates(
        [cand], document_type="CV"
    )

    accepted_labels = [s.label for s in accepted]
    rejected_labels = [v.proposed_label for v in verifications if not v.is_accepted]

    assert "Test Strategy" not in accepted_labels, (
        f"'Test Strategy' was improperly accepted in compound decomposition: {accepted_labels}"
    )
    assert "Test Strategy" in rejected_labels, (
        f"'Test Strategy' was not found in rejected verifications: {rejected_labels}"
    )
    assert "Coverage Improvement" in accepted_labels, (
        f"'Coverage Improvement' was expected in accepted skills: {accepted_labels}"
    )
    cov_skill = next(s for s in accepted if s.label == "Coverage Improvement")
    assert cov_skill.decomposed_from == "test-strategy-and-coverage-improvement"


def test_stage_b3_compound_both_components_evidenced_accepted():
    """(b) A compound label where BOTH sub-components are genuinely evidenced:
    both accepted as separate implicit skills with decomposed_from preserved.
    """
    ev_text = (
        "Automated deployment pipelines and configured Docker container "
        "orchestration for production microservices."
    )
    cand = ImplicitExtractedSkill(
        skill_id="deployment-automation-and-container-orchestration",
        label="Deployment Automation and Container Orchestration",
        category="Technical Concept",
        evidences=[
            ImplicitEvidence(
                inferred_from_raw=ev_text,
                snippets=[
                    ImplicitEvidenceSnippet(
                        text=ev_text,
                        start=0,
                        end=len(ev_text),
                        section="experience",
                        verbatim_ok=True,
                    )
                ],
                reasoning="Automated deployment pipelines and configured Docker container orchestration.",
                llm_confidence_raw=0.90,
            )
        ],
    )

    accepted, rejected, verifications = ImplicitEvidenceVerifier.verify_candidates(
        [cand], document_type="CV"
    )

    assert len(accepted) == 2, f"Expected both subcomponents accepted, got {[s.label for s in accepted]}"
    assert {s.skill_id for s in accepted} == {"deployment-automation", "container-orchestration"}
    assert all(
        s.decomposed_from == "deployment-automation-and-container-orchestration"
        for s in accepted
    )
    assert len([v for v in verifications if not v.is_accepted]) == 0


def test_stage_b3_compound_partial_support_only_evidenced_accepted():
    """(c) A compound label where ONE sub-component is evidenced and ONE is unsupported:
    only the evidenced sub-component is accepted; the other is rejected as unsupported.
    """
    ev_text = "Maintained MySQL database clusters, tuned slow queries and automated backups."
    cand = ImplicitExtractedSkill(
        skill_id="database-optimization-and-quantum-computing",
        label="Database Optimization & Quantum Computing",
        category="Engineering Practice",
        evidences=[
            ImplicitEvidence(
                inferred_from_raw=ev_text,
                snippets=[
                    ImplicitEvidenceSnippet(
                        text=ev_text,
                        start=0,
                        end=len(ev_text),
                        section="experience",
                        verbatim_ok=True,
                    )
                ],
                reasoning="Tuned slow queries; speculated on quantum computing.",
                llm_confidence_raw=0.75,
            )
        ],
    )

    accepted, rejected, verifications = ImplicitEvidenceVerifier.verify_candidates(
        [cand], document_type="CV"
    )

    assert len(accepted) == 1, f"Expected 1 accepted skill, got {[s.label for s in accepted]}"
    assert accepted[0].skill_id == "database-optimization"
    assert accepted[0].decomposed_from == "database-optimization-and-quantum-computing"

    unsupported_vers = [v for v in verifications if not v.is_accepted]
    assert len(unsupported_vers) == 1
    assert unsupported_vers[0].skill_id == "quantum-computing"
    assert unsupported_vers[0].support_status == "unsupported"


def test_stage_b3_compound_and_atomic_decision_parity():
    """(d) Parity test: verify that for a given evidence snippet, an atomic candidate
    and a compound candidate containing that same label produce the EXACT SAME
    acceptance decision.
    """
    ev_text = (
        "Primary on-call engineer for tier-1 production outages, triaging live "
        "alerts and restoring service availability."
    )
    test_cases = [
        ("Incident Management", True),
        ("Root Cause Post-Mortem", False),
        ("Test Strategy", False),
    ]

    for lbl, expected_acc in test_cases:
        # Atomic candidate
        atomic_cand = ImplicitExtractedSkill(
            skill_id="test-atomic",
            label=lbl,
            category="Engineering Practice",
            evidences=[
                ImplicitEvidence(
                    inferred_from_raw=ev_text,
                    snippets=[
                        ImplicitEvidenceSnippet(
                            text=ev_text,
                            start=0,
                            end=len(ev_text),
                            section="experience",
                            verbatim_ok=True,
                        )
                    ],
                    llm_confidence_raw=0.85,
                )
            ],
        )
        atomic_acc, atomic_rej, atomic_vers = ImplicitEvidenceVerifier.verify_candidates(
            [atomic_cand], document_type="CV"
        )
        atomic_decision = len(atomic_acc) == 1

        # Compound candidate containing the label
        compound_lbl = f"{lbl} & Production Operations"
        compound_cand = ImplicitExtractedSkill(
            skill_id="test-compound",
            label=compound_lbl,
            category="Engineering Practice",
            evidences=[
                ImplicitEvidence(
                    inferred_from_raw=ev_text,
                    snippets=[
                        ImplicitEvidenceSnippet(
                            text=ev_text,
                            start=0,
                            end=len(ev_text),
                            section="experience",
                            verbatim_ok=True,
                        )
                    ],
                    llm_confidence_raw=0.85,
                )
            ],
        )
        comp_acc, comp_rej, comp_vers = ImplicitEvidenceVerifier.verify_candidates(
            [compound_cand], document_type="CV"
        )
        comp_matching_acc = [s for s in comp_acc if s.label == lbl]
        comp_decision = len(comp_matching_acc) == 1

        assert atomic_decision == expected_acc, (
            f"Atomic '{lbl}' expected {expected_acc}, got {atomic_decision}"
        )
        assert comp_decision == atomic_decision, (
            f"Parity mismatch for '{lbl}': atomic={atomic_decision}, compound={comp_decision}"
        )
