"""Generic server-side code verification driven by Question.coding_spec and CodeExecutionProvider."""
from __future__ import annotations

from dataclasses import dataclass
import logging
import re

from .code_runner import (
    CodeExecutionProvider,
    CodingCaseResult,
    CodingSpec,
    SupportedLanguage,
    default_code_runner,
    extract_code_snippet,
)
from .models import CodingCheckResult, Judgment, Mode, Observation, Turn

logger = logging.getLogger(__name__)
_FENCE_SPAN = re.compile(r"^```(?:[a-zA-Z0-9_+#.-]+)?[ \t]*\n(.*?)^```[ \t]*$", re.MULTILINE | re.DOTALL)


@dataclass(frozen=True)
class CodingCheck:
    line_range: tuple[int, int]
    language: str
    total: int
    passed: int
    compile_error: str = ""
    sample_results: tuple[CodingCaseResult, ...] = ()

    def to_result(self) -> CodingCheckResult:
        return CodingCheckResult(
            passed=self.passed,
            total=self.total,
            language=self.language,
            compile_error=self.compile_error,
            sample_results=list(self.sample_results),
        )

    def failure_judgment(self, turn: Turn) -> Judgment:
        if self.compile_error:
            detail = f"Mã nguồn {self.language} bị lỗi biên dịch/thực thi: {self.compile_error[:240]}"
        else:
            failed_count = self.total - self.passed
            first_fail = next((item for item in self.sample_results if not item.passed), None)
            hint = ""
            if first_fail and first_fail.error:
                hint = f" Lỗi ở ca `{first_fail.name}`: {first_fail.error[:180]}."
            elif first_fail:
                hint = (
                    f" Ở ca `{first_fail.name}`, kết quả thực tế là `{first_fail.actual_output[:100]}` "
                    f"khác kỳ vọng `{first_fail.expected_output[:100]}`."
                )
            detail = f"Mã nguồn chưa đạt {failed_count}/{self.total} ca kiểm thử tự động.{hint}"
        return Judgment(
            feedback="",
            observations=[Observation(
                criterion_id=turn.question.criterion_ids[0],
                response_line_range=self.line_range,
                observation="CONTRADICTS",
                performance="BELOW",
                rationale=detail,
            )],
        )


def _code_line_range(answer: str) -> tuple[int, int]:
    normalized = answer.replace("\r\n", "\n").replace("\r", "\n")
    blocks = list(_FENCE_SPAN.finditer(normalized))
    if len(blocks) == 1:
        start_line = normalized.count("\n", 0, blocks[0].start(1)) + 1
        body_lines = max(1, len(blocks[0].group(1).rstrip("\n").splitlines()))
        return (start_line, start_line + body_lines - 1)
    extracted = extract_code_snippet(normalized)
    lines = extracted.splitlines()
    non_empty = [idx for idx, line in enumerate(lines, start=1) if line.strip()]
    if not non_empty:
        return (1, 1)
    return (non_empty[0], non_empty[-1])


def check_coding_answer(
    turn: Turn,
    interaction_mode: str,
    runner: CodeExecutionProvider | None = None,
) -> CodingCheck | None:
    """Execute generic test cases from Turn.question.coding_spec via the configured sandbox runner."""
    spec: CodingSpec | None = turn.question.coding_spec
    if spec is None or len(turn.question.criterion_ids) != 1:
        return None
    if interaction_mode != "TEXT" and not turn.submitted_code:
        return None
    if turn.mode not in {Mode.CODING, Mode.DEBUGGING} and not turn.question.requires_code:
        return None
    all_cases = [*spec.sample_tests, *spec.hidden_tests]
    if not all_cases:
        return None
    raw_source = turn.submitted_code if turn.submitted_code else (turn.answer or "")
    code = extract_code_snippet(raw_source).strip()
    if not code:
        return None
    active_runner = runner or default_code_runner()
    try:
        outcome = active_runner.execute(
            language=spec.language,
            code=code,
            entry_point=spec.entry_point,
            setup_sql=spec.setup_sql,
            cases=all_cases,
        )
    except Exception as exc:
        logger.warning("Code runner execution failed for turn %s (%s): %s", turn.turn_id, type(exc).__name__, exc)
        return None
    sample_count = len(spec.sample_tests)
    return CodingCheck(
        line_range=_code_line_range(raw_source),
        language=outcome.language,
        total=outcome.total or len(all_cases),
        passed=outcome.passed,
        compile_error=outcome.compile_error,
        sample_results=tuple(outcome.results[:sample_count]),
    )


def run_sample_code(
    *,
    code: str,
    spec: CodingSpec | None,
    language_override: SupportedLanguage | None = None,
    runner: CodeExecutionProvider | None = None,
):
    """Dry-run candidate code against public sample_tests only (or free-run if no sample tests exist)."""
    active_runner = runner or default_code_runner()
    language: SupportedLanguage = language_override or (spec.language if spec else "python")
    entry_point = spec.entry_point if (spec and spec.language == language) else ""
    setup_sql = spec.setup_sql if (spec and spec.language == language) else ""
    cases = list(spec.sample_tests) if (spec and spec.language == language) else []
    cleaned = extract_code_snippet(code)
    return active_runner.execute(
        language=language,
        code=cleaned,
        entry_point=entry_point,
        setup_sql=setup_sql,
        cases=cases,
    )
