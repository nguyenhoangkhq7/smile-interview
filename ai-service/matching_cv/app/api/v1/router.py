"""API v1 master router."""
from typing import Optional
from fastapi import APIRouter, File, Form, UploadFile, status
from matching_cv.app.api.v1.endpoints import (
    health,
    pipeline,
)
from matching_cv.app.schemas.unified_skill_extraction import UnifiedExtractFileResponse
from matching_cv.app.services.unified_skill_service import unified_skill_service

api_router = APIRouter()

# Primary Production Pipeline Endpoint
api_router.include_router(
    pipeline.router,
    prefix="/pipeline",
    tags=["Primary - Unified Pipeline"],
)


@api_router.post(
    "/extract-all-from-file",
    response_model=UnifiedExtractFileResponse,
    status_code=status.HTTP_200_OK,
    tags=["Skill Extraction"],
    summary="Extract explicit and implicit skills from CV and/or JD files",
)
async def extract_all_from_file(
    cv_file: Optional[UploadFile] = File(
        default=None,
        description="Candidate CV document file (.pdf or .txt)",
    ),
    jd_file: Optional[UploadFile] = File(
        default=None,
        description="Job Description document file (.pdf or .txt)",
    ),
    file: Optional[UploadFile] = File(
        default=None,
        description="Single document file (.pdf or .txt) when testing one file with document_type",
    ),
    document_type: Optional[str] = Form(
        default="CV",
        description="Document type ('CV' or 'JD') when uploading via the single 'file' field",
    ),
) -> UnifiedExtractFileResponse:
    return await unified_skill_service.extract_unified_from_files(
        cv_file=cv_file,
        jd_file=jd_file,
        file=file,
        document_type=document_type,
    )

# Include health routes
api_router.include_router(
    health.router,
    tags=["Health"],
)
