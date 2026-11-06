"""
FastAPI Router for Module 1 (`POST /api/v1/match`) and End-to-End Pipeline (`POST /api/v1/pipeline/analyze`).
Supports DUAL-INPUT: Both raw text (JSON) and PDF file uploads (Multipart Form-Data).
Connects Module 1 (SBERT + GNN Adapter) -> Module 2 (Skill-Gap Detection).
"""

import uuid
from typing import Optional
from fastapi import APIRouter, Request, File, Form, UploadFile, status, HTTPException

from src.api.routes import _get_orchestrator, _get_report_store
from src.api.schemas import AnalyzeWithReportResponse
from .schemas import MatchPipelineRequest, Module1Output
from .extractor import DefaultModule1Extractor, Module1MatcherProtocol
from .pdf_helper import extract_document_text

router = APIRouter(prefix="/api/v1", tags=["NCKH Pipeline (Module 1 -> Module 2)"])


def _get_module1_matcher(request: Request) -> Module1MatcherProtocol:
    if not hasattr(request.app.state, "module1_matcher"):
        orchestrator = _get_orchestrator(request)
        fallback_llm = getattr(orchestrator.llm_client, "fallback_client", None) or orchestrator.llm_client
        request.app.state.module1_matcher = DefaultModule1Extractor(
            llm_client=fallback_llm,
            use_llm=True,
        )
    return request.app.state.module1_matcher


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
            body.get("cv_text", "").strip(),
            body.get("jd_text", "").strip(),
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
    summary="Execute Module 1 (SBERT + GNN Adapter) with JSON or Multipart (PDF/Text)",
)
async def run_module1_match(request: Request) -> Module1Output:
    cv_text, jd_text, _ = await _resolve_request_inputs(request)
    if not cv_text or not jd_text:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Both CV content and JD content (file or text) are required.",
        )
    matcher = _get_module1_matcher(request)
    return matcher.extract_and_match(cv_text=cv_text, jd_text=jd_text)


@router.post(
    "/match/upload",
    response_model=Module1Output,
    status_code=status.HTTP_200_OK,
    summary="Execute Module 1 using explicit file uploads (PDF) or text fields",
)
async def run_module1_match_upload(
    request: Request,
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

    matcher = _get_module1_matcher(request)
    return matcher.extract_and_match(cv_text=resolved_cv, jd_text=resolved_jd)


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

    matcher = _get_module1_matcher(request)
    orchestrator = _get_orchestrator(request)
    store = _get_report_store(request)

    m1_out = matcher.extract_and_match(cv_text=cv_text, jd_text=jd_text)
    final_analysis_id = analysis_id or str(uuid.uuid4())

    gap_results, report = orchestrator.run_pipeline_with_report(
        cv_text=cv_text,
        jd_text=jd_text,
        cv_skills=m1_out.cv_skills,
        jd_skills=m1_out.jd_skills,
        match_results=m1_out.match_results,
        analysis_id=final_analysis_id,
    )
    store[report.analysis_id] = report

    return AnalyzeWithReportResponse(
        analysis_id=report.analysis_id,
        skills=gap_results,
        report=report,
    )


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

    matcher = _get_module1_matcher(request)
    orchestrator = _get_orchestrator(request)
    store = _get_report_store(request)

    m1_out = matcher.extract_and_match(cv_text=resolved_cv, jd_text=resolved_jd)
    final_analysis_id = analysis_id or str(uuid.uuid4())

    gap_results, report = orchestrator.run_pipeline_with_report(
        cv_text=resolved_cv,
        jd_text=resolved_jd,
        cv_skills=m1_out.cv_skills,
        jd_skills=m1_out.jd_skills,
        match_results=m1_out.match_results,
        analysis_id=final_analysis_id,
    )
    store[report.analysis_id] = report

    return AnalyzeWithReportResponse(
        analysis_id=report.analysis_id,
        skills=gap_results,
        report=report,
    )
