"""Bound model concurrency with isolated pools and explicit transient failure retry."""
import os
import random
from threading import BoundedSemaphore, Lock
from time import monotonic, sleep
from typing import Callable, TypeVar

from .errors import ProviderUnavailableError
from .telemetry import event

T = TypeVar("T")
LIVE_CONCURRENCY = max(1, int(os.getenv("EVIDENCE_LIVE_CONCURRENCY", "6")))
BLUEPRINT_CONCURRENCY = max(1, int(os.getenv("EVIDENCE_BLUEPRINT_CONCURRENCY", "4")))
MODEL_CONCURRENCY = LIVE_CONCURRENCY
RETRY_DELAYS = (1.0, 3.0)
MAX_RETRY_DELAY = 30.0
TRANSIENT_STATUSES = {408, 429, 500, 502, 503, 504}
RATE_LIMIT_MESSAGE = "Dịch vụ AI đang giới hạn yêu cầu. Vui lòng chờ một chút rồi thử lại; dữ liệu hồ sơ vẫn được giữ nguyên."
UNAVAILABLE_MESSAGE = "Dịch vụ AI chưa thể phản hồi. Vui lòng thử lại; dữ liệu hồ sơ vẫn được giữ nguyên."


def _default_jitter() -> float:
    return random.uniform(0.0, 0.25)


def provider_status(error: Exception) -> int | None:
    cause: BaseException | None = error
    while cause is not None:
        status = getattr(cause, "status", None) or getattr(cause, "status_code", None)
        if isinstance(status, int):
            return status
        if isinstance(cause, (TimeoutError, ConnectionError)):
            return 503
        cause = cause.__cause__
    return None


class ModelRuntime:
    def __init__(
        self,
        *,
        concurrency: int = MODEL_CONCURRENCY,
        clock: Callable[[], float] = monotonic,
        wait: Callable[[float], None] = sleep,
        jitter: Callable[[], float] | None = None,
    ):
        self._slots = BoundedSemaphore(concurrency)
        self._lock = Lock()
        self._clock, self._wait = clock, wait
        self._jitter = _default_jitter if jitter is None else jitter
        self._retry_at = 0.0

    def _cool_down(self) -> None:
        while True:
            with self._lock:
                delay = self._retry_at - self._clock()
            if delay <= 0:
                return
            self._wait(delay)

    def call(self, operation: str, compute: Callable[[], T], *, retries: int | None = None) -> T:
        max_retries = len(RETRY_DELAYS) if retries is None else max(0, retries)
        for attempt in range(max_retries + 1):
            # Never hold a concurrency slot while sleeping on shared rate-limit cooldown.
            self._cool_down()
            try:
                with self._slots:
                    event("model.started", operation=operation, attempt=attempt + 1)
                    started = monotonic()
                    result = compute()
                    event("model.completed", operation=operation, attempt=attempt + 1,
                          elapsed_seconds=round(monotonic() - started, 3))
                    return result
            except Exception as error:
                status = provider_status(error)
                if status is None:
                    raise
                self._retry_or_raise(operation, attempt, error, status, max_retries)
        raise AssertionError("Unreachable retry state")

    def _retry_or_raise(self, operation: str, attempt: int, error: Exception, status: int,
                        max_retries: int = len(RETRY_DELAYS)) -> None:
        retry_after = getattr(error, "retry_after", None) or 0.0
        if status not in TRANSIENT_STATUSES or attempt >= max_retries or retry_after > MAX_RETRY_DELAY:
            event("model.failed", operation=operation, status=status, attempts=attempt + 1,
                  error_type=type(error).__name__)
            message = RATE_LIMIT_MESSAGE if status == 429 else UNAVAILABLE_MESSAGE
            raise ProviderUnavailableError(message, status=status) from error
        base_delay = RETRY_DELAYS[min(attempt, len(RETRY_DELAYS) - 1)]
        extra = max(0.0, float(self._jitter())) if retry_after <= 0 else 0.0
        delay = max(base_delay + extra, retry_after)
        event("model.retry", operation=operation, status=status, attempt=attempt + 1, wait_seconds=round(delay, 3))
        if status == 429:
            with self._lock:
                self._retry_at = max(self._retry_at, self._clock() + delay)
        else:
            # 5xx / timeout errors back off locally without stalling other concurrent requests.
            self._wait(delay)


live_runtime = ModelRuntime(concurrency=LIVE_CONCURRENCY)
blueprint_runtime = ModelRuntime(concurrency=BLUEPRINT_CONCURRENCY)
model_runtime = live_runtime
