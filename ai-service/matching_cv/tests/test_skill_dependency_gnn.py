"""Comprehensive tests for Skill-Dependency Heterogeneous Graph & Dependency-Aware Hybrid GNN.

Verifies:
1. Curated technical skill prerequisite DAG is strictly acyclic and free of self-loops.
2. PaperAlignedGraphBuilder resolves `(skill, prerequisite_to, skill)` and reverse
   `(skill, prerequisite_of, skill)` edges weighted by SBERT cosine similarity.
3. Stage 4 LLM prerequisite relations (`a_to_b` and `b_to_a`) are ingested safely with
   automatic cycle blocking.
4. Disabling `enable_skill_dependencies` reproduces strict Baghbanzadeh & Wu (2025)
   bipartite topology for ablation comparability.
5. GNNInferenceService validates skill prerequisite edges (symmetry, bounds, no self-loops)
   while strictly rejecting unauthorized skill-skill edge types.
6. Dependency-aware PaperAlignedHybridGNN propagates prerequisite signals into `match_score`,
   exposes `skill_dependency_attention_map`, and supports end-to-end backpropagation.
7. Both v1 bipartite baseline checkpoint and v2 dependency-aware checkpoint load cleanly.
"""
from __future__ import annotations

from pathlib import Path
from typing import List
import numpy as np
import pytest
import torch

from matching_cv.app.schemas.semantic_reasoning import SkillPairReasoningResult, SkillRef
from matching_cv.app.services.gnn_inference_service import (
    GNNInferenceService,
    GNNInputValidationError,
)
from matching_cv.research.paper_aligned_gnn.graph_builder import PaperAlignedGraphBuilder
from matching_cv.research.paper_aligned_gnn.hybrid_gnn import (
    PaperAlignedGNNConfig,
    PaperAlignedHybridGNN,
)
from matching_cv.research.paper_aligned_gnn.schemas import (
    PaperAlignedGraphConfig,
    SkillInputItem,
)
from matching_cv.research.paper_aligned_gnn.skill_dependency_resolver import (
    CURATED_SKILL_PREREQUISITE_DAG,
    _lookup_key,
    detect_directed_cycles,
)


def _unit_vec(dim: int, primary: int, secondary: int = -1, weight: float = 0.0) -> List[float]:
    vec = np.zeros(dim, dtype=np.float32)
    vec[primary % dim] = 1.0
    if secondary >= 0:
        vec[secondary % dim] += weight
    norm = float(np.linalg.norm(vec))
    if norm > 0:
        vec = vec / norm
    return [float(x) for x in vec]


def test_curated_skill_prerequisite_dag_is_strictly_acyclic():
    edges = [(_lookup_key(u), _lookup_key(v)) for u, v in CURATED_SKILL_PREREQUISITE_DAG]
    assert len(edges) > 100
    assert all(u != v for u, v in edges), "Curated DAG must contain zero self-loops"
    assert detect_directed_cycles(edges) == [], "Curated DAG must be strictly cycle-free"


def test_builder_emits_prerequisite_edges_from_curated_dag_with_sbert_weights():
    dim = 16
    cfg = PaperAlignedGraphConfig(embedding_dim=dim, enable_skill_dependencies=True, dependency_scope="jd_anchored")
    builder = PaperAlignedGraphBuilder(cfg)

    v_docker = _unit_vec(dim, 0)
    v_k8s = _unit_vec(dim, 0, 1, 0.5)  # cosine = 1 / sqrt(1.25) ~= 0.894427
    v_linux = _unit_vec(dim, 0, 2, 1.0)  # cosine with docker ~= 0.707107

    cv_items = [
        SkillInputItem(
            occurrence_id="cv_linux",
            canonical_skill_id="linux",
            surface_name="Linux",
            source_document="CV",
            evidence_sentences=["Strong Linux administration."],
            embedding_vector=v_linux,
        ),
        SkillInputItem(
            occurrence_id="cv_docker",
            canonical_skill_id="docker",
            surface_name="Docker",
            source_document="CV",
            evidence_sentences=["Proficient in Docker."],
            embedding_vector=v_docker,
        ),
    ]
    jd_items = [
        SkillInputItem(
            occurrence_id="jd_docker",
            canonical_skill_id="docker",
            surface_name="Docker",
            source_document="JD",
            evidence_sentences=["Experienced with Docker."],
            embedding_vector=v_docker,
        ),
        SkillInputItem(
            occurrence_id="jd_k8s",
            canonical_skill_id="kubernetes",
            surface_name="Kubernetes",
            source_document="JD",
            evidence_sentences=["Strong Kubernetes required."],
            embedding_vector=v_k8s,
        ),
    ]

    graph, report = builder.build_graph_from_items(cv_items, jd_items, pair_id="dep_test_1")
    assert report.is_valid
    assert report.skill_dependency_dag_valid
    assert report.no_unintended_doc_doc_or_skill_skill_edges
    # Expected DAG edges: linux -> docker, docker -> kubernetes
    assert report.skill_dependency_edge_count == 2

    pyg, _, summary = builder.export_to_pyg(graph)
    assert ("skill", "prerequisite_to", "skill") in pyg.edge_types
    assert ("skill", "prerequisite_of", "skill") in pyg.edge_types
    fwd_ei = pyg[("skill", "prerequisite_to", "skill")].edge_index
    rev_ei = pyg[("skill", "prerequisite_of", "skill")].edge_index
    fwd_ea = pyg[("skill", "prerequisite_to", "skill")].edge_attr
    assert fwd_ei.shape == (2, 2)
    assert rev_ei.shape == (2, 2)
    assert torch.equal(fwd_ei[0], rev_ei[1]) and torch.equal(fwd_ei[1], rev_ei[0])
    # Weights come directly from SBERT cosine similarity in [0.1, 1.0]
    assert torch.all((fwd_ea >= 0.1) & (fwd_ea <= 1.0))
    assert summary["num_edges_by_type"]["skill__prerequisite_to__skill"] == 2


