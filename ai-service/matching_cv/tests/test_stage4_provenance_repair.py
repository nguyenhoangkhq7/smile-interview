"""Graph construction and provenance safeguards used by the analyze pipeline."""
import json
import os
import pytest
from matching_cv.app.schemas.hetero_graph import GraphBuildRequest
from matching_cv.app.schemas.semantic_reasoning import (
    SkillPairReasoningResult,
    SkillRef,
)
from matching_cv.app.schemas.semantic_representation import EmbeddingGenerateRequest
from matching_cv.app.schemas.unified_skill_extraction import UnifiedExtractFileResponse
from matching_cv.app.services.graph_builder import hetero_graph_builder
from matching_cv.app.services.semantic_representation_service import semantic_representation_service

FIXTURE_PATH = os.path.join("tests", "fixtures", "02_Frontend_run.json")


@pytest.fixture(scope="module")
def frontend_unified():
    with open(FIXTURE_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    return UnifiedExtractFileResponse.model_validate(data)


@pytest.fixture(scope="module")
def frontend_stage3(frontend_unified):
    emb_req = EmbeddingGenerateRequest(
        unified_response=frontend_unified,
        include_vectors=True,
        compute_similarity=True,
        top_k=5,
    )
    return semantic_representation_service.generate_representations(emb_req)


def test_hardcoded_inference_prevention(frontend_unified, frontend_stage3):
    """Verify that building a graph without reasoning inputs creates zero synthetic LLM edges."""
    req = GraphBuildRequest(
        unified_response=frontend_unified,
        stage3_response=frontend_stage3,
        graph_mode="evidence_only",
        edge_policy="trusted_structural_only",
    )
    graph_data, report = hetero_graph_builder.build_graph(req)

    # Ensure no LLM semantic edges exist
    llm_types = {"equivalent_to", "related_to", "prerequisite_for", "specialization_of", "alternative_to"}
    semantic_edges = [e for e in graph_data.edges if e.edge_type in llm_types]
    assert len(semantic_edges) == 0, f"Expected 0 semantic edges in Mode A, found {len(semantic_edges)}"

    # Ensure no synthetic Jest <-> Playwright edges exist
    jest_playwright = [
        e for e in graph_data.edges
        if "jest" in e.source_id.lower() and "playwright" in e.target_id.lower()
    ]
    assert len(jest_playwright) == 0


def test_boundary_provenance_sanitization(frontend_unified):
    """Verify that model_knowledge + context_verified without contextual text is sanitized at graph boundary."""
    # Fabricate an invalid pair with no context but claiming context_verified
    bogus_pair = SkillPairReasoningResult(
        skill_a=SkillRef(skill_id="react", name="React", source="CV", context=None),
        skill_b=SkillRef(skill_id="react-query", name="React Query", source="JD", context=None),
        identity="distinct",
        relationship="related",
        direction="none",
        reasoning_summary="Test sanity check",
        evidence_basis="model_knowledge",
        verification_status="context_verified",  # Contradiction: no context!
        graph_relation_status="eligible",
        model_id="test-model",
        prompt_version="test-v1",
    )

    req = GraphBuildRequest(
        unified_response=frontend_unified,
        reasoning_results=[bogus_pair],
        graph_mode="llm_enriched",
        edge_policy="eligible_llm_edges",
    )
    graph_data, report = hetero_graph_builder.build_graph(req)

    # Check that provenance sanitization occurred
    sanitizations = [a for a in graph_data.rejected_audit if a.get("entity_type") == "provenance_sanitization"]
    assert len(sanitizations) > 0
    assert sanitizations[0]["action"] == "downgraded_verification_status"
    assert sanitizations[0]["new_status"] == "model_inferred"

    # Verify edge attributes reflect the downgraded status
    rel_edges = [e for e in graph_data.edges if e.edge_type == "related_to"]
    assert len(rel_edges) > 0
    for e in rel_edges:
        assert e.attributes["verification_status"] == "model_inferred"


def test_ambiguous_endpoint_mapping_rejection(frontend_unified):
    """Verify that multiple matching candidate occurrences without occurrence_id are rejected as ambiguous."""
    # Test ambiguous endpoint rejection directly on _resolve_node_ids
    from matching_cv.app.schemas.hetero_graph import HeteroGraphData, SkillNode

    graph_data = HeteroGraphData(
        graph_id="test_ambig",
        run_id="run_test",
        mode="llm_enriched",
        edge_policy="eligible_llm_edges",
        cv_nodes={},
        jd_nodes={},
        skill_nodes={
            "occ_cv_react_1": SkillNode(
                node_id="occ_cv_react_1",
                skill_occurrence_id="occ_cv_react_1",
                original_label="React",
                canonical_skill_id="react",
                source_document="CV",
                explicit_or_implicit="explicit",
                source_identifier="doc_cv",
            ),
            "occ_cv_react_2": SkillNode(
                node_id="occ_cv_react_2",
                skill_occurrence_id="occ_cv_react_2",
                original_label="React",
                canonical_skill_id="react",
                source_document="CV",
                explicit_or_implicit="implicit",
                source_identifier="doc_cv",
            ),
        },
        evidence_nodes={},
        requirement_nodes={},
        edges=[],
        rejected_audit=[],
    )

    slug_map = {"react": ["occ_cv_react_1", "occ_cv_react_2"]}
    label_map = {"react": ["occ_cv_react_1", "occ_cv_react_2"]}

    # Case A: With unambiguous occurrence ID, resolution succeeds
    ref_with_id = SkillRef(skill_id="react", name="React", source="CV")
    res_a = hetero_graph_builder._resolve_node_ids(
        ref_with_id,
        source_occurrence_ids=["occ_cv_react_1"],
        occurrence_idx=0,
        graph_data=graph_data,
        slug_map=slug_map,
        label_map=label_map,
    )
    assert res_a == ["occ_cv_react_1"]

    # Case B: Without occurrence ID and multiple candidates exist, resolution fails and logs ambiguous audit
    ref_ambig = SkillRef(skill_id="react", name="React", source="CV")
    res_b = hetero_graph_builder._resolve_node_ids(
        ref_ambig,
        source_occurrence_ids=[],  # No occurrence ID provided
        occurrence_idx=0,
        graph_data=graph_data,
        slug_map=slug_map,
        label_map=label_map,
    )
    assert res_b == []
    ambig_audits = [a for a in graph_data.rejected_audit if a.get("entity_type") == "ambiguous_endpoint_mapping"]
    assert len(ambig_audits) > 0
    assert "Multiple occurrences" in ambig_audits[0]["reason"]
