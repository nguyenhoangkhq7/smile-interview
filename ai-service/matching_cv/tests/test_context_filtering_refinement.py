"""Unit and integration test suite for Context-Filtering Refinement and Graph Data Preservation.

Reference:
Baghbanzadeh, A., & Wu, D. (2025). Resume-Job Compatibility Scoring Using Graph Neural Networks
and Large Language Models. ICIT 2025. https://doi.org/10.1145/3787330.3787359

Verifies the 12 required audit and regression scenarios:
1. Microservices architectural concept retained.
2. Named order-management microservice remains contextual.
3. Message-driven architecture retained.
4. Containerized deployment workflows retained.
5. Generic reporting workflow not automatically retained.
6. Same surface term under different evidence contexts.
7. No duplicate canonical nodes.
8. Shared-node merging remains correct.
9. All JD requirements are accounted for.
10. Graph integrity and reverse edge symmetry.
11. Proficiency edge attributes preserved.
12. Deterministic filtering and provenance.
"""
from typing import Any, Dict, List
import pytest

from matching_cv.app.schemas.skill_extraction import Evidence, ExtractedSkill, ExtractionResult
from matching_cv.app.schemas.implicit_skill_extraction import ImplicitExtractedSkill, ImplicitExtractionResult
from matching_cv.app.schemas.unified_skill_extraction import (
    DocumentUnifiedResult,
    DocumentValidationResult,
    UnifiedExtractFileResponse,
)
from matching_cv.app.services.competency_granularity import (
    classify_competency_granularity,
    evaluate_competency_retention,
)
from matching_cv.app.services.extraction_adapter import AdaptedSkillItem
from matching_cv.research.data.canonical_skill_normalizer import normalize_canonical_skill
from matching_cv.research.paper_aligned_gnn.graph_builder import PaperAlignedGraphBuilder, PaperAlignedGraphConfig
from matching_cv.research.paper_aligned_gnn.schemas import SkillInputItem


def _make_dummy_doc_pair(
    cv_skills: List[ExtractedSkill],
    jd_skills: List[ExtractedSkill],
    cv_implicit: List[ImplicitExtractedSkill] = None,
    jd_implicit: List[ImplicitExtractedSkill] = None,
) -> UnifiedExtractFileResponse:
    cv_doc = DocumentUnifiedResult.model_construct(
        document_type="CV",
        filename="test_cv.pdf",
        text_sha256="cv_sha256_mock_hash",
        explicit=ExtractionResult.model_construct(
            document_type="CV",
            filename="test_cv.pdf",
            text_sha256="cv_sha256_mock_hash",
            skills=cv_skills,
        ),
        implicit=ImplicitExtractionResult.model_construct(
            document_type="CV",
            filename="test_cv.pdf",
            text_sha256="cv_sha256_mock_hash",
            skills=cv_implicit or [],
        ),
        validation=DocumentValidationResult.model_construct(
            status="completed",
            accepted_implicit_skills=cv_implicit or [],
            duplicate_implicit_skills=[],
            rejected_implicit_skills=[],
        ),
    )
    jd_doc = DocumentUnifiedResult.model_construct(
        document_type="JD",
        filename="test_jd.pdf",
        text_sha256="jd_sha256_mock_hash",
        explicit=ExtractionResult.model_construct(
            document_type="JD",
            filename="test_jd.pdf",
            text_sha256="jd_sha256_mock_hash",
            skills=jd_skills,
        ),
        implicit=ImplicitExtractionResult.model_construct(
            document_type="JD",
            filename="test_jd.pdf",
            text_sha256="jd_sha256_mock_hash",
            skills=jd_implicit or [],
        ),
        validation=DocumentValidationResult.model_construct(
            status="completed",
            accepted_implicit_skills=jd_implicit or [],
            duplicate_implicit_skills=[],
            rejected_implicit_skills=[],
        ),
    )
    return UnifiedExtractFileResponse.model_construct(
        run_id="test_refinement_run",
        status="completed",
        cv=cv_doc,
        jd=jd_doc,
    )


# Scenario 1: Microservices architectural concept retained
def test_scenario_01_microservices_architectural_concept_retained():
    decision = evaluate_competency_retention(
        label="microservices",
        kind="context",
        category="Technical Concept",
        evidence="Backend engineer with 4 years building and scaling Java microservices.",
        side="CV",
    )
    assert decision.should_retain is True
    assert decision.reason_code == "RETAIN_ARCHITECTURAL_CONCEPT"
    assert decision.decision_source == "rule_architectural_capability"
    assert decision.granularity == "atomic_skill"


