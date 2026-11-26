"""Main entry point for AI Inference Service application."""
import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from matching_cv.app.api.v1.endpoints.health import router as health_router
from matching_cv.app.api.v1.router import api_router
from matching_cv.app.container import pipeline_orchestrator
from matching_cv.app.core.config import settings
from matching_cv.app.core.model_loader import model_loader

# Configure logging format
logging.basicConfig(
    level=logging.INFO if not settings.DEBUG else logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("ai_inference_service")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    FastAPI Lifespan context manager:
    - Startup: Preload Sentence-BERT model into RAM/VRAM once.
    - Shutdown: Gracefully clean up ML resources and GPU memory if needed.
    """
    logger.info("==================================================")
    logger.info(f"Starting {settings.PROJECT_NAME}...")
    logger.info(f"Environment: {settings.ENVIRONMENT} | Debug: {settings.DEBUG}")

    # Preload the exact embedding model used by the analyze pipeline.
    try:
        model_loader.load_model(
            model_name=settings.STAGE3_MODEL_NAME,
            revision=settings.STAGE3_MODEL_REVISION,
        )
        logger.info(
            f"Preloaded pipeline model: '{settings.STAGE3_MODEL_NAME}' "
            f"(revision={settings.STAGE3_MODEL_REVISION}) on device '{model_loader.device}'."
        )
    except Exception as exc:
        logger.critical(f"FATAL: Model initialization failed: {exc}", exc_info=True)
        raise

    logger.info(f"{settings.PROJECT_NAME} is ready to serve inference requests.")
    logger.info("==================================================")

    yield

    # Teardown logic on server shutdown
    logger.info("==================================================")
    logger.info(f"Shutting down {settings.PROJECT_NAME}...")
    # Optional: Clean up GPU memory if PyTorch CUDA was in use
    try:
        import torch
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
            logger.info("CUDA cache cleared.")
    except Exception as e:
        logger.warning(f"Error while releasing CUDA cache: {e}")

    logger.info("Application shutdown completed.")
    logger.info("==================================================")


TAGS_METADATA = [
    {
        "name": "Primary - Unified Pipeline",
        "description": "Analyze CV and job description documents through the configured matching pipeline.",
    },
    {
        "name": "Health",
        "description": "System liveness and readiness health checks.",
    },
]

app = FastAPI(
    title=settings.PROJECT_NAME,
    description=(
        "API phân tích mức độ phù hợp giữa CV và mô tả công việc. "
        "Endpoint chính: `POST /api/v1/pipeline/analyze`."
    ),
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    openapi_tags=TAGS_METADATA,
    lifespan=lifespan,
)
app.state.pipeline_orchestrator = pipeline_orchestrator

# Enable CORS for cross-origin frontend or gateway microservices
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Root-level health check endpoint (convenient for Docker, K8s, Load Balancers)
app.include_router(health_router, prefix="", tags=["Root Health"])

# Include versioned API v1 endpoints
app.include_router(api_router, prefix=settings.API_V1_STR)


@app.get("/", include_in_schema=False)
def root_redirect():
    """Root endpoint info."""
    return {
        "service": settings.PROJECT_NAME,
        "version": "0.1.0",
        "docs": "/docs",
        "health": "/health",
    }
