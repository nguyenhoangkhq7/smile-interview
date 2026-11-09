from pathlib import Path
from typing import Dict
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from module1_matcher.router import router as module1_router
from skill_gap.api.routes import router as skill_gap_router
from adaptive_questioning.api.routes import router as interview_router
from adaptive_questioning.evidence.routes import router as evidence_router
from voice.routes import router as voice_router

_ROOT_DIR = Path(__file__).resolve().parent.parent
load_dotenv(_ROOT_DIR.parent / ".env")
load_dotenv(_ROOT_DIR / ".env", override=True)


def create_app() -> FastAPI:
    application = FastAPI(
        title="Smile Interview NCKH AI Service",
        description=(
            "Unified Scientific Research Pipeline: "
            "Module 1 (SBERT+GNN Skill Matcher) -> "
            "Module 2 (Skill-Gap Detection V2.0) -> "
            "Module 3 (Evidence-based Adaptive Interviewing)"
        ),
        version="2.2.0",
    )

    application.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    application.state.report_store = {}

    application.include_router(module1_router)
    application.include_router(skill_gap_router)
    application.include_router(interview_router)
    application.include_router(evidence_router)
    application.include_router(voice_router)

    @application.get("/health", tags=["Health"])
    async def health_check() -> Dict[str, str]:
        return {
            "status": "ok",
            "service": settings.APP_NAME,
            "version": "2.2.0",
        }

    @application.get("/", tags=["Health"])
    async def root() -> Dict[str, str]:
        return {
            "message": "Smile Interview NCKH AI Service (Module 1 -> Module 2 -> Module 3). See /docs for OpenAPI."
        }

    return application


app = create_app()

if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host=settings.HOST, port=settings.PORT, reload=settings.DEBUG)
