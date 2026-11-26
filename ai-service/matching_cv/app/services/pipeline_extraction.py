"""Cached and live extraction stage for the analyze pipeline."""
from dataclasses import dataclass
import logging
import time
from typing import Optional, Protocol, Tuple

from fastapi import UploadFile

from matching_cv.app.schemas.unified_skill_extraction import UnifiedExtractFileResponse

logger = logging.getLogger(__name__)


class ExtractionCache(Protocol):
    """Cache interface needed by the extraction stage."""

    def parse_document(self, file_bytes: bytes, filename: str) -> str: ...

    def resolve_cached_extraction(
        self,
        cv_text: str,
        jd_text: str,
        cv_filename: str,
        jd_filename: str,
    ) -> Tuple[Optional[UnifiedExtractFileResponse], Optional[str], Optional[str]]: ...


class SkillExtractor(Protocol):
    """Live extraction interface used when no cached result matches."""

    async def extract_unified_from_files(
        self,
        cv_file: Optional[UploadFile],
        jd_file: Optional[UploadFile],
    ) -> UnifiedExtractFileResponse: ...


@dataclass(frozen=True)
class PipelineExtractionOutcome:
    unified_response: UnifiedExtractFileResponse
    matched_pair_id: Optional[str]
    cv_text: Optional[str]
    jd_text: Optional[str]
    duration_ms: float


class PipelineExtractionError(RuntimeError):
    """Live extraction failed after cache resolution was unavailable."""

    def __init__(self, cause: Exception, duration_ms: float) -> None:
        super().__init__(str(cause))
        self.cause = cause
        self.duration_ms = duration_ms


class PipelineExtractionService:
    """Resolve cached extraction or run live extraction, preserving parsed text."""

    def __init__(self, cache: ExtractionCache, extractor: SkillExtractor) -> None:
        self._cache = cache
        self._extractor = extractor

    async def extract(
        self,
        *,
        cv_file: Optional[UploadFile],
        jd_file: Optional[UploadFile],
        run_id: str,
    ) -> PipelineExtractionOutcome:
        started_at = time.perf_counter()
        unified_response: Optional[UnifiedExtractFileResponse] = None
        matched_pair_id: Optional[str] = None
        cv_text: Optional[str] = None
        jd_text: Optional[str] = None

        if cv_file is not None and jd_file is not None:
            try:
                cv_bytes = await cv_file.read()
                jd_bytes = await jd_file.read()
                await cv_file.seek(0)
                await jd_file.seek(0)
                cv_text = self._cache.parse_document(cv_bytes, cv_file.filename or "")
                jd_text = self._cache.parse_document(jd_bytes, jd_file.filename or "")
                cached_response, matched_pair_id, _ = self._cache.resolve_cached_extraction(
                    cv_text=cv_text,
                    jd_text=jd_text,
                    cv_filename=cv_file.filename or "",
                    jd_filename=jd_file.filename or "",
                )
                if cached_response is not None:
                    unified_response = cached_response
                    logger.info(
                        f"[{run_id}] Resolved offline cached extraction for pair: "
                        f"{matched_pair_id or 'corpus_match'}"
                    )
            except Exception as cache_error:
                logger.debug(f"[{run_id}] Cache lookup bypassed: {cache_error}")
                try:
                    await cv_file.seek(0)
                    await jd_file.seek(0)
                except Exception:
                    pass

        if unified_response is None:
            try:
                unified_response = await self._extractor.extract_unified_from_files(
                    cv_file=cv_file,
                    jd_file=jd_file,
                )
            except Exception as error:
                duration = (time.perf_counter() - started_at) * 1000.0
                raise PipelineExtractionError(error, duration) from error

        return PipelineExtractionOutcome(
            unified_response=unified_response,
            matched_pair_id=matched_pair_id,
            cv_text=cv_text,
            jd_text=jd_text,
            duration_ms=(time.perf_counter() - started_at) * 1000.0,
        )
