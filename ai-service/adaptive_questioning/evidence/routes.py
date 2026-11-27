"""Internal V2 compute API. Only the backend owns persisted snapshots."""
import logging
import os
from threading import Lock
from time import monotonic

from fastapi import APIRouter, HTTPException, Request

from app.ai_runtime import active

from ..optimization.compiler import DEFAULT_COMPILED_DIR
from .models import (
    Blueprint, BlueprintRequest, ConversationRequest, NextQuestionRequest, RunCodeRequest, RunCodeResponse,
    Snapshot, StartRequest, TransitionRequest, TransitionResult,
)
from .provider import DSPyAssessmentProvider
from .policy_config import configured_policy
from .workflow import EvidenceWorkflow
from .errors import JudgmentUnavailableError, QuestionUnavailableError, ProviderUnavailableError
from .telemetry import event, session_id
from .preparation_cache import PreparationCache

router = APIRouter(prefix="/api/v2/interview", tags=["Evidence Interview V2"])
_workflow_lock = Lock()
logger = logging.getLogger(__name__)


def init_evidence_workflow(app) -> EvidenceWorkflow | None:
    """Eagerly initialize EvidenceWorkflow during FastAPI lifespan when credentials are configured."""
    if not os.environ.get("OPENROUTER_API_KEY"):
        logger.info("Skipping eager EvidenceWorkflow initialization because OPENROUTER_API_KEY is unset")
        return None
    with _workflow_lock:
        if not hasattr(app.state, "evidence_workflow"):
            app.state.evidence_workflow = EvidenceWorkflow(
                DSPyAssessmentProvider(compiled_dir=str(DEFAULT_COMPILED_DIR)),
                policy=configured_policy(),
                preparation_cache=PreparationCache(),
                prewarm_q1=True,
            )
        return app.state.evidence_workflow


def workflow(request: Request) -> EvidenceWorkflow:
    revision = active.get().revision
    if revision:
        with _workflow_lock:
            entry = getattr(request.app.state, "configured_evidence_workflow", None)
            if entry is None or entry[0] != revision:
                workflow = EvidenceWorkflow(
                    DSPyAssessmentProvider(compiled_dir=str(DEFAULT_COMPILED_DIR)),
                    policy=configured_policy(),
                    preparation_cache=PreparationCache(),
                    prewarm_q1=True,
                )
                entry = (revision, workflow)
                request.app.state.configured_evidence_workflow = entry
            return entry[1]
    existing = getattr(request.app.state, "evidence_workflow", None)
    if existing is not None:
        return existing
    with _workflow_lock:
        existing = getattr(request.app.state, "evidence_workflow", None)
        if existing is None:
            existing = EvidenceWorkflow(
                DSPyAssessmentProvider(compiled_dir=str(DEFAULT_COMPILED_DIR)),
                policy=configured_policy(),
                preparation_cache=PreparationCache(),
                prewarm_q1=True,
            )
            request.app.state.evidence_workflow = existing
        return existing


def execute(operation, payload):
    identity = getattr(payload, "session_id", None) or getattr(getattr(payload, "snapshot", None), "session_id", "-")
    token = session_id.set(identity)
    started = monotonic()
    event("request.started", operation=operation.__name__)
    try:
        result = operation(payload)
        event("request.completed", operation=operation.__name__, elapsed_seconds=round(monotonic() - started, 2))
        return result
    except (JudgmentUnavailableError, QuestionUnavailableError, ProviderUnavailableError) as exc:
        event("request.failed", operation=operation.__name__, error_type=type(exc).__name__,
              elapsed_seconds=round(monotonic() - started, 2))
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except ValueError as exc:
        event("request.failed", operation=operation.__name__, error_type=type(exc).__name__,
              elapsed_seconds=round(monotonic() - started, 2))
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    finally:
        session_id.reset(token)


@router.post("/blueprint", response_model=Blueprint)
def blueprint(payload: BlueprintRequest, request: Request):
    return execute(workflow(request).build_blueprint, payload)


@router.post("/start", response_model=TransitionResult)
def start(payload: StartRequest, request: Request):
    return execute(workflow(request).start, payload)


@router.post("/respond", response_model=TransitionResult)
def respond(payload: TransitionRequest, request: Request):
    return execute(workflow(request).respond, payload)


@router.post("/next-question", response_model=TransitionResult)
def next_question(payload: NextQuestionRequest, request: Request):
    return execute(workflow(request).next_question, payload)


@router.post("/stop", response_model=TransitionResult)
def stop(payload: Snapshot, request: Request):
    return execute(workflow(request).stop, payload)


@router.post("/conversation", response_model=TransitionResult)
def converse(payload: ConversationRequest, request: Request):
    return execute(workflow(request).converse, payload)


@router.post("/run-code", response_model=RunCodeResponse)
def run_code(payload: RunCodeRequest, request: Request):
    return execute(workflow(request).run_code, payload)
