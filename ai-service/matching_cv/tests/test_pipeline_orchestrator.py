"""Unit tests for PipelineOrchestrator."""
import io
import json
import os
import asyncio
import threading
from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from fastapi import UploadFile

from matching_cv.app.schemas.hetero_graph import (
    GraphIntegrityReport,
    HeteroGraphData,
    SkillNode,
)
from matching_cv.research.paper_aligned_gnn.schemas import PaperAlignedGraphIntegrityReport
from matching_cv.app.schemas.pipeline import PipelineAnalyzeResponse
from matching_cv.app.schemas.semantic_reasoning import (
    BatchSkillPairReasoningResponse,
    SkillPairReasoningResult,
    SkillRef,
)
from matching_cv.app.schemas.semantic_representation import (
    EmbeddingRecord,
    SemanticRepresentationResponse,
    TopKRetrievalResult,
)
from matching_cv.app.schemas.unified_skill_extraction import (
    DocumentUnifiedResult,
    DocumentValidationResult,
    ExtractionResult,
    ImplicitExtractedSkill,
    ImplicitExtractionResult,
    UnifiedExtractFileResponse,
    UnifiedExtractionSummary,
)
from matching_cv.app.container import pipeline_orchestrator
from matching_cv.app.services.pipeline_semantic_stage import SemanticStageError

FRONTEND_FIXTURE_PATH = os.path.join("tests", "fixtures", "02_Frontend_run.json")


def make_dummy_upload(filename: str, content: bytes) -> UploadFile:
    """Helper to construct in-memory UploadFile."""
    return UploadFile(
        file=io.BytesIO(content),
        filename=filename,
        headers={"content-type": "application/pdf" if filename.endswith(".pdf") else "text/plain"},
    )


@pytest.fixture
def valid_cv_file():
    return make_dummy_upload("candidate_cv.pdf", b"%PDF-1.4 Mock CV Content with React and TypeScript competencies")


@pytest.fixture
def valid_jd_file():
    return make_dummy_upload("job_description.txt", b"Job Description: Looking for Senior Frontend Engineer with React experience.")


