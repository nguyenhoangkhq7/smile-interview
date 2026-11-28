"""Offline regression for the Backend PDF pair used in the candidate flow."""

import json
from pathlib import Path
from types import SimpleNamespace
from typing import Literal

import pytest

from matching_cv.app.schemas.skill_extraction import Evidence, ExtractedSkill
from matching_cv.app.schemas.unified_skill_extraction import DocumentUnifiedResult, UnifiedExtractFileResponse
from matching_cv.app.services.document_parser import document_parser_service
from matching_cv.app.services.resume_evidence_matching import enrich_verified_resume_skills
from matching_cv.app.services.skill_postprocessor import skill_postprocessor
from matching_cv.app.services.standardized_output_builder import MATRIX_KEY, PublicOutputContext, build_module1_output
from matching_cv.research.data.canonical_skill_normalizer import normalize_canonical_skill


FIXTURES = Path(__file__).parent / "fixtures"

# Deliberately preserve the adverse ordering seen in the saved report. These
# values control candidate ranking during the test and are not SBERT measurements.
SEMANTIC_SCORES = {
    ("java", "java"): 0.98,
    ("rest-api", "restful-microservices"): 0.76,
    ("microservices", "restful-microservices"): 0.61,
    ("testcontainers", "unit-tests"): 0.77,
    ("junit", "unit-tests"): 0.54,
    ("mockito", "unit-tests"): 0.56,
    ("query-indexing", "query-optimization"): 0.73,
    ("jenkins", "ci-cd"): 0.66,
    ("git", "github-actions"): 0.74,
}


def _pdf_text(filename: str) -> str:
    text, _ = document_parser_service.extract_text_from_pdf((FIXTURES / filename).read_bytes())
    return document_parser_service.clean_extracted_text(text)


def _explicit_skill(skill_id: str, name: str, sentence: str, *, domain: bool = False) -> ExtractedSkill:
    kind = "domain" if domain else "skill"
    category = "Domain Knowledge" if domain else "Technical Concept"
    return ExtractedSkill(
        skill_id=skill_id,
        surface_forms=[name],
        category=category,
        kind=kind,
        evidences=[Evidence(sentence=sentence, surface_form=name, category=category, kind=kind)],
    )


def _line(text: str, phrase: str) -> str:
    return next(line for line in text.splitlines() if phrase.casefold() in line.casefold())


def _document(side: Literal["CV", "JD"], text: str, skills: list[ExtractedSkill]) -> DocumentUnifiedResult:
    return DocumentUnifiedResult(
        document_type=side,
        raw_text=text,
        explicit=skill_postprocessor._route_and_build_result(
            entities=skills,
            quarantined=[],
            text=text,
            filename=None,
            document_type=side,
            extraction_meta=None,
        ),
    )


def _semantic_record(skill_id: str) -> SimpleNamespace:
    return SimpleNamespace(embedding_id=skill_id, associated_skill_ids=[skill_id])


def _context(
    cv: DocumentUnifiedResult,
    jd: DocumentUnifiedResult,
    *,
    retained_cv_ids: list[str],
) -> PublicOutputContext:
    jd_ids = [skill.skill_id for skill in jd.explicit.skills]
    nodes = {}
    for skill_id in dict.fromkeys([*retained_cv_ids, *jd_ids]):
        shared = skill_id in retained_cv_ids and skill_id in jd_ids
        nodes[skill_id] = SimpleNamespace(
            node_id=skill_id,
            cv_canonical_id=skill_id if skill_id in retained_cv_ids else "",
            jd_canonical_id=skill_id if skill_id in jd_ids else "",
            cv_occurrence_ids=[],
            jd_occurrence_ids=[],
            merge_decision=SimpleNamespace(merge_reason="same_canonical_id") if shared else None,
            cosine_similarity_if_shared=None,
        )
    matrix = SimpleNamespace(
        source_ids=retained_cv_ids,
        target_ids=jd_ids,
        matrix=[],
        raw_matrix=[
            [SEMANTIC_SCORES.get((cv_id, jd_id), 0.05) for jd_id in jd_ids]
            for cv_id in retained_cv_ids
        ],
    )
    stage3 = SimpleNamespace(
        cv_skill_embeddings=[_semantic_record(skill_id) for skill_id in retained_cv_ids],
        jd_skill_embeddings=[_semantic_record(skill_id) for skill_id in jd_ids],
        similarity_matrices={MATRIX_KEY: matrix},
    )
    return PublicOutputContext(
        cv_text=cv.raw_text,
        jd_text=jd.raw_text,
        unified_response=UnifiedExtractFileResponse(run_id="backend-regression", status="completed", cv=cv, jd=jd),
        graph_data=SimpleNamespace(skill_nodes=nodes, diagnostics={}),
        stage3_response=stage3,
        skill_importance_output={"records": [{"skill_id": skill_id, "weight": 0.8} for skill_id in jd_ids]},
    )


