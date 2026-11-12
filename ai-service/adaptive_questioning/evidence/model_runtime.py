"""Bound model concurrency and retry transient provider failures explicitly."""
from threading import BoundedSemaphore, Lock
from time import monotonic, sleep
from typing import Callable, TypeVar

from .errors import ProviderUnavailableError
from .telemetry import event

T = TypeVar("T")
MODEL_CONCURRENCY = 3
RETRY_DELAYS = (5.0, 15.0)
MAX_RETRY_DELAY = 30.0
TRANSIENT_STATUSES = {408, 429, 500, 502, 503, 504}
RATE_LIMIT_MESSAGE = "Dịch vụ AI đang giới hạn yêu cầu. Vui lòng chờ một chút rồi thử lại; dữ liệu hồ sơ vẫn được giữ nguyên."
UNAVAILABLE_MESSAGE = "Dịch vụ AI chưa thể phản hồi. Vui lòng thử lại; dữ liệu hồ sơ vẫn được giữ nguyên."


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
    def __init__(self, *, concurrency=MODEL_CONCURRENCY, clock=monotonic, wait=sleep):
        self._slots = BoundedSemaphore(concurrency)
        self._lock = Lock()
        self._clock, self._wait = clock, wait
        self._retry_at = 0.0

    def _cool_down(self) -> None:
        while True:
            with self._lock:
                delay = self._retry_at - self._clock()
            if delay <= 0:
                return
            self._wait(delay)

    def call(self, operation: str, compute: Callable[[], T]) -> T:
        for attempt in range(len(RETRY_DELAYS) + 1):
            try:
                with self._slots:
                    self._cool_down()
                    event("model.started", operation=operation, attempt=attempt + 1)
                    return compute()
            except Exception as error:
                status = provider_status(error)
                if status is None:
                    raise
                self._retry_or_raise(operation, attempt, error, status)
        raise AssertionError("Unreachable retry state")

    def _retry_or_raise(self, operation: str, attempt: int, error: Exception, status: int) -> None:
        retry_after = getattr(error, "retry_after", None) or 0.0
        if status not in TRANSIENT_STATUSES or attempt >= len(RETRY_DELAYS) or retry_after > MAX_RETRY_DELAY:
            event("model.failed", operation=operation, status=status, attempts=attempt + 1,
                  error_type=type(error).__name__)
            message = RATE_LIMIT_MESSAGE if status == 429 else UNAVAILABLE_MESSAGE
            raise ProviderUnavailableError(message, status=status) from error
        delay = max(RETRY_DELAYS[attempt], retry_after)
        with self._lock:
            self._retry_at = max(self._retry_at, self._clock() + delay)
        event("model.retry", operation=operation, status=status, attempt=attempt + 1, wait_seconds=delay)


model_runtime = ModelRuntime()
