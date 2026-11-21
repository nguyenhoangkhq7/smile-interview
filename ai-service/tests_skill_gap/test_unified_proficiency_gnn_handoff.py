"""Tests Approach 1: Module 2 continuous P_CV / P_JD proficiencies injected into Stage 6 GNN
during POST /api/v1/pipeline/analyze.
"""
from __future__ import annotations

from pathlib import Path
from typing import List
import numpy as np
import pytest
from fastapi.testclient import TestClient

from main import create_app
from matching_cv.app.container import MatchedDocuments
from matching_cv.app.schemas.module1 import Module1Output
from matching_cv.research.paper_aligned_gnn.graph_builder import PaperAlignedGraphBuilder
from matching_cv.research.paper_aligned_gnn.schemas import PaperAlignedGraphConfig, SkillInputItem
from skill_gap.adapters.config import AppConfig
from skill_gap.domain.models import ExtractedCVSkill, ExtractedJDSkill, MatchResult
from tests_skill_gap.test_upgraded_architecture import SimulatedLatencyMockLLM


def _unit_vec(dim: int, hot: int) -> List[float]:
    v = np.zeros(dim, dtype=np.float32)
    v[hot % dim] = 1.0
    return [float(x) for x in v]


def test_pipeline_analyze_injects_module2_proficiencies_into_gnn(monkeypatch):
    ckpt = (
        Path(__file__).resolve().parents[1]
        / "matching_cv/data/checkpoints/paper_aligned_gnn/paper_aligned_hybrid_gnn_v3_asym_prof.pt"
    )
    if not ckpt.is_file():
        pytest.skip("v3 checkpoint not yet trained")

    builder = PaperAlignedGraphBuilder(
        PaperAlignedGraphConfig(
            embedding_dim=768,
            enable_skill_dependencies=True,
            dependency_scope="jd_bidirectional",
            enable_evidence_proficiency_fallback=True,
        )
    )
    v_k8s = _unit_vec(768, 0)
    v_rabbit = _unit_vec(768, 1)

    base_graph, rep = builder.build_graph_from_items(
        cv_items=[
            SkillInputItem(
                occurrence_id="c_k8s",
                canonical_skill_id="kubernetes",
                surface_name="Kubernetes",
                source_document="CV",
                evidence_sentences=["Vận hành Kubernetes production"],
                metadata={"sections": ["experience"]},
                embedding_vector=v_k8s,
            ),
        ],
        jd_items=[
            SkillInputItem(
                occurrence_id="j_k8s",
                canonical_skill_id="kubernetes",
                surface_name="Kubernetes",
                source_document="JD",
                evidence_sentences=["Yêu cầu vận hành Kubernetes ở môi trường production."],
                metadata={"sections": ["requirements"]},
                embedding_vector=v_k8s,
            ),
            SkillInputItem(
                occurrence_id="j_rb",
                canonical_skill_id="rabbitmq",
                surface_name="RabbitMQ",
                source_document="JD",
                evidence_sentences=["Yêu cầu kinh nghiệm RabbitMQ message broker."],
                metadata={"sections": ["requirements"]},
                embedding_vector=v_rabbit,
            ),
        ],
        pair_id="m2_gnn_handoff_test",
    )
    assert rep.is_valid

    captured = {}
    orig_apply = PaperAlignedGraphBuilder.apply_module2_proficiencies

    def spy_apply(self, graph_data, cv_proficiencies=None, jd_proficiencies=None):
        captured["cv_proficiencies"] = dict(cv_proficiencies or {})
        captured["jd_proficiencies"] = dict(jd_proficiencies or {})
        return orig_apply(self, graph_data, cv_proficiencies=cv_proficiencies, jd_proficiencies=jd_proficiencies)

    async def fake_match_documents(cv_text: str, jd_text: str, *, include_compatibility_score: bool = False):
        captured["early_gnn_skipped"] = not include_compatibility_score
        return MatchedDocuments(
            cv_text=cv_text,
            jd_text=jd_text,
            output=Module1Output(
                matcher_source="MATCHING_CV",
                cv_skills=[
                    ExtractedCVSkill(
                        skill_id="kubernetes",
                        skill_name="Vận hành Kubernetes",
                        type="explicit",
                        confidence=0.9,
                        evidence_spans=["Vận hành Kubernetes production"],
                    ),
                ],
                jd_skills=[
                    ExtractedJDSkill(
                        skill_id="kubernetes",
                        skill_name="Quản trị Kubernetes",
                        type="explicit",
                        confidence=0.9,
                        evidence_spans=["Yêu cầu vận hành Kubernetes ở môi trường production."],
                    ),
                    ExtractedJDSkill(
                        skill_id="rabbitmq",
                        type="explicit",
                        confidence=0.9,
                        evidence_spans=["Yêu cầu kinh nghiệm RabbitMQ message broker."],
                    ),
                ],
                match_results=[
                    MatchResult(jd_skill_id="kubernetes", w_j=0.8, matched_cv_skill_id="kubernetes", soft_match=0.95),
                    MatchResult(jd_skill_id="rabbitmq", w_j=0.6, matched_cv_skill_id="none", soft_match=0.0),
                ],
            ),
            matching_score=None,
            graph_data=base_graph,
            graph_mode="similarity_enriched",
            pair_id="m2_gnn_handoff_test",
        )

    monkeypatch.setattr("matching_cv.app.api.v1.endpoints.unified.match_documents", fake_match_documents)
    monkeypatch.setattr(PaperAlignedGraphBuilder, "apply_module2_proficiencies", spy_apply)

    config = AppConfig(reference_date="2024-06-01")
    app = create_app(llm_client=SimulatedLatencyMockLLM(delay_sec=0.0), config=config)
    client = TestClient(app)

    res = client.post(
        "/api/v1/pipeline/analyze",
        json={
            "analysis_id": "m2-handoff-01",
            "cv_text": "Jane Smith - DevOps Engineer\nCông ty CloudNine (01/2021 - 01/2024)\n- Vận hành Kubernetes production",
            "jd_text": "Yêu cầu vận hành Kubernetes ở môi trường production. Yêu cầu kinh nghiệm RabbitMQ message broker.",
        },
    )
    assert res.status_code == 200
    body = res.json()
    assert captured.get("early_gnn_skipped") is True
    assert "kubernetes" in captured.get("cv_proficiencies", {})
    assert "kubernetes" in captured.get("jd_proficiencies", {})
    assert "rabbitmq" in captured.get("jd_proficiencies", {})
    assert body["report"]["matching_score"] is not None
    assert 0.0 <= body["report"]["matching_score"] <= 1.0
