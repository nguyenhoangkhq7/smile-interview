"""Health and system status check endpoint."""
from typing import Any, Dict
from fastapi import APIRouter, status
from matching_cv.app.core.config import settings
from matching_cv.app.core.model_loader import model_loader

router = APIRouter()


@router.get(
    "/health",
    status_code=status.HTTP_200_OK,
    summary="Health check & system diagnostic",
    response_description="Service health, device status, and active model information",
)
def check_health() -> Dict[str, Any]:
    """
    Check service health, loaded model status, and computing hardware (CUDA / CPU).
    """
    model_info = model_loader.get_info()

    return {
        "status": "healthy",
        "service": settings.PROJECT_NAME,
        "environment": settings.ENVIRONMENT,
        "device": model_loader.device,
        "model": model_info,
    }
