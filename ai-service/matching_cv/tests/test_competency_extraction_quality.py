"""Regression tests for source-grounded explicit competency extraction."""

import hashlib
import json

import pytest

from matching_cv.app.schemas.implicit_skill_extraction import (
    ImplicitEvidence, ImplicitEvidenceSnippet, ImplicitExtractedSkill, ImplicitExtractionResult, ImplicitExtractionStats,
)
from matching_cv.app.schemas.skill_extraction import Evidence, ExtractedSkill
from matching_cv.app.schemas.unified_skill_extraction import DocumentUnifiedResult, UnifiedExtractFileResponse
from matching_cv.app.services import cached_extraction_service
from matching_cv.app.services.pipeline_extraction import refine_cached_pair
from matching_cv.app.services.skill_postprocessor import skill_postprocessor
from matching_cv.app.services.unified_skill_service import deduplicate_explicit_implicit

def _process(text, side, mentions):
    return skill_postprocessor.process_extraction(
        [{"mention": name, "kind": kind, "category": category, "sentence": sentence}
         for name, kind, category, sentence in mentions],
        text=text,
        document_type=side,
    )


def _skill_ids(result):
    return {skill.skill_id for skill in result.skills}


def test_cv_keeps_project_objects_as_context_without_promoting_payments():
    context = "Used Kafka to decouple inventory updates from checkout."
    payment = "Migrated a legacy payment module to a separate service without downtime."
    cv = f"Experience\n• {context}\n• {payment}"
    result = _process(cv, "CV", [
        ("Kafka", "skill", "Technology/Tool", context),
        ("inventory updates", "domain", "Domain Knowledge", context),
        ("checkout", "domain", "Domain Knowledge", context),
        ("payment module", "context", "Domain Knowledge", payment),
    ])

    assert _skill_ids(result) == {"kafka"}
    assert {item.skill_id for item in result.non_skill_entities} == {"inventory-updates", "checkout", "payment-module"}
    evidence = next(item for item in result.non_skill_entities if item.skill_id == "payment-module").evidences[0]
    assert evidence.surface_form == cv[evidence.mention_start:evidence.mention_end] == "payment module"
    assert cv[evidence.start:evidence.end] == evidence.sentence == payment


@pytest.mark.parametrize(("label", "sentence"), [
    ("thanh toán", "Triển khai module thanh toán cho người bán."),
    ("inventory", "Built a dashboard for inventory."),
    ("billing", "Experience with Java for a billing platform."),
    ("payments", "Experience in implementing a payments module for merchants."),
    ("healthcare", "Developed a portal for healthcare providers."),
])
def test_domain_mentions_in_project_actions_remain_context(label, sentence):
    for side, heading in (("CV", "Experience"), ("JD", "Responsibilities")):
        result = _process(f"{heading}\n{sentence}", side, [(label, "domain", "Domain Knowledge", sentence)])
        assert not result.skills
        assert any(item.kind == "context" and item.evidences[0].sentence == sentence
                   for item in result.non_skill_entities)


def test_explicit_payment_requirement_and_payment_aliases_are_retained():
    first = "Experience in Payment is required."
    repeated = "Payments expertise is preferred."
    jd = _process(f"Requirements\n{first}\n{repeated}", "JD", [
        ("Payment", "domain", "Domain Knowledge", first),
        ("Payments", "domain", "Domain Knowledge", repeated),
    ])
    assert _skill_ids(jd) == {"payments"}
    assert {evidence.sentence for evidence in jd.skills[0].evidences} == {first, repeated}

    source = "Có kinh nghiệm trong nghiệp vụ thanh toán."
    cv = _process(f"Kinh nghiệm\n{source}", "CV", [("thanh toán", "domain", "Domain Knowledge", source)])
    assert _skill_ids(cv) == {"payments"}
    assert cv.skills[0].evidences[0].surface_form == "thanh toán"


def test_domain_requirement_in_role_intro_keeps_only_candidate_evidence():
    company = "We have extensive experience in healthcare."
    candidate = "We are looking for someone with experience in healthcare."
    jd = _process(f"About the role\n{company}\n{candidate}", "JD", [
        ("healthcare", "domain", "Domain Knowledge", company),
        ("healthcare", "domain", "Domain Knowledge", candidate),
    ])
    assert [evidence.sentence for evidence in jd.skills[0].evidences] == [candidate]
    assert [evidence.sentence for evidence in jd.non_skill_entities[0].evidences] == [company]


