"""Unified end-to-end pipeline API endpoint."""
import logging
from typing import Optional

from fastapi import (
    APIRouter,
    File,
    Form,
    Request,
    Response,
    UploadFile,
    status,
)
from fastapi.responses import JSONResponse

from matching_cv.app.schemas.standardized_output import (
    STANDARDIZED_OUTPUT_SCHEMA_VERSION,
    STANDARDIZED_OUTPUT_VERSION_HEADER,
    PublicErrorResponse,
    StandardizedPipelineOutput,
)
from matching_cv.app.services.standardized_output_builder import standardized_output_from_internal

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post(
    "/analyze",
    response_model=StandardizedPipelineOutput,
    status_code=status.HTTP_200_OK,
    summary="CV-JD pipeline: standardized skill-gap and proficiency input (standardized-output-v1)",
    response_description=(
        "Compact public output: match_score (null until a verified trained checkpoint exists), status, cv_text, "
        "jd_text, skill_gap_input and proficiency_input. Internal diagnostics are not part of this contract."
    ),
)
async def analyze_pipeline(
    request: Request,
    response: Response,
    cv_file: UploadFile = File(
        ...,
        description="Candidate CV document file (.pdf or .txt)",
    ),
    jd_file: UploadFile = File(
        ...,
        description="Job Description document file (.pdf or .txt)",
    ),
    graph_mode: str = Form(
        default="similarity_enriched",
        description="Heterogeneous graph mode: 'similarity_enriched' (Mode B - default research mode), 'evidence_only' (Mode A), 'llm_enriched' (Mode C)",
    ),
    top_k: int = Form(
        default=5,
        description="Number of Top-K candidate CV-JD skill pairs to retrieve via SBERT cosine similarity",
    ),
    include_details: bool = Form(
        default=True,
        description="Whether to include granular lists of explicit/implicit skills and LLM reasoning results",
    ),
    include_embeddings: bool = Form(
        default=False,
        description="Whether to include 768-dimensional float vectors in the response",
    ),
    include_graph: bool = Form(
        default=False,
        description="Whether to include full in-memory graph data and PyG HeteroData export metadata",
    ),
    enable_critic: bool = Form(
        default=False,
        description="Whether to enable selective critic pass during LLM semantic reasoning",
    ),
    reasoning_max_pairs: int = Form(
        default=25,
        ge=1,
        le=100,
        description="Total budget for LLM semantic reasoning pairs (Stage 4)",
    ),
    reasoning_selection_strategy: str = Form(
        default="balanced_coverage",
        description="Candidate selection strategy: 'balanced_coverage' (stratified round-robin across CV skills) or 'global_top_cosine' (global top-N)",
    ),
    enable_skill_importance: Optional[bool] = Form(
        default=None,
        description="Explicitly enable/disable skill importance estimation (defaults to JSI_IMPORTANCE_ENABLED)",
    ),
) -> StandardizedPipelineOutput:
    """
    Executes the consolidated CV-JD inference pipeline from raw documents through Stage 6 GNN Compatibility Inference:

    1. **Stage 0 — Input Validation**: Checks file extensions, sizes, and non-empty content.
    2. **Stage 1 — Document Parsing**: Extracts raw text and computes document SHA-256 hashes.
    3. **Stage 2 — Unified Skill Extraction**: Runs explicit extraction, implicit inference, and semantic deduplication.
    4. **Stage 3 — SBERT Representation**: Encodes competencies into 768D embeddings and retrieves Top-K candidate pairs.
    5. **Stage 4 — LLM Semantic Reasoning**: Classifies skill identity, relationship type, and directionality (Mode C).
    6. **Stage 5 — Graph Construction**: Constructs a multi-mode heterogeneous graph and validates structural and embedding integrity.
    7. **Stage 6 — GNN Inference**: Evaluates RelationAwareHybridGNN compatibility and outputs an uncalibrated regression score.
    """
    orchestrator = request.app.state.pipeline_orchestrator
    result = await orchestrator.execute_pipeline(
        cv_file=cv_file,
        jd_file=jd_file,
        graph_mode=graph_mode,
        top_k=top_k,
        include_details=include_details,
        include_embeddings=include_embeddings,
        include_graph=include_graph,
        enable_critic=enable_critic,
        reasoning_max_pairs=reasoning_max_pairs,
        reasoning_selection_strategy=reasoning_selection_strategy,
        enable_skill_importance=enable_skill_importance,
    )

    # Internal diagnostics (run_id, extraction, graph, timings, failure detail) stay in logs / the internal DTO.
    if result.status == "failed" and result.failure is not None:
        err_code = result.failure.error_code
        if err_code in ("MISSING_FILE", "UNSUPPORTED_FILE_TYPE", "EMPTY_FILE", "FILE_SIZE_EXCEEDED", "INVALID_TOP_K", "INVALID_GRAPH_MODE"):
            http_status = status.HTTP_400_BAD_REQUEST
        elif err_code in ("GRAPH_INTEGRITY_VIOLATION", "VALIDATION_ERROR"):
            http_status = status.HTTP_422_UNPROCESSABLE_CONTENT
        else:
            http_status = status.HTTP_500_INTERNAL_SERVER_ERROR
        return JSONResponse(
            status_code=http_status,
            content=PublicErrorResponse(
                run_id=result.failure.run_id,
                stage=result.failure.stage,
                error_code=err_code,
                message=result.failure.message,
                retryable=result.failure.retryable,
            ).model_dump(),
            headers={STANDARDIZED_OUTPUT_VERSION_HEADER: STANDARDIZED_OUTPUT_SCHEMA_VERSION},
        )

    try:
        built = standardized_output_from_internal(result)
    except Exception as exc:  # pragma: no cover - defensive; details stay in logs only
        logger.error(f"[{result.run_id}] Standardized output assembly failed: {exc}", exc_info=True)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=PublicErrorResponse(
                run_id=result.run_id,
                stage="standardized_output",
                error_code="STANDARDIZED_OUTPUT_FAILURE",
                message="Failed to assemble the standardized pipeline output.",
                retryable=False,
            ).model_dump(),
            headers={STANDARDIZED_OUTPUT_VERSION_HEADER: STANDARDIZED_OUTPUT_SCHEMA_VERSION},
        )

    response.headers[STANDARDIZED_OUTPUT_VERSION_HEADER] = STANDARDIZED_OUTPUT_SCHEMA_VERSION
    return built.public
