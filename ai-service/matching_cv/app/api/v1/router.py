"""API v1 master router."""
from fastapi import APIRouter
from matching_cv.app.api.v1.endpoints import (
    health,
    pipeline,
)

api_router = APIRouter()

# Primary Production Pipeline Endpoint
api_router.include_router(
    pipeline.router,
    prefix="/pipeline",
    tags=["Primary - Unified Pipeline"],
)

# Include health routes
api_router.include_router(
    health.router,
    tags=["Health"],
)
