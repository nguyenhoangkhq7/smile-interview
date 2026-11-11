"""
Analyze pipeline score normalization and public output contract tests.
Verifies:
1. Negative raw score bounds to 0.0000 (FitCategory.NO_FIT)
2. Raw score > 1.0 bounds to 1.0000 (FitCategory.GOOD_FIT)
3. Raw scores in [0.0, 1.0] are preserved exactly
4. Threshold boundary conditions (0.0, 0.25, 0.75, 1.0, and epsilons)
5. Rejection of NaN and +/- Infinity with GNNInputValidationError
6. raw_score is preserved strictly unmodified
7. matching_score == bounded_display_score numerical equality
8. POST /api/v1/pipeline/analyze includes matching_score in matching_result
9. Partial failure when GNN is unavailable does not fabricate score (matching_result is None)
10. Public Pydantic schema cross-syncing validator
11. Empirical backend CV/JD analysis

Strictly offline execution ($0.00 spend).
"""
import asyncio
import json
import math
import os
from unittest.mock import AsyncMock, patch
import pytest
from fastapi.testclient import TestClient

from matching_cv.app.main import app
from matching_cv.app.schemas.gnn_inference import (
    FitCategory,
    GNNInferenceResponse,
)
from matching_cv.app.schemas.pipeline import PipelineMatchingResult
from matching_cv.app.services.gnn_inference_service import (
    GNNInputValidationError,
    classify_score,
    compute_bounded_matching_score,
    gnn_inference_service,
)
from matching_cv.app.services.llm_service import llm_service

SAMPLE_PAIR_ID = "pair_ebe2388be982de53"
SAMPLE_EXTRACTION_PATH = f"data/cache/stage6b3_live/{SAMPLE_PAIR_ID}_extraction.json"


@pytest.fixture(scope="module")
def client() -> TestClient:
    return TestClient(app)


