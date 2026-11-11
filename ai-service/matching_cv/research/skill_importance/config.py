"""Configuration and provisional research hyperparameters for JSI-v1.

Reference:
- Shi et al. (KDD 2020), Job2Skills
- Section 6 & 9 of JSI-2 Specification
"""
from dataclasses import dataclass, field
from typing import Dict, Optional


@dataclass
class JSIConfig:
    """Provisional research configuration for JD Skill Importance Estimator v1."""

    # Pinned SBERT infrastructure (identical to Stage 3 & Phase J)
    sbert_model_id: str = "sentence-transformers/paraphrase-multilingual-mpnet-base-v2"
    sbert_revision: str = "4328cf26390c98c5e3c738b4460a05b95f4911f5"
    sbert_dim: int = 768

    # Scoring version tag
    scoring_version: str = "jsi-v1"

    # Dimension mixture weights (provisional research hyperparameters, not learned)
    weight_segment: float = 0.40
    weight_sentence: float = 0.35
    weight_job: float = 0.25

    # Section priors (Table in Section 7)
    section_priors: Dict[str, float] = field(
        default_factory=lambda: {
            "requirements": 1.00,
            "responsibilities": 0.80,
            "nice_to_have": 0.50,
            "about": 0.30,
            "benefits": 0.05,
        }
    )

    # Deontic modality initial values (Table in Section 6)
    modality_values: Dict[str, float] = field(
        default_factory=lambda: {
            "Mandatory": 1.00,
            "Operational": 0.75,
            "Preferred": 0.50,
            "Contextual": 0.25,
            "Negated": 0.00,
        }
    )

    # Sentence-level salience balance: alpha * transformed_cosine + (1 - alpha) * modality
    sentence_cosine_weight: float = 0.50
    sentence_modality_weight: float = 0.50

    # Job-level salience balance: beta * title_sim + (1 - beta) * req_centroid_sim
    job_title_weight: float = 0.60
    job_req_weight: float = 0.40

    # Engineering constraints for downstream edge-weight contract
    # Fixed monotonic transformation parameters into [scale_min, scale_max]
    scale_min: float = 0.10
    scale_max: float = 0.90  # w_j = scale_min + scale_max * raw_score

    # Multi-occurrence aggregation
    multi_occurrence_strategy: str = "max_pooling"

    # Normalization method label
    normalization_method: str = "provisional_fixed_monotonic"


# Default singleton config instance
default_jsi_config = JSIConfig()