# Scenario 2: Named order-management microservice remains contextual
def test_scenario_02_named_order_management_microservice_contextual():
    decision = evaluate_competency_retention(
        label="order-management microservice",
        kind="context",
        category=None,
        evidence="Own the order-management microservice handling ~120k orders/day.",
        side="CV",
    )
    assert decision.should_retain is False
    assert decision.reason_code == "FILTER_NAMED_PROJECT_ARTIFACT"
    assert decision.decision_source == "rule_named_artifact"
    assert decision.granularity == "contextual_activity_or_product"


# Scenario 3: Message-driven architecture retained
def test_scenario_03_message_driven_architectures_retained():
    decision = evaluate_competency_retention(
        label="message-driven architectures",
        kind="context",
        category="Technical Concept",
        evidence="Strong background in relational database design, REST API development, and message-driven architectures.",
        side="CV",
    )
    assert decision.should_retain is True
    assert decision.reason_code == "RETAIN_ARCHITECTURAL_CONCEPT"
    assert decision.decision_source == "rule_architectural_capability"
    assert decision.granularity == "compound_competency"


# Scenario 4: Containerized deployment workflows retained
def test_scenario_04_containerized_deployment_workflows_retained():
    decision = evaluate_competency_retention(
        label="containerized deployment workflows",
        kind="skill",
        category="Engineering Practice",
        evidence="Familiarity with Docker and basic containerized deployment workflows.",
        side="JD",
    )
    assert decision.should_retain is True
    assert decision.reason_code == "RETAIN_ENGINEERING_PRACTICE"
    assert decision.decision_source == "rule_engineering_practice"
    assert decision.granularity == "compound_competency"


# Scenario 5: Generic reporting workflow not automatically retained
def test_scenario_05_generic_reporting_workflow_not_retained():
    decision = evaluate_competency_retention(
        label="generic reporting workflow",
        kind="skill",
        category=None,
        evidence="Created a generic reporting workflow for weekly sales statistics.",
        side="CV",
    )
    assert decision.should_retain is False
    assert decision.reason_code == "FILTER_GENERIC_BUSINESS_WORKFLOW"
    assert decision.decision_source == "rule_generic_workflow"
    assert decision.granularity == "contextual_activity_or_product"

    decision_reporting = evaluate_competency_retention(
        label="reporting workflow",
        kind="context",
        evidence="Maintain internal reporting workflow.",
    )
    assert decision_reporting.should_retain is False
    assert decision_reporting.reason_code == "FILTER_GENERIC_BUSINESS_WORKFLOW"


# Scenario 6: Same surface term under different evidence contexts
def test_scenario_06_same_surface_term_different_evidence_contexts():
    # Context A: Candidate has transferable architectural capability
    dec_arch = evaluate_competency_retention(
        label="microservices",
        kind="context",
        category="Technical Concept",
        evidence="Extensive experience architecting and building microservices in fintech.",
        side="CV",
    )
    assert dec_arch.should_retain is True
    assert dec_arch.reason_code == "RETAIN_ARCHITECTURAL_CONCEPT"

    # Context B: Candidate assigned to tickets in a specific named service
    dec_assignment = evaluate_competency_retention(
        label="microservice",
        kind="context",
        category=None,
        evidence="Assigned to the payment microservice to investigate production deadlock tickets.",
        side="CV",
    )
    assert dec_assignment.should_retain is False
    assert dec_assignment.reason_code == "FILTER_CONTEXT_ARTIFACT_EVIDENCE"
    assert dec_assignment.decision_source == "evidence_context_analysis"


# Scenario 7: No duplicate canonical nodes
def test_scenario_07_no_duplicate_canonical_nodes():
    cv_skills = [
        ExtractedSkill(
            skill_id="microservices",
            surface_forms=["microservices"],
            category="Technical Concept",
            kind="context",
            evidences=[Evidence(surface_form="microservices", sentence="Building microservices.", section="summary")],
        ),
        ExtractedSkill(
            skill_id="microservices",
            surface_forms=["Microservices Architecture"],
            category="Technical Concept",
            kind="skill",
            evidences=[Evidence(surface_form="Microservices Architecture", sentence="Microservices architecture.", section="skills")],
        ),
    ]
    resp = _make_dummy_doc_pair(cv_skills=cv_skills, jd_skills=[])
    builder = PaperAlignedGraphBuilder()
    graph_data, report = builder.build_graph(unified_response=resp)

    # Should only produce 1 canonical node for 'microservices'
    micro_nodes = [n for n in graph_data.skill_nodes.values() if n.canonical_skill_id == "microservices"]
    assert len(micro_nodes) == 1
    assert report.is_valid is True


