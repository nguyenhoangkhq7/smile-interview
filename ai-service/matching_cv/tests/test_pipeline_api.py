"""FastAPI Endpoint unit tests for POST /api/v1/pipeline/analyze."""
import io
import json
import os
from unittest.mock import AsyncMock, patch
import pytest
from fastapi.testclient import TestClient

from matching_cv.app.main import app
from matching_cv.app.schemas.hetero_graph import GraphBuildRequest
from matching_cv.app.schemas.semantic_reasoning import (
    BatchSkillPairReasoningResponse,
)
from matching_cv.app.schemas.unified_skill_extraction import UnifiedExtractFileResponse
from matching_cv.app.services.gnn_inference_service import gnn_inference_service
from matching_cv.app.services.graph_builder import hetero_graph_builder
from matching_cv.app.services.semantic_representation_service import semantic_representation_service


FRONTEND_FIXTURE_PATH = os.path.join("tests", "fixtures", "02_Frontend_run.json")


@pytest.fixture(autouse=True)
def missing_checkpoint(monkeypatch, tmp_path):
    monkeypatch.setattr(gnn_inference_service, "checkpoint_path", str(tmp_path / "missing.pt"))


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


@pytest.fixture
def frontend_fixture() -> UnifiedExtractFileResponse:
    with open(FRONTEND_FIXTURE_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    return UnifiedExtractFileResponse.model_validate(data)


def test_api_analyze_missing_files(client: TestClient):
    """Calling POST /api/v1/pipeline/analyze without files returns 422."""
    resp = client.post("/api/v1/pipeline/analyze")
    assert resp.status_code == 422


def test_api_analyze_unsupported_file_extension(client: TestClient):
    """Uploading files with unsupported extensions returns 400 Bad Request with PublicErrorResponse."""
    files = {
        "cv_file": ("resume.exe", io.BytesIO(b"fake binary"), "application/octet-stream"),
        "jd_file": ("job.txt", io.BytesIO(b"Job description text"), "text/plain"),
    }
    resp = client.post("/api/v1/pipeline/analyze", files=files)
    assert resp.status_code == 400
    data = resp.json()
    assert data["status"] == "failed"
    assert data["stage"] == "input_validation"
    assert data["error_code"] == "UNSUPPORTED_FILE_TYPE"


def test_api_analyze_empty_file(client: TestClient):
    """Uploading empty files returns 400 Bad Request with PublicErrorResponse."""
    files = {
        "cv_file": ("resume.txt", io.BytesIO(b""), "text/plain"),
        "jd_file": ("job.txt", io.BytesIO(b"Job description text"), "text/plain"),
    }
    resp = client.post("/api/v1/pipeline/analyze", files=files)
    assert resp.status_code == 400
    data = resp.json()
    assert data["status"] == "failed"
    assert data["stage"] == "input_validation"
    assert data["error_code"] == "EMPTY_FILE"


def test_api_analyze_invalid_graph_mode(client: TestClient):
    """Invalid graph_mode returns 400 Bad Request with PublicErrorResponse."""
    files = {
        "cv_file": ("cv.txt", io.BytesIO(b"Software Engineer React TypeScript"), "text/plain"),
        "jd_file": ("jd.txt", io.BytesIO(b"Frontend Developer React Next.js"), "text/plain"),
    }
    resp = client.post(
        "/api/v1/pipeline/analyze",
        files=files,
        data={"graph_mode": "unsupported_mode"},
    )
    assert resp.status_code == 400
    data = resp.json()
    assert data["status"] == "failed"
    assert data["stage"] == "input_validation"
    assert data["error_code"] == "INVALID_GRAPH_MODE"


def test_api_analyze_invalid_top_k(client: TestClient):
    """Invalid top_k (< 1 or > 25) returns 400 Bad Request with PublicErrorResponse."""
    files = {
        "cv_file": ("cv.txt", io.BytesIO(b"Software Engineer React TypeScript"), "text/plain"),
        "jd_file": ("jd.txt", io.BytesIO(b"Frontend Developer React Next.js"), "text/plain"),
    }
    resp = client.post(
        "/api/v1/pipeline/analyze",
        files=files,
        data={"top_k": 0},
    )
    assert resp.status_code == 400
    data = resp.json()
    assert data["status"] == "failed"
    assert data["stage"] == "input_validation"
    assert data["error_code"] == "INVALID_TOP_K"


def test_api_mode_a_evidence_only(client: TestClient, frontend_fixture):
    """Test Mode A (evidence_only) through HTTP API returning StandardizedPipelineOutput."""
    files = {
        "cv_file": ("frontend_cv.txt", io.BytesIO(b"Frontend developer with React and TypeScript"), "text/plain"),
        "jd_file": ("frontend_jd.txt", io.BytesIO(b"Hiring React frontend developer with TypeScript"), "text/plain"),
    }

    with patch(
        "matching_cv.app.services.unified_skill_service.unified_skill_service.extract_unified_from_files",
        new=AsyncMock(return_value=frontend_fixture),
    ):
        resp = client.post(
            "/api/v1/pipeline/analyze",
            files=files,
            data={"graph_mode": "evidence_only", "top_k": 5},
        )

    assert resp.status_code == 200
    data = resp.json()
    assert resp.headers.get("x-output-schema-version") == "standardized-output-v1"
    assert data["match_score"] is None
    assert data["status"] == "MODEL_NOT_TRAINED"
    assert "Frontend developer" in data["cv_text"]
    assert "Hiring React" in data["jd_text"]
    assert isinstance(data["skill_gap_input"], list)
    assert "cv_skills" in data["proficiency_input"]
    assert "jd_skills" in data["proficiency_input"]
    # Internal keys must be omitted from public contract
    for internal_key in ["run_id", "pipeline_version", "graph_mode", "extraction", "graph", "matching_result"]:
        assert internal_key not in data


def test_api_mode_b_similarity_enriched(client: TestClient, frontend_fixture):
    """Test Mode B (similarity_enriched) through HTTP API returning StandardizedPipelineOutput."""
    files = {
        "cv_file": ("frontend_cv.txt", io.BytesIO(b"Frontend developer with React and TypeScript"), "text/plain"),
        "jd_file": ("frontend_jd.txt", io.BytesIO(b"Hiring React frontend developer with TypeScript"), "text/plain"),
    }

    with patch(
        "matching_cv.app.services.unified_skill_service.unified_skill_service.extract_unified_from_files",
        new=AsyncMock(return_value=frontend_fixture),
    ):
        resp = client.post(
            "/api/v1/pipeline/analyze",
            files=files,
            data={"graph_mode": "similarity_enriched", "top_k": 3},
        )

    assert resp.status_code == 200
    data = resp.json()
    assert resp.headers.get("x-output-schema-version") == "standardized-output-v1"
    assert data["match_score"] is None
    assert data["status"] == "MODEL_NOT_TRAINED"
    assert len(data["skill_gap_input"]) > 0
    assert len(data["proficiency_input"]["cv_skills"]) > 0
    assert len(data["proficiency_input"]["jd_skills"]) > 0


def test_api_mode_c_llm_enriched(client: TestClient, frontend_fixture):
    """Test Mode C through HTTP without depending on a historical reasoning report."""
    files = {
        "cv_file": ("frontend_cv.txt", io.BytesIO(b"Frontend developer with React and TypeScript"), "text/plain"),
        "jd_file": ("frontend_jd.txt", io.BytesIO(b"Hiring React frontend developer with TypeScript"), "text/plain"),
    }

    mock_batch = BatchSkillPairReasoningResponse(
        run_id="test-run-recording-replay",
        model_id="test-model",
        prompt_version="test-v1",
        critic_enabled=False,
        total_pairs=0,
        evaluated_pairs=0,
        cached_dedup_pairs=0,
        failed_pairs=0,
        critic_invocations=0,
        contradictions_resolved=0,
        duration_ms=125.0,
        results=[],
    )

    with patch(
        "matching_cv.app.services.unified_skill_service.unified_skill_service.extract_unified_from_files",
        new=AsyncMock(return_value=frontend_fixture),
    ), patch(
        "matching_cv.app.services.skill_reasoning_service.skill_reasoning_service.reason_stage3_topk",
        new=AsyncMock(return_value=mock_batch),
    ):
        resp = client.post(
            "/api/v1/pipeline/analyze",
            files=files,
            data={"graph_mode": "llm_enriched", "top_k": 5},
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["match_score"] is None
    assert data["status"] == "MODEL_NOT_TRAINED"
    assert len(data["skill_gap_input"]) > 0


def test_internal_flags_details_and_embeddings_and_graph(frontend_fixture):
    """Test internal pipeline orchestrator diagnostic flags (tested directly on orchestrator)."""
    import asyncio
    from fastapi import UploadFile
    from matching_cv.app.container import pipeline_orchestrator

    cv_upload = UploadFile(filename="frontend_cv.txt", file=io.BytesIO(b"Frontend developer with React"))
    jd_upload = UploadFile(filename="frontend_jd.txt", file=io.BytesIO(b"Hiring React developer"))

    with patch(
        "matching_cv.app.services.unified_skill_service.unified_skill_service.extract_unified_from_files",
        new=AsyncMock(return_value=frontend_fixture),
    ):
        result = asyncio.run(
            pipeline_orchestrator.execute_pipeline(
                cv_file=cv_upload,
                jd_file=jd_upload,
                graph_mode="similarity_enriched",
                top_k=3,
                include_details=False,
                include_embeddings=True,
                include_graph=True,
            )
        )

    assert result.status == "partial"
    # details excluded
    assert result.extraction.cv.explicit_skills is None
    # embeddings included
    assert result.semantic_representation.cv_embeddings is not None
    assert result.semantic_representation.jd_embeddings is not None
    # graph included
    assert result.graph.graph_data is not None


def test_api_strictly_no_fabricated_scores(client: TestClient, frontend_fixture):
    """Strictly verify no fabricated compatibility or matching head scores (match_score is null)."""
    files = {
        "cv_file": ("frontend_cv.txt", io.BytesIO(b"Frontend developer with React"), "text/plain"),
        "jd_file": ("frontend_jd.txt", io.BytesIO(b"Hiring React developer"), "text/plain"),
    }

    with patch(
        "matching_cv.app.services.unified_skill_service.unified_skill_service.extract_unified_from_files",
        new=AsyncMock(return_value=frontend_fixture),
    ):
        resp = client.post(
            "/api/v1/pipeline/analyze",
            files=files,
            data={"graph_mode": "evidence_only"},
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["match_score"] is None
    assert data["status"] == "MODEL_NOT_TRAINED"
    raw_text = resp.text
    forbidden_fabricated_patterns = [
        '"match_score": 0.',
        '"match_score": 1.',
        '"matching_score"',
        '"compatibility_score"',
        '"overall_score"',
        '"cv_jd_score"',
    ]
    for pattern in forbidden_fabricated_patterns:
        assert pattern not in raw_text, f"Forbidden fabricated score pattern found: {pattern}"
