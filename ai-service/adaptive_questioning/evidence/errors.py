"""Failures of assessment infrastructure, separate from invalid candidate requests."""


class JudgmentUnavailableError(RuntimeError):
    """No valid assessment was obtained; the original snapshot must remain unchanged."""


class QuestionUnavailableError(RuntimeError):
    """Generation failed after retries; preserve the stored session and allow retry."""
