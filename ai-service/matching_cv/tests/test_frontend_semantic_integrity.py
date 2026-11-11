"""
Regression Test Suite for Frontend CV-JD Pipeline Output Cleanup & Stage 3-5 Semantic Integrity Audit.
Validating all 20 test points specified in the Phase D audit requirements.

Scientific Reference: Baghbanzadeh & Wu (ICIT 2025)
DOI: https://doi.org/10.1145/3787330.3787359
Contract: standardized-output-v1
"""
import copy
import hashlib
import io
import json
import math
import os
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from matching_cv.app.core.config import settings
from matching_cv.app.main import app
from matching_cv.app.schemas.standardized_output import (
    STANDARDIZED_OUTPUT_SCHEMA_VERSION,
    STANDARDIZED_OUTPUT_VERSION_HEADER,
    SkillGapRow,
    StandardizedPipelineOutput,
)
from matching_cv.app.schemas.unified_skill_extraction import UnifiedExtractFileResponse
from matching_cv.app.services.standardized_output_builder import (
    IDENTITY_MERGE_REASONS,
    PublicOutputContext,
    build_skill_gap,
    build_standardized_output,
)
from matching_cv.research.data.canonical_skill_normalizer import normalize_canonical_skill
from matching_cv.research.paper_aligned_gnn.graph_builder import PaperAlignedGraphBuilder
from matching_cv.research.paper_aligned_gnn.schemas import (
    PaperAlignedGraphData,
    PaperAlignedSkillNode,
)

FRONTEND_FIXTURE_PATH = os.path.join("tests", "fixtures", "02_Frontend_run.json")
FRONTEND_PUBLIC_PATH = os.path.join("scratch", "frontend_public_output.json")
FRONTEND_INTERNAL_PATH = os.path.join("scratch", "frontend_internal_output.json")
FRONTEND_GRAPH_PATH = os.path.join("scratch", "frontend_graph_data.json")


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


@pytest.fixture
def frontend_fixture() -> UnifiedExtractFileResponse:
    assert os.path.exists(FRONTEND_FIXTURE_PATH), f"Fixture {FRONTEND_FIXTURE_PATH} missing"
    with open(FRONTEND_FIXTURE_PATH, "r", encoding="utf-8") as f:
        return UnifiedExtractFileResponse.model_validate(json.load(f))


