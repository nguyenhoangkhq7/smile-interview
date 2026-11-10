"""Core configuration and settings module."""
from pathlib import Path
from typing import Literal, Optional
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    PROJECT_NAME: str = "AI Inference Service"
    API_V1_STR: str = "/api/v1"
    ENVIRONMENT: str = "development"
    DEBUG: bool = True

    # Server configuration
    HOST: str = "0.0.0.0"
    PORT: int = 8000

    # Model settings
    DEVICE: Literal["auto", "cuda", "cpu"] = "auto"

    # Stage 3 SBERT Semantic Representation settings
    STAGE3_MODEL_NAME: str = "sentence-transformers/paraphrase-multilingual-mpnet-base-v2"
    STAGE3_MODEL_REVISION: Optional[str] = "4328cf26390c98c5e3c738b4460a05b95f4911f5"
    STAGE3_EMBEDDING_DIM: int = 768
    STAGE3_BATCH_SIZE: int = 32
    STAGE3_MAX_SEQ_LENGTH: int = 128

    # OpenRouter LLM Configuration
    OPENROUTER_API_KEY: str = ""
    OPENROUTER_MODEL: str = "google/gemini-2.5-flash"
    OPENROUTER_VERIFIER_MODEL: str = ""
    OPENROUTER_BASE_URL: str = "https://openrouter.ai/api/v1"

    # Stage 4 / Pre-GNN Pipeline Orchestration Settings
    PIPELINE_MAX_FILE_SIZE_BYTES: int = 15 * 1024 * 1024  # 15 MB
    PIPELINE_ALLOWED_EXTENSIONS: list[str] = [".pdf", ".txt"]
    PIPELINE_MAX_TOP_K: int = 25
    PIPELINE_LLM_TIMEOUT_SECONDS: float = 45.0
    PIPELINE_MAX_CONCURRENCY: int = 5
    PIPELINE_DEFAULT_REASONING_MAX_PAIRS: int = 25
    PIPELINE_DEFAULT_SELECTION_STRATEGY: str = "balanced_coverage"
    # Standardized public output (standardized-output-v1): minimum raw SBERT cosine for a NON-identical
    # JD->CV skill match to be reported in skill_gap_input. Operational default, NOT calibrated and NOT
    # evidence of equivalence; tune against annotated skill-pair data. Verified-identity matches ignore it.
    SKILL_GAP_MIN_SOFT_MATCH: float = 0.50

    # Production skill importance inference
    JSI_IMPORTANCE_ENABLED: bool = True

    model_config = SettingsConfigDict(
        env_file=Path(__file__).resolve().parents[3] / ".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )


settings = Settings()
