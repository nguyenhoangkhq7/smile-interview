"""Unified matching_cv endpoints and the matching_cv → skill_gap pipeline."""

import logging
import uuid
from typing import Optional

from fastapi import APIRouter, HTTPException, Request, status
from starlette.concurrency import run_in_threadpool

from matching_cv.app.container import match_documents
from matching_cv.app.schemas.module1 import Module1Output
from matching_cv.app.services.document_parser import document_parser_service
from matching_cv.app.services.standardized_output_builder import Module1OutputError
from skill_gap.api.routes import _get_orchestrator, _get_report_store
from skill_gap.api.schemas import AnalyzeWithReportResponse

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1", tags=["Matching CV"])


async def read_inputs(request: Request) -> tuple[str, str, Optional[str]]:
    content_type = request.headers.get("content-type", "").lower()
    if "multipart/form-data" in content_type or "application/x-www-form-urlencoded" in content_type:
        form = await request.form()

        async def get_text(name: str) -> str:
            uploaded = form.get(f"{name}_file")
            if uploaded is not None and hasattr(uploaded, "read") and getattr(uploaded, "filename", None):
                return (await document_parser_service.parse_file(uploaded)).raw_text
            return str(form.get(f"{name}_text") or "").strip()

        analysis_id = form.get("analysis_id")
        return await get_text("cv"), await get_text("jd"), str(analysis_id) if analysis_id else None

    try:
        payload = await request.json()
    except Exception as error:
        raise HTTPException(status_code=400, detail="Invalid request body format.") from error
    return str(payload.get("cv_text") or "").strip(), str(payload.get("jd_text") or "").strip(), payload.get("analysis_id")


async def run_matching(cv_text: str, jd_text: str, *, include_compatibility_score: bool = False):
    try:
        return await match_documents(cv_text, jd_text, include_compatibility_score=include_compatibility_score)
    except Module1OutputError as error:
        logger.warning("matching_cv analysis failed: %s", error)
        raise HTTPException(status_code=503, detail="Không thể hoàn tất phân tích kỹ năng từ CV và JD.") from error


@router.post("/match", response_model=Module1Output, status_code=status.HTTP_200_OK)
async def match(request: Request) -> Module1Output:
    cv_text, jd_text, _ = await read_inputs(request)
    if not cv_text or not jd_text:
        raise HTTPException(status_code=400, detail="Both CV content and JD content (file or text) are required.")
    return (await run_matching(cv_text, jd_text)).output


@router.post("/pipeline/analyze", response_model=AnalyzeWithReportResponse, status_code=status.HTTP_200_OK)
async def analyze(request: Request) -> AnalyzeWithReportResponse:
    cv_text, jd_text, analysis_id = await read_inputs(request)
    if not cv_text or not jd_text:
        raise HTTPException(status_code=400, detail="Both CV content and JD content (file or text) are required.")
    documents = await run_matching(cv_text, jd_text, include_compatibility_score=True)
    match_result = documents.output
    skills, report = await run_in_threadpool(
        _get_orchestrator(request).run_pipeline_with_report,
        cv_text=documents.cv_text,
        jd_text=documents.jd_text,
        cv_skills=match_result.cv_skills,
        jd_skills=match_result.jd_skills,
        match_results=match_result.match_results,
        analysis_id=analysis_id or str(uuid.uuid4()),
    )
    for skill in skills:
        skill.flags.append(f"matcher_source:{match_result.matcher_source}")
    report.matching_score = documents.matching_score
    _get_report_store(request)[report.analysis_id] = report
    return AnalyzeWithReportResponse(analysis_id=report.analysis_id, skills=skills, report=report)
