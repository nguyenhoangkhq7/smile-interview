"""Inference stage adapter for the analyze pipeline."""
from dataclasses import dataclass
import logging
import time
from typing import Any, Dict, Optional, Protocol

from torch_geometric.data import HeteroData

from matching_cv.app.schemas.gnn_inference import GNNInferenceResponse
from matching_cv.app.schemas.pipeline import (
    PipelineFailureDetail,
    PipelineMatchingResult,
    StageDiagnostic,
)
from matching_cv.app.services.gnn_inference_service import (
    GNNInputValidationError,
    PaperGNNCheckpointUnavailableError,
    PaperGNNIncompatibleCheckpointError,
)

logger = logging.getLogger(__name__)


class GraphPredictor(Protocol):
    """Port implemented by the configured graph inference engine."""

    def predict_graph(
        self,
        graph: HeteroData,
        mode: str,
        pair_id: Optional[str] = None,
    ) -> GNNInferenceResponse: ...


@dataclass(frozen=True)
class PipelineInferenceOutcome:
    """Inference values and diagnostics consumed by pipeline response assembly."""

    matching_result: Optional[PipelineMatchingResult]
    matching_status: Optional[str]
    pipeline_status: str
    failure: Optional[PipelineFailureDetail]
    diagnostic: StageDiagnostic
    errors: list[Dict[str, Any]]
    duration_ms: float