@pytest.fixture
def backend_case():
    cv_text = _pdf_text("01_Backend_CV.pdf")
    jd_text = _pdf_text("01_Backend_JD.pdf")
    recording = json.loads((FIXTURES / "01_Backend_CV_run1_d7.json").read_text(encoding="utf-8"))
    skills = [
        ExtractedSkill.model_validate(skill)
        for skill in recording["processed_result"]["skills"]
        if skill["skill_id"] in {
            "java", "spring-boot", "microservices", "rest-api-development", "query-indexing",
            "junit-5", "mockito", "testcontainers", "jenkins", "git", "fintech", "payment-module",
        }
    ]
    cv = _document("CV", cv_text, skills)
    domain_requirement = _line(jd_text, "fintech, payments")
    jd = _document("JD", jd_text, [
        _explicit_skill("java", "Java", _line(jd_text, "2+ years")),
        _explicit_skill("fintech", "fintech", domain_requirement, domain=True),
        _explicit_skill("payments", "payments", domain_requirement, domain=True),
        _explicit_skill("query-optimization", "query optimization", _line(jd_text, "query optimization")),
        _explicit_skill("query-performance", "query performance", _line(jd_text, "query performance")),
        _explicit_skill("restful-microservices", "RESTful microservices", _line(jd_text, "RESTful microservices")),
        _explicit_skill("unit-tests", "unit", _line(jd_text, "unit and integration tests")),
        _explicit_skill("integration-tests", "integration tests", _line(jd_text, "unit and integration tests")),
        _explicit_skill("ci-cd", "CI/CD", _line(jd_text, "CI/CD")),
        _explicit_skill("github-actions", "GitHub Actions", _line(jd_text, "GitHub Actions")),
    ])
    # Simulate the saved run where neither domain item was available as a CV node.
    retained = [normalize_canonical_skill(skill.skill_id) for skill in skills
                if skill.skill_id not in {"fintech", "payment-module"}]
    return cv, jd, retained


def test_backend_pdf_requirements_use_the_cv_evidence(backend_case):
    cv, jd, retained = backend_case
    output = build_module1_output(_context(cv, jd, retained_cv_ids=retained))
    matches = {match.jd_skill_id: match for match in output.match_results}
    evidence = {skill.skill_id: " ".join(skill.evidence_spans).casefold() for skill in output.cv_skills}

    for skill_id, phrase in {
        "query-optimization": "query indexing",
        "query-performance": "latency by 38%",
        "restful-microservices": "microservices",
    }.items():
        assert matches[skill_id].soft_match >= 0.85
        assert phrase in evidence[matches[skill_id].matched_cv_skill_id]

    for skill_id in ("fintech", "payments"):
        assert matches[skill_id].matched_cv_skill_id == "none"
        assert matches[skill_id].soft_match == 0

    assert matches["java"].matched_cv_skill_id == "java"
    assert matches["java"].soft_match >= 0.85
    assert matches["unit-tests"].matched_cv_skill_id in {"junit", "junit-5", "mockito"}
    assert 0.40 <= matches["unit-tests"].soft_match < 0.85
    assert matches["ci-cd"].matched_cv_skill_id == "jenkins"
    assert 0.40 <= matches["ci-cd"].soft_match < 0.85
    assert matches["github-actions"].matched_cv_skill_id == "none"
    assert matches["github-actions"].soft_match == 0


