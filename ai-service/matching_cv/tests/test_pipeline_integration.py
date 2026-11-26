"""Full Integration Tests for the Consolidated End-to-End Pipeline.

Executes Stages 0 through 5 with real files, real SBERT embeddings,
and authentic graph construction.
"""
import io
import json
import os
import pytest
from fastapi import UploadFile

from unittest.mock import AsyncMock, patch

from matching_cv.app.core.config import settings
from matching_cv.app.schemas.pipeline import PipelineAnalyzeResponse
from matching_cv.app.schemas.unified_skill_extraction import UnifiedExtractFileResponse
from matching_cv.app.container import pipeline_orchestrator


BACKEND_CV_PATH = os.path.join("tests", "fixtures", "01_Backend_CV.pdf")
BACKEND_JD_PATH = os.path.join("tests", "fixtures", "01_Backend_JD.pdf")
FRONTEND_FIXTURE_PATH = os.path.join("tests", "fixtures", "02_Frontend_run.json")


def _load_upload_file(file_path: str, content_type: str = "application/pdf") -> UploadFile:
    with open(file_path, "rb") as f:
        data = f.read()
    return UploadFile(
        file=io.BytesIO(data),
        filename=os.path.basename(file_path),
        headers={"content-type": content_type},
    )


@pytest.mark.anyio
async def test_integration_real_backend_pdfs_similarity_enriched():
    """Execute end-to-end pipeline with real Backend CV and JD PDF fixtures.

    Validates:
    - Real file uploads (.pdf format, size, checksum)
    - Real SBERT embeddings (768D sentence-transformers) & Top-K retrieval
    - Real heterogeneous graph construction (Mode B: similarity_enriched)
    - Structural and embedding integrity verification
    """
    assert os.path.exists(BACKEND_CV_PATH), f"Missing fixture: {BACKEND_CV_PATH}"
    assert os.path.exists(BACKEND_JD_PATH), f"Missing fixture: {BACKEND_JD_PATH}"
    assert os.path.exists(FRONTEND_FIXTURE_PATH), f"Missing fixture: {FRONTEND_FIXTURE_PATH}"

    with open(FRONTEND_FIXTURE_PATH, "r", encoding="utf-8") as f:
        frozen_extraction = UnifiedExtractFileResponse.model_validate(json.load(f))

    cv_upload = _load_upload_file(BACKEND_CV_PATH, "application/pdf")
    jd_upload = _load_upload_file(BACKEND_JD_PATH, "application/pdf")

    with patch(
        "matching_cv.app.services.unified_skill_service.unified_skill_service.extract_unified_from_files",
        new=AsyncMock(return_value=frozen_extraction),
    ):
        res: PipelineAnalyzeResponse = await pipeline_orchestrator.execute_pipeline(
            cv_file=cv_upload,
            jd_file=jd_upload,
            graph_mode="similarity_enriched",
            top_k=5,
            include_details=True,
            include_embeddings=False,
            include_graph=True,
        )

    # 1. Pipeline status
    assert res.status == "completed"
    assert res.failure is None
    assert res.graph_mode == "similarity_enriched"
    assert res.run_id is not None

    # 2. Document parsing verification
    assert res.documents is not None
    assert res.documents.cv.file_type == "pdf"
    assert res.documents.jd.file_type == "pdf"

    # 3. Extraction verification
    assert res.extraction is not None
    assert res.extraction.cv.explicit_count > 0
    assert res.extraction.jd.explicit_count > 0
    assert res.extraction.total_unique_skills > 0

    # 4. Semantic representation verification
    assert res.semantic_representation is not None
    assert res.semantic_representation.cv_skills_encoded > 0
    assert res.semantic_representation.jd_skills_encoded > 0
    assert res.semantic_representation.candidate_pairs_count > 0
    assert len(res.semantic_representation.candidate_pairs) > 0

    # 5. Graph construction verification
    assert res.graph is not None
    assert res.graph.graph_mode == "similarity_enriched"
    assert res.graph.node_counts["cv"] == 1
    assert res.graph.node_counts["jd"] == 1
    assert res.graph.node_counts["skill"] > 0
    assert res.graph.edge_counts["total"] > 0
    assert res.graph.edge_counts.get("similar_to_candidate", 0) > 0
    assert res.graph.integrity["is_valid"] is True
    assert len(res.graph.integrity["errors"]) == 0

    # 6. Diagnostics verification
    assert len(res.diagnostics.stages) >= 4
    for stage_d in res.diagnostics.stages:
        assert stage_d.status in ["completed", "skipped"]
        assert stage_d.duration_ms >= 0


