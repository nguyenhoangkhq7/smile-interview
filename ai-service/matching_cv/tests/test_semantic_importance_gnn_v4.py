"""Verification Suite for Decoupled Semantic-Importance GNN (v4).

Verifies:
1. `semantic_importance` edge weighting mode:
   - `Job <-> Skill` edges carry JSI `w_j` (fallback `1.0` when absent).
   - `Resume <-> Skill` edges carry uniform `1.0` (`uniform_semantic_topology`), ignoring CV proficiency words.
   - `Skill <-> Skill` prerequisite edges carry SBERT cosine weights (`jd_bidirectional`).
2. `PipelineOrchestrator` evaluates `skill_importance_stage` BEFORE Stage 5 graph construction
   and passes `skill_importance_output` into `graph_service.build`.
3. Production `paper_aligned_graph_builder` singleton defaults to `edge_weight_mode="semantic_importance"`.
4. Trained v4 checkpoint (`paper_aligned_hybrid_gnn_v4_semantic_importance.pt`):
   - Loads via default `GNNInferenceService()`.
   - Preserves zero-shot Docker <-> Kubernetes directional asymmetry.
   - Is strictly invariant to CV proficiency modifiers (proving complete decoupling from Module 2 proficiency).
"""
from __future__ import annotations

import asyncio
import io
from pathlib import Path
from typing import List
from unittest.mock import AsyncMock, MagicMock

from fastapi import UploadFile
import numpy as np
import pytest

from matching_cv.app.container import build_pipeline_orchestrator
from matching_cv.app.schemas.skill_extraction import (
    Evidence,
    ExtractedSkill,
    ExtractionResult,
    ExtractionStats,
)
from matching_cv.app.schemas.unified_skill_extraction import (
    DocumentUnifiedResult,
    UnifiedExtractFileResponse,
)
from matching_cv.app.services.gnn_inference_service import GNNInferenceService
from matching_cv.app.services.graph_edge_audit import audit_semantic_edge_weights
from matching_cv.research.paper_aligned_gnn.graph_builder import (
    PaperAlignedGraphBuilder,
    paper_aligned_graph_builder,
)
from matching_cv.research.paper_aligned_gnn.schemas import (
    PaperAlignedGraphConfig,
    SkillInputItem,
)


def _unit_vec(dim: int, hot: int, sec: int = -1, sec_w: float = 0.0) -> List[float]:
    vec = np.zeros(dim, dtype=np.float32)
    vec[hot % dim] = 1.0
    if sec >= 0:
        vec[sec % dim] += sec_w
    norm = float(np.linalg.norm(vec))
    if norm > 0:
        vec = vec / norm
    return [float(x) for x in vec]


def test_production_singleton_uses_semantic_importance_mode():
    assert paper_aligned_graph_builder.config.edge_weight_mode == "semantic_importance"
    assert paper_aligned_graph_builder.config.enable_evidence_proficiency_fallback is False
    assert paper_aligned_graph_builder.config.dependency_scope == "jd_bidirectional"


