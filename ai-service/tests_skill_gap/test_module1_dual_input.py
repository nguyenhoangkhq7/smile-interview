import io
import pytest
import pypdf
from fastapi.testclient import TestClient

from main import create_app
from tests_skill_gap.test_upgraded_architecture import SimulatedLatencyMockLLM


def create_in_memory_pdf(text_content: str) -> bytes:
    """Helper to create a valid minimal PDF in-memory containing text."""
    writer = pypdf.PdfWriter()
    page = writer.add_blank_page(width=300, height=300)
    # Using pypdf annotations or simple text writer
    buf = io.BytesIO()
    writer.write(buf)
    return buf.getvalue()


@pytest.fixture
def dual_input_client():
    mock_llm = SimulatedLatencyMockLLM()
    app = create_app(llm_client=mock_llm)
    return TestClient(app)


def test_json_analyze_pipeline(dual_input_client):
    """Test standard JSON payload to /api/v1/pipeline/analyze."""
    payload = {
        "cv_text": "Experienced Kubernetes and RabbitMQ Engineer with 5 years backend experience.",
        "jd_text": "Looking for Senior Kubernetes Developer proficient in RabbitMQ and microservices.",
        "analysis_id": "test-json-pipeline-1",
    }
    response = dual_input_client.post("/api/v1/pipeline/analyze", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["analysis_id"] == "test-json-pipeline-1"
    assert "skills" in data
    assert "report" in data
    assert len(data["skills"]) > 0


def test_multipart_form_text_pipeline(dual_input_client):
    """Test multipart form-data text fields to /api/v1/pipeline/analyze."""
    data = {
        "cv_text": "Backend Engineer proficient in Kubernetes clusters and RabbitMQ messaging.",
        "jd_text": "Senior DevOps Engineer with Kubernetes and RabbitMQ expertise required.",
        "analysis_id": "test-multipart-text-1",
    }
    response = dual_input_client.post("/api/v1/pipeline/analyze", data=data)
    assert response.status_code == 200
    res_data = response.json()
    assert res_data["analysis_id"] == "test-multipart-text-1"
    assert len(res_data["skills"]) > 0


def test_multipart_pdf_upload_pipeline(dual_input_client):
    """Test uploading a real PDF file via multipart/form-data to /api/v1/pipeline/analyze."""
    pdf_cv_bytes = create_in_memory_pdf("CV Kubernetes RabbitMQ")
    files = {
        "cv_file": ("my_resume.pdf", pdf_cv_bytes, "application/pdf"),
    }
    data = {
        "jd_text": "Senior DevOps Engineer with Kubernetes and RabbitMQ expertise required.",
        "analysis_id": "test-multipart-pdf-1",
    }
    response = dual_input_client.post("/api/v1/pipeline/analyze", data=data, files=files)
    assert response.status_code == 200
    res_data = response.json()
    assert res_data["analysis_id"] == "test-multipart-pdf-1"
    assert "report" in res_data