def test_inferred_domain_is_not_an_accepted_skill():
    paragraph = "Built a portal for healthcare providers."
    implicit = ImplicitExtractionResult(stats=ImplicitExtractionStats(total_inferences=1, unique_skills=1), skills=[ImplicitExtractedSkill(
        skill_id="healthcare", label="Healthcare", category="Domain Knowledge",
        evidences=[ImplicitEvidence(inferred_from_raw=paragraph, snippets=[
            ImplicitEvidenceSnippet(text=paragraph, start=0, end=len(paragraph), verbatim_ok=True),
        ])],
    )])
    result = deduplicate_explicit_implicit(None, implicit, validation_policy="dedup_only")
    assert not result.accepted_implicit_skills
    assert [item.skill_id for item in result.rejected_implicit_skills] == ["healthcare"]


def test_cv_recovers_verbatim_integration_tests_when_extraction_only_returns_the_tool():
    sentence = "Wrote integration\n tests with Testcontainers and raised service coverage."
    cv = "Experience\n• " + sentence
    result = _process(cv, "CV", [("Testcontainers", "skill", "Technology/Tool", sentence)])

    assert _skill_ids(result) == {"integration-tests", "testcontainers"}
    skill = next(skill for skill in result.skills if skill.skill_id == "integration-tests")
    evidence = skill.evidences[0]
    assert cv[evidence.mention_start:evidence.mention_end] == evidence.surface_form == "integration\n tests"
    assert cv[evidence.start:evidence.end] == evidence.sentence == sentence
    assert skill_postprocessor.refine_cached_extraction(result, cv, "CV").skills == result.skills


def test_integration_testing_aliases_consolidate_without_inferring_unit_tests():
    sentence = "Wrote integration tests and led integration testing."
    result = _process("Experience\n" + sentence, "CV", [
        ("integration tests", "skill", "Engineering Practice", sentence),
        ("integration testing", "skill", "Engineering Practice", sentence),
    ])
    assert _skill_ids(result) == {"integration-tests"}
    assert set(result.skills[0].surface_forms) == {"integration tests", "integration testing"}


def test_integration_test_recovery_rejects_plans_negation_and_tool_only_mentions():
    cv = ("Experience\nUsed Testcontainers to provision databases.\n"
          "• Never wrote integration tests.\n• Plan to write integration tests.")
    assert "integration-tests" not in _skill_ids(_process(cv, "CV", []))


def test_payment_title_negation_and_assignment_lack_work_evidence():
    result = _process(
        "Northbridge Payments\nExperience\n"
        "• Assigned to the payment module.\n"
        "• Never migrated a payment module.",
        "CV",
        [],
    )
    assert "payments" not in _skill_ids(result)


def test_jd_requires_domain_qualification_instead_of_company_and_project_context():
    intro = "Willow Health builds a patient-scheduling and telehealth platform."
    activity = "Write integration tests to protect critical booking flows."
    optional = "Familiarity with healthcare or another regulated consumer product."
    preferred = "Experience with reporting systems is preferred."
    jd = f"About the role\n{intro}\nKey responsibilities\n{activity}\nNice to have\n{optional}\n{preferred}"

    result = _process(jd, "JD", [
        ("telehealth", "domain", "Domain Knowledge", intro),
        ("booking flows", "domain", "Domain Knowledge", activity),
        ("healthcare", "domain", "Domain Knowledge", optional),
        ("regulated consumer product", "domain", "Domain Knowledge", optional),
        ("reporting systems", "domain", "Domain Knowledge", preferred),
    ])

    assert _skill_ids(result) == {"healthcare", "reporting-system"}
    assert {item.skill_id for item in result.non_skill_entities} == {
        "telehealth", "booking-flows", "regulated-consumer-product",
    }


def test_registered_stack_and_verified_aliases_keep_exact_offsets():
    sentence = "Experience with Java Spring Boot, Apache Kafka, and Kafka."
    jd = "Requirements\n" + sentence
    result = _process(jd, "JD", [
        ("Java Spring Boot", "skill", "Technology/Tool", sentence),
        ("Apache Kafka", "skill", "Technology/Tool", sentence),
        ("Kafka", "skill", "Technology/Tool", sentence),
    ])

    assert _skill_ids(result) == {"java", "spring-boot", "kafka"}
    kafka = next(skill for skill in result.skills if skill.skill_id == "kafka")
    assert set(kafka.surface_forms) == {"Apache Kafka", "Kafka"}
    for skill in result.skills:
        for evidence in skill.evidences:
            assert evidence.mention_start is not None and evidence.mention_end is not None
            assert jd[evidence.mention_start:evidence.mention_end] == evidence.surface_form


