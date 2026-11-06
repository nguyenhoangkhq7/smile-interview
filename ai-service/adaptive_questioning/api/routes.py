"""
FastAPI REST API endpoints for Pipeline V2.2 Adaptive Questioning:
  - POST /api/v1/interview/start
  - POST /api/v1/interview/respond
  - GET  /api/v1/interview/report/{session_id}
"""

from typing import Dict
from fastapi import APIRouter, HTTPException, Request, status

from adaptive_questioning.graph.workflow import AdaptiveQuestioningWorkflow
from adaptive_questioning.schemas.api_models import (
    HITLReportResponse,
    RespondInterviewRequest,
    RespondInterviewResponse,
    StartInterviewPayload,
    StartInterviewRequestWrapper,
    StartInterviewResponse,
)
from adaptive_questioning.schemas.state import InterviewSessionState

router = APIRouter(prefix="/api/v1/interview", tags=["Adaptive Questioning V2.2"])


def _get_session_store(request: Request) -> Dict[str, InterviewSessionState]:
    if not hasattr(request.app.state, "session_store"):
        request.app.state.session_store = {}
    return request.app.state.session_store


def _get_workflow(request: Request) -> AdaptiveQuestioningWorkflow:
    if not hasattr(request.app.state, "workflow"):
        request.app.state.workflow = AdaptiveQuestioningWorkflow()
    return request.app.state.workflow


@router.post(
    "/start",
    response_model=StartInterviewResponse,
    status_code=status.HTTP_200_OK,
    summary="Initialize Phase 1 Belief Anchoring and generate Turn 1 Adaptive Question",
)
def start_interview(
    payload: StartInterviewPayload,
    request: Request,
) -> StartInterviewResponse:
    skills_list = (
        payload.skills
        if isinstance(payload, StartInterviewRequestWrapper)
        else payload
    )

    workflow = _get_workflow(request)
    store = _get_session_store(request)

    session, response = workflow.start_session(skills_input=skills_list)
    store[session.session_id] = session
    return response


@router.post(
    "/respond",
    response_model=RespondInterviewResponse,
    status_code=status.HTTP_200_OK,
    summary="Evaluate Candidate Response (Step 2B), Route Convergence (Phase 3), and Generate Next Question (Step 2A)",
)
def respond_interview(
    payload: RespondInterviewRequest,
    request: Request,
) -> RespondInterviewResponse:
    store = _get_session_store(request)
    workflow = _get_workflow(request)

    session = store.get(payload.session_id)
    if session is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Interview session '{payload.session_id}' not found.",
        )

    if session.is_finished:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Interview session '{payload.session_id}' is already finished.",
        )

    try:
        return workflow.process_candidate_response(
            session=session,
            candidate_response=payload.candidate_response,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc


@router.get(
    "/report/{session_id}",
    response_model=HITLReportResponse,
    status_code=status.HTTP_200_OK,
    summary="Generate Phase 4 Auditable HITL Report (JSON + Markdown Summary)",
)
def get_interview_report(
    session_id: str,
    request: Request,
) -> HITLReportResponse:
    store = _get_session_store(request)
    workflow = _get_workflow(request)

    session = store.get(session_id)
    if session is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Interview session '{session_id}' not found.",
        )

    return workflow.build_report(session)