def test_backend_query_performance_enters_graph_with_anchored_project_evidence(backend_case):
    cv, jd, retained = backend_case
    context = _context(cv, jd, retained_cv_ids=retained)
    enriched = enrich_verified_resume_skills(context.unified_response, cv.raw_text)
    added = next(skill for skill in enriched.cv._verified_resume_skills if skill.skill_id == "query-performance")

    assert all(skill.skill_id != "query-performance" for skill in cv._verified_resume_skills)
    snippet = added.evidences[0].snippets[0]
    assert snippet.text == cv.raw_text[snippet.start:snippet.end]
    assert "latency by 38%" in snippet.text.casefold()
    assert "query indexing and redis caching" in snippet.text.casefold()


@pytest.mark.parametrize(
    "text",
    [
        "Skills\nQuery indexing, PostgreSQL, Redis.",
        "Skills\nReduced API latency by 38% through query indexing.",
        "Experience\nUsed query indexing for the order service.",
        "Experience\n• Used query indexing for reporting.\n• Reduced API latency by caching responses.",
        "Experience\nNever reduced query latency through query indexing.",
    ],
)
def test_query_indexing_without_linked_project_outcome_does_not_prove_query_performance(
    backend_case, text, monkeypatch,
):
    _, jd, _ = backend_case
    cv = _document("CV", text, [_explicit_skill("query-indexing", "Query indexing", _line(text, "query indexing"))])
    monkeypatch.setitem(SEMANTIC_SCORES, ("query-indexing", "query-performance"), 0.78)
    context = _context(cv, jd, retained_cv_ids=["query-indexing"])
    enriched = enrich_verified_resume_skills(context.unified_response, text)
    output = build_module1_output(context)
    match = next(match for match in output.match_results if match.jd_skill_id == "query-performance")

    assert all(skill.skill_id != "query-performance" for skill in enriched.cv._verified_resume_skills)
    assert all(skill.skill_id != "query-performance" for skill in output.cv_skills)
    assert match.matched_cv_skill_id != "query-performance"
    assert match.soft_match < 0.85


def test_title_and_integration_testing_do_not_create_bogus_matches(backend_case):
    _, jd, _ = backend_case
    text = (
        "Candidate Name\nNorthbridge Payments\nExperience\n"
        "Wrote integration tests with Testcontainers.\n"
    )
    cv = _document("CV", text, [_explicit_skill("testcontainers", "Testcontainers", _line(text, "Testcontainers"))])
    matches = {
        match.jd_skill_id: match
        for match in build_module1_output(_context(cv, jd, retained_cv_ids=["testcontainers"])).match_results
    }
    for skill_id in ("payments", "unit-tests"):
        assert matches[skill_id].matched_cv_skill_id == "none"
        assert matches[skill_id].soft_match == 0


def test_negated_domain_claims_do_not_receive_a_match(backend_case, monkeypatch):
    _, jd, _ = backend_case
    text = "Summary\nNo fintech experience. Never migrated any payment module or worked in payments."
    cv = _document("CV", text, [
        _explicit_skill("fintech", "fintech", _line(text, "fintech"), domain=True),
        _explicit_skill("payments", "payments", _line(text, "payments"), domain=True),
    ])
    for skill_id in ("fintech", "payments"):
        monkeypatch.setitem(SEMANTIC_SCORES, (skill_id, skill_id), 0.98)

    output = build_module1_output(_context(cv, jd, retained_cv_ids=["fintech", "payments"]))
    matches = {match.jd_skill_id: match for match in output.match_results}

    for skill_id in ("fintech", "payments"):
        assert matches[skill_id].matched_cv_skill_id == "none"
        assert matches[skill_id].soft_match == 0


def test_direct_listed_skills_take_precedence_over_related_tools(backend_case):
    _, jd, _ = backend_case
    line = "Unit tests, CI/CD, JUnit and Jenkins."
    text = f"Skills\n{line}"
    cv = _document("CV", text, [
        _explicit_skill("junit", "JUnit", line),
        _explicit_skill("jenkins", "Jenkins", line),
    ])

    output = build_module1_output(_context(cv, jd, retained_cv_ids=["junit", "jenkins"]))
    matches = {match.jd_skill_id: match for match in output.match_results}
    evidence = {skill.skill_id: skill.evidence_spans for skill in output.cv_skills}

    for skill_id, phrase in {"unit-tests": "Unit tests", "ci-cd": "CI/CD"}.items():
        assert matches[skill_id].matched_cv_skill_id == skill_id
        assert matches[skill_id].soft_match >= 0.85
        assert any(phrase in span and span in text for span in evidence[skill_id])