class PipelineInferenceService:
    """Runs graph inference and translates model outcomes into pipeline DTOs."""

    def __init__(self, predictor: GraphPredictor) -> None:
        self._predictor = predictor

    def infer(
        self,
        *,
        graph: HeteroData,
        graph_mode: str,
        pair_id: str,
        run_id: str,
    ) -> PipelineInferenceOutcome:
        started_at = time.perf_counter()
        try:
            result = self._predictor.predict_graph(
                graph=graph,
                mode=graph_mode,
                pair_id=pair_id,
            )
        except PaperGNNCheckpointUnavailableError as error:
            duration = self._duration(started_at)
            logger.info(
                f"[{run_id}] Stage 6 entering Graph-Only / Diagnostic Mode "
                f"(MODEL_NOT_TRAINED / CHECKPOINT_UNAVAILABLE): {error}"
            )
            failure = PipelineFailureDetail(
                stage="gnn_inference",
                error_code="MODEL_NOT_TRAINED",
                message=(
                    "CHECKPOINT_UNAVAILABLE: PaperAlignedHybridGNN does not yet have a verified trained checkpoint. "
                    "Stages 0-5 completed in Graph-Only Diagnostic Mode without numeric compatibility score."
                ),
                retryable=False,
                run_id=run_id,
            )
            return self._partial_outcome(
                duration=duration,
                status="MODEL_NOT_TRAINED",
                error_code="MODEL_NOT_TRAINED",
                message=str(error),
                diagnostic_status="skipped",
                diagnostic_error=(
                    "MODEL_NOT_TRAINED: CHECKPOINT_UNAVAILABLE - Verified trained checkpoint for "
                    "PaperAlignedHybridGNN is unavailable; returning validated paper-aligned graph diagnostics only."
                ),
                failure=failure,
                diagnostic_status_detail="CHECKPOINT_UNAVAILABLE",
            )
        except PaperGNNIncompatibleCheckpointError as error:
            duration = self._duration(started_at)
            logger.error(f"[{run_id}] Stage 6 incompatible checkpoint rejected: {error}")
            failure = PipelineFailureDetail(
                stage="gnn_inference",
                error_code="INCOMPATIBLE_CHECKPOINT_ARCHITECTURE",
                message=str(error),
                retryable=False,
                run_id=run_id,
            )
            return self._partial_outcome(
                duration=duration,
                status="INCOMPATIBLE_CHECKPOINT_ARCHITECTURE",
                error_code="INCOMPATIBLE_CHECKPOINT_ARCHITECTURE",
                message=str(error),
                diagnostic_status="failed",
                diagnostic_error=str(error),
                failure=failure,
            )
        except GNNInputValidationError as error:
            duration = self._duration(started_at)
            logger.error(f"[{run_id}] Stage 6 GNN validation failure: {error}", exc_info=True)
            failure = PipelineFailureDetail(
                stage="gnn_inference",
                error_code="GRAPH_FEATURE_CONTRACT_VIOLATION",
                message=f"Kiểm tra đặc trưng đồ thị GNN thất bại: {str(error)}",
                retryable=False,
                run_id=run_id,
            )
            return self._partial_outcome(
                duration=duration,
                status="failed",
                error_code="GRAPH_FEATURE_CONTRACT_VIOLATION",
                message=str(error),
                diagnostic_status="failed",
                diagnostic_error=str(error),
                failure=failure,
            )
        except FileNotFoundError as error:
            duration = self._duration(started_at)
            logger.error(f"[{run_id}] Stage 6 GNN checkpoint unavailable: {error}", exc_info=True)
            failure = PipelineFailureDetail(
                stage="gnn_inference",
                error_code="CHECKPOINT_UNAVAILABLE",
                message="GNN model checkpoint is unavailable.",
                retryable=False,
                run_id=run_id,
            )
            return self._partial_outcome(
                duration=duration,
                status="CHECKPOINT_UNAVAILABLE",
                error_code="CHECKPOINT_UNAVAILABLE",
                message="GNN model checkpoint is not accessible on disk.",
                diagnostic_status="failed",
                diagnostic_error="GNN model checkpoint is not accessible",
                failure=failure,
            )
        except Exception as error:
            duration = self._duration(started_at)
            logger.error(f"[{run_id}] Stage 6 GNN inference failure: {error}", exc_info=True)
            failure = PipelineFailureDetail(
                stage="gnn_inference",
                error_code="GNN_INFERENCE_FAILURE",
                message="GNN compatibility inference failed.",
                retryable=True,
                run_id=run_id,
            )
            return self._partial_outcome(
                duration=duration,
                status="failed",
                error_code="GNN_INFERENCE_FAILURE",
                message="GNN forward pass encountered an unexpected error.",
                diagnostic_status="failed",
                diagnostic_error=str(error),
                failure=failure,
            )

        duration = self._duration(started_at)
        matching_result = PipelineMatchingResult(
            model_name="PaperAlignedHybridGNN",
            model_version=result.model_version,
            graph_mode=result.graph_mode,
            checkpoint_sha256=result.checkpoint_sha256,
            matching_score=result.matching_score,
            raw_score=result.raw_score,
            raw_model_score=result.raw_model_score,
            predicted_target_name=result.predicted_target_name,
            score_version=result.score_version,
            calibrated_score=result.calibrated_score,
            calibration_status=result.calibration_status,
            bounded_display_score=result.bounded_display_score,
            fit_category=result.fit_category,
            score_scale=result.score_scale,
            score_range=result.score_range,
            is_calibrated=result.calibration_status == "CALIBRATED",
            score_type=result.score_type,
            classification_thresholds=result.classification_thresholds,
            resume_skill_attention=result.resume_skill_attention,
            inference_latency_ms=result.inference_latency_ms,
            probability_calibration_disclaimer=result.probability_calibration_disclaimer,
        )
        return PipelineInferenceOutcome(
            matching_result=matching_result,
            matching_status="completed",
            pipeline_status="completed",
            failure=None,
            diagnostic=StageDiagnostic(
                stage="gnn_inference",
                status="completed",
                duration_ms=round(duration, 2),
            ),
            errors=[],
            duration_ms=round(duration, 2),
        )

    @staticmethod
    def _duration(started_at: float) -> float:
        return (time.perf_counter() - started_at) * 1000.0

    @staticmethod
    def _partial_outcome(
        *,
        duration: float,
        status: str,
        error_code: str,
        message: str,
        diagnostic_status: str,
        diagnostic_error: str,
        failure: PipelineFailureDetail,
        diagnostic_status_detail: Optional[str] = None,
    ) -> PipelineInferenceOutcome:
        error: Dict[str, Any] = {
            "stage": "gnn_inference",
            "error_code": error_code,
            "message": message,
        }
        if diagnostic_status_detail is not None:
            error["diagnostic_status"] = diagnostic_status_detail

        return PipelineInferenceOutcome(
            matching_result=None,
            matching_status=status,
            pipeline_status="partial",
            failure=failure,
            diagnostic=StageDiagnostic(
                stage="gnn_inference",
                status=diagnostic_status,
                duration_ms=round(duration, 2),
                error=diagnostic_error,
            ),
            errors=[error],
            duration_ms=round(duration, 2),
        )
