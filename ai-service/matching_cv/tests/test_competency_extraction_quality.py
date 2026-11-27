"""Regression tests for source-grounded explicit competency extraction."""

import hashlib
import json

from matching_cv.app.schemas.unified_skill_extraction import DocumentUnifiedResult, UnifiedExtractFileResponse
from matching_cv.app.services import cached_extraction_service
from matching_cv.app.services.pipeline_extraction import refine_cached_pair
from matching_cv.app.services.skill_postprocessor import skill_postprocessor

def _process(text, side, mentions):
    return skill_postprocessor.process_extraction(
        [{"mention": name, "kind": kind, "category": category, "sentence": sentence}
         for name, kind, category, sentence in mentions],
        text=text,
        document_type=side,
    )


def _skill_ids(result):
    return {skill.skill_id for skill in result.skills}


def test_cv_recovers_grounded_payments_without_promoting_project_objects():
    context = "Used Kafka to decouple inventory updates from checkout."
    payment = "Migrated a legacy payment module to a separate service without downtime."
    cv = f"Experience\n• {context}\n• {payment}"
    result = _process(cv, "CV", [
        ("Kafka", "skill", "Technology/Tool", context),
        ("inventory updates", "domain", "Domain Knowledge", context),
        ("checkout", "domain", "Domain Knowledge", context),
        ("payment module", "context", "Domain Knowledge", payment),
    ])

    assert _skill_ids(result) == {"kafka", "payments"}
    assert {item.skill_id for item in result.non_skill_entities} == {"inventory-updates", "checkout", "payment-module"}
    evidence = next(skill for skill in result.skills if skill.skill_id == "payments").evidences[0]
    assert evidence.surface_form == cv[evidence.mention_start:evidence.mention_end] == "payment"
    assert cv[evidence.start:evidence.end] == evidence.sentence == payment


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
    cached = UnifiedExtractFileResponse(run_id="old-cache", status="completed", **documents)

    assert refine_cached_pair(cached, cv + " Edited.", jd) is None
    once = refine_cached_pair(cached, cv, jd)
    assert once is not None
    twice = refine_cached_pair(once, cv, jd)
    assert twice == once
    assert once.summary.cv_explicit_count == 1


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