@pytest.mark.parametrize(
    "github_evidence",
    [
        "Configured GitHub Actions to automate deployments.",
        "Sử dụng GitHub Actions để tự động hóa việc triển khai.",
    ],
)
def test_work_evidence_preserves_github_actions_without_inferring_payments(backend_case, github_evidence):
    _, jd, _ = backend_case
    payment_evidence = "Migrated the payment module to a standalone service without downtime."
    text = f"Experience\n{github_evidence}\n{payment_evidence}"
    cv = _document("CV", text, [])

    output = build_module1_output(_context(cv, jd, retained_cv_ids=[]))
    matches = {match.jd_skill_id: match for match in output.match_results}
    evidence = {skill.skill_id: skill.evidence_spans for skill in output.cv_skills}

    assert matches["github-actions"].matched_cv_skill_id == "github-actions"
    assert matches["github-actions"].soft_match >= 0.85
    assert any(span in github_evidence for span in evidence["github-actions"])
    assert matches["payments"].matched_cv_skill_id == "none"
    assert "payments" not in evidence


def test_domain_requirement_matches_explicit_domain_evidence_and_excludes_technical_tools(monkeypatch):
    requirement = "Experience in payments is required."
    jd = _document("JD", f"Requirements\n{requirement}", [
        _explicit_skill("payments", "payments", requirement, domain=True),
    ])
    tool = "Integrated Stripe for checkout."
    experience = "Experience in payment processing and merchant settlement."
    text = f"Experience\n{tool}\n{experience}"
    cv = _document("CV", text, [
        _explicit_skill("stripe", "Stripe", tool),
        _explicit_skill("payment", "payment", experience, domain=True),
    ])
    monkeypatch.setitem(SEMANTIC_SCORES, ("stripe", "payments"), 0.99)
    tool_only = build_module1_output(_context(cv, jd, retained_cv_ids=["stripe"]))
    assert tool_only.match_results[0].matched_cv_skill_id == "none"
    with_domain = build_module1_output(_context(cv, jd, retained_cv_ids=["stripe", "payments"]))
    assert with_domain.match_results[0].matched_cv_skill_id == "payments"
    assert with_domain.match_results[0].soft_match == 1.0


def test_unrelated_work_bullets_do_not_prove_restful_microservices(backend_case):
    _, jd, _ = backend_case
    rest = "Built REST APIs for KYC with Spring Boot."
    microservices = "Developed microservices for analytics with Spring Boot."
    text = f"Experience\nCompany A\n• {rest}\nCompany B\n• {microservices}"
    cv = _document("CV", text, [
        _explicit_skill("rest-api", "REST APIs", rest),
        _explicit_skill("microservices", "microservices", microservices),
    ])

    output = build_module1_output(_context(cv, jd, retained_cv_ids=["rest-api", "microservices"]))
    match = next(match for match in output.match_results if match.jd_skill_id == "restful-microservices")

    assert match.matched_cv_skill_id == "rest-api"
    assert match.soft_match == pytest.approx(0.76)


def test_match_uses_an_eligible_candidate_when_highest_score_fails_its_own_threshold(monkeypatch):
    text = "Experience\nBuilt CI/CD pipelines and used Testcontainers in integration tests."
    requirement = "Experience with Jenkins to manage builds."
    cv = _document("CV", text, [
        _explicit_skill("ci-cd", "CI/CD", _line(text, "CI/CD")),
        _explicit_skill("testcontainers", "Testcontainers", _line(text, "Testcontainers")),
    ])
    jd = _document("JD", requirement, [_explicit_skill("jenkins", "Jenkins", requirement)])
    monkeypatch.setitem(SEMANTIC_SCORES, ("testcontainers", "jenkins"), 0.49)
    monkeypatch.setitem(SEMANTIC_SCORES, ("ci-cd", "jenkins"), 0.50)

    output = build_module1_output(_context(cv, jd, retained_cv_ids=["ci-cd", "testcontainers"]))

    match = output.match_results[0]
    assert match.matched_cv_skill_id == "ci-cd"
    assert match.soft_match == pytest.approx(0.46)


