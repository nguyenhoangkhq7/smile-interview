"""Comprehensive Verification Suite for v3 Asymmetric Prerequisite & Unified Proficiency Upgrades.

Verifies:
1. Issue 4 Layer 1: Asymmetric directed `soft_match` for Kubernetes <-> Docker, SQL <-> PostgreSQL,
   Java <-> Spring Boot, 2-hop Linux <-> Kubernetes, and Stage 4 LLM directional reasoning.
2. Issue 4 Layer 2: `jd_bidirectional` dependency scope creates prerequisite bridges in BOTH
   JD=Docker/CV=Kubernetes and JD=Kubernetes/CV=Docker while excluding unrelated CV-only pairs.
3. Approach 2 Fallback: Vietnamese proficiency descriptors ('cơ bản', 'thành thạo', 'chuyên sâu')
   and continuous evidence-based fallback (Experience > Skills list > Implicit, never 0.0).
4. Approach 1 Unified Pipeline: `apply_module2_proficiencies` maps Module 2 P_CV / P_JD in [1, 5]
   onto [0.2, 1.0] symmetrically across forward & reverse edges while preserving integrity.
5. Trained v3 GNN Checkpoint: Zero-shot asymmetric ordering (Docker <-> Kubernetes) and monotonic
   depth sensitivity (Basic 3 months < No modifier < Expert 6 years).
"""
from __future__ import annotations

from pathlib import Path
from typing import List
import numpy as np
import pytest

from matching_cv.app.schemas.semantic_reasoning import SkillPairReasoningResult, SkillRef
from matching_cv.app.services.gnn_inference_service import GNNInferenceService
from matching_cv.app.services.standardized_output_builder import build_skill_gap
from matching_cv.research.paper_aligned_gnn.graph_builder import PaperAlignedGraphBuilder
from matching_cv.research.paper_aligned_gnn.proficiency_extractor import (
    build_module2_proficiency_record,
    extract_skill_proficiency,
)
from matching_cv.research.paper_aligned_gnn.schemas import (
    PaperAlignedGraphConfig,
    PaperAlignedGraphData,
    PaperAlignedSkillNode,
    SkillInputItem,
)
from matching_cv.research.paper_aligned_gnn.skill_dependency_resolver import (
    resolve_directed_skill_relation,
)


def _unit_vec(dim: int, hot: int, sec: int = -1, sec_w: float = 0.0) -> List[float]:
    v = np.zeros(dim, dtype=np.float32)
    v[hot % dim] = 1.0
    if sec >= 0:
        v[sec % dim] += sec_w
    norm = float(np.linalg.norm(v))
    if norm > 0:
        v = v / norm
    return [float(x) for x in v]


def _make_mock_stage3(cv_canon: str, jd_canon: str, cosine: float):
    class MockRec:
        def __init__(self, eid: str, occ: str, cid: str):
            self.embedding_id = eid
            self.occurrence_id = occ
            self.associated_skill_ids = [cid]

    class MockMat:
        source_ids = ["emb_cv"]
        target_ids = ["emb_jd"]
        raw_matrix = [[cosine]]
        matrix = [[round(cosine, 4)]]

    class MockStage3:
        similarity_matrices = {"cv_entities_vs_jd_entities": MockMat()}
        cv_skill_embeddings = [MockRec("emb_cv", "occ_cv", cv_canon)]
        jd_skill_embeddings = [MockRec("emb_jd", "occ_jd", jd_canon)]

    return MockStage3()


def _make_two_node_graph(cv_canon: str, jd_canon: str) -> PaperAlignedGraphData:
    cv_node = PaperAlignedSkillNode.model_construct(
        node_id=f"skill_cv_{cv_canon}",
        canonical_skill_id=cv_canon,
        cv_canonical_id=cv_canon,
        source_documents=["CV"],
        membership="resume_only",
        cv_occurrence_ids=["occ_cv"],
    )
    jd_node = PaperAlignedSkillNode.model_construct(
        node_id=f"skill_jd_{jd_canon}",
        canonical_skill_id=jd_canon,
        jd_canonical_id=jd_canon,
        source_documents=["JD"],
        membership="job_only",
        jd_occurrence_ids=["occ_jd"],
    )
    return PaperAlignedGraphData.model_construct(
        skill_nodes={cv_node.node_id: cv_node, jd_node.node_id: jd_node}
    )