# Scenario 8: Shared-node merging remains correct
def test_scenario_08_shared_node_merging_correct():
    cv_skills = [
        ExtractedSkill(
            skill_id="java",
            surface_forms=["Java"],
            category="Technology/Tool",
            kind="skill",
            evidences=[Evidence(surface_form="Java", sentence="Proficient in Java.", section="summary")],
        ),
        ExtractedSkill(
            skill_id="microservices",
            surface_forms=["microservices"],
            category="Technical Concept",
            kind="context",
            evidences=[Evidence(surface_form="microservices", sentence="Building microservices.", section="summary")],
        ),
    ]
    jd_skills = [
        ExtractedSkill(
            skill_id="java",
            surface_forms=["Java"],
            category="Technology/Tool",
            kind="skill",
            evidences=[Evidence(surface_form="Java", sentence="Requires Java expertise.", section="requirements")],
        ),
        ExtractedSkill(
            skill_id="restful-microservices",
            surface_forms=["RESTful microservices"],
            category="Technical Concept",
            kind="skill",
            evidences=[Evidence(surface_form="RESTful microservices", sentence="Design RESTful microservices.", section="requirements")],
        ),
    ]
    resp = _make_dummy_doc_pair(cv_skills=cv_skills, jd_skills=jd_skills)
    builder = PaperAlignedGraphBuilder()
    graph_data, report = builder.build_graph(unified_response=resp)

    # 'java' is shared
    java_node = next(n for n in graph_data.skill_nodes.values() if n.canonical_skill_id == "java")
    assert java_node.membership == "shared"
    assert set(java_node.source_documents) == {"CV", "JD"}

    # 'microservices' and 'restful-microservices' are NOT merged under verified equivalence
    cv_micro = next(n for n in graph_data.skill_nodes.values() if n.canonical_skill_id == "microservices")
    assert cv_micro.membership == "resume_only"

    jd_micro = next(n for n in graph_data.skill_nodes.values() if n.canonical_skill_id == "restful-microservices")
    assert jd_micro.membership == "job_only"


# Scenario 9: All JD requirements are accounted for
def test_scenario_09_all_jd_requirements_accounted_for():
    jd_skills = [
        ExtractedSkill(
            skill_id="docker",
            surface_forms=["Docker"],
            category="Technology/Tool",
            kind="skill",
            evidences=[Evidence(surface_form="Docker", sentence="Experience with Docker.", section="requirements")],
        ),
        ExtractedSkill(
            skill_id="containerized-deployment-workflows",
            surface_forms=["containerized deployment workflows"],
            category="Engineering Practice",
            kind="skill",
            evidences=[Evidence(surface_form="containerized deployment workflows", sentence="Containerized deployment workflows.", section="requirements")],
        ),
        ExtractedSkill(
            skill_id="production-environment",
            surface_forms=["production environment"],
            category=None,
            kind="context",
            evidences=[Evidence(surface_form="production environment", sentence="In a production environment.", section="requirements")],
        ),
    ]
    resp = _make_dummy_doc_pair(cv_skills=[], jd_skills=jd_skills)
    builder = PaperAlignedGraphBuilder()
    graph_data, report = builder.build_graph(unified_response=resp)

    canon_ids = {n.canonical_skill_id for n in graph_data.skill_nodes.values()}
    # Docker and containerized deployment workflows must be present
    assert "docker" in canon_ids
    assert "containerized-deployment-workflows" in canon_ids
    # Production environment must be filtered
    assert "production-environment" not in canon_ids

    # Lineage must account for all 3
    lineage = graph_data.diagnostics["competency_lineage"]
    jd_lineage = [r for r in lineage if r["source_side"] == "JD"]
    assert len(jd_lineage) == 3
    assert {r["canonical_id"] for r in jd_lineage} == {"docker", "containerized-deployment-workflows", "production-environment"}


