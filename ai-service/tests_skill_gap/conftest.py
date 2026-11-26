import pytest

from matching_cv.app.schemas.module1 import Module1Output
from skill_gap.domain.models import ExtractedCVSkill, ExtractedJDSkill, MatchResult


@pytest.fixture
def fixed_matching_result(monkeypatch):
    """Use a fixed Module 1 response to exercise routing and Module 2."""
    from matching_cv.app.container import MatchedDocuments

    async def match_documents(
        cv_text: str, jd_text: str, *, include_compatibility_score: bool = False,
    ) -> MatchedDocuments:
        return MatchedDocuments(cv_text, jd_text, Module1Output(
            matcher_source="MATCHING_CV",
            cv_skills=[
                ExtractedCVSkill(skill_id="kubernetes", skill_name="Vận hành Kubernetes", type="explicit", confidence=0.9, evidence_spans=[]),
            ],
            jd_skills=[
                ExtractedJDSkill(skill_id="kubernetes", skill_name="Quản trị Kubernetes", type="explicit", confidence=0.9, evidence_spans=["Kubernetes"]),
                ExtractedJDSkill(skill_id="rabbitmq", type="explicit", confidence=0.9, evidence_spans=["RabbitMQ"]),
            ],
            match_results=[
                MatchResult(jd_skill_id="kubernetes", w_j=0.8, matched_cv_skill_id="kubernetes", soft_match=0.95),
                MatchResult(jd_skill_id="rabbitmq", w_j=0.6, matched_cv_skill_id="none", soft_match=0.0),
            ],
        ))

    monkeypatch.setattr("matching_cv.app.container.match_documents", match_documents)
    monkeypatch.setattr("matching_cv.app.api.v1.endpoints.unified.match_documents", match_documents)