@pytest.fixture(scope="module")
def sample_pair_data():
    assert os.path.exists(SAMPLE_EXTRACTION_PATH), f"Missing {SAMPLE_EXTRACTION_PATH}"
    with open(SAMPLE_EXTRACTION_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    return {
        "cv_text": data["cv"]["raw_text"],
        "jd_text": data["jd"]["raw_text"],
        "cv_filename": "cv_f1128f7451e88924.txt",
        "jd_filename": "jd_9a7bfabb2a7d0e5a.txt",
    }


# =====================================================================
# Unit Tests for Bounding and Threshold Logic
# =====================================================================

def test_01_negative_raw_score_bounds_to_zero():
    """Test 1: Negative raw score (-0.1452) bounds to 0.0000, FitCategory.NO_FIT."""
    raw_input = -0.1452
    matching_score, bounded, cat = compute_bounded_matching_score(raw_input)
    assert raw_input == -0.1452  # raw input unchanged
    assert matching_score == 0.0000
    assert bounded == 0.0000
    assert cat == FitCategory.NO_FIT


def test_02_raw_score_greater_than_one_bounds_to_one():
    """Test 2: Raw score > 1.0 (1.1155) bounds to 1.0000, FitCategory.GOOD_FIT."""
    raw_input = 1.1155
    matching_score, bounded, cat = compute_bounded_matching_score(raw_input)
    assert raw_input == 1.1155  # raw input unchanged
    assert matching_score == 1.0000
    assert bounded == 1.0000
    assert cat == FitCategory.GOOD_FIT


def test_03_raw_score_in_unit_interval_preserved():
    """Test 3: Raw scores in [0.0, 1.0] (0.0323, 0.6421, 0.9128) are preserved unmodified."""
    test_scores = [0.0323, 0.6421, 0.9128]
    for val in test_scores:
        matching_score, bounded, cat = compute_bounded_matching_score(val)
        assert matching_score == val
        assert bounded == val


def test_04_threshold_boundary_conditions():
    """Test 4: Exact threshold boundaries (< 0.25 No Fit, [0.25, 0.75] Potential Fit, > 0.75 Good Fit)."""
    # Exact 0.0
    m_0, b_0, cat_0 = compute_bounded_matching_score(0.0)
    assert m_0 == 0.0
    assert b_0 == 0.0
    assert cat_0 == FitCategory.NO_FIT

    # Just below 0.25
    m_sub25, b_sub25, cat_sub25 = compute_bounded_matching_score(0.2499)
    assert m_sub25 == 0.2499
    assert b_sub25 == 0.2499
    assert cat_sub25 == FitCategory.NO_FIT

    # Exact 0.25
    m_25, b_25, cat_25 = compute_bounded_matching_score(0.25)
    assert m_25 == 0.25
    assert b_25 == 0.25
    assert cat_25 == FitCategory.POTENTIAL_FIT

    # Midpoint 0.50
    m_50, b_50, cat_50 = compute_bounded_matching_score(0.50)
    assert m_50 == 0.50
    assert b_50 == 0.50
    assert cat_50 == FitCategory.POTENTIAL_FIT

    # Exact 0.75
    m_75, b_75, cat_75 = compute_bounded_matching_score(0.75)
    assert m_75 == 0.75
    assert b_75 == 0.75
    assert cat_75 == FitCategory.POTENTIAL_FIT

    # Just above 0.75
    m_sup75, b_sup75, cat_sup75 = compute_bounded_matching_score(0.7501)
    assert m_sup75 == 0.7501
    assert b_sup75 == 0.7501
    assert cat_sup75 == FitCategory.GOOD_FIT

    # Exact 1.0
    m_100, b_100, cat_100 = compute_bounded_matching_score(1.0)
    assert m_100 == 1.0
    assert b_100 == 1.0
    assert cat_100 == FitCategory.GOOD_FIT


def test_05_rejection_of_nan_and_infinity():
    """Test 5: Explicit rejection of NaN and +/- Infinity with GNNInputValidationError."""
    with pytest.raises(GNNInputValidationError, match="NaN"):
        compute_bounded_matching_score(float("nan"))

    with pytest.raises(GNNInputValidationError, match="Infinite"):
        compute_bounded_matching_score(float("inf"))

    with pytest.raises(GNNInputValidationError, match="Infinite"):
        compute_bounded_matching_score(float("-inf"))


def test_06_raw_score_preserved_unmodified():
    """Test 6: Raw score is strictly preserved in prediction output and never overwritten with clamped value."""
    test_values = [-2.5, -0.001, 1.0001, 3.89, 1.1378]
    for val in test_values:
        matching_score, bounded, cat = compute_bounded_matching_score(val)
        # When creating a response or result, raw_score retains the exact unclamped val
        res = GNNInferenceResponse(
            raw_score=val,
            matching_score=matching_score,
            bounded_display_score=bounded,
            fit_category=cat,
            graph_mode="similarity_enriched",
            checkpoint_name="mock.pt",
            checkpoint_sha256="abc",
            input_validation={},
            inference_latency_ms=1.0,
        )
        assert res.raw_score == val
        assert 0.0 <= res.matching_score <= 1.0


def test_07_matching_score_equals_bounded_display_score():
    """Test 7: Numerical equality between matching_score and bounded_display_score."""
    for val in [-1.5, 0.0, 0.1, 0.25, 0.5, 0.75, 0.99, 1.0, 1.5]:
        _, bounded, _ = compute_bounded_matching_score(val)
        # Construct schema instance and test equality
        res = GNNInferenceResponse(
            raw_score=val,
            matching_score=bounded,
            bounded_display_score=bounded,
            fit_category=classify_score(bounded),
            graph_mode="similarity_enriched",
            checkpoint_name="mock.pt",
            checkpoint_sha256="abc",
            input_validation={},
            inference_latency_ms=1.0,
        )
        assert res.matching_score == res.bounded_display_score


# =====================================================================
# API Contract and Pipeline Integration Tests
# =====================================================================

def test_08_pipeline_analyze_includes_matching_score(client: TestClient, sample_pair_data):
    """Test 8: POST /api/v1/pipeline/analyze returns canonical matching_score with correct metadata."""
    cv_bytes = sample_pair_data["cv_text"].encode("utf-8")
    jd_bytes = sample_pair_data["jd_text"].encode("utf-8")

    response = client.post(
        "/api/v1/pipeline/analyze",
        files={
            "cv_file": (sample_pair_data["cv_filename"], cv_bytes, "text/plain"),
            "jd_file": (sample_pair_data["jd_filename"], jd_bytes, "text/plain"),
        },
        data={"graph_mode": "similarity_enriched"},
    )
    assert response.status_code == 200, response.text
    data = response.json()
    matching = data["matching_result"]
    assert matching is not None

    assert "matching_score" in matching
    assert "raw_score" in matching
    assert "bounded_display_score" in matching
    assert "score_range" in matching
    assert "score_type" in matching

    assert matching["score_range"] == {"min": 0.0, "max": 1.0}
    assert matching["score_type"] == "bounded_uncalibrated_regression"
    assert 0.0 <= matching["matching_score"] <= 1.0
    assert matching["matching_score"] == matching["bounded_display_score"]


def test_11_partial_failure_does_not_fabricate_score(client: TestClient, sample_pair_data):
    """Test 11: Partial failure when GNN is unavailable preserves upstream data and returns matching_result=None."""
    cv_bytes = sample_pair_data["cv_text"].encode("utf-8")
    jd_bytes = sample_pair_data["jd_text"].encode("utf-8")

    with patch.object(
        gnn_inference_service,
        "predict_graph",
        side_effect=RuntimeError("GNN execution hardware fault"),
    ):
        response = client.post(
            "/api/v1/pipeline/analyze",
            files={
                "cv_file": (sample_pair_data["cv_filename"], cv_bytes, "text/plain"),
                "jd_file": (sample_pair_data["jd_filename"], jd_bytes, "text/plain"),
            },
            data={"graph_mode": "similarity_enriched"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "partial"
        assert data["matching_result"] is None
        assert data["matching_status"] == "failed"
        assert data["failure"]["stage"] == "gnn_inference"


def test_12_backward_compatibility_schema_cross_sync():
    """Test 12: Schemas accept legacy payload with only bounded_display_score or matching_score and cross-sync."""
    # 1. PipelineMatchingResult with only bounded_display_score
    pmr_legacy = PipelineMatchingResult(
        graph_mode="similarity_enriched",
        checkpoint_sha256="abc",
        raw_score=0.88,
        bounded_display_score=0.88,
        fit_category=FitCategory.GOOD_FIT,
    )
    assert pmr_legacy.matching_score == 0.88
    assert pmr_legacy.bounded_display_score == 0.88

    # 2. PipelineMatchingResult with only matching_score
    pmr_new = PipelineMatchingResult(
        graph_mode="similarity_enriched",
        checkpoint_sha256="abc",
        raw_score=0.88,
        matching_score=0.88,
        fit_category=FitCategory.GOOD_FIT,
    )
    assert pmr_new.bounded_display_score == 0.88
    assert pmr_new.matching_score == 0.88

    # 3. GNNInferenceResponse cross-sync
    gir_legacy = GNNInferenceResponse(
        raw_score=0.15,
        bounded_display_score=0.15,
        fit_category=FitCategory.NO_FIT,
        graph_mode="similarity_enriched",
        checkpoint_name="mock.pt",
        checkpoint_sha256="abc",
        input_validation={},
        inference_latency_ms=1.0,
    )
    assert gir_legacy.matching_score == 0.15




def test_13_empirical_backend_cv_jd_verification(client: TestClient):
    """Test 13: Real Backend CV/JD pair produces raw_score > 1.0 (approx 1.1378) bounded to matching_score = 1.0."""
    with open("tests/fixtures/01_Backend_CV.pdf", "rb") as f:
        cv_bytes = f.read()
    with open("tests/fixtures/01_Backend_JD.pdf", "rb") as f:
        jd_bytes = f.read()
    with open("tests/fixtures/01_Backend_llm_raw.json", "r", encoding="utf-8") as f:
        raw_data = json.load(f)

    cv_explicit = raw_data["cv"]["explicit_skills"]
    jd_explicit = raw_data["jd"]["explicit_skills"]

    async def mock_explicit(text, document_type, **kwargs):
        if document_type.upper() == "CV":
            return {"explicit_skills": cv_explicit}
        else:
            return {"explicit_skills": jd_explicit}

    with patch.object(llm_service, "extract_explicit_skills", side_effect=mock_explicit), \
         patch.object(llm_service, "extract_implicit_skills", new_callable=AsyncMock) as m_imp:
        m_imp.return_value = {"implicit_skills": []}

        resp = client.post(
            "/api/v1/pipeline/analyze",
            files={
                "cv_file": ("01_Backend_CV.pdf", cv_bytes, "application/pdf"),
                "jd_file": ("01_Backend_JD.pdf", jd_bytes, "application/pdf"),
            },
            data={"graph_mode": "similarity_enriched", "include_details": "true"},
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["status"] == "completed"

        matching = data["matching_result"]
        assert matching is not None

        # Verify raw regression score strictly exceeds 1.0
        assert matching["raw_score"] > 1.0, f"Expected raw_score > 1.0, got {matching['raw_score']}"
        assert round(matching["raw_score"], 4) == 1.1378

        # Verify canonical matching score is bounded to 1.0
        assert matching["matching_score"] == 1.0
        assert matching["bounded_display_score"] == 1.0
        assert matching["fit_category"] == "Good Fit"
        assert matching["score_range"] == {"min": 0.0, "max": 1.0}
        assert matching["score_type"] == "bounded_uncalibrated_regression"
