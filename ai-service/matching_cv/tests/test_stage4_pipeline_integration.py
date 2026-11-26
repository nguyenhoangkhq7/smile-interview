"""Integration tests for Stage 4 Phase 1: Real Fixture & End-to-End API Pipeline."""
import json
import os
import pytest
from fastapi.testclient import TestClient

from matching_cv.app.main import app
from matching_cv.app.schemas.hetero_graph import (
    GraphBuildRequest,
    GraphBuildResponse,
)
from matching_cv.app.schemas.semantic_reasoning import (
    SkillPairReasoningResult,
    SkillRef,
)
from matching_cv.app.schemas.semantic_representation import (
    EmbeddingGenerateRequest,
)
from matching_cv.app.schemas.unified_skill_extraction import (
    UnifiedExtractFileResponse,
)
from matching_cv.app.services.graph_builder import hetero_graph_builder
from matching_cv.app.services.semantic_representation_service import semantic_representation_service


FRONTEND_FIXTURE_PATH = os.path.join("tests", "fixtures", "02_Frontend_run.json")
SPRINT2_PREDICTIONS_PATH = os.path.join("docs", "verification", "sprint2_phase1_integration_results.json")


@pytest.fixture
def frontend_unified_response() -> UnifiedExtractFileResponse:
    with open(FRONTEND_FIXTURE_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    return UnifiedExtractFileResponse.model_validate(data)


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def test_mode_a_frontend_fixture(frontend_unified_response):
    """Test Mode A (evidence_only) on real 02_Frontend_run fixture."""
    req = GraphBuildRequest(
        unified_response=frontend_unified_response,
        graph_mode="evidence_only",
        edge_policy="trusted_structural_only",
        export_pyg=True,
    )
    g, rep = hetero_graph_builder.build_graph(req)

    assert rep.is_valid
    assert rep.errors == []
    assert len(g.cv_nodes) == 1
    assert len(g.jd_nodes) == 1
    assert len(g.skill_nodes) == 91  # 47 CV skills (40 explicit + 7 implicit) + 44 JD skills (39 explicit + 5 implicit)
    assert len(g.evidence_nodes) == 15
    assert len(g.requirement_nodes) == 15

    # In Mode A, no similarity candidates and no LLM edges
    edge_counts = rep.edge_integrity["edge_counts"]
    assert "similar_to_candidate" not in edge_counts
    assert "equivalent_to" not in edge_counts
    assert "prerequisite_for" not in edge_counts
    assert edge_counts["has_skill"] == 47
    assert edge_counts["requires_skill"] == 44
    assert edge_counts["has_evidence"] == 15
    assert edge_counts["has_requirement"] == 15
    assert edge_counts["mentions_skill"] == 50
    assert edge_counts["supported_by"] == 56

    # Verify PyG Export
    pyg, node_map, summary = hetero_graph_builder.export_to_pyg(g)
    assert summary["total_nodes"] == 1 + 1 + 91 + 15 + 15
    assert summary["total_edges"] == 227
    assert pyg["skill"].num_nodes == 91


def test_mode_b_frontend_with_stage3_embeddings(frontend_unified_response):
    """Test Mode B (similarity_enriched) with real Stage 3 SBERT embeddings and Top-K retrieval."""
    emb_req = EmbeddingGenerateRequest(
        unified_response=frontend_unified_response,
        include_vectors=True,
        compute_similarity=True,
        top_k=5,
    )
    stage3_resp = semantic_representation_service.generate_representations(emb_req)

    req = GraphBuildRequest(
        unified_response=frontend_unified_response,
        stage3_response=stage3_resp,
        graph_mode="similarity_enriched",
        edge_policy="trusted_structural_only",
        export_pyg=True,
    )
    g, rep = hetero_graph_builder.build_graph(req)

    assert rep.is_valid
    assert rep.errors == []
    assert rep.embedding_integrity["nan_count"] == 0
    assert rep.embedding_integrity["inf_count"] == 0
    assert rep.embedding_integrity["nodes_with_vectors"] == 91

    # Similarity edges present
    edge_counts = rep.edge_integrity["edge_counts"]
    assert edge_counts["similar_to_candidate"] > 0
    assert "equivalent_to" not in edge_counts

    # Verify PyG export with similarity edge_attr
    pyg, _, summary = hetero_graph_builder.export_to_pyg(g)
    assert ("skill", "similar_to_candidate", "skill") in pyg.edge_types
    sim_attrs = pyg["skill", "similar_to_candidate", "skill"].edge_attr
    assert sim_attrs is not None
    assert sim_attrs.size(0) == edge_counts["similar_to_candidate"]


def test_mode_c_frontend_with_llm_reasoning(frontend_unified_response):
    """Test Mode C (llm_enriched) with representative pairs on the real Frontend fixture."""
    representative_pairs = [
        # React / React (equivalent)
        SkillPairReasoningResult(
            skill_a=SkillRef(skill_id="react", name="React", source="CV"),
            skill_b=SkillRef(skill_id="react", name="React", source="JD"),
            identity="equivalent",
            relationship=None,
            direction="none",
            reasoning_summary="Same React competency across CV and JD",
            graph_relation_status="eligible",
            model_id="test_llm",
        ),
        # React / React Query (distinct, related)
        SkillPairReasoningResult(
            skill_a=SkillRef(skill_id="react", name="React", source="CV"),
            skill_b=SkillRef(skill_id="react-query", name="React Query", source="JD"),
            identity="distinct",
            relationship="related",
            direction="none",
            reasoning_summary="React Query is a complementary server-state library for React",
            graph_relation_status="eligible",
            model_id="test_llm",
        ),
        # JavaScript / TypeScript (distinct, prerequisite, a_to_b)
        SkillPairReasoningResult(
            skill_a=SkillRef(skill_id="javascript-es6", name="JavaScript (ES6+)", source="CV"),
            skill_b=SkillRef(skill_id="typescript", name="TypeScript", source="JD"),
            identity="distinct",
            relationship="prerequisite",
            direction="a_to_b",
            reasoning_summary="JavaScript is a prerequisite for TypeScript",
            graph_relation_status="eligible",
            model_id="test_llm",
        ),
        # Jest / Playwright (distinct, alternative)
        SkillPairReasoningResult(
            skill_a=SkillRef(skill_id="jest", name="Jest", source="CV"),
            skill_b=SkillRef(skill_id="playwright", name="Playwright", source="JD"),
            identity="distinct",
            relationship="alternative",
            direction="none",
            reasoning_summary="Alternative testing frameworks",
            graph_relation_status="eligible",
            model_id="test_llm",
        ),
    ]

    req = GraphBuildRequest(
        unified_response=frontend_unified_response,
        reasoning_results=representative_pairs,
        graph_mode="llm_enriched",
        edge_policy="eligible_llm_edges",
    )
    g, rep = hetero_graph_builder.build_graph(req)

    assert rep.is_valid
    edge_counts = rep.edge_integrity["edge_counts"]
    assert edge_counts["equivalent_to"] == 2
    assert edge_counts["related_to"] == 2
    assert edge_counts["prerequisite_for"] == 1
    assert edge_counts["alternative_to"] == 2
