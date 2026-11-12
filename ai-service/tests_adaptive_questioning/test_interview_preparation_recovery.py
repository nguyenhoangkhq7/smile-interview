"""Transient provider failures must be observable and preserve completed work."""
import json
import logging
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier, Lock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from adaptive_questioning.evidence.errors import ProviderUnavailableError
from adaptive_questioning.evidence.model_runtime import ModelRuntime, RATE_LIMIT_MESSAGE
from adaptive_questioning.evidence.planning import BlueprintBuilder
from adaptive_questioning.evidence.preparation_cache import PreparationCache, CACHE_TTL_SECONDS
from adaptive_questioning.evidence.routes import router
from adaptive_questioning.evidence.workflow import EvidenceWorkflow
from test_evidence_workflow import ScriptedProvider, skill


class ProviderError(Exception):
    def __init__(self, status, retry_after=None):
        self.status, self.retry_after = status, retry_after
        super().__init__("upstream response with private account information")


class Clock:
    def __init__(self):
        self.now = 0.0
        self.waits = []

    def __call__(self):
        return self.now

    def wait(self, delay):
        self.waits.append(delay)
        self.now += delay


def test_rate_limit_retries_with_backoff_and_recovers(caplog):
    clock, attempts = Clock(), []
    runtime = ModelRuntime(clock=clock, wait=clock.wait)

    def compute():
        attempts.append(True)
        if len(attempts) < 3:
            raise ProviderError(429)
        return "recovered"

    with caplog.at_level(logging.INFO, logger="uvicorn.error"):
        assert runtime.call("blueprint", compute) == "recovered"
    assert len(attempts) == 3
    assert clock.waits == [5.0, 15.0]
    assert "interview.model.retry" in caplog.text
    assert "status=429" in caplog.text
    assert "private account information" not in caplog.text


def test_retry_after_is_respected_and_long_provider_waits_fail_promptly():
    clock = Clock()
    runtime = ModelRuntime(clock=clock, wait=clock.wait)
    attempts = []

    def compute():
        attempts.append(True)
        if len(attempts) == 1:
            raise ProviderError(429, retry_after=12)
        return True

    assert runtime.call("question", compute)
    assert clock.waits == [12]
    with pytest.raises(ProviderUnavailableError) as error:
        runtime.call("question", lambda: (_ for _ in ()).throw(ProviderError(429, retry_after=120)))
    assert str(error.value) == RATE_LIMIT_MESSAGE
    assert clock.waits == [12]


def test_authentication_failure_does_not_retry_and_unknown_errors_are_not_swallowed():
    clock = Clock()
    runtime = ModelRuntime(clock=clock, wait=clock.wait)
    with pytest.raises(ProviderUnavailableError):
        runtime.call("blueprint", lambda: (_ for _ in ()).throw(ProviderError(401)))
    assert clock.waits == []
    with pytest.raises(ValueError, match="invalid rubric"):
        runtime.call("blueprint", lambda: (_ for _ in ()).throw(ValueError("invalid rubric")))


def test_model_concurrency_is_bounded_across_batches():
    runtime, lock, barrier = ModelRuntime(concurrency=3), Lock(), Barrier(3)
    active, peak, calls = 0, 0, 0

    def compute():
        nonlocal active, peak, calls
        with lock:
            calls += 1
            first_wave = calls <= 3
            active += 1
            peak = max(peak, active)
        if first_wave:
            barrier.wait(timeout=5)
        with lock:
            active -= 1
        return True

    with ThreadPoolExecutor(max_workers=9) as executor:
        assert all(executor.map(lambda _: runtime.call("blueprint", compute), range(9)))
    assert peak == 3


def test_completed_batches_are_reused_after_one_batch_fails(caplog):
    class PartialFailureProvider(ScriptedProvider):
        def __init__(self):
            super().__init__()
            self.calls = {}
            self.lock, self.barrier = Lock(), Barrier(3)
            self.fail = True

        def blueprint(self, context):
            keys = tuple(json.loads(context)["requirements"])
            with self.lock:
                self.calls[keys] = self.calls.get(keys, 0) + 1
                first_wave = sum(self.calls.values()) <= 3
            if first_wave:
                self.barrier.wait(timeout=5)
            if "skill-6:inferred" in keys and self.fail:
                raise ProviderUnavailableError(RATE_LIMIT_MESSAGE, status=429)
            return super().blueprint(context)

    provider, cache = PartialFailureProvider(), PreparationCache()
    skills = [skill(f"skill-{index}") for index in range(9)]
    with caplog.at_level(logging.INFO, logger="uvicorn.error"):
        with pytest.raises(ProviderUnavailableError):
            BlueprintBuilder(provider, cache=cache).build(skills)
        provider.fail = False
        result = BlueprintBuilder(provider, cache=cache).build(skills)
    assert len(result.objectives) == 9
    assert sorted(provider.calls.values()) == [1, 1, 2]
    assert "interview.blueprint.cache_hit" in caplog.text
    assert "completed=3 total=3" in caplog.text


def test_cache_returns_independent_results_and_expires():
    clock, cache, calls = Clock(), None, []
    cache = PreparationCache(clock=clock)
    provider = ScriptedProvider()
    context = json.dumps({"requirements": {"postgresql:inferred": {
        "skill_id": "postgresql", "description": "Diagnose queries", "required_proficiency": 3, "has_task": False,
    }}})

    def compute():
        calls.append(True)
        return provider.blueprint(context)

    first = cache.get_or_compute(context, compute)
    first.objectives[0].claim = "changed by validation"
    assert cache.get_or_compute(context, compute).objectives[0].claim == "Diagnose queries"
    assert len(calls) == 1
    clock.now += CACHE_TTL_SECONDS + 1
    cache.get_or_compute(context, compute)
    assert len(calls) == 2


def test_exhausted_rate_limit_returns_visible_503_with_correlated_logs(caplog):
    clock = Clock()
    runtime = ModelRuntime(clock=clock, wait=clock.wait)

    class UnavailableProvider(ScriptedProvider):
        def blueprint(self, context):
            return runtime.call("blueprint", lambda: (_ for _ in ()).throw(ProviderError(429)))

    app = FastAPI()
    app.include_router(router)
    app.state.evidence_workflow = EvidenceWorkflow(UnavailableProvider())
    with caplog.at_level(logging.INFO, logger="uvicorn.error"), TestClient(app) as client:
        response = client.post("/api/v2/interview/start", json={
            "session_id": "recovery-503", "skills": [skill().model_dump(mode="json")],
        })
    assert response.status_code == 503
    assert response.json() == {"detail": RATE_LIMIT_MESSAGE}
    assert "session_id=recovery-503" in caplog.text
    assert "interview.request.failed" in caplog.text
    assert "private account information" not in response.text + caplog.text
