"""
FastAPI Router for Module 1 (`POST /api/v1/match`) and End-to-End Pipeline (`POST /api/v1/pipeline/analyze`).
Supports DUAL-INPUT: Both raw text (JSON) and PDF file uploads (Multipart Form-Data).
Connects matching_cv to Module 2 (Skill-Gap Detection).
"""

from __future__ import annotations

import logging
import uuid
from typing import Optional, TYPE_CHECKING
from fastapi import APIRouter, Request, File, Form, UploadFile, status, HTTPException
from starlette.concurrency import run_in_threadpool

from skill_gap.api.routes import _get_orchestrator, _get_report_store
from skill_gap.api.schemas import AnalyzeWithReportResponse
from .schemas import Module1Output
from .pdf_helper import extract_document_text

if TYPE_CHECKING:
    from matching_cv.app.container import MatchedDocuments

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1", tags=["NCKH Pipeline (Module 1 -> Module 2)"])


async def _match_documents(
    cv_text: str, jd_text: str, *, include_compatibility_score: bool = False,
) -> MatchedDocuments:
    # Load the ML pipeline on the first matching request.
    from matching_cv.app.container import match_documents
    from matching_cv.app.services.standardized_output_builder import Module1OutputError

    try:
        return await match_documents(
            cv_text, jd_text, include_compatibility_score=include_compatibility_score,
        )
    except Module1OutputError as error:
        logger.warning("Module 1 could not complete the analysis: %s", error)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Không thể hoàn tất phân tích kỹ năng từ CV và JD.",
        ) from error


async def _analyze_documents(
    request: Request, documents: MatchedDocuments, analysis_id: Optional[str],
) -> AnalyzeWithReportResponse:
    orchestrator = _get_orchestrator(request)
    match = documents.output
    skills, report = await run_in_threadpool(
        orchestrator.run_pipeline_with_report,
        cv_text=documents.cv_text,
        jd_text=documents.jd_text,
        cv_skills=match.cv_skills,
        jd_skills=match.jd_skills,
        match_results=match.match_results,
        analysis_id=analysis_id or str(uuid.uuid4()),
    )
    for skill in skills:
        skill.flags.append(f"matcher_source:{match.matcher_source}")
    report.matching_score = documents.matching_score
    _get_report_store(request)[report.analysis_id] = report
    return AnalyzeWithReportResponse(analysis_id=report.analysis_id, skills=skills, report=report)


async def _resolve_request_inputs(request: Request) -> tuple[str, str, Optional[str]]:
    """
    Dynamically extract (cv_text, jd_text, analysis_id) based on Content-Type header.
    Works for both application/json and multipart/form-data.
    """
    content_type = request.headers.get("content-type", "").lower()

    if "multipart/form-data" in content_type or "application/x-www-form-urlencoded" in content_type:
        form = await request.form()
        cv_file = form.get("cv_file")
        jd_file = form.get("jd_file")
        raw_cv_text = str(form.get("cv_text") or "")
        raw_jd_text = str(form.get("jd_text") or "")
        analysis_id = form.get("analysis_id")
        if analysis_id:
            analysis_id = str(analysis_id)

        cv_bytes = None
        cv_filename = None
        if hasattr(cv_file, "read"):
            cv_bytes = await cv_file.read()
            cv_filename = getattr(cv_file, "filename", None)

        jd_bytes = None
        jd_filename = None
        if hasattr(jd_file, "read"):
            jd_bytes = await jd_file.read()
            jd_filename = getattr(jd_file, "filename", None)

        cv_text = extract_document_text(cv_bytes, cv_filename, raw_cv_text)
        jd_text = extract_document_text(jd_bytes, jd_filename, raw_jd_text)
        return cv_text, jd_text, analysis_id

    # Default to JSON
    try:
        body = await request.json()
        return (
            (body.get("cv_text") or "").strip(),
            (body.get("jd_text") or "").strip(),
            body.get("analysis_id"),
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid request body format: {e}",
        )


@router.post(
    "/match",
    response_model=Module1Output,
    status_code=status.HTTP_200_OK,
    summary="Run CV/JD matching with JSON or multipart (PDF/text)",
)
async def run_module1_match(request: Request) -> Module1Output:
    cv_text, jd_text, _ = await _resolve_request_inputs(request)
    if not cv_text or not jd_text:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Both CV content and JD content (file or text) are required.",
        )
    return (await _match_documents(cv_text, jd_text)).output


@router.post(
    "/match/upload",
    response_model=Module1Output,
    status_code=status.HTTP_200_OK,
    summary="Execute Module 1 using explicit file uploads (PDF) or text fields",
)
async def run_module1_match_upload(
    cv_file: Optional[UploadFile] = File(None, description="CV PDF file"),
    jd_file: Optional[UploadFile] = File(None, description="JD PDF file"),
    cv_text: Optional[str] = Form(None, description="CV plain text"),
    jd_text: Optional[str] = Form(None, description="JD plain text"),
) -> Module1Output:
    cv_bytes = await cv_file.read() if cv_file else None
    jd_bytes = await jd_file.read() if jd_file else None

    resolved_cv = extract_document_text(cv_bytes, cv_file.filename if cv_file else None, cv_text)
    resolved_jd = extract_document_text(jd_bytes, jd_file.filename if jd_file else None, jd_text)

    if not resolved_cv or not resolved_jd:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Both CV and JD must be provided via file upload or text.",
        )

    return (await _match_documents(resolved_cv, resolved_jd)).output


@router.post(
    "/pipeline/analyze",
    response_model=AnalyzeWithReportResponse,
    status_code=status.HTTP_200_OK,
    summary="End-to-End NCKH Pipeline: Dual-Input (PDF/Text) -> Module 1 -> Module 2",
)
async def run_full_static_pipeline(request: Request) -> AnalyzeWithReportResponse:
    cv_text, jd_text, analysis_id = await _resolve_request_inputs(request)
    if not cv_text or not jd_text:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Both CV content and JD content (file or text) are required.",
        )

    documents = await _match_documents(cv_text, jd_text, include_compatibility_score=True)
    return await _analyze_documents(request, documents, analysis_id)


@router.post(
    "/pipeline/analyze-upload",
    response_model=AnalyzeWithReportResponse,
    status_code=status.HTTP_200_OK,
    summary="End-to-End NCKH Pipeline with explicit Multipart PDF/Text uploads",
)
async def run_full_static_pipeline_upload(
    request: Request,
    cv_file: Optional[UploadFile] = File(None, description="CV PDF file"),
    jd_file: Optional[UploadFile] = File(None, description="JD PDF file"),
    cv_text: Optional[str] = Form(None, description="CV plain text"),
    jd_text: Optional[str] = Form(None, description="JD plain text"),
    analysis_id: Optional[str] = Form(None),
) -> AnalyzeWithReportResponse:
    cv_bytes = await cv_file.read() if cv_file else None
    jd_bytes = await jd_file.read() if jd_file else None

    resolved_cv = extract_document_text(cv_bytes, cv_file.filename if cv_file else None, cv_text)
    resolved_jd = extract_document_text(jd_bytes, jd_file.filename if jd_file else None, jd_text)

    if not resolved_cv or not resolved_jd:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Both CV and JD must be provided via file upload or text.",
        )

    documents = await _match_documents(resolved_cv, resolved_jd, include_compatibility_score=True)
    return await _analyze_documents(request, documents, analysis_id)
