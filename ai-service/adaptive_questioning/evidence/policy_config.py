"""Snapshot-persisted evaluation and allocation thresholds; none maps proficiency to depth."""
import os
from pydantic import BaseModel, ConfigDict, Field


class InterviewPolicy(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    fallback_depth: int = Field(default=2, ge=1, le=4)
    core_importance: float = Field(default=0.7, ge=0, le=1)
    reserve_followup_fraction: float = Field(default=0.3, ge=0, le=0.8)
    min_failure_contexts: int = Field(default=2, ge=2, le=5)
    allow_extension_probes: bool = True


def configured_policy() -> InterviewPolicy:
    """Operator configuration, not candidate-controlled interview input."""
    value = os.environ.get("EVIDENCE_POLICY_JSON")
    return InterviewPolicy.model_validate_json(value) if value is not None else InterviewPolicy()
