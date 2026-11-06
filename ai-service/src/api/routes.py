"""
FastAPI REST API endpoints for Module 2 (Skill-Gap Detection):
  - POST /api/v1/skill-gap/analyze
  - POST /api/v1/skill-gap/analyze-with-report
  - GET  /api/v1/skill-gap/report/{analysis_id}
"""

from typing import Dict
import uuid
from fastapi import APIRouter, HTTPException, Request, status

from src.adapters.config import load_config
from src.adapters.llm_client import DSPyLLMClient
from src.api.schemas import (
    AnalyzeSkillGapRequest,
    AnalyzeSkillGapResponse,
    AnalyzeWithReportResponse,
)
from src.domain.enums import QuestionStrategy
from src.pipeline.orchestrator import SkillGapOrchestrator
from src.services.report_generator import StaticGapAuditReport

router = APIRouter(prefix="/api/v1/skill-gap", tags=["Skill-Gap Detection V2.0"])


def _get_report_store(request: Request) -> Dict[str, StaticGapAuditReport]:
    if not hasattr(request.app.state, "report_store"):
        request.app.state.report_store = {}
    return request.app.state.report_store


def _get_orchestrator(request: Request) -> SkillGapOrchestrator:
    if not hasattr(request.app.state, "orchestrator"):
        config = load_config()
        llm_client = DSPyLLMClient(model=config.llm.model)
        request.app.state.orchestrator = SkillGapOrchestrator(
            llm_client=llm_client,
            config=config,
        )
    return request.app.state.orchestrator


@router.post(
    "/analyze",
    response_model=AnalyzeSkillGapResponse,
    status_code=status.HTTP_200_OK,
    summary="Execute Parallel LangGraph Skill-Gap Detection Pipeline and return Module 3-compatible SkillGapResult list",
)
def analyze_skill_gap(
    payload: AnalyzeSkillGapRequest,
    request: Request,
) -> AnalyzeSkillGapResponse:
    orchestrator = _get_orchestrator(request)
    store = _get_report_store(request)

    analysis_id = payload.analysis_id or str(uuid.uuid4())
    gap_results, report = orchestrator.run_pipeline_with_report(
        cv_text=payload.cv_text,
        jd_text=payload.jd_text,
        cv_skills=payload.cv_skills,
        jd_skills=payload.jd_skills,
        match_results=payload.match_results,
        analysis_id=analysis_id,
    )
    store[report.analysis_id] = report

    probing_cnt = sum(
        1
        for r in gap_results
        if r.suggested_strategy != QuestionStrategy.NONE and r.priority > 0.0
    )

    return AnalyzeSkillGapResponse(
        analysis_id=report.analysis_id,
        total_skills=len(gap_results),
        skills_requiring_probing=probing_cnt,
        skills=gap_results,
    )


@router.post(
    "/analyze-with-report",
    response_model=AnalyzeWithReportResponse,
    status_code=status.HTTP_200_OK,
    summary="Execute Parallel LangGraph Pipeline and return both SkillGapResult list and Fact-based Static XAI Audit Report",
)
def analyze_skill_gap_with_report(
    payload: AnalyzeSkillGapRequest,
    request: Request,
) -> AnalyzeWithReportResponse:
    orchestrator = _get_orchestrator(request)
    store = _get_report_store(request)

    analysis_id = payload.analysis_id or str(uuid.uuid4())
    gap_results, report = orchestrator.run_pipeline_with_report(
        cv_text=payload.cv_text,
        jd_text=payload.jd_text,
        cv_skills=payload.cv_skills,
        jd_skills=payload.jd_skills,
        match_results=payload.match_results,
        analysis_id=analysis_id,
    )
    store[report.analysis_id] = report

    return AnalyzeWithReportResponse(
        analysis_id=report.analysis_id,
        skills=gap_results,
        report=report,
    )


@router.get(
    "/report/{analysis_id}",
    response_model=StaticGapAuditReport,
    status_code=status.HTTP_200_OK,
    summary="Retrieve Fact-based Static XAI Audit Report (JSON + Markdown Summary) by analysis_id",
)
def get_static_gap_report(
    analysis_id: str,
    request: Request,
) -> StaticGapAuditReport:
    store = _get_report_store(request)
    report = store.get(analysis_id)
    if report is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Skill-gap analysis session '{analysis_id}' not found.",
        )
    return report
