"""Cached and live extraction stage for the analyze pipeline."""
from dataclasses import dataclass
import hashlib
import logging
import time
from typing import Optional, Protocol, Tuple

from fastapi import UploadFile

from matching_cv.app.schemas.unified_skill_extraction import UnifiedExtractFileResponse
from matching_cv.app.services.skill_postprocessor import skill_postprocessor

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


def refine_cached_pair(
    response: UnifiedExtractFileResponse, cv_text: str, jd_text: str
) -> Optional[UnifiedExtractFileResponse]:
    """Revalidate stored extractions against their exact source before embedding them."""
    from matching_cv.app.services.unified_skill_service import deduplicate_explicit_implicit

    updated = response.model_copy(deep=True)
    skills: set[str] = set()
    duplicates = 0
    for side, document, text in (("cv", updated.cv, cv_text), ("jd", updated.jd, jd_text)):
        if document is None or document.explicit is None:
            return None
        expected_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()
        if document.text_sha256:
            if document.text_sha256 != expected_hash:
                return None
        elif document.raw_text != text:
            return None

        document.raw_text = text
        document.explicit = skill_postprocessor.refine_cached_extraction(
            document.explicit, text, document.document_type
        )
        document.validation = deduplicate_explicit_implicit(
            document.explicit, document.implicit, document.document_type
        )
        document.validation.validation_origin = "revalidated"
        skills.update(skill.skill_id for skill in document.explicit.skills)
        skills.update(skill.skill_id for skill in document.validation.accepted_implicit_skills)
        duplicates += len(document.validation.duplicate_implicit_skills)
        setattr(updated.summary, f"{side}_explicit_count", len(document.explicit.skills))
        setattr(updated.summary, f"{side}_implicit_count", len(document.validation.accepted_implicit_skills))

    updated.cv_text = cv_text
    updated.jd_text = jd_text
    updated.summary.total_unique_skills = len(skills)
    updated.summary.duplicate_count = duplicates
    return updated


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
                    unified_response = refine_cached_pair(cached_response, cv_text, jd_text)
                if unified_response is not None:
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
            matched_pair_id = None
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
