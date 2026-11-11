"""Unit tests for Stage 6C.2 extraction recovery and fail-closed integrity guardrails."""
import pytest
from matching_cv.app.schemas.skill_extraction import Evidence, ExtractedSkill, ExtractionResult, ExtractionStats, RawSkillMention
from matching_cv.app.schemas.unified_skill_extraction import (
    DocumentUnifiedResult,
    DocumentValidationResult,
    PipelineError,
    UnifiedExtractFileResponse,
)
from matching_cv.app.services.extraction_recovery import (
    ExtractionIntegrityError,
    attempt_json_truncation_recovery,
    validate_extraction_integrity,
    validate_pipeline_extraction_response,
)


def test_truncation_recovery_direct_parse():
    """Verify that a valid JSON string parses directly without modification."""
    valid_json = '{"skills": [{"surface_form": "Python", "sentence": "Used Python for backend."}]}'
    result, diag = attempt_json_truncation_recovery(valid_json)
    assert result is not None
    assert diag["success"] is True
    assert diag["recovery_method"] == "direct_parse"
    assert diag["salvaged_count"] == 1
    assert result["skills"][0]["surface_form"] == "Python"


def test_truncation_recovery_suffix_bracket_closure():
    """Verify that a JSON string truncated mid-stream is repaired by closing brackets."""
    # Simulated truncation mid-way through a second skill item
    truncated_json = (
        '{"skills": [\n'
        '  {"surface_form": "Python", "sentence": "Developed in Python.", "category": "Technology/Tool"},\n'
        '  {"surface_form": "Docker", "sentence": "Deployed with Docker.", "category": "Technology/Tool"},\n'
        '  {"surface_form": "Kuber'
    )
    result, diag = attempt_json_truncation_recovery(truncated_json)
    assert result is not None
    assert diag["success"] is True
    assert diag["recovery_method"] == "suffix_bracket_closure"
    assert diag["salvaged_count"] == 2
    assert result["skills"][0]["surface_form"] == "Python"
    assert result["skills"][1]["surface_form"] == "Docker"


def test_truncation_recovery_regex_block_salvage():
    """Verify regex salvage when JSON structure is heavily malformed before bracket closing."""
    malformed_json = (
        'Random garbage prefix ... '
        '{"surface_form": "PyTorch", "sentence": "Trained models in PyTorch."} '
        'corrupted tokens ... '
        '{"surface_form": "FastAPI", "sentence": "Built APIs using FastAPI."} '
        'unfinished {"surface_form": "broken...'
    )
    result, diag = attempt_json_truncation_recovery(malformed_json, min_skills=2)
    assert result is not None
    assert diag["success"] is True
    assert diag["recovery_method"] == "regex_block_salvage"
    assert diag["salvaged_count"] == 2
    assert result["skills"][0]["surface_form"] == "PyTorch"
    assert result["skills"][1]["surface_form"] == "FastAPI"


def test_truncation_recovery_unrecoverable():
    """Verify that unrecoverable strings return None."""
    garbage = "Total gibberish without any JSON or skill objects."
    result, diag = attempt_json_truncation_recovery(garbage)
    assert result is None
    assert diag["success"] is False
    assert diag["recovery_method"] == "exhausted_unrecoverable"


def test_validate_extraction_integrity_success():
    """Verify valid document passes fail-closed check."""
    skill = ExtractedSkill(
        skill_id="python",
        surface_forms=["Python"],
        category="Technology/Tool",
        evidences=[
            Evidence(
                surface_form="Python",
                sentence="Built backend in Python.",
                kind="skill",
            )
        ],
    )
    doc_res = DocumentUnifiedResult(
        filename="test.txt",
        document_type="CV",
        text_sha256="abc123",
        raw_text="A" * 600,
        explicit=ExtractionResult(
            filename="test.txt",
            document_type="CV",
            skills=[skill],
            stats=ExtractionStats(
                total_mentions=1,
                unique_skills=1,
                unresolved_evidences=1,
                unresolved_mentions=1,
            ),
        ),
    )
    # Should not raise
    validate_extraction_integrity(doc_res, raw_text="A" * 600, document_type="CV")


def test_validate_extraction_integrity_raises_on_none_explicit():
    """Verify that a document with explicit=None triggers ExtractionIntegrityError."""
    doc_res = DocumentUnifiedResult(
        filename="test.txt",
        document_type="CV",
        text_sha256="abc123",
        raw_text="A" * 600,
        explicit=None,
    )
    with pytest.raises(ExtractionIntegrityError, match="explicit extraction result is None"):
        validate_extraction_integrity(doc_res, raw_text="A" * 600, document_type="CV")


def test_validate_extraction_integrity_raises_on_zero_skills():
    """Verify that a substantial document (>500 chars) with 0 explicit skills triggers fail-closed error."""
    doc_res = DocumentUnifiedResult(
        filename="test.txt",
        document_type="CV",
        text_sha256="abc123",
        raw_text="A" * 600,
        explicit=ExtractionResult(
            filename="test.txt",
            document_type="CV",
            skills=[],
            stats=ExtractionStats(total_mentions=0, unique_skills=0),
        ),
    )
    with pytest.raises(ExtractionIntegrityError, match="yielded 0 explicit skills"):
        validate_extraction_integrity(doc_res, raw_text="A" * 600, document_type="CV")


def test_validate_pipeline_extraction_response_raises_on_error():
    """Verify that a pipeline response with errors or non-completed status triggers ExtractionIntegrityError."""
    response = UnifiedExtractFileResponse(
        run_id="run_123",
        status="partial_success",
        errors=[
            PipelineError(
                document="CV",
                stage="explicit_extraction",
                error_type="JSONDecodeError",
                message="Unterminated string",
            )
        ],
    )
    with pytest.raises(ExtractionIntegrityError, match="non-completed status"):
        validate_pipeline_extraction_response(response)