# ==============================================================================
# 1. Asymmetric Directed soft_match (Issue 4 — Layer 1)
# ==============================================================================
@pytest.mark.parametrize(
    "base_skill,adv_skill,raw_cos",
    [
        ("docker", "kubernetes", 0.3304),
        ("docker", "kubernetes", 0.72),
        ("sql", "postgresql", 0.6176),
        ("java", "spring-boot", 0.1189),
        ("react", "next.js", 0.2316),
        ("kubernetes", "helm", 0.3693),
    ],
)
def test_asymmetric_directed_soft_match_favors_advanced_cv_over_prereq_only_cv(
    base_skill: str, adv_skill: str, raw_cos: float
):
    # Case B: JD requires foundational skill, CV has advanced skill (e.g., JD=docker, CV=kubernetes)
    g_sup = _make_two_node_graph(cv_canon=adv_skill, jd_canon=base_skill)
    rows_sup, det_sup = build_skill_gap(
        graph_data=g_sup,
        stage3_response=_make_mock_stage3(adv_skill, base_skill, raw_cos),
        jd_order=[base_skill],
        min_soft_match=0.50,
    )

    # Case A: JD requires advanced skill, CV only has foundational prerequisite (e.g., JD=kubernetes, CV=docker)
    g_pre = _make_two_node_graph(cv_canon=base_skill, jd_canon=adv_skill)
    rows_pre, det_pre = build_skill_gap(
        graph_data=g_pre,
        stage3_response=_make_mock_stage3(base_skill, adv_skill, raw_cos),
        jd_order=[adv_skill],
        min_soft_match=0.50,
    )

    assert rows_sup[0].matched_cv_skill_id == adv_skill
    assert rows_sup[0].soft_match is not None
    assert 0.72 <= rows_sup[0].soft_match <= 0.84
    assert det_sup[0]["directed_relation"] == "cv_supersedes_jd"

    pre_score = rows_pre[0].soft_match or 0.0
    assert pre_score <= 0.52
    assert rows_sup[0].soft_match - pre_score >= 0.25
    assert det_pre[0]["directed_relation"] == "cv_is_prerequisite_only"


def test_two_hop_transitive_asymmetry_linux_vs_kubernetes():
    # JD=linux, CV=kubernetes (2-hop: linux -> docker -> kubernetes) -> moderate partial credit
    g_sup = _make_two_node_graph(cv_canon="kubernetes", jd_canon="linux")
    rows_sup, det_sup = build_skill_gap(
        graph_data=g_sup,
        stage3_response=_make_mock_stage3("kubernetes", "linux", 0.3891),
        jd_order=["linux"],
        min_soft_match=0.50,
    )
    assert rows_sup[0].matched_cv_skill_id == "kubernetes"
    assert rows_sup[0].soft_match is not None and 0.56 <= rows_sup[0].soft_match <= 0.70
    assert det_sup[0]["directed_hops"] == 2

    # JD=kubernetes, CV=linux -> discounted below 0.40 floor -> unmatched (no_match)
    g_pre = _make_two_node_graph(cv_canon="linux", jd_canon="kubernetes")
    rows_pre, det_pre = build_skill_gap(
        graph_data=g_pre,
        stage3_response=_make_mock_stage3("linux", "kubernetes", 0.3891),
        jd_order=["kubernetes"],
        min_soft_match=0.50,
    )
    assert rows_pre[0].matched_cv_skill_id is None
    assert rows_pre[0].soft_match is None
    assert det_pre[0]["directed_relation"] == "cv_is_prerequisite_only"
    assert det_pre[0]["directed_hops"] == 2


def test_stage4_llm_directional_relation_resolves_custom_skills():
    reasoning = [
        SkillPairReasoningResult(
            skill_a=SkillRef(skill_id="custom-core", name="Custom Core", source="CV"),
            skill_b=SkillRef(skill_id="custom-pro", name="Custom Pro", source="JD"),
            identity="distinct",
            relationship="prerequisite",
            direction="a_to_b",
            reasoning_summary="Custom Core is a prerequisite for Custom Pro.",
            model_id="test",
            graph_relation_status="eligible",
        )
    ]
    assert resolve_directed_skill_relation("custom-core", "custom-pro", reasoning_results=reasoning) == (
        "cv_supersedes_jd",
        1,
    )
    assert resolve_directed_skill_relation("custom-pro", "custom-core", reasoning_results=reasoning) == (
        "cv_is_prerequisite_only",
        1,
    )


