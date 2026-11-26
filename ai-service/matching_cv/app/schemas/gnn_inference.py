"""Pydantic schemas for GNN Inference Service (Default: PaperAlignedHybridGNN)."""
from enum import Enum
from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, Field, PrivateAttr, model_validator


class FitCategory(str, Enum):
    NO_FIT = "No Fit"
    POTENTIAL_FIT = "Potential Fit"
    GOOD_FIT = "Good Fit"
    UNCALIBRATED = "Uncalibrated"


class GNNInferenceResponse(BaseModel):
    """Response schema for trained PaperAlignedHybridGNN compatibility inference."""
    pair_id: Optional[str] = Field(default=None, description="Pair identifier if known")
    model_name: str = Field(
        default="PaperAlignedHybridGNN",
        description="Active GNN architecture name",
    )
    matching_score: float = Field(
        ...,
        ge=0.0,
        le=100.0,
        description="Bounded compatibility score on active score_scale ([0, 1] or [0, 100])",
    )
    raw_score: float = Field(
        ...,
        description="Raw continuous regression score from MLP head (unbounded; never silently clamped)",
    )
    raw_model_score: Optional[float] = Field(
        default=None,
        description="Canonical raw regression score from the GNN model head (synced with raw_score)",
    )
    predicted_target_name: str = Field(
        default="skill_score",
        description="Supervision target predicted by the loaded checkpoint (e.g. 'skill_score')",
    )
    score_version: str = Field(
        default="skill-target-regression-v1",
        description="Versioned scoring contract identifier",
    )
    calibrated_score: Optional[float] = Field(
        default=None,
        description="Empirically calibrated compatibility probability; None when uncalibrated",
    )
    calibration_status: str = Field(
        default="UNCALIBRATED",
        description="Calibration status ('UNCALIBRATED' when no validated probability calibration exists)",
    )
    bounded_display_score: float = Field(
        ...,
        ge=0.0,
        le=100.0,
        description="Explicitly bounded score for presentation and backward compatibility",
    )
    fit_category: Optional[FitCategory] = Field(
        default=None,
        description="Optional post-processing categorical fit derived from documented thresholds, or FitCategory.UNCALIBRATED when uncalibrated",
    )
    score_scale: str = Field(
        default="0_1",
        description="Active score scale ('0_1' or '0_100')",
    )
    score_range: Dict[str, float] = Field(
        default_factory=lambda: {"min": 0.0, "max": 1.0},
        description="Theoretical bounds [min, max] of the bounded compatibility score",
    )
    score_type: str = Field(
        default="bounded_uncalibrated_regression",
        description="Mathematical score type description",
    )
    classification_thresholds: Optional[Dict[str, float]] = Field(
        default=None,
        description="Optional post-processing classification threshold boundaries; None when uncalibrated",
    )
    graph_mode: str = Field(
        ...,
        description="Active graph mode evaluated",
    )
    model_version: str = Field(
        default="paper-aligned-2025-v1",
        description="Inference model release version",
    )
    checkpoint_name: str = Field(..., description="Filename of active checkpoint")
    checkpoint_sha256: str = Field(..., description="SHA-256 integrity hash of checkpoint")
    input_validation: Dict[str, Any] = Field(
        ...,
        description="Input graph structural validation metrics, proficiency coverage, and node/edge inventories",
    )
    resume_skill_attention: Optional[Dict[str, float]] = Field(
        default=None,
        description="Final-layer Equation (2) modified GAT attention weights over resume skills (Figure 6)",
    )
    inference_latency_ms: float = Field(..., description="Measured forward-pass latency in milliseconds")
    probability_calibration_disclaimer: str = Field(
        default=(
            "Raw regression scores are uncalibrated continuous model outputs trained with MSE loss and must NOT be "
            "interpreted as posterior probabilities."
        ),
        description="Mandatory scientific reproducibility and statistical disclaimer",
    )

    # Non-serialized hand-off (never part of model_dump/JSON) used to derive the standardized public output.
    _public_context: Optional[Any] = PrivateAttr(default=None)

    @model_validator(mode="before")
    @classmethod
    def sync_scores(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if "matching_score" in data and "bounded_display_score" not in data:
                data["bounded_display_score"] = data["matching_score"]
            elif "bounded_display_score" in data and "matching_score" not in data:
                data["matching_score"] = data["bounded_display_score"]
            if data.get("raw_score") is not None and data.get("raw_model_score") is None:
                data["raw_model_score"] = data["raw_score"]
            elif data.get("raw_model_score") is not None and data.get("raw_score") is None:
                data["raw_score"] = data["raw_model_score"]
        return data
