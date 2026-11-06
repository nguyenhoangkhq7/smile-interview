"""
Root entrypoint compatibility wrapper for `ai-service` and `skill_gap` tests.
"""

import os
from pathlib import Path
from typing import Optional
from fastapi import FastAPI
from app.main import create_app as _create_unified_app
from src.adapters.config import AppConfig, load_config
from src.adapters.llm_client import DSPyLLMClient, LLMClient
from src.pipeline.orchestrator import SkillGapOrchestrator

_PACKAGE_DIR = Path(__file__).resolve().parent


def create_app(
    llm_client: Optional[LLMClient] = None,
    config: Optional[AppConfig] = None,
) -> FastAPI:
    application = _create_unified_app()
    if llm_client is not None or config is not None:
        app_config = config or load_config(str(_PACKAGE_DIR / "config" / "settings.yaml"))
        model_name = os.environ.get("OPENROUTER_MODEL", app_config.llm.model)
        active_llm = llm_client or DSPyLLMClient(model=model_name)
        application.state.config = app_config
        application.state.orchestrator = SkillGapOrchestrator(
            llm_client=active_llm, config=app_config
        )
    return application


app = create_app()