def test_builder_ingests_stage4_llm_prerequisite_both_directions_and_blocks_cycles():
    dim = 16
    cfg = PaperAlignedGraphConfig(
        embedding_dim=dim,
        enable_skill_dependencies=True,
        use_curated_dependency_dag=False,
        use_stage4_dependency_reasoning=True,
    )
    builder = PaperAlignedGraphBuilder(cfg)

    cv_items = [
        SkillInputItem(
            occurrence_id="cv_a",
            canonical_skill_id="custom-core",
            surface_name="Custom Core",
            source_document="CV",
            embedding_vector=_unit_vec(dim, 0),
        ),
    ]
    jd_items = [
        SkillInputItem(
            occurrence_id="jd_a",
            canonical_skill_id="custom-core",
            surface_name="Custom Core",
            source_document="JD",
            embedding_vector=_unit_vec(dim, 0),
        ),
        SkillInputItem(
            occurrence_id="jd_b",
            canonical_skill_id="custom-advanced",
            surface_name="Custom Advanced",
            source_document="JD",
            embedding_vector=_unit_vec(dim, 0, 1, 0.4),
        ),
    ]

    # First relation: custom-core -> custom-advanced (b_to_a with A=advanced, B=core)
    # Second relation attempts to create a cycle: custom-advanced -> custom-core
    reasoning = [
        SkillPairReasoningResult(
            skill_a=SkillRef(skill_id="custom-advanced", name="Custom Advanced", source="JD"),
            skill_b=SkillRef(skill_id="custom-core", name="Custom Core", source="CV"),
            identity="distinct",
            relationship="prerequisite",
            direction="b_to_a",
            reasoning_summary="Custom Core is prerequisite for Custom Advanced.",
            model_id="test",
            graph_relation_status="eligible",
            source_occurrence_ids=["jd_b", "cv_a"],
        ),
        SkillPairReasoningResult(
            skill_a=SkillRef(skill_id="custom-advanced", name="Custom Advanced", source="JD"),
            skill_b=SkillRef(skill_id="custom-core", name="Custom Core", source="JD"),
            identity="distinct",
            relationship="prerequisite",
            direction="a_to_b",
            reasoning_summary="Conflicting reverse prerequisite that would close a cycle.",
            model_id="test",
            graph_relation_status="eligible",
            source_occurrence_ids=["jd_b", "jd_a"],
        ),
    ]

    graph, report = builder.build_graph_from_items(cv_items, jd_items, reasoning_results=reasoning)
    assert report.is_valid
    assert report.skill_dependency_dag_valid
    assert report.skill_dependency_edge_count == 1
    audit = graph.diagnostics["skill_dependency_audit"]
    assert audit["from_stage4_llm"] == 1
    assert audit["cycles_blocked"] == 1
    assert audit["edges"][0]["source_canonical_id"] == "custom-core"
    assert audit["edges"][0]["target_canonical_id"] == "custom-advanced"


