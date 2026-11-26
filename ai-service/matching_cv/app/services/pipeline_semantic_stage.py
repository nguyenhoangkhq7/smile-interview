"""Semantic embedding stage adapter for CV/JD analysis."""
from dataclasses import dataclass
import time
from typing import Protocol

from matching_cv.app.schemas.semantic_representation import (
    EmbeddingGenerateRequest,
    SemanticRepresentationResponse,
)
from matching_cv.app.schemas.unified_skill_extraction import UnifiedExtractFileResponse


class SemanticEncoder(Protocol):
    """Interface implemented by the configured semantic representation service."""

    def generate_representations(
        self,
        request: EmbeddingGenerateRequest,
    ) -> SemanticRepresentationResponse: ...


@dataclass(frozen=True)
class SemanticStageOutcome:
    response: SemanticRepresentationResponse
    duration_ms: float


class SemanticStageError(RuntimeError):
    def __init__(self, cause: Exception, duration_ms: float) -> None:
        super().__init__(str(cause))
        self.cause = cause
        self.duration_ms = duration_ms


class PipelineSemanticStage:
    """Build the embedding request and execute Stage 3."""

    def __init__(self, encoder: SemanticEncoder) -> None:
        self._encoder = encoder

    def execute(
        self,
        *,
        unified_response: UnifiedExtractFileResponse,
        cv_text: str,
        jd_text: str,
        top_k: int,
    ) -> SemanticStageOutcome:
        started_at = time.perf_counter()
        try:
            request = EmbeddingGenerateRequest(
                unified_response=unified_response,
                cv_text=cv_text,
                jd_text=jd_text,
                include_vectors=True,
                compute_similarity=True,
                top_k=top_k,
                on_overlength="segment",
            )
            response = self._encoder.generate_representations(request)
        except Exception as error:
            duration = (time.perf_counter() - started_at) * 1000.0
            raise SemanticStageError(error, duration) from error

        return SemanticStageOutcome(
            response=response,
            duration_ms=(time.perf_counter() - started_at) * 1000.0,
        )
