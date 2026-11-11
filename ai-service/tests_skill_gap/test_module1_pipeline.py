"""API contract for the Module 1 to Module 2 handoff."""

from fastapi.testclient import TestClient
from main import create_app
from tests_skill_gap.test_upgraded_architecture import SimulatedLatencyMockLLM
from skill_gap.adapters.config import AppConfig


def test_module1_to_module2_pipeline_endpoint(fixed_matching_result):
    config = AppConfig(reference_date="2024-06-01")
    mock_llm = SimulatedLatencyMockLLM(delay_sec=0.0)
    app = create_app(llm_client=mock_llm, config=config)
    client = TestClient(app)

    cv_text = """
    Jane Smith - DevOps Engineer
    Công ty CloudNine (01/2021 - 01/2024) - Vị trí: DevOps Engineer
    - Vận hành Kubernetes production
    - Xây dựng Kafka pipeline
    """
    jd_text = """
    Tuyển dụng: DevOps Engineer
    - Yêu cầu vận hành Kubernetes ở môi trường production.
    - Yêu cầu kinh nghiệm RabbitMQ message broker.
    """

    # 1. Test /api/v1/match
    m1_res = client.post(
        "/api/v1/match",
        json={"cv_text": cv_text, "jd_text": jd_text},
    )
    assert m1_res.status_code == 200
    m1_data = m1_res.json()
    assert len(m1_data["jd_skills"]) == 2
    assert len(m1_data["match_results"]) == 2
    assert m1_data["matcher_source"] == "MATCHING_CV"

    # 2. Test /api/v1/pipeline/analyze
    pipe_res = client.post(
        "/api/v1/pipeline/analyze",
        json={"analysis_id": "test-session-123", "cv_text": cv_text, "jd_text": jd_text},
    )
    assert pipe_res.status_code == 200
    pipe_data = pipe_res.json()
    assert pipe_data["analysis_id"] == "test-session-123"
    assert len(pipe_data["skills"]) == 2
    assert all("matcher_source:MATCHING_CV" in skill["flags"] for skill in pipe_data["skills"])
    assert "markdown_summary" in pipe_data["report"]
    assert pipe_data["report"]["total_jd_skills"] == 2