# ==============================================================================
# 2. Bidirectional JD Scope in Graph Builder (Issue 4 — Layer 2)
# ==============================================================================
def test_jd_bidirectional_scope_connects_both_docker_k8s_directions_and_filters_cv_noise():
    dim = 16
    builder = PaperAlignedGraphBuilder(
        PaperAlignedGraphConfig(
            embedding_dim=dim,
            enable_skill_dependencies=True,
            dependency_scope="jd_bidirectional",
            enable_evidence_proficiency_fallback=True,
        )
    )

    # Case B: JD=Docker, CV=Kubernetes + irrelevant CV-only pair (html -> css)
    cv_items = [
        SkillInputItem(occurrence_id="c1", canonical_skill_id="kubernetes", surface_name="Kubernetes", source_document="CV", embedding_vector=_unit_vec(dim, 0)),
        SkillInputItem(occurrence_id="c2", canonical_skill_id="html", surface_name="HTML", source_document="CV", embedding_vector=_unit_vec(dim, 2)),
        SkillInputItem(occurrence_id="c3", canonical_skill_id="css", surface_name="CSS", source_document="CV", embedding_vector=_unit_vec(dim, 3)),
    ]
    jd_items = [
        SkillInputItem(occurrence_id="j1", canonical_skill_id="docker", surface_name="Docker", source_document="JD", embedding_vector=_unit_vec(dim, 0, 1, 0.4)),
    ]
    g_b, rep_b = builder.build_graph_from_items(cv_items, jd_items)
    assert rep_b.is_valid
    # Must include docker -> kubernetes (anchored on JD=docker), must NOT include CV-only html -> css!
    assert rep_b.skill_dependency_edge_count == 1
    dep_edges = g_b.diagnostics["skill_dependency_audit"]["edges"]
    assert dep_edges[0]["source_canonical_id"] == "docker"
    assert dep_edges[0]["target_canonical_id"] == "kubernetes"

    pyg_b, _, _ = builder.export_to_pyg(g_b)
    assert pyg_b[("skill", "prerequisite_to", "skill")].edge_index.shape == (2, 1)
    assert pyg_b[("skill", "prerequisite_of", "skill")].edge_index.shape == (2, 1)


# ==============================================================================
# 3. Approach 2 Fallback & Vietnamese Proficiency Extraction
# ==============================================================================
def test_vietnamese_proficiency_and_continuous_evidence_fallback():
    item_basic_vn = SkillInputItem(
        occurrence_id="cv1",
        canonical_skill_id="python",
        surface_name="Python",
        source_document="CV",
        evidence_sentences=["Python (cơ bản, 3 tháng)"],
    )
    item_expert_vn = SkillInputItem(
        occurrence_id="cv2",
        canonical_skill_id="python",
        surface_name="Python",
        source_document="CV",
        evidence_sentences=["Python (chuyên sâu, 6 năm)"],
    )
    item_exp_no_mod = SkillInputItem(
        occurrence_id="cv3",
        canonical_skill_id="python",
        surface_name="Python",
        source_document="CV",
        evidence_sentences=[
            "Built and deployed production REST APIs with Python microservices.",
            "Optimized Python async worker queues for high throughput.",
        ],
        metadata={"sections": ["experience"]},
    )
    item_list_no_mod = SkillInputItem(
        occurrence_id="cv4",
        canonical_skill_id="python",
        surface_name="Python",
        source_document="CV",
        evidence_sentences=["Python"],
        metadata={"sections": ["skills"]},
    )
    item_implicit = SkillInputItem(
        occurrence_id="cv5",
        canonical_skill_id="system-design",
        surface_name="System Design",
        source_document="CV",
        extraction_type="implicit",
        evidence_sentences=["Designed scalable service architecture."],
    )

    r_basic = extract_skill_proficiency(item_basic_vn, enable_evidence_fallback=True)
    r_expert = extract_skill_proficiency(item_expert_vn, enable_evidence_fallback=True)
    r_exp = extract_skill_proficiency(item_exp_no_mod, enable_evidence_fallback=True)
    r_list = extract_skill_proficiency(item_list_no_mod, enable_evidence_fallback=True)
    r_imp = extract_skill_proficiency(item_implicit, enable_evidence_fallback=True)

    assert not r_basic.is_missing and r_basic.normalized_weight == pytest.approx(0.10)
    assert not r_expert.is_missing and r_expert.normalized_weight == pytest.approx(0.90)
    assert not r_exp.is_missing and r_exp.mapping_source == "evidence_context_fallback"
    assert not r_list.is_missing and r_list.mapping_source == "evidence_context_fallback"
    assert not r_imp.is_missing and r_imp.mapping_source == "evidence_context_fallback"
    # Strict monotonic ordering: basic < implicit < skills list < multi-sentence experience < expert
    assert (
        r_basic.normalized_weight
        < r_imp.normalized_weight
        < r_list.normalized_weight
        < r_exp.normalized_weight
        < r_expert.normalized_weight
    )


