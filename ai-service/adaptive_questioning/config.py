"""
Configuration and Hyperparameters for Pipeline V2.2 Architecture using `pydantic-settings`.
Supports reproducible Ablation Studies & Sensitivity Analysis via environment overrides
while exporting canonical module-level constants.
"""

from pathlib import Path
from typing import Dict, Tuple
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

_PACKAGE_DIR = Path(__file__).resolve().parent
_PROJECT_ROOT_DIR = _PACKAGE_DIR.parent


class AdaptiveQuestioningSettings(BaseSettings):
    """
    Validated configuration for Pipeline V2.2 Adaptive Questioning.
    Can be overridden via environment variables prefixed with `AQ_` for ablation experiments.
    Automatically loads `.env` from either project root (`NCKH/.env`) or `adaptive_questioning/.env`.
    """

    model_config = SettingsConfigDict(
        env_prefix="AQ_",
        env_file=(
            str(_PROJECT_ROOT_DIR / ".env"),
            str(_PACKAGE_DIR / ".env"),
            ".env",
        ),
        extra="ignore",
    )

    rubric_levels: Tuple[str, str, str] = Field(
        default=("Low", "Med", "High"),
        description="Rubric Ordinal Levels L = {Low, Med, High}",
    )
    centroids: Tuple[float, float, float] = Field(
        default=(1.5, 3.0, 4.5),
        description="Rubric Centroids c = [1.5, 3.0, 4.5] on a 5.0 scale",
    )
    tau_prior: float = Field(
        default=2.0,
        gt=0.0,
        description="Temperature for Prior Belief Initialization (prevents Turn-1 saturation)",
    )
    delta_bounds: Dict[str, float] = Field(
        default={
            "INVARIANT": 0.00,
            "MINOR_SHIFT": 0.12,
            "MODERATE_SHIFT": 0.25,
            "DECISIVE_SHIFT": 0.45,
        },
        description="Metamorphic Step Bounds (delta_max) for Total Variation distance",
    )
    convergence_prob_threshold: float = Field(
        default=0.75,
        ge=0.5,
        le=1.0,
        description="MAP belief probability threshold for local convergence",
    )
    convergence_tv_threshold: float = Field(
        default=0.03,
        ge=0.0,
        le=1.0,
        description="Total Variation step threshold for local Cauchy-like convergence at k >= 2",
    )
    max_sub_slots: int = Field(
        default=2,
        ge=1,
        description="Hard cap of dynamic probing sub-slots per primary skill d*",
    )
    k_max: int = Field(
        default=3,
        ge=1,
        description="Maximum local turns per primary skill d* (1 opening + 2 follow-ups)",
    )
    t_max: int = Field(
        default=10,
        ge=1,
        description="Maximum global turns across the entire interview session",
    )
    global_completion_threshold: float = Field(
        default=0.80,
        ge=0.0,
        le=1.0,
        description="Global completion ratio D_verified / D to terminate interview",
    )


settings = AdaptiveQuestioningSettings()

# Canonical module-level exports matching specification
RUBRIC_LEVELS: Tuple[str, str, str] = settings.rubric_levels
CENTROIDS: Tuple[float, float, float] = settings.centroids
TAU_PRIOR: float = settings.tau_prior
DELTA_BOUNDS: Dict[str, float] = dict(settings.delta_bounds)
CONVERGENCE_PROB_THRESHOLD: float = settings.convergence_prob_threshold
CONVERGENCE_TV_THRESHOLD: float = settings.convergence_tv_threshold
MAX_SUB_SLOTS: int = settings.max_sub_slots
K_MAX: int = settings.k_max
T_MAX: int = settings.t_max
GLOBAL_COMPLETION_THRESHOLD: float = settings.global_completion_threshold
