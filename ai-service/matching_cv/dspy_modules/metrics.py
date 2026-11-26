"""Precision-weighted metrics for explicit skill extraction."""

from collections import Counter
import re
from typing import Any


def _field(value: Any, key: str, default: Any = None) -> Any:
    if hasattr(value, key):
        return getattr(value, key)
    if isinstance(value, dict):
        return value.get(key, default)
    return default


def _normalize(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip().casefold()


def _candidate_key(candidate: Any) -> tuple[str, str, str]:
    return (
        _normalize(_field(candidate, "mention")),
        _normalize(_field(candidate, "source_sentence")),
        _normalize(_field(candidate, "kind")),
    )


def explicit_skill_metric(example: Any, prediction: Any, trace: Any = None) -> float:
    """Score exact grounded outputs with a precision-weighted F0.5 objective."""
    expected = _field(example, "explicit_skills", []) or []
    predicted = _field(prediction, "explicit_skills", None)
    if not isinstance(predicted, list):
        return 0.0

    expected_counts = Counter(_candidate_key(item) for item in expected)
    predicted_counts = Counter(_candidate_key(item) for item in predicted)
    true_positives = sum((expected_counts & predicted_counts).values())
    false_positives = sum((predicted_counts - expected_counts).values())
    false_negatives = sum((expected_counts - predicted_counts).values())

    if not expected and not predicted:
        return 1.0
    if not expected:
        return 0.0

    precision = true_positives / max(true_positives + false_positives, 1)
    recall = true_positives / max(true_positives + false_negatives, 1)
    if precision == 0 or recall == 0:
        return 0.0

    beta_squared = 0.25
    f_score = (1 + beta_squared) * precision * recall / (beta_squared * precision + recall)
    return f_score
