"""Internal V2 compute API. Only the backend owns persisted snapshots."""
from fastapi import APIRouter, HTTPException, Request

from .models import Snapshot, StartRequest, TransitionRequest, TransitionResult
from .provider import DSPyAssessmentProvider
from .policy_config import configured_policy
from .workflow import EvidenceWorkflow
from .errors import JudgmentUnavailableError, QuestionUnavailableError

router = APIRouter(prefix="/api/v2/interview", tags=["Evidence Interview V2"])


def workflow(request: Request) -> EvidenceWorkflow:
    if not hasattr(request.app.state, "evidence_workflow"):
        request.app.state.evidence_workflow = EvidenceWorkflow(DSPyAssessmentProvider(), policy=configured_policy())
    return request.app.state.evidence_workflow


def execute(operation, payload):
    try:
        return operation(payload)
    except (JudgmentUnavailableError, QuestionUnavailableError) as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/start", response_model=TransitionResult)
def start(payload: StartRequest, request: Request):
    return execute(workflow(request).start, payload)


@router.post("/respond", response_model=TransitionResult)
def respond(payload: TransitionRequest, request: Request):
    return execute(workflow(request).respond, payload)


@router.post("/stop", response_model=TransitionResult)
def stop(payload: Snapshot, request: Request):
    return execute(workflow(request).stop, payload)
