"""Versioned, snapshot-persisted heuristics; none maps proficiency to question depth."""
import re
import os
from pydantic import BaseModel, ConfigDict, Field, model_validator


class InterviewPolicy(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    version: str = "criterion-policy-2"
    fallback_depth: int = Field(default=2, ge=1, le=4)
    # Empty by default: a job title alone must not imply a particular depth.
    seniority_fallback_depths: dict[str, int] = Field(default_factory=dict)
    depth_patterns: dict[str, int] = Field(default_factory=lambda: {
        r"\b(design|architect|trade.?offs?)\b|thiết kế|đánh đổi": 4,
        r"\b(debug|diagnos\w*|analy[sz]\w*|optimi[sz]\w*|troubleshoot\w*)\b|phân tích|chẩn đoán|tối ưu": 3,
        r"\b(write|implement|build|use|apply|develop|execute)\b|viết|triển khai|sử dụng|vận dụng": 2,
        r"\b(explain|define|describe|identify)\b|giải thích|định nghĩa|mô tả": 1,
    })
    mode_patterns: dict[str, str] = Field(default_factory=lambda: {
        "DEBUGGING": r"\b(debug|diagnos\w*|troubleshoot\w*|optimi[sz]\w*)\b|chẩn đoán|tối ưu|sửa lỗi",
        "DESIGN": r"\b(design|architect|trade.?offs?)\b|thiết kế|đánh đổi",
        "CODING": r"\b(write|implement|code|program)\b|viết|lập trình",
        "TECHNICAL_EXPLANATION": r"\b(explain|define|describe)\b|giải thích|định nghĩa|mô tả",
        "BEHAVIORAL": r"\b(collaborat\w*|mentor\w*|conflict|stakeholders?)\b|phối hợp|hướng dẫn|xung đột",
    })
    reserve_followup_fraction: float = Field(default=0.3, ge=0, le=0.8)
    core_importance: float = Field(default=0.7, ge=0, le=1)
    min_failure_contexts: int = Field(default=2, ge=2, le=5)
    allow_extension_probes: bool = False
    generation_attempts: int = Field(default=2, ge=1, le=3)
    judgment_attempts: int = Field(default=2, ge=1, le=3)
    criterion_soft_limit: int = Field(default=3, ge=1, le=10)
    max_turns_per_criterion: int = Field(default=6, ge=1, le=40)
    max_stagnant_turns: int = Field(default=2, ge=1, le=10)

    @model_validator(mode="after")
    def valid_rules(self):
        if self.max_turns_per_criterion < self.criterion_soft_limit:
            raise ValueError("Criterion hard limit must not be below its soft limit")
        if any(depth not in range(1, 5) for depth in [*self.depth_patterns.values(), *self.seniority_fallback_depths.values()]):
            raise ValueError("Configured depth must be L1–L4")
        modes = {"CODING", "DEBUGGING", "DESIGN", "TECHNICAL_EXPLANATION", "BEHAVIORAL"}
        if not set(self.mode_patterns).issubset(modes):
            raise ValueError("Unknown configured question mode")
        for pattern in [*self.depth_patterns, *self.mode_patterns.values()]:
            try:
                re.compile(pattern)
            except re.error as exc:
                raise ValueError("Invalid policy pattern") from exc
        return self


def configured_policy() -> InterviewPolicy:
    """Operator configuration, not candidate-controlled interview input."""
    value = os.environ.get("EVIDENCE_POLICY_JSON")
    return InterviewPolicy.model_validate_json(value) if value is not None else InterviewPolicy()