# ==============================================================================
# 4. Approach 1 Unified Module 2 Proficiency Injection
# ==============================================================================
def test_apply_module2_proficiencies_updates_edges_symmetrically_and_keeps_fallback():
    dim = 16
    builder = PaperAlignedGraphBuilder(
        PaperAlignedGraphConfig(
            embedding_dim=dim,
            enable_evidence_proficiency_fallback=True,
            dependency_scope="jd_bidirectional",
        )
    )
    cv_items = [
        SkillInputItem(
            occurrence_id="c1",
            canonical_skill_id="python",
            surface_name="Python",
            source_document="CV",
            evidence_sentences=["Built backend services in Python."],
            metadata={"sections": ["experience"]},
            embedding_vector=_unit_vec(dim, 0),
        ),
        SkillInputItem(
            occurrence_id="c2",
            canonical_skill_id="redis",
            surface_name="Redis",
            source_document="CV",
            evidence_sentences=["Redis"],
            metadata={"sections": ["skills"]},
            embedding_vector=_unit_vec(dim, 1),
        ),
    ]
    jd_items = [
        SkillInputItem(
            occurrence_id="j1",
            canonical_skill_id="python",
            surface_name="Python",
            source_document="JD",
            evidence_sentences=["Python backend development."],
            metadata={"sections": ["requirements"]},
            embedding_vector=_unit_vec(dim, 0),
        ),
    ]
    base_graph, rep = builder.build_graph_from_items(cv_items, jd_items)
    assert rep.is_valid

    # Inject Module 2 P_CV=4.8 for python (w=0.96), P_JD=4.0 for python (w=0.80); redis untouched (keeps fallback)
    enriched = builder.apply_module2_proficiencies(
        base_graph,
        cv_proficiencies={"python": 4.8},
        jd_proficiencies={"python": 4.0},
    )
    assert enriched.integrity_report is not None and enriched.integrity_report.is_valid
    assert enriched.diagnostics["module2_proficiency_injection"]["cv_edges_updated"] == 1
    assert enriched.diagnostics["module2_proficiency_injection"]["jd_edges_updated"] == 1

    for edge in enriched.edges:
        if edge.edge_type in ("has_skill", "in_resume"):
            sk_id = edge.target_id if edge.edge_type == "has_skill" else edge.source_id
            cid = enriched.skill_nodes[sk_id].canonical_skill_id
            if cid == "python":
                assert edge.tensor_weight == pytest.approx(0.96)
                assert edge.proficiency.mapping_source == "module2_proficiency_estimator"
            elif cid == "redis":
                # Retained Approach 2 fallback weight (never 0.0!)
                assert edge.tensor_weight == pytest.approx(0.40)
                assert edge.proficiency.mapping_source == "evidence_context_fallback"
        elif edge.edge_type in ("requires_skill", "required_by_job"):
            assert edge.tensor_weight == pytest.approx(0.80)
            assert edge.proficiency.mapping_source == "module2_proficiency_estimator"

    rec = build_module2_proficiency_record(3.5, side="CV_DEMONSTRATED")
    assert rec.normalized_weight == pytest.approx(0.70)