def test_builder_disable_skill_dependencies_preserves_strict_bipartite_baseline():
    dim = 16
    cfg = PaperAlignedGraphConfig(embedding_dim=dim, enable_skill_dependencies=False)
    builder = PaperAlignedGraphBuilder(cfg)

    cv_items = [
        SkillInputItem(occurrence_id="c1", canonical_skill_id="docker", surface_name="Docker", source_document="CV", embedding_vector=_unit_vec(dim, 0)),
    ]
    jd_items = [
        SkillInputItem(occurrence_id="j1", canonical_skill_id="docker", surface_name="Docker", source_document="JD", embedding_vector=_unit_vec(dim, 0)),
        SkillInputItem(occurrence_id="j2", canonical_skill_id="kubernetes", surface_name="Kubernetes", source_document="JD", embedding_vector=_unit_vec(dim, 1)),
    ]

    graph, report = builder.build_graph_from_items(cv_items, jd_items)
    assert report.is_valid
    assert report.skill_dependency_edge_count == 0
    pyg, _, _ = builder.export_to_pyg(graph)
    assert ("skill", "prerequisite_to", "skill") not in pyg.edge_types
    assert len(pyg.edge_types) == 4


def test_gnn_inference_service_validates_dependency_edges_and_rejects_invalid_ones():
    dim = 768
    cfg = PaperAlignedGraphConfig(embedding_dim=dim, enable_skill_dependencies=True)
    builder = PaperAlignedGraphBuilder(cfg)

    cv_items = [
        SkillInputItem(occurrence_id="c1", canonical_skill_id="docker", surface_name="Docker", source_document="CV", embedding_vector=_unit_vec(dim, 0)),
    ]
    jd_items = [
        SkillInputItem(occurrence_id="j1", canonical_skill_id="docker", surface_name="Docker", source_document="JD", embedding_vector=_unit_vec(dim, 0)),
        SkillInputItem(occurrence_id="j2", canonical_skill_id="kubernetes", surface_name="Kubernetes", source_document="JD", embedding_vector=_unit_vec(dim, 0, 1, 0.3)),
    ]
    graph, report = builder.build_graph_from_items(cv_items, jd_items)
    assert report.is_valid
    pyg, _, _ = builder.export_to_pyg(graph)

    svc = GNNInferenceService()
    val = svc.validate_graph(pyg)
    assert val["validation_status"] == "VALID"
    assert val["edge_counts"]["skill__prerequisite_to__skill"] == 1
    assert val["edge_counts"]["skill__prerequisite_of__skill"] == 1

    # Self-loop must be rejected
    bad_self_loop = pyg.clone()
    bad_self_loop[("skill", "prerequisite_to", "skill")].edge_index = torch.tensor([[0], [0]], dtype=torch.long)
    bad_self_loop[("skill", "prerequisite_of", "skill")].edge_index = torch.tensor([[0], [0]], dtype=torch.long)
    with pytest.raises(GNNInputValidationError, match="Self-loop"):
        svc.validate_graph(bad_self_loop)

    # Unauthorized skill-skill edge type must still be rejected
    bad_rel = pyg.clone()
    bad_rel[("skill", "related_to", "skill")].edge_index = torch.tensor([[0], [1]], dtype=torch.long)
    with pytest.raises(GNNInputValidationError, match="Forbidden edge type"):
        svc.validate_graph(bad_rel)


