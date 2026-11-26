"""
FastAPI REST API endpoints for Module 2 (Skill-Gap Detection):
  - POST /api/v1/skill-gap/analyze
  - POST /api/v1/skill-gap/analyze-with-report
"""

import os
import uuid
from threading import Lock

from app.ai_runtime import active, credential, model_value
from fastapi import APIRouter, Request, status

from skill_gap.adapters.config import load_config
from skill_gap.adapters.llm_client import DSPyLLMClient
from skill_gap.api.schemas import (
    AnalyzeSkillGapRequest,
    AnalyzeWithReportResponse,
)
from skill_gap.pipeline.orchestrator import SkillGapOrchestrator

router = APIRouter(prefix="/api/v1/skill-gap", tags=["Skill-Gap Detection V2.0"])


_orchestrator_lock = Lock()


def _get_orchestrator(request: Request) -> SkillGapOrchestrator:
    revision = active.get().revision
    if revision:
        with _orchestrator_lock:
            entry = getattr(request.app.state, "configured_orchestrator", None)
            if entry is None or entry[0] != revision:
                config = load_config()
                config.llm.model = model_value("skillGapModel", config.llm.model)
                client = DSPyLLMClient(
                    model=config.llm.model,
                    api_key=credential("openRouterKey", os.getenv("OPENROUTER_API_KEY", "")),
                )
                entry = (revision, SkillGapOrchestrator(llm_client=client, config=config))
                request.app.state.configured_orchestrator = entry
            return entry[1]
    if not hasattr(request.app.state, "orchestrator"):
        config = load_config()
        llm_client = DSPyLLMClient(model=config.llm.model)
        request.app.state.orchestrator = SkillGapOrchestrator(
            llm_client=llm_client,
            config=config,
        )
    return request.app.state.orchestrator


@router.post("/analyze", response_model=AnalyzeWithReportResponse)
@router.post(
    "/analyze-with-report",
    response_model=AnalyzeWithReportResponse,
    status_code=status.HTTP_200_OK,
    summary="Analyze CV–JD skill gaps and return the skill list and analysis summary",
)
def analyze_skill_gap(
    payload: AnalyzeSkillGapRequest,
    request: Request,
) -> AnalyzeWithReportResponse:
    orchestrator = _get_orchestrator(request)

    analysis_id = payload.analysis_id or str(uuid.uuid4())
    gap_results, report = orchestrator.run_pipeline_with_report(
        cv_text=payload.cv_text,
        jd_text=payload.jd_text,
        cv_skills=payload.cv_skills,
        jd_skills=payload.jd_skills,
        match_results=payload.match_results,
        analysis_id=analysis_id,
    )

    return AnalyzeWithReportResponse(
        analysis_id=analysis_id,
        skills=gap_results,
        report=report,
    )