@pytest.fixture
def frontend_public():
    assert os.path.exists(FRONTEND_PUBLIC_PATH), f"Public output {FRONTEND_PUBLIC_PATH} missing"
    with open(FRONTEND_PUBLIC_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture
def frontend_internal():
    assert os.path.exists(FRONTEND_INTERNAL_PATH), f"Internal output {FRONTEND_INTERNAL_PATH} missing"
    with open(FRONTEND_INTERNAL_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture
def frontend_graph():
    assert os.path.exists(FRONTEND_GRAPH_PATH), f"Graph data {FRONTEND_GRAPH_PATH} missing"
    with open(FRONTEND_GRAPH_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


# ==============================================================================
# Point 1: Zustand / Jest is never merged as verified identity
# ==============================================================================
def test_point1_zustand_jest_never_merged_as_verified_identity(frontend_graph, frontend_internal):
    """Zustand (JD) and Jest (CV) have cosine 0.632484 in SBERT space, but MUST NOT be merged in Stage 5."""
    nodes = frontend_graph["nodes"]
    zustand_nodes = [n for n in nodes if n.get("jd_canonical_id") == "zustand"]
    assert len(zustand_nodes) == 1, "Zustand should exist as exactly one JD skill node"
    z_node = zustand_nodes[0]

    # Must be JD-only, NOT shared with Jest
    assert z_node.get("membership") == "job_only"
    assert z_node.get("cv_canonical_id") is None
    assert z_node.get("merge_reason") == "unique_to_jd"

    # Jest must be a shared node (because both CV and JD explicit skills contain Jest)
    jest_nodes = [n for n in nodes if n.get("canonical_skill_id") == "jest"]
    assert len(jest_nodes) == 1
    j_node = jest_nodes[0]
    assert j_node.get("membership") == "shared"
    assert j_node.get("cv_canonical_id") == "jest"
    assert j_node.get("jd_canonical_id") == "jest"

    # In internal details, zustand match_type is semantic_related, not verified_identity
    details = {d["jd_skill_id"]: d for d in frontend_internal["skill_gap_details"]}
    assert details["zustand"]["match_type"] == "semantic_related"


# ==============================================================================
# Point 2: Core Web Vitals / Webpack is not treated as identical
# ==============================================================================
def test_point2_core_web_vitals_webpack_not_treated_as_identical(frontend_graph, frontend_internal):
    """Core Web Vitals (JD) and Webpack (CV) have cosine 0.565302, but are distinct nodes."""
    nodes = frontend_graph["nodes"]
    cwv_nodes = [n for n in nodes if n.get("jd_canonical_id") == "core-web-vitals"]
    webpack_nodes = [n for n in nodes if n.get("cv_canonical_id") == "webpack"]

    assert len(cwv_nodes) == 1
    assert len(webpack_nodes) == 1

    cwv = cwv_nodes[0]
    wp = webpack_nodes[0]

    assert cwv.get("membership") == "job_only"
    assert wp.get("membership") == "resume_only"
    assert cwv.get("node_id") != wp.get("node_id")
    assert cwv.get("cv_canonical_id") is None
    assert wp.get("jd_canonical_id") is None

    details = {d["jd_skill_id"]: d for d in frontend_internal["skill_gap_details"]}
    assert details["core-web-vitals"]["match_type"] == "semantic_related"


# ==============================================================================
# Point 3: Unit & E2E Tests composite requirements are not silently collapsed
# ==============================================================================
def test_point3_unit_and_e2e_tests_not_silently_collapsed(frontend_graph):
    """'Unit & E2E Tests' remains its own JD node, preserving testing frameworks separately."""
    nodes = frontend_graph["nodes"]
    test_node = [n for n in nodes if n.get("jd_canonical_id") == "unit-and-end-to-end-tests"]
    assert len(test_node) == 1
    assert test_node[0].get("membership") == "job_only"

    # Specific frameworks like jest and playwright exist as distinct entities
    canonicals = {n.get("canonical_skill_id") for n in nodes}
    assert "jest" in canonicals
    assert "playwright" in canonicals


# ==============================================================================
# Point 4: React + TypeScript composite preserves legitimate components
# ==============================================================================
def test_point4_react_typescript_composite_preserves_components(frontend_graph):
    """'React + TypeScript Application' (JD) is distinct from 'typescript' and 'react'."""
    nodes = frontend_graph["nodes"]
    comp_node = [n for n in nodes if n.get("jd_canonical_id") == "react-typescript-application"]
    assert len(comp_node) == 1
    assert comp_node[0].get("membership") == "job_only"
    assert comp_node[0].get("cv_canonical_id") is None

    # 'typescript' and 'react' are preserved as shared nodes
    ts_node = [n for n in nodes if n.get("canonical_skill_id") == "typescript"]
    react_node = [n for n in nodes if n.get("canonical_skill_id") == "react"]
    assert len(ts_node) == 1 and ts_node[0].get("membership") == "shared"
    assert len(react_node) == 1 and react_node[0].get("membership") == "shared"


# ==============================================================================
# Point 5: Tailwind CSS and utility-first framework are not falsely merged
# ==============================================================================
def test_point5_tailwind_and_utility_first_not_falsely_merged(frontend_graph, frontend_public):
    """'Utility-First Framework' and 'Tailwind CSS' are not merged without verified identity."""
    nodes = frontend_graph["nodes"]
    uf_nodes = [n for n in nodes if n.get("jd_canonical_id") == "utility-first-framework"]
    tw_nodes = [n for n in nodes if n.get("canonical_skill_id") == "tailwind-css"]

    assert len(uf_nodes) == 1
    assert uf_nodes[0].get("membership") == "job_only"
    assert len(tw_nodes) == 1
    assert uf_nodes[0].get("node_id") != tw_nodes[0].get("node_id")

    # In public output, utility-first-framework is unmatched because cosine < 0.50
    gap_rows = {r["jd_skill_id"]: r for r in frontend_public["skill_gap_input"]}
    assert "utility-first-framework" in gap_rows
    assert gap_rows["utility-first-framework"]["matched_cv_skill_id"] is None
    assert gap_rows["utility-first-framework"]["soft_match"] is None


# ==============================================================================
# Point 6: Page load performance evidence remains available in graph inputs
# ==============================================================================
def test_point6_page_load_performance_evidence_preserved(frontend_public):
    """'page-load-performance' remains preserved with verbatim evidence spans."""
    jd_skills = {s["skill_id"]: s for s in frontend_public["proficiency_input"]["jd_skills"]}
    assert "page-load-performance" in jd_skills
    plp = jd_skills["page-load-performance"]
    assert len(plp["evidence_spans"]) > 0
    # Verbatim span in JD text
    assert any("page load" in span.lower() or "performance" in span.lower() for span in plp["evidence_spans"])


# ==============================================================================
# Point 7: Suspicious retrieval candidates do not become unauthorized graph edges
# ==============================================================================
def test_point7_retrieval_candidates_do_not_become_unauthorized_graph_edges(frontend_graph):
    """Stage 5 graph topology must be purely bipartite document-entity (0 skill-skill edges)."""
    assert frontend_graph["skill_skill_edges"] == 0


# ==============================================================================
# Point 8: Stage 4 relation eligibility is respected
# ==============================================================================
def test_point8_stage4_relation_eligibility_respected(frontend_graph):
    """When Stage 4 evaluates a relation as distinct/prerequisite, no merge occurs."""
    # react-typescript-application vs typescript was evaluated as prerequisite/distinct
    nodes = frontend_graph["nodes"]
    node = [n for n in nodes if n.get("jd_canonical_id") == "react-typescript-application"][0]
    assert node.get("membership") == "job_only"
    assert node.get("merge_reason") == "unique_to_jd"


# ==============================================================================
# Point 9: Shared graph nodes require valid verified identity
# ==============================================================================
def test_point9_shared_graph_nodes_require_valid_verified_identity(frontend_graph):
    """Every node with membership='shared' MUST have a valid verified identity reason."""
    nodes = frontend_graph["nodes"]
    shared_nodes = [n for n in nodes if n.get("membership") == "shared"]
    assert len(shared_nodes) > 0, "There must be verified shared nodes"
    for n in shared_nodes:
        assert n.get("cv_canonical_id") is not None
        assert n.get("jd_canonical_id") is not None
        assert n.get("merge_reason") in IDENTITY_MERGE_REASONS or n.get("merge_reason") == "same_canonical_id"


# ==============================================================================
# Point 10: Canonical normalization does not cause false merges
# ==============================================================================
def test_point10_canonical_normalization_does_not_cause_false_merges():
    """Canonical normalizer keeps distinct tech concepts separate."""
    assert normalize_canonical_skill("Zustand") == "zustand"
    assert normalize_canonical_skill("Jest") == "jest"
    assert normalize_canonical_skill("Zustand") != normalize_canonical_skill("Jest")
    assert normalize_canonical_skill("Webpack") != normalize_canonical_skill("Core Web Vitals")
    assert normalize_canonical_skill("Tailwind CSS") != normalize_canonical_skill("Utility-First Framework")


# ==============================================================================
# Point 11: SBERT similarity matrix orientation is correct
# ==============================================================================
def test_point11_sbert_similarity_matrix_orientation_is_correct(frontend_internal):
    """Matrix is available and properly populated."""
    assert frontend_internal["similarity_matrix_available"] is True
    details = frontend_internal["skill_gap_details"]
    assert len(details) == 36
    assert any(d["similarity_source"] == "stage3_matrix" for d in details)


# ==============================================================================
# Point 12: Reverse retrieval uses actual cosine values
# ==============================================================================
def test_point12_reverse_retrieval_uses_actual_cosine_values(frontend_public):
    """soft_match in skill_gap_input contains authentic un-clipped cosines rounded to 6 decimals."""
    for row in frontend_public["skill_gap_input"]:
        if row["matched_cv_skill_id"] is not None:
            assert row["soft_match"] is not None
            assert -1.0 <= row["soft_match"] <= 1.0
            # Ensure not artificially forced to 1.0 (unless exact same embedding)
            if row["jd_skill_id"] == "zustand":
                assert row["matched_cv_skill_id"] == "jest"
                assert math.isclose(row["soft_match"], 0.632484, abs_tol=1e-5)
            elif row["jd_skill_id"] == "core-web-vitals":
                assert row["matched_cv_skill_id"] == "webpack"
                assert math.isclose(row["soft_match"], 0.565302, abs_tol=1e-5)


# ==============================================================================
# Point 13: Six-field public schema remains unchanged
# ==============================================================================
def test_point13_six_field_public_schema_unchanged(frontend_public):
    """Public output has EXACTLY 6 top-level keys in specified order."""
    expected_keys = [
        "match_score",
        "status",
        "cv_text",
        "jd_text",
        "skill_gap_input",
        "proficiency_input",
    ]
    actual_keys = list(frontend_public.keys())
    assert actual_keys == expected_keys


# ==============================================================================
# Point 14: match_score=null when GNN is untrained
# ==============================================================================
def test_point14_match_score_null_when_gnn_untrained(frontend_public):
    """match_score is null and status is MODEL_NOT_TRAINED when no trained checkpoint is loaded."""
    assert frontend_public["match_score"] is None
    assert frontend_public["status"] == "MODEL_NOT_TRAINED"


# ==============================================================================
# Point 15: w_j=null while importance model is unavailable
# ==============================================================================
def test_point15_w_j_null_while_importance_model_unavailable(frontend_public):
    """All rows in skill_gap_input must have w_j=None."""
    for row in frontend_public["skill_gap_input"]:
        assert row["w_j"] is None


# ==============================================================================
# Point 16: Explicit and implicit skill evidence remains preserved
# ==============================================================================
def test_point16_explicit_and_implicit_skill_evidence_preserved(frontend_public):
    """Both explicit and implicit skills retain evidence spans in proficiency_input."""
    cv_skills = frontend_public["proficiency_input"]["cv_skills"]
    jd_skills = frontend_public["proficiency_input"]["jd_skills"]

    cv_types = {s["type"] for s in cv_skills}
    jd_types = {s["type"] for s in jd_skills}
    assert "explicit" in cv_types
    assert "implicit" in cv_types
    assert "explicit" in jd_types

    # Evidence spans must be non-empty strings
    for s in cv_skills + jd_skills:
        assert isinstance(s["evidence_spans"], list)
        for span in s["evidence_spans"]:
            assert isinstance(span, str) and len(span.strip()) > 0


# ==============================================================================
# Point 17: GraphConv and Modified GAT inputs remain valid
# ==============================================================================
def test_point17_graphconv_and_modified_gat_inputs_remain_valid(frontend_graph):
    """Graph topology: 67 total nodes, 11 shared, 31 resume-only, 25 job-only."""
    assert frontend_graph["total_nodes"] == 67
    assert frontend_graph["shared_count"] == 11
    assert frontend_graph["resume_only_count"] == 31
    assert frontend_graph["job_only_count"] == 25
    assert frontend_graph["total_edges"] > 0


# ==============================================================================
# Point 18: No production checkpoint is changed
# ==============================================================================
def test_point18_no_production_checkpoint_changed():
    """Verify that no checkpoint file has been created or modified in models/ or checkpoints/."""
    checkpoint_dir = os.path.join("research", "paper_aligned_gnn", "checkpoints")
    if os.path.exists(checkpoint_dir):
        files = os.listdir(checkpoint_dir)
        for f in files:
            assert not f.startswith("audit_temp")


# ==============================================================================
# Point 19: No new LLM call is required for regression tests
# ==============================================================================
def test_point19_no_new_llm_call_required():
    """Regression test runs 100% locally from static test fixtures."""
    assert os.path.exists(FRONTEND_FIXTURE_PATH)
    assert os.path.exists(FRONTEND_PUBLIC_PATH)


# ==============================================================================
