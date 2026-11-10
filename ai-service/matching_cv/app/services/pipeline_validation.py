"""Input validation for the CV/JD analyze use case."""
from dataclasses import dataclass
import os
import time
from typing import NoReturn, Optional, Protocol, Sequence

from fastapi import UploadFile


class PipelineSettings(Protocol):
    """Settings required by request validation."""

    PIPELINE_ALLOWED_EXTENSIONS: Sequence[str]
    PIPELINE_MAX_FILE_SIZE_BYTES: int
    PIPELINE_MAX_TOP_K: int
    PIPELINE_DEFAULT_REASONING_MAX_PAIRS: int
    PIPELINE_DEFAULT_SELECTION_STRATEGY: str


SUPPORTED_GRAPH_MODES = (
    "verified_equivalence",
    "similarity_enriched",
    "llm_enriched",
    "evidence_only",
    "paper_cosine_08",
    "canonical_only",
)
SUPPORTED_SELECTION_STRATEGIES = ("balanced_coverage", "global_top_cosine")


@dataclass(frozen=True)
class ValidatedPipelineInput:
    reasoning_max_pairs: int
    reasoning_selection_strategy: str
    cv_extension: str
    jd_extension: str
    duration_ms: float


class PipelineInputValidationError(ValueError):
    """Validation failure with the public error and diagnostic fields needed by the API."""

    def __init__(
        self,
        *,
        error_code: str,
        message: str,
        diagnostic_error: str,
        duration_ms: float,
    ) -> None:
        super().__init__(message)
        self.error_code = error_code
        self.message = message
        self.diagnostic_error = diagnostic_error
        self.duration_ms = duration_ms


class PipelineInputValidator:
    """Validates uploaded documents and analyze options before pipeline work starts."""

    def __init__(
        self,
        pipeline_settings: PipelineSettings,
        supported_graph_modes: Sequence[str] = SUPPORTED_GRAPH_MODES,
    ) -> None:
        self._settings = pipeline_settings
        self._supported_graph_modes = tuple(supported_graph_modes)

    async def validate(
        self,
        *,
        cv_file: Optional[UploadFile],
        jd_file: Optional[UploadFile],
        graph_mode: str,
        top_k: int,
        reasoning_max_pairs: Optional[int],
        reasoning_selection_strategy: Optional[str],
    ) -> ValidatedPipelineInput:
        """Validate files and options, restoring upload streams for downstream consumers."""
        started_at = time.perf_counter()

        if cv_file is None or not getattr(cv_file, "filename", None):
            self._raise(
                started_at,
                "MISSING_FILE",
                "Tệp CV ('cv_file') là bắt buộc.",
                "Missing CV file",
            )
        if jd_file is None or not getattr(jd_file, "filename", None):
            self._raise(
                started_at,
                "MISSING_FILE",
                "Tệp JD ('jd_file') là bắt buộc.",
                "Missing JD file",
            )

        cv_ext = os.path.splitext(cv_file.filename.lower())[1]
        jd_ext = os.path.splitext(jd_file.filename.lower())[1]
        allowed_extensions = self._settings.PIPELINE_ALLOWED_EXTENSIONS
        if cv_ext not in allowed_extensions or jd_ext not in allowed_extensions:
            self._raise(
                started_at,
                "UNSUPPORTED_FILE_TYPE",
                (
                    f"Định dạng tệp không được hỗ trợ (cv: '{cv_ext}', jd: '{jd_ext}'). "
                    f"Chỉ chấp nhận các tệp có đuôi: {allowed_extensions}"
                ),
                f"Unsupported file format (cv='{cv_ext}', jd='{jd_ext}')",
            )

        try:
            cv_content = await cv_file.read()
            jd_content = await jd_file.read()

            if not cv_content:
                self._raise(
                    started_at,
                    "EMPTY_FILE",
                    f"Tệp CV '{cv_file.filename}' rỗng hoặc không có dữ liệu.",
                    "Empty CV file",
                )
            if not jd_content:
                self._raise(
                    started_at,
                    "EMPTY_FILE",
                    f"Tệp JD '{jd_file.filename}' rỗng hoặc không có dữ liệu.",
                    "Empty JD file",
                )

            max_bytes = self._settings.PIPELINE_MAX_FILE_SIZE_BYTES
            if len(cv_content) > max_bytes or len(jd_content) > max_bytes:
                self._raise(
                    started_at,
                    "FILE_SIZE_EXCEEDED",
                    f"Kích thước tệp vượt quá giới hạn tối đa cho phép ({max_bytes} bytes).",
                    "File size exceeded",
                )

            await cv_file.seek(0)
            await jd_file.seek(0)
        except PipelineInputValidationError:
            raise
        except Exception as read_error:
            self._raise(
                started_at,
                "READ_ERROR",
                f"Lỗi khi đọc dữ liệu tệp tải lên: {str(read_error)}",
                str(read_error),
            )

        if top_k < 1 or top_k > self._settings.PIPELINE_MAX_TOP_K:
            self._raise(
                started_at,
                "INVALID_TOP_K",
                f"Tham số 'top_k' phải nằm trong khoảng từ 1 đến {self._settings.PIPELINE_MAX_TOP_K}.",
                "Invalid top_k",
            )
        if graph_mode not in self._supported_graph_modes:
            self._raise(
                started_at,
                "INVALID_GRAPH_MODE",
                (
                    f"Tham số 'graph_mode' không hợp lệ ('{graph_mode}'). "
                    f"Chỉ chấp nhận các giá trị: {self._supported_graph_modes}."
                ),
                "Invalid graph_mode",
            )

        effective_max_pairs = (
            reasoning_max_pairs
            if reasoning_max_pairs is not None
            else self._settings.PIPELINE_DEFAULT_REASONING_MAX_PAIRS
        )
        if effective_max_pairs < 1 or effective_max_pairs > 100:
            self._raise(
                started_at,
                "INVALID_REASONING_MAX_PAIRS",
                "Tham số 'reasoning_max_pairs' phải nằm trong khoảng từ 1 đến 100.",
                "Invalid reasoning_max_pairs",
            )

        effective_strategy = (
            reasoning_selection_strategy or self._settings.PIPELINE_DEFAULT_SELECTION_STRATEGY
        )
        if effective_strategy not in SUPPORTED_SELECTION_STRATEGIES:
            self._raise(
                started_at,
                "INVALID_SELECTION_STRATEGY",
                "Tham số 'reasoning_selection_strategy' phải thuộc một trong hai giá trị: "
                "'balanced_coverage', 'global_top_cosine'.",
                "Invalid reasoning_selection_strategy",
            )

        return ValidatedPipelineInput(
            reasoning_max_pairs=effective_max_pairs,
            reasoning_selection_strategy=effective_strategy,
            cv_extension=cv_ext,
            jd_extension=jd_ext,
            duration_ms=round((time.perf_counter() - started_at) * 1000.0, 2),
        )

    @staticmethod
    def _raise(
        started_at: float,
        error_code: str,
        message: str,
        diagnostic_error: str,
    ) -> NoReturn:
        duration_ms = (time.perf_counter() - started_at) * 1000.0
        raise PipelineInputValidationError(
            error_code=error_code,
            message=message,
            diagnostic_error=diagnostic_error,
            duration_ms=duration_ms,
        )
