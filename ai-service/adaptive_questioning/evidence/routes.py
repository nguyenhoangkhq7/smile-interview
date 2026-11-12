"""Internal V2 compute API. Only the backend owns persisted snapshots."""
from fastapi import APIRouter, HTTPException, Request
from time import monotonic

from .models import (
    CompactTransitionRequest, CompactTransitionResult, ConversationRequest, Snapshot, StartRequest,
    TransitionRequest, TransitionResult, decompose_snapshot, recompose_snapshot
)
from .provider import DSPyAssessmentProvider
from .policy_config import configured_policy
from .workflow import EvidenceWorkflow
from .errors import JudgmentUnavailableError, QuestionUnavailableError, ProviderUnavailableError
from .telemetry import event, session_id
from .preparation_cache import PreparationCache

router = APIRouter(prefix="/api/v2/interview", tags=["Evidence Interview V2"])


def workflow(request: Request) -> EvidenceWorkflow:
    if not hasattr(request.app.state, "evidence_workflow"):
        request.app.state.evidence_workflow = EvidenceWorkflow(DSPyAssessmentProvider(), policy=configured_policy(),
                                                               preparation_cache=PreparationCache())
    return request.app.state.evidence_workflow


def get_static_specs(request: Request) -> dict:
    if not hasattr(request.app.state, "interview_static_specs"):
        request.app.state.interview_static_specs = {}
    return request.app.state.interview_static_specs


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
    result = execute(workflow(request).start, payload)
    static, dynamic = decompose_snapshot(result.snapshot)
    get_static_specs(request)[payload.session_id] = static
    result.blueprint = static.model_dump(mode="json")
    result.dynamic_state = dynamic
    return result


@router.post("/respond", response_model=TransitionResult)
def respond(payload: TransitionRequest, request: Request):
    result = execute(workflow(request).respond, payload)
    static, dynamic = decompose_snapshot(result.snapshot)
    get_static_specs(request)[payload.snapshot.session_id] = static
    result.dynamic_state = dynamic
    return result


@router.post("/respond-compact", response_model=CompactTransitionResult)
def respond_compact(payload: CompactTransitionRequest, request: Request):
    static = payload.static_spec or get_static_specs(request).get(payload.session_id)
    if not static:
        raise HTTPException(
            status_code=422,
            detail="Static blueprint/specification missing for session; supply static_spec or re-initialize session."
        )
    snapshot = recompose_snapshot(static, payload.dynamic_state)
    transition_request = TransitionRequest(
        snapshot=snapshot,
        turn_id=payload.turn_id,
        expected_state_version=payload.expected_state_version,
        candidate_response=payload.candidate_response,
    )
    result = execute(workflow(request).respond, transition_request)
    _, updated_dynamic = decompose_snapshot(result.snapshot)
    return CompactTransitionResult(dynamic_state=updated_dynamic, public=result.public)


@router.post("/stop", response_model=TransitionResult)
def stop(payload: Snapshot, request: Request):
    return execute(workflow(request).stop, payload)


@router.post("/conversation", response_model=TransitionResult)
def converse(payload: ConversationRequest, request: Request):
    result = execute(workflow(request).converse, payload)
    _, result.dynamic_state = decompose_snapshot(result.snapshot)
    return result