def test_semantic_importance_graph_assigns_jsi_to_jd_and_uniform_one_to_cv():
    dim = 16
    builder = PaperAlignedGraphBuilder(
        PaperAlignedGraphConfig(
            embedding_dim=dim,
            edge_weight_mode="semantic_importance",
            enable_skill_dependencies=True,
            dependency_scope="jd_bidirectional",
        )
    )
    cv_items = [
        SkillInputItem(
            occurrence_id="c1",
            canonical_skill_id="python",
            surface_name="Python",
            source_document="CV",
            evidence_sentences=["Basic knowledge in Python (3 months)"],
            embedding_vector=_unit_vec(dim, 0),
        ),
        SkillInputItem(
            occurrence_id="c2",
            canonical_skill_id="kubernetes",
            surface_name="Kubernetes",
            source_document="CV",
            evidence_sentences=["Expert Kubernetes (8 years)"],
            embedding_vector=_unit_vec(dim, 1, 2, 0.4),
        ),
    ]
    jd_items = [
        SkillInputItem(
            occurrence_id="j1",
            canonical_skill_id="python",
            surface_name="Python",
            source_document="JD",
            evidence_sentences=["Strong Python required."],
            embedding_vector=_unit_vec(dim, 0),
        ),
        SkillInputItem(
            occurrence_id="j2",
            canonical_skill_id="docker",
            surface_name="Docker",
            source_document="JD",
            evidence_sentences=["Docker containers."],
            embedding_vector=_unit_vec(dim, 1),
        ),
    ]
    jsi_payload = {
        "records": [
            {"skill_id": "python", "weight": 0.91},
            # docker omitted intentionally -> must fall back to 1.0
        ]
    }

    graph, report = builder.build_graph_from_items(
        cv_items,
        jd_items,
        skill_importance_output=jsi_payload,
        pair_id="sem_imp_test",
    )
    assert report.is_valid
    assert graph.edge_weight_mode == "semantic_importance"
    assert report.skill_dependency_edge_count == 1  # docker -> kubernetes

    for edge in graph.edges:
        if edge.edge_type in ("has_skill", "in_resume"):
            assert edge.tensor_weight == pytest.approx(1.0)
            assert edge.proficiency.mapping_source == "uniform_semantic_topology"
        elif edge.edge_type in ("requires_skill", "required_by_job"):
            skill_node_id = edge.target_id if edge.edge_type == "requires_skill" else edge.source_id
            cid = graph.skill_nodes[skill_node_id].canonical_skill_id
            assert edge.proficiency.mapping_source == "jd_skill_importance"
            if cid == "python":
                assert edge.tensor_weight == pytest.approx(0.91)
            elif cid == "docker":
                assert edge.tensor_weight == pytest.approx(1.0)


    pyg, _, _ = builder.export_to_pyg(graph)
    result = audit_semantic_edge_weights(graph, pyg, jsi_payload)
    assert result["formula_mismatches"] == 0
    assert result["pyg_mismatch_relations"] == []
    assert result["jd_unverified_by_jsi_edges"] == 2
    assert result["prerequisite_cosine_fallback_edges"] == 0

    pyg["job", "requires_skill", "skill"].edge_attr[0] = 0.11
    result = audit_semantic_edge_weights(graph, pyg, jsi_payload)
    assert result["pyg_mismatch_relations"] == ["requires_skill"]


def test_orchestrator_evaluates_skill_importance_before_stage5_graph_construction():
    call_order: List[str] = []
    received_importance: List[object] = []

    cv_doc = DocumentUnifiedResult(
        document_type="CV",
        raw_text="Built Python services.",
        explicit=ExtractionResult(
            skills=[
                ExtractedSkill(
                    skill_id="python",
                    evidences=[Evidence(surface_form="Python", sentence="Built Python services.", kind="skill")],
                )
            ],
            stats=ExtractionStats(total_mentions=1, unique_skills=1, unresolved_evidences=1, unresolved_mentions=1),
        ),
    )
    jd_doc = DocumentUnifiedResult(
        document_type="JD",
        raw_text="Python is mandatory.",
        explicit=ExtractionResult(
            skills=[
                ExtractedSkill(
                    skill_id="python",
                    evidences=[Evidence(surface_form="Python", sentence="Python is mandatory.", kind="skill")],
                )
            ],
            stats=ExtractionStats(total_mentions=1, unique_skills=1, unresolved_evidences=1, unresolved_mentions=1),
        ),
    )
    fake_unified = UnifiedExtractFileResponse(run_id="order-test", status="completed", cv=cv_doc, jd=jd_doc)
    fake_jsi = {"status": "SUCCESS", "records": [{"skill_id": "python", "weight": 0.87}]}

    orchestrator = build_pipeline_orchestrator()
    orchestrator.extraction_service = MagicMock()
    orchestrator.extraction_service.extract = AsyncMock(
        return_value=MagicMock(
            unified_response=fake_unified,
            matched_pair_id="pair-order-1",
            cv_text=cv_doc.raw_text,
            jd_text=jd_doc.raw_text,
            duration_ms=1.0,
        )
    )

    def fake_jsi_eval(**kwargs):
        call_order.append("skill_importance")
        return fake_jsi

    orig_graph_build = orchestrator.graph_service.build

    def spy_graph_build(**kwargs):
        call_order.append("graph_construction")
        received_importance.append(kwargs.get("skill_importance_output"))
        return orig_graph_build(**kwargs)

    orchestrator.skill_importance_stage.evaluate = fake_jsi_eval  # type: ignore[method-assign]
    orchestrator.graph_service.build = spy_graph_build  # type: ignore[method-assign]

    res = asyncio.run(
        orchestrator.execute_pipeline(
            cv_file=UploadFile(io.BytesIO(b"Built Python services."), filename="cv.txt"),
            jd_file=UploadFile(io.BytesIO(b"Python is mandatory."), filename="jd.txt"),
            graph_mode="evidence_only",
            enable_skill_importance=True,
            include_compatibility_score=False,
        )
    )
    assert res.status == "completed"
    assert call_order == ["skill_importance", "graph_construction"]
    assert received_importance == [fake_jsi]
    jd_edges = [
        e for e in res._public_context.graph_data.edges
        if e.edge_type == "requires_skill"
    ]
    assert len(jd_edges) == 1
    assert jd_edges[0].tensor_weight == pytest.approx(0.87)