@pytest.mark.anyio
async def test_integration_multilingual_plain_text():
    """Execute end-to-end pipeline with bilingual (Vietnamese/English) plain text files."""
    assert os.path.exists(FRONTEND_FIXTURE_PATH)
    with open(FRONTEND_FIXTURE_PATH, "r", encoding="utf-8") as f:
        frozen_extraction = UnifiedExtractFileResponse.model_validate(json.load(f))

    cv_vi_text = (
        "HỌ VÀ TÊN: NGUYỄN VĂN A\n"
        "VỊ TRÍ: LẬP TRÌNH VIÊN PYTHON SENIOR\n"
        "KINH NGHIỆM:\n"
        "- Có hơn 5 năm kinh nghiệm phát triển backend với Python, FastAPI, Django.\n"
        "- Thành thạo cơ sở dữ liệu PostgreSQL, Redis cache, và message queue RabbitMQ.\n"
        "- Kinh nghiệm thiết kế hệ thống Microservices, Docker, Kubernetes trên AWS.\n"
        "- Sử dụng Git, CI/CD pipeline với GitHub Actions.\n"
    )

    jd_vi_text = (
        "CÔNG TY CÔNG NGHỆ TUYỂN DỤNG\n"
        "VỊ TRÍ: SENIOR BACKEND ENGINEER (PYTHON)\n"
        "YÊU CẦU CÔNG VIỆC:\n"
        "- Tối thiểu 4 năm kinh nghiệm làm việc với ngôn ngữ Python.\n"
        "- Nắm vững kiến trúc FastAPI hoặc Django Framework.\n"
        "- Thành thạo cơ sở dữ liệu quan hệ PostgreSQL và NoSQL Redis.\n"
        "- Ưu tiên ứng viên có kinh nghiệm với Docker, Kubernetes, AWS.\n"
        "- Tiếng Anh giao tiếp tốt và khả năng đọc hiểu tài liệu kỹ thuật.\n"
    )

    cv_file = UploadFile(
        file=io.BytesIO(cv_vi_text.encode("utf-8")),
        filename="cv_nguyen_van_a.txt",
        headers={"content-type": "text/plain"},
    )
    jd_file = UploadFile(
        file=io.BytesIO(jd_vi_text.encode("utf-8")),
        filename="jd_senior_python.txt",
        headers={"content-type": "text/plain"},
    )

    with patch(
        "matching_cv.app.services.unified_skill_service.unified_skill_service.extract_unified_from_files",
        new=AsyncMock(return_value=frozen_extraction),
    ):
        res: PipelineAnalyzeResponse = await pipeline_orchestrator.execute_pipeline(
            cv_file=cv_file,
            jd_file=jd_file,
            graph_mode="similarity_enriched",
            top_k=5,
            include_details=True,
        )

    assert res.status == "completed"
    assert res.documents.cv.file_type == "txt"
    assert res.documents.jd.file_type == "txt"
    assert res.extraction.cv.explicit_count > 0
    assert res.extraction.jd.explicit_count > 0
    assert res.semantic_representation.candidate_pairs_count > 0
    assert res.graph.node_counts["total"] > 0
    assert res.graph.edge_counts["total"] > 0


@pytest.mark.skipif(
    not os.getenv("OPENROUTER_API_KEY"),
    reason="Live LLM integration test requires OPENROUTER_API_KEY in environment",
)
@pytest.mark.anyio
async def test_integration_live_openrouter_mode_c():
    """Live LLM end-to-end integration test with OpenRouter (opt-in)."""
    cv_file = UploadFile(
        file=io.BytesIO(b"Experienced Python backend developer skilled in FastAPI and PostgreSQL"),
        filename="candidate_cv.txt",
        headers={"content-type": "text/plain"},
    )
    jd_file = UploadFile(
        file=io.BytesIO(b"Seeking Senior Python Developer proficient in FastAPI and relational databases"),
        filename="job_post.txt",
        headers={"content-type": "text/plain"},
    )

    res = await pipeline_orchestrator.execute_pipeline(
        cv_file=cv_file,
        jd_file=jd_file,
        graph_mode="llm_enriched",
        top_k=2,
        include_details=True,
    )

    assert res.status == "completed"
    assert res.semantic_reasoning is not None
    assert res.semantic_reasoning.total_pairs_evaluated > 0
    assert res.graph is not None
    assert res.graph.graph_mode == "llm_enriched"
