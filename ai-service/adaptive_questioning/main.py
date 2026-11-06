"""
FastAPI Application Entrypoint for Adaptive Questioning (Pipeline V2.2).
"""

from pathlib import Path
from typing import Dict, Optional
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from adaptive_questioning.api.routes import router as interview_router
from adaptive_questioning.core.engine import BaseLLMEngine, OpenAILLMEngine
from adaptive_questioning.graph.workflow import AdaptiveQuestioningWorkflow
from adaptive_questioning.schemas.state import InterviewSessionState

_PACKAGE_DIR = Path(__file__).resolve().parent
_PROJECT_ROOT_DIR = _PACKAGE_DIR.parent

# Load .env from project root first, and allow package-level .env override if present
load_dotenv(_PROJECT_ROOT_DIR / ".env")
load_dotenv(_PACKAGE_DIR / ".env", override=True)


def create_app(engine: Optional[BaseLLMEngine] = None) -> FastAPI:
    """Create and configure the FastAPI application instance."""
    application = FastAPI(
        title="Adaptive Questioning Service (Pipeline V2.2)",
        description=(
            "Contribution 3: Sequenced Prompt-Chaining Mechanism for LLMs to Generate "
            "Adaptive Questions to Clarify Suspected Competency Gaps in Resumes Without Topic Drift."
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

    session_store: Dict[str, InterviewSessionState] = {}
    llm_engine = engine or OpenAILLMEngine()
    workflow = AdaptiveQuestioningWorkflow(engine=llm_engine)

    application.state.session_store = session_store
    application.state.workflow = workflow

    application.include_router(interview_router)

    @application.get("/health", tags=["Health"])
    def health_check() -> Dict[str, str]:
        return {"status": "ok", "version": "2.2.0"}

    return application


app = create_app()