def test_v4_semantic_importance_checkpoint_asymmetry_and_proficiency_invariance():
    ckpt_path = (
        Path(__file__).resolve().parents[1]
        / "data/checkpoints/paper_aligned_gnn/paper_aligned_hybrid_gnn_v4_semantic_importance.pt"
    )
    if not ckpt_path.is_file():
        pytest.skip("v4 semantic-importance checkpoint not yet trained")

    svc = GNNInferenceService()
    assert Path(svc.checkpoint_path).name == "paper_aligned_hybrid_gnn_v4_semantic_importance.pt"

    builder = PaperAlignedGraphBuilder(
        PaperAlignedGraphConfig(
            embedding_dim=768,
            edge_weight_mode="semantic_importance",
            enable_skill_dependencies=True,
            dependency_scope="jd_bidirectional",
        )
    )

    v_docker = _unit_vec(768, 0)
    v_k8s = _unit_vec(768, 0, 1, 0.9)
    v_python = _unit_vec(768, 5)

    def _predict(cv_items: List[SkillInputItem], jd_items: List[SkillInputItem], w_map: dict[str, float]):
        g, rep = builder.build_graph_from_items(cv_items, jd_items, jd_importance_weights=w_map)
        assert rep.is_valid
        pyg, _, _ = builder.export_to_pyg(g)
        return svc.predict_graph(pyg)

    # 1. Zero-shot Docker <-> Kubernetes directional asymmetry preserved without proficiency
    res_sup = _predict(
        [SkillInputItem(occurrence_id="c1", canonical_skill_id="kubernetes", surface_name="Kubernetes", source_document="CV", embedding_vector=v_k8s)],
        [SkillInputItem(occurrence_id="j1", canonical_skill_id="docker", surface_name="Docker", source_document="JD", embedding_vector=v_docker)],
        {"docker": 0.85},
    )
    res_pre = _predict(
        [SkillInputItem(occurrence_id="c1", canonical_skill_id="docker", surface_name="Docker", source_document="CV", embedding_vector=v_docker)],
        [SkillInputItem(occurrence_id="j1", canonical_skill_id="kubernetes", surface_name="Kubernetes", source_document="JD", embedding_vector=v_k8s)],
        {"kubernetes": 0.85},
    )
    assert res_sup.model_version == "semantic-importance-dependency-gnn-v4"
    assert res_sup.matching_score > res_pre.matching_score + 0.08, (
        f"Expected S_semantic(JD=Docker, CV=K8s)={res_sup.matching_score} > "
        f"S_semantic(JD=K8s, CV=Docker)={res_pre.matching_score} + 0.08"
    )

    # 2. Strict invariance to self-reported CV proficiency words (decoupled from Module 2)
    jd_py = [
        SkillInputItem(
            occurrence_id="j1",
            canonical_skill_id="python",
            surface_name="Python",
            source_document="JD",
            evidence_sentences=["Python backend development"],
            embedding_vector=v_python,
        )
    ]
    s_basic = _predict(
        [SkillInputItem(occurrence_id="c1", canonical_skill_id="python", surface_name="Python", source_document="CV", evidence_sentences=["Python (cơ bản, 3 tháng)"], embedding_vector=v_python)],
        jd_py,
        {"python": 0.90},
    ).matching_score
    s_expert = _predict(
        [SkillInputItem(occurrence_id="c1", canonical_skill_id="python", surface_name="Python", source_document="CV", evidence_sentences=["Python (chuyên sâu, 6 năm)"], embedding_vector=v_python)],
        jd_py,
        {"python": 0.90},
    ).matching_score
    assert s_basic == pytest.approx(s_expert, abs=1e-6)
