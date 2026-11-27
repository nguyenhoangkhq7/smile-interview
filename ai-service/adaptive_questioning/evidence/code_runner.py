"""Pluggable code execution abstraction supporting isolated HTTP runner and local subprocess fallback."""
from __future__ import annotations

import json
import logging
import os
import re
import shutil
import sqlite3
import subprocess
import sys
import tempfile
from time import perf_counter
from typing import Literal, Protocol

import httpx
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

SupportedLanguage = Literal["python", "javascript", "sql"]
DEFAULT_TIMEOUT_SECONDS = 3.0
MAX_OUTPUT_CHARS = 8192
_FORBIDDEN_SQL = re.compile(r"\b(?:ATTACH|DETACH|PRAGMA|VACUUM|LOAD_EXTENSION)\b", re.IGNORECASE)
_CODE_FENCE = re.compile(r"^```(?:[a-zA-Z0-9_+#.-]+)?[ \t]*\n(.*?)^```[ \t]*$", re.MULTILINE | re.DOTALL)
_TRAILING_PROSE = re.compile(r"(?m)^\s*\n(?:Em|Tôi|Mình|I|This)\s+[^\n]+")


class CodingTestCase(BaseModel):
    name: str = Field(default="case", min_length=1, max_length=80)
    input_data: str = Field(default="", max_length=4000)
    expected_output: str = Field(default="", max_length=4000)


class PublicCodingSpec(BaseModel):
    language: SupportedLanguage = "python"
    entry_point: str = Field(default="", max_length=80)
    starter_code: str = Field(default="", max_length=4000)
    setup_sql: str = Field(default="", max_length=8000)
    sample_tests: list[CodingTestCase] = Field(default_factory=list, max_length=3)


class CodingSpec(PublicCodingSpec):
    hidden_tests: list[CodingTestCase] = Field(default_factory=list, max_length=5)

    def to_public(self) -> PublicCodingSpec:
        return PublicCodingSpec(
            language=self.language,
            entry_point=self.entry_point,
            starter_code=self.starter_code,
            setup_sql=self.setup_sql,
            sample_tests=list(self.sample_tests),
        )


class CodingCaseResult(BaseModel):
    name: str
    passed: bool
    actual_output: str = ""
    expected_output: str = ""
    error: str = ""
    elapsed_ms: int = 0


class ExecutionResult(BaseModel):
    language: SupportedLanguage
    passed: int = 0
    total: int = 0
    compile_error: str = ""
    stdout: str = ""
    results: list[CodingCaseResult] = Field(default_factory=list)
    environment_notice: str = ""


class CodeExecutionProvider(Protocol):
    def execute(
        self,
        *,
        language: SupportedLanguage,
        code: str,
        entry_point: str = "",
        setup_sql: str = "",
        cases: list[CodingTestCase] | None = None,
        timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    ) -> ExecutionResult: ...


def extract_code_snippet(raw: str) -> str:
    """Strip fenced markdown blocks or trailing plain-text explanation paragraphs."""
    normalized = raw.replace("\r\n", "\n").replace("\r", "\n")
    blocks = list(_CODE_FENCE.finditer(normalized))
    if len(blocks) == 1:
        return blocks[0].group(1)
    prose = _TRAILING_PROSE.search(normalized)
    if prose and not re.search(r"(?m)^(?:def |function |class |SELECT |```)", normalized[prose.end():], re.IGNORECASE):
        return normalized[:prose.start()]
    return normalized


