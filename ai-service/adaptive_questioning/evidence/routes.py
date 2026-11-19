"""Internal V2 compute API. Only the backend owns persisted snapshots."""
from fastapi import APIRouter, HTTPException, Request
from time import monotonic

from ..optimization.compiler import DEFAULT_COMPILED_DIR
from .models import ConversationRequest, NextQuestionRequest, Snapshot, StartRequest, TransitionRequest, TransitionResult
from .provider import DSPyAssessmentProvider
from .policy_config import configured_policy
from .workflow import EvidenceWorkflow
from .errors import JudgmentUnavailableError, QuestionUnavailableError, ProviderUnavailableError
from .telemetry import event, session_id
from .preparation_cache import PreparationCache

router = APIRouter(prefix="/api/v2/interview", tags=["Evidence Interview V2"])


def workflow(request: Request) -> EvidenceWorkflow:
    if not hasattr(request.app.state, "evidence_workflow"):
        request.app.state.evidence_workflow = EvidenceWorkflow(
            DSPyAssessmentProvider(compiled_dir=str(DEFAULT_COMPILED_DIR)),
            policy=configured_policy(),
            preparation_cache=PreparationCache(),
        )
    return request.app.state.evidence_workflow


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
