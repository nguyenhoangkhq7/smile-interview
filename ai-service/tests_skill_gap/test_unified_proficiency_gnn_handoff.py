"""Verifies strictly decoupled one-way Module 1 -> Module 2 pipeline contract.

Ensures:
1. POST /api/v1/pipeline/analyze executes Module 1 once with `include_compatibility_score=True`
   so Module 1 computes S_semantic (`matching_score`) self-contained without waiting for Module 2.
2. Module 2 runs strictly downstream on Module 1 outputs and NEVER injects proficiencies back
   into Module 1's graph or GNN (`apply_module2_proficiencies` is never invoked).
3. `report.matching_score` equals Module 1's `S_semantic` directly, and no `S_readiness` or
   score-fusion fields are added to `report` (strictly `{"matching_score", "degraded"}`).
"""
from __future__ import annotations

from fastapi.testclient import TestClient

from main import create_app
from matching_cv.app.container import MatchedDocuments
from matching_cv.app.schemas.module1 import Module1Output
from matching_cv.research.paper_aligned_gnn.graph_builder import PaperAlignedGraphBuilder
from skill_gap.adapters.config import AppConfig
from skill_gap.domain.models import ExtractedCVSkill, ExtractedJDSkill, MatchResult
from tests_skill_gap.test_upgraded_architecture import SimulatedLatencyMockLLM


def test_pipeline_analyze_is_strictly_one_way_and_uses_s_semantic_as_match_score(monkeypatch):
    captured: dict[str, object] = {}

    def fail_if_backward_injection_called(*args, **kwargs):
        raise AssertionError("Module 2 must not inject proficiencies back into Module 1 GNN")

    async def fake_match_documents(
        cv_text: str, jd_text: str, *, include_compatibility_score: bool = False
    ) -> MatchedDocuments:
        captured["include_compatibility_score"] = include_compatibility_score
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
                    MatchResult(
                        jd_skill_id="kubernetes",
                        w_j=0.85,
                        matched_cv_skill_id="kubernetes",
                        soft_match=0.95,
                    ),
                    MatchResult(
                        jd_skill_id="rabbitmq",
                        w_j=0.60,
                        matched_cv_skill_id="none",
                        soft_match=0.0,
                    ),
                ],
            ),
            matching_score=0.7314,
        )

    monkeypatch.setattr("matching_cv.app.api.v1.endpoints.unified.match_documents", fake_match_documents)
    monkeypatch.setattr(PaperAlignedGraphBuilder, "apply_module2_proficiencies", fail_if_backward_injection_called)

    config = AppConfig(reference_date="2024-06-01")
    app = create_app(llm_client=SimulatedLatencyMockLLM(delay_sec=0.0), config=config)
    client = TestClient(app)

    res = client.post(
        "/api/v1/pipeline/analyze",
        json={
            "analysis_id": "decoupled-m1-m2-01",
            "cv_text": (
                "Jane Smith - DevOps Engineer\n"
                "Công ty CloudNine (01/2021 - 01/2024)\n"
                "- Vận hành Kubernetes production"
            ),
            "jd_text": (
                "Yêu cầu vận hành Kubernetes ở môi trường production. "
                "Yêu cầu kinh nghiệm RabbitMQ message broker."
            ),
        },
    )
    assert res.status_code == 200
    body = res.json()
    assert captured.get("include_compatibility_score") is True
    assert set(body["report"].keys()) == {"matching_score", "degraded"}
    assert body["report"]["matching_score"] == 0.7314
    assert len(body["skills"]) == 2