class HttpCodeRunner:
    """Calls the dedicated isolated code-runner microservice over the internal Docker network."""

    def __init__(self, base_url: str, api_key: str = "", timeout: float = 12.0):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout

    def execute(
        self,
        *,
        language: SupportedLanguage,
        code: str,
        entry_point: str = "",
        setup_sql: str = "",
        cases: list[CodingTestCase] | None = None,
        timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    ) -> ExecutionResult:
        headers = {"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}
        payload = {
            "language": language,
            "code": code,
            "entry_point": entry_point,
            "setup_sql": setup_sql,
            "cases": [c.model_dump(mode="json") for c in (cases or [])],
            "timeout_seconds": timeout_seconds,
        }
        response = httpx.post(
            f"{self.base_url}/execute", json=payload, headers=headers, timeout=self.timeout,
        )
        response.raise_for_status()
        return ExecutionResult.model_validate(response.json())


def _normalize_compare(actual: str, expected: str) -> bool:
    a_clean, e_clean = actual.strip(), expected.strip()
    if a_clean == e_clean:
        return True
    try:
        return json.loads(a_clean) == json.loads(e_clean)
    except (ValueError, TypeError):
        return False


def _sandbox_env() -> dict[str, str]:
    env = {
        "PATH": os.environ.get("PATH", "/usr/local/bin:/usr/bin:/bin"),
        "PYTHONDONTWRITEBYTECODE": "1",
        "PYTHONIOENCODING": "utf-8",
    }
    if os.name == "nt" and "SYSTEMROOT" in os.environ:
        env["SYSTEMROOT"] = os.environ["SYSTEMROOT"]
    return env


def _run_subprocess(cmd: list[str], cwd: str, stdin_text: str, timeout: float) -> tuple[int, str, str, int]:
    started = perf_counter()
    try:
        completed = subprocess.run(
            cmd, input=stdin_text, capture_output=True, text=True, encoding="utf-8",
            errors="replace", cwd=cwd, env=_sandbox_env(), timeout=timeout, check=False,
        )
        elapsed = int((perf_counter() - started) * 1000)
        return completed.returncode, completed.stdout[:MAX_OUTPUT_CHARS], completed.stderr[:MAX_OUTPUT_CHARS], elapsed
    except subprocess.TimeoutExpired:
        return -1, "", f"Hết thời gian thực thi ({timeout:.1f}s).", int((perf_counter() - started) * 1000)


_OPTIONAL_SHIM_PRELUDE = """
try:
    import fakeredis as _fr, redis as _r, redis.client as _rc
    _srv = _fr.FakeServer()
    _orig_init = _r.Redis.__init__
    class _SR:
        __init__ = _orig_init
        def __new__(cls, *a, **kw):
            return _fr.FakeRedis(server=_srv, db=int(kw.get('db', 0) or 0), decode_responses=bool(kw.get('decode_responses', False)))
        @classmethod
        def from_url(cls, url, **kw):
            return _fr.FakeRedis(server=_srv, db=int(kw.get('db', 0) or 0), decode_responses=bool(kw.get('decode_responses', False)))
    _r.Redis = _r.StrictRedis = _rc.Redis = _rc.StrictRedis = _SR
    _r.from_url = _SR.from_url
except Exception:
    pass
try:
    import mongomock as _mm, pymongo as _pm
    _mc = _mm.MongoClient()
    class _SM:
        def __new__(cls, *a, **kw):
            return _mc
    _pm.MongoClient = _SM
except Exception:
    pass
"""


def _python_harness(entry_point: str) -> str:
    return (
        "import inspect, json, sys\n"
        + _OPTIONAL_SHIM_PRELUDE
        + "import solution\n"
        f"_ep = {entry_point!r}\n"
        "fn = getattr(solution, _ep, None)\n"
        "if not callable(fn):\n"
        "    _cands = [f for n, f in inspect.getmembers(solution, inspect.isfunction) if getattr(f, '__module__', None) == 'solution' and not n.startswith('_')]\n"
        "    if len(_cands) == 1: fn = _cands[0]\n"
        "    elif len(_cands) > 1: sys.stderr.write(f\"Không tìm thấy hàm '{_ep}' (đang có các hàm: {', '.join(f.__name__ for f in _cands[:5])}).\"); sys.exit(2)\n"
        "    else: sys.stderr.write(f\"Không tìm thấy hàm '{_ep}'.\"); sys.exit(2)\n"
        "raw = sys.stdin.read().strip()\n"
        "if raw:\n"
        "    try: arg = json.loads(raw)\n"
        "    except ValueError: arg = raw\n"
        "else:\n"
        "    arg = None\n"
        "sig = inspect.signature(fn)\n"
        "params = [p for p in sig.parameters.values() if p.kind in (p.POSITIONAL_ONLY, p.POSITIONAL_OR_KEYWORD)]\n"
        "kw_names = {p.name for p in sig.parameters.values() if p.kind in (p.POSITIONAL_OR_KEYWORD, p.KEYWORD_ONLY)}\n"
        "req_pos = [p for p in params if p.default is inspect.Parameter.empty]\n"
        "req_kw = {p.name for p in sig.parameters.values() if p.kind in (p.POSITIONAL_OR_KEYWORD, p.KEYWORD_ONLY) and p.default is inspect.Parameter.empty}\n"
        "has_kwonly = any(p.kind == p.KEYWORD_ONLY for p in sig.parameters.values())\n"
        "has_varkw = any(p.kind == p.VAR_KEYWORD for p in sig.parameters.values())\n"
        "if len(params) == 0 and not kw_names and not has_varkw: out = fn()\n"
        "elif isinstance(arg, dict) and (len(params) > 1 or has_kwonly or (len(params) == 0 and has_varkw)) and (has_varkw or set(arg.keys()).issubset(kw_names)) and req_kw.issubset(arg.keys()): out = fn(**arg)\n"
        "elif len(params) == 1: out = fn(arg)\n"
        "elif isinstance(arg, list) and len(req_pos) <= len(arg) <= len(params): out = fn(*arg)\n"
        "else: out = fn(arg)\n"
        "def _norm(v):\n"
        "    if isinstance(v, bytes): return v.decode('utf-8', errors='replace')\n"
        "    if isinstance(v, (tuple, set, list)): return [_norm(x) for x in v]\n"
        "    if isinstance(v, dict): return {(k.decode('utf-8', errors='replace') if isinstance(k, bytes) else k): _norm(val) for k, val in v.items()}\n"
        "    return v\n"
        "sys.stdout.write(json.dumps(_norm(out), ensure_ascii=False, default=str))\n"
    )


def _node_harness(entry_point: str) -> str:
    return (
        "const fs = require('fs');\nconst mod = require('./solution.js');\n"
        f"const name = {json.dumps(entry_point)};\n"
        "const fn = typeof mod === 'function' ? mod : (mod && mod[name]);\n"
        "if (typeof fn !== 'function') { process.stderr.write('Không tìm thấy hàm ' + name); process.exit(2); }\n"
        "const raw = fs.readFileSync(0, 'utf8');\n"
        "let arg;\n"
        "if (raw.trim()) { try { arg = JSON.parse(raw); } catch { arg = raw.trim(); } }\n"
        "let out;\n"
        "if (fn.length === 0) out = fn();\n"
        "else if (fn.length === 1) out = fn(arg);\n"
        "else if (Array.isArray(arg) && arg.length === fn.length) out = fn(...arg);\n"
        "else out = fn(arg);\n"
        "process.stdout.write(JSON.stringify(out));\n"
    )


class LocalSubprocessCodeRunner:
    """Dev/test fallback running Python, Node.js, and in-memory SQLite with strict timeouts."""

    def execute(
        self,
        *,
        language: SupportedLanguage,
        code: str,
        entry_point: str = "",
        setup_sql: str = "",
        cases: list[CodingTestCase] | None = None,
        timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    ) -> ExecutionResult:
        test_cases = cases or []
        if language == "sql":
            return self._execute_sql(code, setup_sql, test_cases)
        if language == "javascript":
            return self._execute_js(code, entry_point, test_cases, timeout_seconds)
        return self._execute_python(code, entry_point, test_cases, timeout_seconds)

    def _execute_python(
        self, code: str, entry_point: str, cases: list[CodingTestCase], timeout: float,
    ) -> ExecutionResult:
        with tempfile.TemporaryDirectory(prefix="smile-py-") as tmpdir:
            sol_path = os.path.join(tmpdir, "solution.py")
            with open(sol_path, "w", encoding="utf-8") as handle:
                handle.write(code)
            syntax = _run_subprocess([sys.executable, "-m", "py_compile", sol_path], tmpdir, "", timeout)
            if syntax[0] != 0:
                return ExecutionResult(language="python", total=len(cases), compile_error=syntax[2] or "Lỗi cú pháp Python")
            if not cases:
                rc, out, err, _ = _run_subprocess([sys.executable, "-I", sol_path], tmpdir, "", timeout)
                return ExecutionResult(language="python", compile_error=err if rc != 0 else "", stdout=out)
            if entry_point:
                harness = os.path.join(tmpdir, "harness.py")
                with open(harness, "w", encoding="utf-8") as handle:
                    handle.write(_python_harness(entry_point))
                cmd = [sys.executable, harness]
            else:
                cmd = [sys.executable, "-I", sol_path]
            results = self._run_cases(cmd, tmpdir, cases, timeout)
            return ExecutionResult(language="python", passed=sum(r.passed for r in results), total=len(results), results=results)

    def _execute_js(
        self, code: str, entry_point: str, cases: list[CodingTestCase], timeout: float,
    ) -> ExecutionResult:
        node_bin = shutil.which("node")
        if not node_bin:
            return ExecutionResult(language="javascript", total=len(cases), compile_error="Node.js runtime không khả dụng.")
        with tempfile.TemporaryDirectory(prefix="smile-js-") as tmpdir:
            sol_path = os.path.join(tmpdir, "solution.js")
            source = code
            if entry_point and "module.exports" not in source:
                source = f"{source}\n;if (typeof {entry_point} === 'function') module.exports = {{ {entry_point} }};\n"
            with open(sol_path, "w", encoding="utf-8") as handle:
                handle.write(source)
            check = _run_subprocess([node_bin, "--check", sol_path], tmpdir, "", timeout)
            if check[0] != 0:
                return ExecutionResult(language="javascript", total=len(cases), compile_error=check[2] or "Lỗi cú pháp JavaScript")
            if not cases:
                rc, out, err, _ = _run_subprocess([node_bin, sol_path], tmpdir, "", timeout)
                return ExecutionResult(language="javascript", compile_error=err if rc != 0 else "", stdout=out)
            if entry_point:
                harness = os.path.join(tmpdir, "harness.js")
                with open(harness, "w", encoding="utf-8") as handle:
                    handle.write(_node_harness(entry_point))
                cmd = [node_bin, harness]
            else:
                cmd = [node_bin, sol_path]
            results = self._run_cases(cmd, tmpdir, cases, timeout)
            return ExecutionResult(language="javascript", passed=sum(r.passed for r in results), total=len(results), results=results)

    @staticmethod
    def _run_cases(cmd: list[str], cwd: str, cases: list[CodingTestCase], timeout: float) -> list[CodingCaseResult]:
        results: list[CodingCaseResult] = []
        for case in cases:
            rc, out, err, elapsed = _run_subprocess(cmd, cwd, case.input_data, timeout)
            if rc != 0:
                results.append(CodingCaseResult(
                    name=case.name, passed=False, actual_output=out.strip(),
                    expected_output=case.expected_output.strip(), error=err.strip() or f"Exit code {rc}", elapsed_ms=elapsed,
                ))
            else:
                results.append(CodingCaseResult(
                    name=case.name, passed=_normalize_compare(out, case.expected_output),
                    actual_output=out.strip(), expected_output=case.expected_output.strip(), elapsed_ms=elapsed,
                ))
        return results

    @staticmethod
    def _execute_sql(code: str, setup_sql: str, cases: list[CodingTestCase]) -> ExecutionResult:
        def run_one(extra_sql: str) -> tuple[str, str]:
            if _FORBIDDEN_SQL.search(code):
                return "", "Câu lệnh SQL chứa từ khóa không được phép trong sandbox."
            conn = sqlite3.connect(":memory:")
            try:
                if setup_sql.strip():
                    conn.executescript(setup_sql)
                if extra_sql.strip():
                    conn.executescript(extra_sql)
                cursor = conn.execute(code)
                rows = [list(row) for row in cursor.fetchall()] if cursor.description else []
                return json.dumps(rows, ensure_ascii=False)[:MAX_OUTPUT_CHARS], ""
            except sqlite3.Error as exc:
                return "", str(exc)
            finally:
                conn.close()

        if not cases:
            out, err = run_one("")
            return ExecutionResult(language="sql", compile_error=err, stdout=out)
        results: list[CodingCaseResult] = []
        for case in cases:
            started = perf_counter()
            out, err = run_one(case.input_data)
            elapsed = int((perf_counter() - started) * 1000)
            results.append(CodingCaseResult(
                name=case.name, passed=(not err) and _normalize_compare(out, case.expected_output),
                actual_output=out, expected_output=case.expected_output.strip(), error=err, elapsed_ms=elapsed,
            ))
        return ExecutionResult(language="sql", passed=sum(r.passed for r in results), total=len(results), results=results)


def default_code_runner() -> CodeExecutionProvider:
    url = os.environ.get("CODE_RUNNER_URL", "").strip()
    if url:
        return HttpCodeRunner(url, api_key=os.environ.get("CODE_RUNNER_API_KEY", "").strip())
    return LocalSubprocessCodeRunner()