@pytest.fixture
def frontend_unified_resp() -> UnifiedExtractFileResponse:
    with open(FRONTEND_FIXTURE_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    return UnifiedExtractFileResponse.model_validate(data)


# -----------------------------------------------------------------------------
# 1. INPUT VALIDATION TESTS (STAGE 0)
# -----------------------------------------------------------------------------


def test_slow_embedding_load_keeps_event_loop_responsive(valid_cv_file, valid_jd_file, frontend_unified_resp):
    """A cold SBERT load must allow concurrent requests to keep running."""
    started, release = threading.Event(), threading.Event()

    def slow_embedding(**kwargs):
        started.set()
        release.wait(timeout=2)
        raise SemanticStageError(RuntimeError("simulated model load failure"), 1)

    async def scenario():
        pending = asyncio.create_task(pipeline_orchestrator.execute_pipeline(
            cv_file=valid_cv_file, jd_file=valid_jd_file,
        ))
        try:
            assert await asyncio.to_thread(started.wait, 1)
            # This coroutine must resume while the synchronous model load is blocked.
            assert not pending.done()
        finally:
            release.set()
            result = await pending
        assert result.failure.error_code == "EMBEDDING_FAILURE"

    with patch("matching_cv.app.services.unified_skill_service.unified_skill_service.extract_unified_from_files",
               new=AsyncMock(return_value=frontend_unified_resp)), \
         patch.object(pipeline_orchestrator.semantic_stage, "execute", side_effect=slow_embedding):
        asyncio.run(scenario())

@pytest.mark.anyio
async def test_validation_missing_cv_file(valid_jd_file):
    """Verify failure when cv_file is missing."""
    res = await pipeline_orchestrator.execute_pipeline(cv_file=None, jd_file=valid_jd_file)
    assert res.status == "failed"
    assert res.failure is not None
    assert res.failure.stage == "input_validation"
    assert res.failure.error_code == "MISSING_FILE"
    assert "cv_file" in res.failure.message.lower()


@pytest.mark.anyio
async def test_validation_missing_jd_file(valid_cv_file):
    """Verify failure when jd_file is missing."""
    res = await pipeline_orchestrator.execute_pipeline(cv_file=valid_cv_file, jd_file=None)
    assert res.status == "failed"
    assert res.failure is not None
    assert res.failure.stage == "input_validation"
    assert res.failure.error_code == "MISSING_FILE"
    assert "jd_file" in res.failure.message.lower()


@pytest.mark.anyio
async def test_validation_unsupported_file_extension():
    """Verify rejection of non-PDF/TXT file extensions."""
    cv = make_dummy_upload("profile.docx", b"Word document content")
    jd = make_dummy_upload("job.txt", b"Job content")
    res = await pipeline_orchestrator.execute_pipeline(cv_file=cv, jd_file=jd)
    assert res.status == "failed"
    assert res.failure.error_code == "UNSUPPORTED_FILE_TYPE"
    assert ".docx" in res.failure.message


@pytest.mark.anyio
async def test_validation_empty_file():
    """Verify rejection of empty 0-byte file."""
    cv = make_dummy_upload("empty_cv.pdf", b"")
    jd = make_dummy_upload("job.txt", b"Valid job description text")
    res = await pipeline_orchestrator.execute_pipeline(cv_file=cv, jd_file=jd)
    assert res.status == "failed"
    assert res.failure.error_code == "EMPTY_FILE"


@pytest.mark.anyio
async def test_validation_invalid_top_k(valid_cv_file, valid_jd_file):
    """Verify rejection of top_k out of allowed bounds."""
    res = await pipeline_orchestrator.execute_pipeline(cv_file=valid_cv_file, jd_file=valid_jd_file, top_k=0)
    assert res.status == "failed"
    assert res.failure.error_code == "INVALID_TOP_K"

    res_large = await pipeline_orchestrator.execute_pipeline(cv_file=valid_cv_file, jd_file=valid_jd_file, top_k=99)
    assert res_large.status == "failed"
    assert res_large.failure.error_code == "INVALID_TOP_K"


@pytest.mark.anyio
async def test_validation_invalid_graph_mode(valid_cv_file, valid_jd_file):
    """Verify rejection of invalid graph_mode value."""
    res = await pipeline_orchestrator.execute_pipeline(cv_file=valid_cv_file, jd_file=valid_jd_file, graph_mode="unknown_mode")  # type: ignore
    assert res.status == "failed"
    assert res.failure.error_code == "INVALID_GRAPH_MODE"


# -----------------------------------------------------------------------------
# 2. STAGE EXECUTION & MULTI-MODE TESTS
# -----------------------------------------------------------------------------

@pytest.mark.anyio
async def test_mode_a_evidence_only_execution(valid_cv_file, valid_jd_file, frontend_unified_resp):
    """Verify Mode A execution skips SBERT and LLM reasoning and constructs grounded skeleton."""
    with patch("matching_cv.app.services.unified_skill_service.unified_skill_service.extract_unified_from_files", new_callable=AsyncMock) as mock_extract:
        mock_extract.return_value = frontend_unified_resp

        res = await pipeline_orchestrator.execute_pipeline(
            cv_file=valid_cv_file,
            jd_file=valid_jd_file,
            graph_mode="evidence_only",
            include_details=True,
            include_embeddings=False,
            include_graph=False,
        )

        assert res.status == "partial"
        assert res.matching_status == "MODEL_NOT_TRAINED"
        assert res.matching_result is None
        assert res.graph_mode == "evidence_only"
        assert res.documents is not None
        assert res.extraction is not None
        assert res.semantic_representation is None
        assert res.semantic_reasoning is None

        # Verify Stage Diagnostics
        stage_names = [s.stage for s in res.diagnostics.stages]
        assert "input_validation" in stage_names
        assert "unified_skill_extraction" in stage_names
        assert "graph_construction" in stage_names

        # Check skipped stages
        sbert_diag = next(s for s in res.diagnostics.stages if s.stage == "semantic_representation")
        assert sbert_diag.status == "skipped"

        reason_diag = next(s for s in res.diagnostics.stages if s.stage == "semantic_reasoning")
        assert reason_diag.status == "skipped"

        # Verify Mode A paper-aligned bipartite graph stats (no skill-skill similarity or LLM edges)
        assert res.graph is not None
        assert res.graph.node_counts["resume"] == 1
        assert res.graph.node_counts["job"] == 1
        assert res.graph.node_counts["skill"] == 67
        assert res.graph.node_counts["total"] == 69
        assert res.graph.edge_counts["total"] == 156
        assert "similar_to_candidate" not in res.graph.edge_counts
        assert "equivalent_to" not in res.graph.edge_counts


@pytest.mark.anyio
async def test_mode_b_similarity_enriched_execution(valid_cv_file, valid_jd_file, frontend_unified_resp):
    """Verify Mode B executes SBERT representation but skips LLM reasoning and keeps bipartite graph."""
    with patch("matching_cv.app.services.unified_skill_service.unified_skill_service.extract_unified_from_files", new_callable=AsyncMock) as mock_extract:
        mock_extract.return_value = frontend_unified_resp

        res = await pipeline_orchestrator.execute_pipeline(
            cv_file=valid_cv_file,
            jd_file=valid_jd_file,
            graph_mode="similarity_enriched",
            top_k=5,
        )

        assert res.status == "partial"
        assert res.matching_status == "MODEL_NOT_TRAINED"
        assert res.matching_result is None
        assert res.graph_mode == "similarity_enriched"
        assert res.semantic_representation is not None
        assert res.semantic_representation.top_k == 5
        assert res.semantic_representation.candidate_pairs_count > 0
        assert res.semantic_reasoning is None

        # Reason stage skipped
        reason_diag = next(s for s in res.diagnostics.stages if s.stage == "semantic_reasoning")
        assert reason_diag.status == "skipped"

        # Verify paper-aligned bipartite graph does not inject skill-skill edges
        assert res.graph is not None
        assert res.graph.node_counts["resume"] == 1
        assert res.graph.node_counts["job"] == 1
        assert res.graph.node_counts["skill"] == 67
        assert res.graph.node_counts["total"] == 69
        assert res.graph.edge_counts["total"] == 156
        assert "similar_to_candidate" not in res.graph.edge_counts
        assert "equivalent_to" not in res.graph.edge_counts


@pytest.mark.anyio
async def test_no_embeddings_in_default_response(valid_cv_file, valid_jd_file, frontend_unified_resp):
    """Verify that 768D float vector embeddings are excluded by default."""
    with patch("matching_cv.app.services.unified_skill_service.unified_skill_service.extract_unified_from_files", new_callable=AsyncMock) as mock_extract:
        mock_extract.return_value = frontend_unified_resp

        res = await pipeline_orchestrator.execute_pipeline(
            cv_file=valid_cv_file,
            jd_file=valid_jd_file,
            graph_mode="similarity_enriched",
            include_embeddings=False,
        )

        assert res.semantic_representation is not None
        assert res.semantic_representation.cv_embeddings is None
        assert res.semantic_representation.jd_embeddings is None


@pytest.mark.anyio
async def test_include_embeddings_flag(valid_cv_file, valid_jd_file, frontend_unified_resp):
    """Verify that embeddings are included when include_embeddings=True."""
    with patch("matching_cv.app.services.unified_skill_service.unified_skill_service.extract_unified_from_files", new_callable=AsyncMock) as mock_extract:
        mock_extract.return_value = frontend_unified_resp

        res = await pipeline_orchestrator.execute_pipeline(
            cv_file=valid_cv_file,
            jd_file=valid_jd_file,
            graph_mode="similarity_enriched",
            include_embeddings=True,
        )

        assert res.semantic_representation is not None
        assert res.semantic_representation.cv_embeddings is not None
        assert len(res.semantic_representation.cv_embeddings) > 0


@pytest.mark.anyio
async def test_no_fabricated_matching_score(valid_cv_file, valid_jd_file, frontend_unified_resp):
    """Verify that no fabricated CV-JD matching score or compatibility percentage is returned."""
    with patch("matching_cv.app.services.unified_skill_service.unified_skill_service.extract_unified_from_files", new_callable=AsyncMock) as mock_extract:
        mock_extract.return_value = frontend_unified_resp

        res = await pipeline_orchestrator.execute_pipeline(
            cv_file=valid_cv_file,
            jd_file=valid_jd_file,
            graph_mode="similarity_enriched",
        )

        res_dict = res.model_dump()
        for forbidden_key in ("matching_score", "compatibility_score", "match_percentage", "fit_score"):
            assert forbidden_key not in res_dict


# -----------------------------------------------------------------------------
# 4. FAILURE HANDLING & ISOLATION
# -----------------------------------------------------------------------------

@pytest.mark.anyio
async def test_extraction_failure_handling(valid_cv_file, valid_jd_file):
    """Verify structured failure response when extraction service throws an exception."""
    with patch("matching_cv.app.services.unified_skill_service.unified_skill_service.extract_unified_from_files", new_callable=AsyncMock) as mock_extract:
        mock_extract.side_effect = RuntimeError("OpenRouter API 503 Service Unavailable")

        res = await pipeline_orchestrator.execute_pipeline(
            cv_file=valid_cv_file,
            jd_file=valid_jd_file,
            graph_mode="evidence_only",
        )

        assert res.status == "failed"
        assert res.failure is not None
        assert res.failure.stage == "unified_skill_extraction"
        assert res.failure.error_code == "EXTRACTION_FAILURE"
        assert res.failure.retryable is True
        assert "503" in res.failure.message


@pytest.mark.anyio
async def test_reasoning_failure_handling(valid_cv_file, valid_jd_file, frontend_unified_resp):
    """Verify structured failure response when LLM reasoning fails."""
    with patch("matching_cv.app.services.unified_skill_service.unified_skill_service.extract_unified_from_files", new_callable=AsyncMock) as mock_extract, \
         patch("matching_cv.app.services.skill_reasoning_service.skill_reasoning_service.reason_stage3_topk", new_callable=AsyncMock) as mock_reason:

        mock_extract.return_value = frontend_unified_resp
        mock_reason.side_effect = TimeoutError("OpenRouter request timed out after 45.0s")

        res = await pipeline_orchestrator.execute_pipeline(
            cv_file=valid_cv_file,
            jd_file=valid_jd_file,
            graph_mode="llm_enriched",
        )

        assert res.status == "failed"
        assert res.failure is not None
        assert res.failure.stage == "semantic_reasoning"
        assert res.failure.error_code == "REASONING_FAILURE"
        assert res.failure.retryable is True
        assert "timed out" in res.failure.message.lower()


@pytest.mark.anyio
async def test_graph_integrity_violation_handling(valid_cv_file, valid_jd_file, frontend_unified_resp):
    """Verify structured failure when graph builder encounters an integrity violation."""
    with patch("matching_cv.app.services.unified_skill_service.unified_skill_service.extract_unified_from_files", new_callable=AsyncMock) as mock_extract, \
         patch.object(pipeline_orchestrator.graph_builder, "validate_graph_integrity") as mock_validate:

        mock_extract.return_value = frontend_unified_resp
        mock_validate.return_value = PaperAlignedGraphIntegrityReport(
            is_valid=False,
            errors=["Orphan edge detected: source node cv_123 does not exist"],
        )

        res = await pipeline_orchestrator.execute_pipeline(
            cv_file=valid_cv_file,
            jd_file=valid_jd_file,
            graph_mode="evidence_only",
        )

        assert res.status == "failed"
        assert res.failure is not None
        assert res.failure.stage == "graph_construction"
        assert res.failure.error_code == "GRAPH_INTEGRITY_VIOLATION"
        assert "Orphan edge" in res.failure.message
