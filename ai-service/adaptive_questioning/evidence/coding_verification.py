"""Generic server-side code verification driven by Question.coding_spec and CodeExecutionProvider."""
from __future__ import annotations

import ast
from dataclasses import dataclass
import logging
import re
import sqlite3
import sys

from .code_runner import (
    CodeExecutionProvider,
    CodingCaseResult,
    CodingSpec,
    ExecutionResult,
    SupportedLanguage,
    default_code_runner,
    extract_code_snippet,
)
from .models import CodingCheckResult, Judgment, Mode, Observation, Question, Turn
from .telemetry import event

logger = logging.getLogger(__name__)
_FENCE_SPAN = re.compile(r"^```(?:[a-zA-Z0-9_+#.-]+)?[ \t]*\n(.*?)^```[ \t]*$", re.MULTILINE | re.DOTALL)
_FORBIDDEN_SQL = re.compile(r"\b(?:ATTACH|DETACH|PRAGMA|VACUUM|LOAD_EXTENSION)\b", re.IGNORECASE)
_PY_IMPORT_RE = re.compile(r"^\s*(?:from\s+([a-zA-Z_][\w]*)|import\s+([a-zA-Z_][\w]*))", re.MULTILINE)
_JS_IMPORT_RE = re.compile(
    r"""(?:require\s*\(\s*['"]([^'"]+)['"]\s*\)|import\s+(?:[^'"]+\s+from\s+)?['"]([^'"]+)['"])"""
)
_SANDBOX_ENV_ERROR_RE = re.compile(
    r"(?:ModuleNotFoundError:\s*No module named '(?!solution')[^']+'|"
    r"Cannot find module\s+['\"]|ERR_MODULE_NOT_FOUND|"
    r"ConnectionRefusedError|ECONNREFUSED|"
    r"redis\.exceptions\.ConnectionError|ServerSelectionTimeoutError|"
    r"Temporary failure in name resolution|Name or service not known|socket\.gaierror)",
    re.IGNORECASE,
)

SANDBOX_PYTHON_CURATED_PACKAGES = frozenset({
    "redis",
    "fakeredis",
    "pymongo",
    "mongomock",
    "pydantic",
    "httpx",
    "fastapi",
    "sortedcontainers",
})
SANDBOX_PYTHON_ALLOWED_MODULES = SANDBOX_PYTHON_CURATED_PACKAGES | frozenset(sys.stdlib_module_names)
SANDBOX_NODE_BUILTINS = frozenset({
    "assert", "buffer", "crypto", "events", "fs", "http", "https", "os", "path",
    "querystring", "stream", "string_decoder", "timers", "url", "util", "zlib",
})
SANDBOX_ENV_NOTICE = (
    "Môi trường chạy thử cô lập không cài sẵn thư viện hoặc dịch vụ mạng mà đoạn mã đang dùng "
    "(hỗ trợ Python chuẩn, Redis/MongoDB giả lập trong RAM, FastAPI/Pydantic, Node.js chuẩn và SQLite). "
    "Bạn vẫn có thể bấm Gửi câu trả lời — hệ thống sẽ chấm điểm theo logic mã nguồn của bạn."
)


def _extract_python_imports(source: str) -> set[str]:
    if not source.strip():
        return set()
    try:
        tree = ast.parse(source)
        found: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    found.add(alias.name.split(".", 1)[0])
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                found.add(node.module.split(".", 1)[0])
        return found
    except SyntaxError:
        found = set()
        for m in _PY_IMPORT_RE.finditer(source):
            name = m.group(1) or m.group(2)
            if name:
                found.add(name)
        return found


def _extract_js_imports(source: str) -> set[str]:
    modules: set[str] = set()
    for match in _JS_IMPORT_RE.finditer(source):
        raw = (match.group(1) or match.group(2) or "").strip()
        if not raw or raw.startswith("."):
            continue
        cleaned = raw[5:] if raw.startswith("node:") else raw
        modules.add(cleaned.split("/", 1)[0])
    return modules


def _sqlite_setup_valid(setup_sql: str) -> bool:
    if not setup_sql.strip():
        return True
    if _FORBIDDEN_SQL.search(setup_sql):
        return False
    conn = sqlite3.connect(":memory:")
    try:
        conn.executescript(setup_sql)
        return True
    except sqlite3.Error:
        return False
    finally:
        conn.close()


def sanitize_coding_spec(question: Question) -> Question:
    """Strip coding_spec when starter_code/setup_sql relies on runtimes unsupported by the isolated sandbox."""
    spec = question.coding_spec
    if spec is None:
        return question
    reason = ""
    if spec.language == "python":
        disallowed = sorted(
            mod for mod in _extract_python_imports(spec.starter_code)
            if mod not in SANDBOX_PYTHON_ALLOWED_MODULES
        )
        if disallowed:
            reason = f"unsupported_python_imports:{','.join(disallowed[:3])}"
    elif spec.language == "javascript":
        disallowed = sorted(
            mod for mod in _extract_js_imports(spec.starter_code)
            if mod not in SANDBOX_NODE_BUILTINS
        )
        if disallowed:
            reason = f"unsupported_js_imports:{','.join(disallowed[:3])}"
    elif spec.language == "sql" and not _sqlite_setup_valid(spec.setup_sql):
        reason = "invalid_sqlite_setup_sql"

    if not reason:
        return question
    logger.info("Stripping non-runnable coding_spec (%s) for language=%s", reason, spec.language)
    event("coding_spec.stripped", language=spec.language, reason=reason)
    return question.model_copy(update={"coding_spec": None})


def is_sandbox_environment_error(outcome: ExecutionResult) -> bool:
    """Return True when execution failed due to missing third-party packages or isolated network limits."""
    if outcome.compile_error and _SANDBOX_ENV_ERROR_RE.search(outcome.compile_error):
        return True
    return any(
        (not item.passed) and bool(item.error) and bool(_SANDBOX_ENV_ERROR_RE.search(item.error))
        for item in outcome.results
    )


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
    total = outcome.total or len(all_cases)
    if outcome.passed < total and is_sandbox_environment_error(outcome):
        logger.warning(
            "Code runner hit sandbox environment limit for turn %s (language=%s); delegating to semantic judge.",
            turn.turn_id,
            outcome.language,
        )
        event("coding.sandbox_env_fallback", turn_id=turn.turn_id, language=outcome.language)
        return None
    sample_count = len(spec.sample_tests)
    return CodingCheck(
        line_range=_code_line_range(raw_source),
        language=outcome.language,
        total=total,
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
) -> ExecutionResult:
    """Dry-run candidate code against public sample_tests only (or free-run if no sample tests exist)."""
    active_runner = runner or default_code_runner()
    language: SupportedLanguage = language_override or (spec.language if spec else "python")
    entry_point = spec.entry_point if (spec and spec.language == language) else ""
    setup_sql = spec.setup_sql if (spec and spec.language == language) else ""
    cases = list(spec.sample_tests) if (spec and spec.language == language) else []
    cleaned = extract_code_snippet(code)
    result = active_runner.execute(
        language=language,
        code=cleaned,
        entry_point=entry_point,
        setup_sql=setup_sql,
        cases=cases,
    )
    if is_sandbox_environment_error(result):
        return result.model_copy(update={"environment_notice": SANDBOX_ENV_NOTICE})
    return result
