"""Core configuration and settings module."""
from pathlib import Path
from typing import Literal, Optional
from app.ai_runtime import credential, model_value, openrouter_id
from pydantic_settings import BaseSettings, SettingsConfigDict


_RUNTIME_FIELDS = {
    "OPENROUTER_MODEL": "matchingModel",
    "OPENROUTER_VERIFIER_MODEL": "verifierModel",
    "STAGE3_MODEL_NAME": "embeddingModel",
    "STAGE3_MODEL_REVISION": "embeddingRevision",
}


class Settings(BaseSettings):
    def __getattribute__(self, name: str):
        value = super().__getattribute__(name)
        if name == "OPENROUTER_API_KEY":
            return credential("openRouterKey", value)
        if name in _RUNTIME_FIELDS:
            value = model_value(_RUNTIME_FIELDS[name], value)
            if name.startswith("OPENROUTER_"):
                return openrouter_id(value)
            return value or None
        return value

    PROJECT_NAME: str = "AI Inference Service"
    API_V1_STR: str = "/api/v1"
    ENVIRONMENT: str = "production"
    DEBUG: bool = False
    OPENROUTER_REFERER: str = "https://smile-interview.app"

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

    # Matching CV explicit extraction uses a compiled DSPy module by default.
    MATCHING_CV_DSPY_EXPLICIT_ENABLED: bool = True

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

    # Explicit skill extraction routing: route domain entities to skills
    ROUTE_DOMAIN_TO_SKILLS: bool = True

    # Stage B2: Disable implicit LLM extraction for JD documents by default (CV unchanged)
    IMPLICIT_ENABLED_FOR_JD: bool = False

    # Stage C: Skill clustering (deterministic near-duplicate grouping, non-destructive)
    SKILL_CLUSTERING_ENABLED: bool = False

    model_config = SettingsConfigDict(
        env_file=Path(__file__).resolve().parents[3] / ".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )


settings = Settings()
