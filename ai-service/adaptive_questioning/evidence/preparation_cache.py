"""Short-lived successful blueprint batches, shared by retries of this workflow."""
from collections import OrderedDict
from concurrent.futures import Future
from hashlib import sha256
from threading import Lock
from time import monotonic
from typing import Callable

from .models import Blueprint
from .telemetry import event

CACHE_TTL_SECONDS = 900
CACHE_MAX_BATCHES = 256


class PreparationCache:
    def __init__(self, clock=monotonic):
        self._clock = clock
        self._lock = Lock()
        self._results: OrderedDict[str, tuple[float, Blueprint]] = OrderedDict()
        self._pending: dict[str, Future[Blueprint]] = {}

    def get_or_compute(self, context: str, compute: Callable[[], Blueprint]) -> Blueprint:
        key = sha256(context.encode("utf-8")).hexdigest()
        with self._lock:
            cached = self._results.get(key)
            if cached and self._clock() - cached[0] < CACHE_TTL_SECONDS:
                self._results.move_to_end(key)
                event("blueprint.cache_hit", objectives=len(cached[1].objectives))
                return cached[1].model_copy(deep=True)
            future = self._pending.get(key)
            owner = future is None
            if owner:
                future = self._pending[key] = Future()
        assert future is not None
        if not owner:
            event("blueprint.joined")
            return future.result().model_copy(deep=True)
        return self._compute(key, future, compute)

    def _compute(self, key: str, future: Future[Blueprint], compute: Callable[[], Blueprint]) -> Blueprint:
        try:
            result = compute()
            with self._lock:
                self._results[key] = (self._clock(), result.model_copy(deep=True))
                self._results.move_to_end(key)
                while len(self._results) > CACHE_MAX_BATCHES:
                    self._results.popitem(last=False)
            future.set_result(result)
            return result.model_copy(deep=True)
        except BaseException as error:
            future.set_exception(error)
            raise
        finally:
            with self._lock:
                self._pending.pop(key, None)

    def discard(self, contexts: list[str]) -> None:
        with self._lock:
            for context in contexts:
                self._results.pop(sha256(context.encode("utf-8")).hexdigest(), None)