# Scenario 10: Graph integrity and reverse edge symmetry
def test_scenario_10_graph_integrity_and_reverse_edge_symmetry():
    cv_skills = [
        ExtractedSkill(
            skill_id="microservices",
            surface_forms=["microservices"],
            category="Technical Concept",
            kind="context",
            evidences=[Evidence(surface_form="microservices", sentence="Building microservices.", section="summary")],
        ),
    ]
    jd_skills = [
        ExtractedSkill(
            skill_id="containerized-deployment-workflows",
            surface_forms=["containerized deployment workflows"],
            category="Engineering Practice",
            kind="skill",
            evidences=[Evidence(surface_form="containerized deployment workflows", sentence="Containerized deployment workflows.", section="requirements")],
        ),
    ]
    resp = _make_dummy_doc_pair(cv_skills=cv_skills, jd_skills=jd_skills)
    builder = PaperAlignedGraphBuilder()
    graph_data, report = builder.build_graph(unified_response=resp)

    assert report.is_valid is True
    assert report.no_unintended_doc_doc_or_skill_skill_edges is True
    assert report.every_entity_belongs_to_at_least_one_doc is True

    # Check reverse edge symmetry: every forward edge has an exact matching reverse edge
    fwd_edges = [e for e in graph_data.edges if not e.is_reverse_edge]
    rev_edges = [e for e in graph_data.edges if e.is_reverse_edge]
    assert len(fwd_edges) == len(rev_edges) == 2
    assert len(graph_data.edges) == 4

    for fwd in fwd_edges:
        matching_rev = [
            r for r in rev_edges
            if r.source_id == fwd.target_id and r.target_id == fwd.source_id and r.tensor_weight == fwd.tensor_weight
        ]
        assert len(matching_rev) == 1


# Scenario 11: Proficiency edge attributes preserved
def test_scenario_11_proficiency_edge_attributes_preserved():
    cv_skills = [
        ExtractedSkill(
            skill_id="kubernetes",
            surface_forms=["Kubernetes"],
            category="Technology/Tool",
            kind="skill",
            evidences=[Evidence(surface_form="Kubernetes", sentence="Basic Kubernetes experience.", modifier_text="basic", section="skills")],
        ),
    ]
    resp = _make_dummy_doc_pair(cv_skills=cv_skills, jd_skills=[])
    builder = PaperAlignedGraphBuilder()
    graph_data, report = builder.build_graph(unified_response=resp)

    edges = [e for e in graph_data.edges if not e.is_reverse_edge]
    assert len(edges) == 1
    edge = edges[0]
    assert edge.proficiency.is_missing is False
    assert edge.proficiency.numeric_level == 1.0
    assert edge.proficiency.normalized_weight == 0.1
    assert edge.tensor_weight == pytest.approx(0.1)


# Scenario 12: Deterministic filtering and provenance
def test_scenario_12_deterministic_filtering_and_provenance():
    cv_skills = [
        ExtractedSkill(
            skill_id="microservices",
            surface_forms=["microservices"],
            category="Technical Concept",
            kind="context",
            evidences=[Evidence(surface_form="microservices", sentence="Building microservices.", section="summary")],
        ),
        ExtractedSkill(
            skill_id="order-management-microservice",
            surface_forms=["order-management microservice"],
            category=None,
            kind="context",
            evidences=[Evidence(surface_form="order-management microservice", sentence="Own order microservice.", section="experience")],
        ),
    ]
    resp = _make_dummy_doc_pair(cv_skills=cv_skills, jd_skills=[])
    builder = PaperAlignedGraphBuilder()
    graph_data, report = builder.build_graph(unified_response=resp)

    lineage = graph_data.diagnostics.get("competency_lineage", [])
    assert len(lineage) == 2

    recs_by_id = {r["canonical_id"]: r for r in lineage}
    assert recs_by_id["microservices"]["retention_decision"] == "RETAINED"
    assert recs_by_id["microservices"]["reason_code"] == "RETAIN_ARCHITECTURAL_CONCEPT"
    assert recs_by_id["microservices"]["is_graph_node"] is True
    assert recs_by_id["microservices"]["is_membership"] is True

    assert recs_by_id["order-management-microservice"]["retention_decision"] == "EXCLUDED"
    assert recs_by_id["order-management-microservice"]["reason_code"] == "FILTER_NAMED_PROJECT_ARTIFACT"
    assert recs_by_id["order-management-microservice"]["is_graph_node"] is False
    assert recs_by_id["order-management-microservice"]["is_membership"] is False

    summary = graph_data.diagnostics.get("competency_lineage_summary", {})
    assert summary["total_input_records"] == 2
    assert summary["retained_records"] == 1
    assert summary["excluded_records"] == 1