def test_verified_backend_skills_reach_gnn_as_shared_nodes(backend_case, monkeypatch):
    import asyncio
    from io import BytesIO
    from unittest.mock import AsyncMock, Mock

    from fastapi import UploadFile
    from matching_cv.app.container import build_pipeline_orchestrator
    from matching_cv.app.services.pipeline_extraction import PipelineExtractionOutcome

    cv, jd, _ = backend_case
    jd.explicit.skills.extend([
        _explicit_skill("indexing", "indexing", _line(jd.raw_text, "indexing")),
        _explicit_skill("junit", "JUnit", _line(jd.raw_text, "JUnit")),
        _explicit_skill("relational-databases", "relational databases", _line(jd.raw_text, "relational databases")),
    ])
    pair = UnifiedExtractFileResponse(run_id="verified-backend", status="completed", cv=cv, jd=jd)
    orchestrator = build_pipeline_orchestrator()
    outcome = PipelineExtractionOutcome(pair, None, cv.raw_text, jd.raw_text, 0.0)
    monkeypatch.setattr(orchestrator.extraction_service, "extract", AsyncMock(return_value=outcome))
    inference = Mock(wraps=orchestrator.inference_service.infer)
    monkeypatch.setattr(orchestrator.inference_service, "infer", inference)
    def evaluate_importance(*, unified_response, **_):
        return {"records": [{"skill_id": skill.skill_id, "weight": 0.8}
                            for skill in unified_response.jd.explicit.skills]}

    monkeypatch.setattr(orchestrator.skill_importance_stage, "evaluate", evaluate_importance)

    result = asyncio.run(orchestrator.execute_pipeline(
        cv_file=UploadFile(BytesIO(cv.raw_text.encode()), filename="cv.txt"),
        jd_file=UploadFile(BytesIO(jd.raw_text.encode()), filename="jd.txt"),
        graph_mode="evidence_only",
    ))

    context = result._public_context
    assert context is not None, result.failure
    assert result.matching_result is not None, result.failure
    inference.assert_called_once()
    pyg = inference.call_args.kwargs["graph"]
    graph = context.graph_data
    by_jd = {node.jd_canonical_id: node for node in graph.skill_nodes.values() if node.jd_canonical_id}
    cv_edges = pyg[("resume", "has_skill", "skill")].edge_index[1].tolist()
    for skill_id in ("restful-microservices", "query-optimization", "indexing", "relational-databases", "junit", "integration-tests"):
        node = by_jd[skill_id]
        assert node.membership == "shared"
        assert node.cv_evidences and all(" ".join(span.split()) in " ".join(cv.raw_text.split()) for span in node.cv_evidences)
        assert pyg["skill"].node_ids.index(node.node_id) in cv_edges
    for skill_id in ("unit-tests", "ci-cd"):
        assert by_jd[skill_id].membership == "job_only"
    assert "github-actions" not in by_jd
    assert context.unified_response.jd._requirement_groups["ci-cd"] == ("jenkins", "github-actions")
    assert "junit-5" not in {node.cv_canonical_id for node in graph.skill_nodes.values()}
    matches = {match.jd_skill_id: match for match in build_module1_output(context).match_results}
    assert matches["integration-tests"].matched_cv_skill_id == "integration-tests"
    assert matches["integration-tests"].soft_match == 1.0
    assert pair.cv._verified_resume_skills == []


def test_resume_graph_evidence_is_idempotent_and_excludes_related_tools_and_negation(backend_case):
    from matching_cv.app.services.resume_evidence_matching import enrich_verified_resume_skills

    _, jd, _ = backend_case
    text = "Skills\nJUnit 5, Jenkins.\nExperience\nNever used GitHub Actions. Migrated a payment module."
    cv = _document("CV", text, [])
    cv.explicit.skills = []
    pair = UnifiedExtractFileResponse(run_id="verified-negative", status="completed", cv=cv, jd=jd)
    enriched = enrich_verified_resume_skills(pair, text)

    assert not enriched.cv._verified_resume_skills
    assert enrich_verified_resume_skills(enriched, text) is enriched
    assert pair.cv._verified_resume_skills == []