@pytest.mark.parametrize("dep_mode", ["light_sbert_diffusion", "modified_gat"])
def test_dependency_aware_gnn_forward_and_score_sensitivity(dep_mode):
    torch.manual_seed(7)
    dim = 32
    builder_dep = PaperAlignedGraphBuilder(PaperAlignedGraphConfig(embedding_dim=dim, enable_skill_dependencies=True))
    builder_bip = PaperAlignedGraphBuilder(PaperAlignedGraphConfig(embedding_dim=dim, enable_skill_dependencies=False))

    cv_items = [
        SkillInputItem(occurrence_id="c1", canonical_skill_id="java", surface_name="Java", source_document="CV", evidence_sentences=["Strong Java"], embedding_vector=_unit_vec(dim, 0)),
    ]
    jd_items = [
        SkillInputItem(occurrence_id="j1", canonical_skill_id="java", surface_name="Java", source_document="JD", evidence_sentences=["Strong Java"], embedding_vector=_unit_vec(dim, 0)),
        SkillInputItem(occurrence_id="j2", canonical_skill_id="spring-boot", surface_name="Spring Boot", source_document="JD", evidence_sentences=["Proficient Spring Boot"], embedding_vector=_unit_vec(dim, 0, 1, 0.4)),
    ]

    g_dep, _ = builder_dep.build_graph_from_items(cv_items, jd_items)
    g_bip, _ = builder_bip.build_graph_from_items(cv_items, jd_items)
    pyg_dep, _, _ = builder_dep.export_to_pyg(g_dep)
    pyg_bip, _, _ = builder_bip.export_to_pyg(g_bip)

    model = PaperAlignedHybridGNN(
        PaperAlignedGNNConfig(
            input_dim=dim,
            hidden_dim=16,
            mlp_hidden_dims=[16, 8],
            dropout=0.0,
            mlp_dropout=0.0,
            use_skill_dependency_edges=True,
            skill_dependency_mode=dep_mode,
        )
    )
    model.eval()
    out_dep = model(pyg_dep)
    out_bip = model(pyg_bip)

    assert torch.isfinite(out_dep["raw_score"]).all()
    assert 0.0 <= float(out_dep["bounded_score"].item()) <= 1.0
    assert "java->spring-boot" in out_dep["skill_dependency_attention_map"]
    # Prerequisite edge MUST actively change the computed compatibility score
    assert abs(float(out_dep["raw_score"].item()) - float(out_bip["raw_score"].item())) > 1e-6

    # Backpropagation flows gradients into dependency parameters
    model.train()
    loss = (model(pyg_dep)["raw_score"] - torch.tensor([0.8])).pow(2).mean()
    loss.backward()
    assert model.layers[0].dep_gate.grad is not None
    assert float(model.layers[0].dep_gate.grad.abs().item()) > 0.0


def test_checkpoints_v1_bipartite_and_v2_dependency_both_load_and_predict():
    ckpt_dir = Path(__file__).resolve().parents[1] / "data/checkpoints/paper_aligned_gnn"
    v1_path = ckpt_dir / "paper_aligned_hybrid_gnn_v1.pt"
    v2_path = ckpt_dir / "paper_aligned_hybrid_gnn_v2_dep.pt"

    dim = 768
    builder = PaperAlignedGraphBuilder(PaperAlignedGraphConfig(embedding_dim=dim, enable_skill_dependencies=True))
    cv_items = [
        SkillInputItem(occurrence_id="c1", canonical_skill_id="docker", surface_name="Docker", source_document="CV", evidence_sentences=["Strong Docker"], embedding_vector=_unit_vec(dim, 0)),
        SkillInputItem(occurrence_id="c2", canonical_skill_id="kubernetes", surface_name="Kubernetes", source_document="CV", evidence_sentences=["Proficient Kubernetes"], embedding_vector=_unit_vec(dim, 0, 1, 0.3)),
    ]
    jd_items = [
        SkillInputItem(occurrence_id="j1", canonical_skill_id="docker", surface_name="Docker", source_document="JD", evidence_sentences=["Proficient Docker"], embedding_vector=_unit_vec(dim, 0)),
        SkillInputItem(occurrence_id="j2", canonical_skill_id="kubernetes", surface_name="Kubernetes", source_document="JD", evidence_sentences=["Strong Kubernetes"], embedding_vector=_unit_vec(dim, 0, 1, 0.3)),
    ]
    graph, _ = builder.build_graph_from_items(cv_items, jd_items)
    pyg, _, _ = builder.export_to_pyg(graph)

    if v1_path.is_file():
        svc_v1 = GNNInferenceService(checkpoint_path=str(v1_path))
        res_v1 = svc_v1.predict_graph(pyg)
        assert 0.0 <= res_v1.matching_score <= 1.0

    if v2_path.is_file():
        svc_v2 = GNNInferenceService(checkpoint_path=str(v2_path))
        res_v2 = svc_v2.predict_graph(pyg)
        assert 0.0 <= res_v2.matching_score <= 1.0
        assert res_v2.model_version == "dependency-aware-hybrid-gnn-v2"

    v3_path = ckpt_dir / "paper_aligned_hybrid_gnn_v3_asym_prof.pt"
    if v3_path.is_file():
        svc_v3 = GNNInferenceService(checkpoint_path=str(v3_path))
        res_v3 = svc_v3.predict_graph(pyg)
        assert 0.0 <= res_v3.matching_score <= 1.0
        assert res_v3.model_version == "asymmetric-proficiency-hybrid-gnn-v3"

    v4_path = ckpt_dir / "paper_aligned_hybrid_gnn_v4_semantic_importance.pt"
    if v4_path.is_file():
        svc_v4 = GNNInferenceService(checkpoint_path=str(v4_path))
        res_v4 = svc_v4.predict_graph(pyg)
        assert 0.0 <= res_v4.matching_score <= 1.0
        assert res_v4.model_version == "semantic-importance-dependency-gnn-v4"