def test_cache_refinement_checks_document_identity_and_is_idempotent():
    cv = "Experience\nMigrated a payment gateway to a new service."
    jd = "Requirements\nExperience in payments."
    documents = {}
    for side, text in (("cv", cv), ("jd", jd)):
        documents[side] = DocumentUnifiedResult(
            document_type=side.upper(),
            text_sha256=hashlib.sha256(text.encode()).hexdigest(),
            raw_text=text,
            explicit=_process(text, side.upper(), []),
        )
    # Older cached runs promoted this project description to a domain skill.
    documents["cv"].explicit.skills.append(ExtractedSkill(
        skill_id="payments", kind="domain", category="Domain Knowledge", evidences=[
            Evidence(surface_form="payment", sentence="Migrated a payment gateway to a new service."),
        ],
    ))
    cached = UnifiedExtractFileResponse(run_id="old-cache", status="completed", **documents)

    assert refine_cached_pair(cached, cv + " Edited.", jd) is None
    once = refine_cached_pair(cached, cv, jd)
    assert once is not None
    twice = refine_cached_pair(once, cv, jd)
    assert twice == once
    assert once.summary.cv_explicit_count == 0
    assert once.cv.explicit.non_skill_entities[0].evidences[0].sentence == "Migrated a payment gateway to a new service."


def test_design_system_work_recovers_mislabeled_competency():
    source = "Improve component reusability and help extend our internal design system."
    jd = f"Responsibilities\n{source}"
    result = _process(jd, "JD", [("design system", "context", "Technical Concept", source)])
    assert _skill_ids(result) == {"design-system"}
    assert result.skills[0].evidences[0].sentence == source


def test_file_name_match_does_not_reuse_stale_document_cache(tmp_path, monkeypatch):
    monkeypatch.setattr(cached_extraction_service, "DOCUMENT_CACHE_DIR", tmp_path)
    monkeypatch.setattr(cached_extraction_service.settings, "MATCHING_CV_DSPY_EXPLICIT_ENABLED", False)
    cache = cached_extraction_service.CachedExtractionService()
    monkeypatch.setattr(cache, "_load_mapping", lambda: ({}, {}))
    for name, text in (("cv_demo", "Built with React."), ("jd_demo", "React required.")):
        payload = {
            "text_sha256": hashlib.sha256(text.encode()).hexdigest(),
            "extracted_skills": {"explicit": [], "implicit": []},
        }
        (tmp_path / f"{name}.json").write_text(json.dumps(payload), encoding="utf8")

    cached, *_ = cache.resolve_cached_extraction(
        "Built with React.", "React required.", "cv_demo.txt", "jd_demo.txt"
    )
    stale, *_ = cache.resolve_cached_extraction(
        "Built with Vue instead.", "React required.", "cv_demo.txt", "jd_demo.txt"
    )
    assert cached is not None
    assert stale is None


def test_coverage_analysis_requires_evidence_of_analysis_in_cv():
    from matching_cv.app.schemas.implicit_skill_extraction import ImplicitEvidence, ImplicitExtractedSkill
    from matching_cv.app.services.competency_granularity import evaluate_competency_retention
    from matching_cv.app.services.implicit_evidence_verifier import ImplicitEvidenceVerifier

    outcome = "Wrote integration tests and raised service test coverage from 46% to 82%."
    inference = ImplicitExtractedSkill(
        skill_id="coverage-analysis", label="Coverage Analysis", category="Engineering Practice",
        evidences=[ImplicitEvidence(inferred_from_raw=outcome, reasoning="The engineer analyzed code coverage.")],
    )
    accepted, rejected, diagnostics = ImplicitEvidenceVerifier.verify_candidates([inference], document_type="CV")
    assert accepted == [] and rejected == [inference]
    assert diagnostics[0].acceptance_decision == "rejected"
    assert not evaluate_competency_retention("Coverage Analysis", evidence=outcome, side="CV").should_retain
    assert not evaluate_competency_retention(
        "Test Coverage Analysis", evidence="Planned to analyze test coverage.", side="CV",
    ).should_retain
    assert evaluate_competency_retention(
        "Coverage Analysis", evidence="Analyzed code coverage to identify untested branches.", side="CV",
    ).should_retain
    assert evaluate_competency_retention("Coverage Analysis", evidence="Coverage Analysis, pytest", side="CV").should_retain
    assert evaluate_competency_retention("Coverage Analysis", evidence="Experience in coverage analysis.", side="JD").should_retain
