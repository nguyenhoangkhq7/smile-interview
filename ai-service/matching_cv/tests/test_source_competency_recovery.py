"""Regression cases for deterministic source recovery after incomplete provider output."""

import pytest

from matching_cv.app.services.skill_postprocessor import skill_postprocessor
from matching_cv.research.data.canonical_skill_normalizer import normalize_canonical_skill


@pytest.mark.parametrize(("text", "expected"), [
    ("Key responsibilities\n• Own data modeling and query performance for PostgreSQL services.",
     {"data-modeling", "query-performance"}),
    ("Key responsibilities\n• Help extend our internal design system.\n"
     "• Optimize page load performance and Core\nWeb Vitals across the portals.",
     {"design-system", "core-web-vitals"}),
    ("Key responsibilities\n• Partner with data scientists to productionize ML models.\n"
     "• Implement data-quality checks and monitoring.\nRequirements\n"
     "• Familiarity with training, evaluation, and deploying models to production.",
     {"data-quality", "model-deployment"}),
])
def test_jd_recovers_the_omitted_engineering_skills_with_exact_offsets(text, expected):
    result = skill_postprocessor.process_extraction([], text=text, document_type="JD")
    assert {skill.skill_id for skill in result.skills} == expected
    for skill in result.skills:
        for evidence in skill.evidences:
            assert text[evidence.start:evidence.end] == evidence.sentence
            assert text[evidence.mention_start:evidence.mention_end] == evidence.surface_form
            assert evidence.verbatim_ok and evidence.offset_resolved
    assert skill_postprocessor.refine_cached_extraction(result, text, "JD").skills == result.skills


def test_containerized_deployment_comes_from_the_requirement_not_from_docker_alone():
    req = "Familiarity with Docker and basic containerized\ndeployment workflows."
    jd = f"Requirements\n• {req}"
    result = skill_postprocessor.process_extraction([], text=jd, document_type="JD")
    assert [skill.skill_id for skill in result.skills] == ["containerized-deployment"]
    evidence = result.skills[0].evidences[0]
    assert jd[evidence.mention_start:evidence.mention_end] == "containerized\ndeployment"
    assert not skill_postprocessor.process_extraction([], text="Skills\nDocker", document_type="CV").skills
    assert not skill_postprocessor.process_extraction(
        [], text="Requirements\nContainerized deployment is not required.", document_type="JD",
    ).skills


def test_cv_recovers_both_data_practices_and_consolidates_explicit_aliases():
    checks = "Implemented data-quality checks using Great Expectations."
    deploy = "Trained and deployed a churn-prediction model (scikit-learn) to production via Flask."
    text = f"Experience\n• {checks}\n• {deploy}"
    result = skill_postprocessor.process_extraction([
        {"mention": "data-quality checks", "kind": "skill", "category": "Engineering Practice", "sentence": checks},
    ], text=text, document_type="CV")
    assert {skill.skill_id for skill in result.skills} == {"data-quality", "model-deployment"}
    assert len(result.skills) == 2
    assert normalize_canonical_skill("data-quality-assurance") == "data-quality"
    assert normalize_canonical_skill("model-serving") == "model-serving"
    assert normalize_canonical_skill("query-optimization") == "query-optimization"


def test_cv_recovers_model_serving_as_a_separate_practice_from_deployment():
    text = ("Summary\nDeploying ML models to production. Strong Python and SQL foundation, with hands-on "
            "experience across the pipeline lifecycle from ingestion to\nmodel serving and monitoring.")
    result = skill_postprocessor.process_extraction([], text=text, document_type="CV")
    assert {skill.skill_id for skill in result.skills} == {"model-deployment", "model-serving"}
    serving = next(skill for skill in result.skills if skill.skill_id == "model-serving")
    evidence = serving.evidences[0]
    assert text[evidence.mention_start:evidence.mention_end] == "model serving"
    assert evidence.offset_resolved and evidence.verbatim_ok


def test_context_negation_and_proxy_metrics_do_not_create_the_missing_skills():
    jd = ("About the role\nWe use Core Web Vitals and data-quality dashboards.\n"
          "Requirements\n• No data modeling is required.\n• Query performance is not required.\n"
          "Benefits\nDesign systems training budget.")
    cv = ("Skills\nGreat Expectations and Lighthouse.\nExperience\n"
          "• Improved the Lighthouse performance score.\n• Built shared components in Storybook.\n"
          "• Deployed infrastructure and documented data models.\n• Never deployed models to production.\n"
          "• Planning to implement data quality checks.")
    for side, text in [("JD", jd), ("CV", cv)]:
        assert not skill_postprocessor.process_extraction([], text=text, document_type=side).skills