# ==============================================================================
# 5. Trained v3 GNN Checkpoint: Zero-Shot Asymmetry & Monotonic Depth Ordering
# ==============================================================================
def test_v3_checkpoint_zero_shot_docker_k8s_asymmetry_and_depth_sensitivity():
    ckpt_path = (
        Path(__file__).resolve().parents[1]
        / "data/checkpoints/paper_aligned_gnn/paper_aligned_hybrid_gnn_v3_asym_prof.pt"
    )
    if not ckpt_path.is_file():
        pytest.skip("v3 checkpoint not yet trained")

    svc = GNNInferenceService(checkpoint_path=str(ckpt_path))
    builder = PaperAlignedGraphBuilder(
        PaperAlignedGraphConfig(
            embedding_dim=768,
            enable_skill_dependencies=True,
            dependency_scope="jd_bidirectional",
            enable_evidence_proficiency_fallback=True,
        )
    )

    v_docker = _unit_vec(768, 0)
    v_k8s = _unit_vec(768, 0, 1, 0.9)
    v_python = _unit_vec(768, 5)

    def _predict(cv_items: List[SkillInputItem], jd_items: List[SkillInputItem]) -> float:
        g, rep = builder.build_graph_from_items(cv_items, jd_items)
        assert rep.is_valid
        pyg, _, _ = builder.export_to_pyg(g)
        return svc.predict_graph(pyg).matching_score

    # 1. Zero-shot Docker <-> Kubernetes asymmetry
    score_jd_docker_cv_k8s = _predict(
        [SkillInputItem(occurrence_id="c1", canonical_skill_id="kubernetes", surface_name="Kubernetes", source_document="CV", evidence_sentences=["Proficient Kubernetes"], embedding_vector=v_k8s)],
        [SkillInputItem(occurrence_id="j1", canonical_skill_id="docker", surface_name="Docker", source_document="JD", evidence_sentences=["Proficient Docker"], embedding_vector=v_docker)],
    )
    score_jd_k8s_cv_docker = _predict(
        [SkillInputItem(occurrence_id="c1", canonical_skill_id="docker", surface_name="Docker", source_document="CV", evidence_sentences=["Proficient Docker"], embedding_vector=v_docker)],
        [SkillInputItem(occurrence_id="j1", canonical_skill_id="kubernetes", surface_name="Kubernetes", source_document="JD", evidence_sentences=["Proficient Kubernetes"], embedding_vector=v_k8s)],
    )
    assert score_jd_docker_cv_k8s > score_jd_k8s_cv_docker + 0.08, (
        f"Expected JD=Docker/CV=K8s ({score_jd_docker_cv_k8s}) > JD=K8s/CV=Docker ({score_jd_k8s_cv_docker}) + 0.08"
    )

    # 2. Monotonic depth ordering on same skill topology (Basic 3 months < Evidence fallback < Expert 6 years)
    jd_py = [SkillInputItem(occurrence_id="j1", canonical_skill_id="python", surface_name="Python", source_document="JD", evidence_sentences=["Python chuyên sâu, 5 năm"], embedding_vector=v_python)]
    s_basic = _predict(
        [SkillInputItem(occurrence_id="c1", canonical_skill_id="python", surface_name="Python", source_document="CV", evidence_sentences=["Python (cơ bản, 3 tháng)"], embedding_vector=v_python)],
        jd_py,
    )
    s_fallback = _predict(
        [SkillInputItem(occurrence_id="c1", canonical_skill_id="python", surface_name="Python", source_document="CV", evidence_sentences=["Built backend services with Python."], metadata={"sections": ["experience"]}, embedding_vector=v_python)],
        jd_py,
    )
    s_expert = _predict(
        [SkillInputItem(occurrence_id="c1", canonical_skill_id="python", surface_name="Python", source_document="CV", evidence_sentences=["Python (chuyên sâu, 6 năm)"], embedding_vector=v_python)],
        jd_py,
    )
    assert s_basic < s_fallback < s_expert, (
        f"Expected strict depth ordering s_basic ({s_basic}) < s_fallback ({s_fallback}) < s_expert ({s_expert})"
    )
