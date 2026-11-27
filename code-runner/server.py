"""Isolated HTTP sandbox service executing bounded Python, JavaScript, and SQL snippets."""
from __future__ import annotations

import json
import os
import re
import shutil
import sqlite3
import subprocess
import sys
import tempfile
from time import perf_counter
from typing import Literal

from fastapi import FastAPI
from pydantic import BaseModel, Field

from sandbox_shims import active_shims

APP_DIR = os.path.dirname(os.path.abspath(__file__))
MAX_CODE_CHARS = 16000
MAX_OUTPUT_CHARS = 8192
DEFAULT_TIMEOUT_SECONDS = 3.0
MAX_TIMEOUT_SECONDS = 5.0
_FORBIDDEN_SQL = re.compile(r"\b(?:ATTACH|DETACH|PRAGMA|VACUUM|LOAD_EXTENSION)\b", re.IGNORECASE)

app = FastAPI(title="Smile Code Runner", version="1.0.0")


class TestCaseInput(BaseModel):
    name: str = Field(default="case", min_length=1, max_length=80)
    input_data: str = Field(default="", max_length=4000)
    expected_output: str = Field(default="", max_length=4000)


class ExecuteRequest(BaseModel):
    language: Literal["python", "javascript", "sql"]
    code: str = Field(min_length=1, max_length=MAX_CODE_CHARS)
    entry_point: str = Field(default="", max_length=80)
    setup_sql: str = Field(default="", max_length=8000)
    cases: list[TestCaseInput] = Field(default_factory=list, max_length=10)
    timeout_seconds: float = Field(default=DEFAULT_TIMEOUT_SECONDS, gt=0.1, le=MAX_TIMEOUT_SECONDS)


class CaseResult(BaseModel):
    name: str
    passed: bool
    actual_output: str = ""
    expected_output: str = ""
    error: str = ""
    elapsed_ms: int = 0


class ExecuteResponse(BaseModel):
    language: Literal["python", "javascript", "sql"]
    passed: int = 0
    total: int = 0
    compile_error: str = ""
    stdout: str = ""
    results: list[CaseResult] = Field(default_factory=list)


def _clip(text: str) -> str:
    return text[:MAX_OUTPUT_CHARS]


def _normalize_compare(actual: str, expected: str) -> bool:
    a_clean = actual.strip()
    e_clean = expected.strip()
    if a_clean == e_clean:
        return True
    try:
        return json.loads(a_clean) == json.loads(e_clean)
    except (ValueError, TypeError):
        return False


def _sandbox_env() -> dict[str, str]:
    path = os.environ.get("PATH", "/usr/local/bin:/usr/bin:/bin")
    env = {"PATH": path, "PYTHONDONTWRITEBYTECODE": "1", "PYTHONIOENCODING": "utf-8"}
    if os.name == "nt" and "SYSTEMROOT" in os.environ:
        env["SYSTEMROOT"] = os.environ["SYSTEMROOT"]
    return env


def _run_subprocess(cmd: list[str], cwd: str, stdin_text: str, timeout: float) -> tuple[int, str, str, int]:
    started = perf_counter()
    try:
        completed = subprocess.run(
            cmd,
            input=stdin_text,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            cwd=cwd,
            env=_sandbox_env(),
            timeout=timeout,
            check=False,
        )
        elapsed = int((perf_counter() - started) * 1000)
        return completed.returncode, _clip(completed.stdout), _clip(completed.stderr), elapsed
    except subprocess.TimeoutExpired:
        elapsed = int((perf_counter() - started) * 1000)
        return -1, "", f"Hết thời gian thực thi ({timeout:.1f}s).", elapsed


def _python_harness(entry_point: str, tmpdir: str) -> str:
    return (
        "import sys\n"
        f"_app_dir = {APP_DIR!r}\n"
        f"_tmp_dir = {tmpdir!r}\n"
        "sys.path.insert(0, _app_dir)\n"
        "from sandbox_shims import install_shims, invoke_entry_point, resolve_entry_point\n"
        "install_shims()\n"
        "sys.path = [p for p in sys.path if p != _app_dir]\n"
        "sys.path.insert(0, _tmp_dir)\n"
        "import solution\n"
        f"fn, err = resolve_entry_point(solution, {entry_point!r})\n"
        "if not callable(fn):\n"
        "    sys.stderr.write(err)\n"
        "    sys.exit(2)\n"
        "sys.stdout.write(invoke_entry_point(fn, sys.stdin.read()))\n"
    )


def _python_free_runner(sol_path: str, tmpdir: str) -> str:
    return (
        "import runpy, sys\n"
        f"_app_dir = {APP_DIR!r}\n"
        f"_tmp_dir = {tmpdir!r}\n"
        "sys.path.insert(0, _app_dir)\n"
        "from sandbox_shims import install_shims\n"
        "install_shims()\n"
        "sys.path = [p for p in sys.path if p != _app_dir]\n"
        "sys.path.insert(0, _tmp_dir)\n"
        f"runpy.run_path({sol_path!r}, run_name='__main__')\n"
    )


def _node_harness(entry_point: str) -> str:
    return (
        "const fs = require('fs');\n"
        "const mod = require('./solution.js');\n"
        f"const name = {json.dumps(entry_point)};\n"
        "let fn = typeof mod === 'function' ? mod : (mod && mod[name]);\n"
        "if (typeof fn !== 'function' && mod && typeof mod === 'object') {\n"
        "  const fns = Object.keys(mod).filter(k => typeof mod[k] === 'function');\n"
        "  if (fns.length === 1) fn = mod[fns[0]];\n"
        "}\n"
        "if (typeof fn !== 'function') {\n"
        "  process.stderr.write('Không tìm thấy hàm ' + name);\n"
        "  process.exit(2);\n"
        "}\n"
        "const raw = fs.readFileSync(0, 'utf8');\n"
        "let arg;\n"
        "if (raw.trim()) {\n"
        "  try { arg = JSON.parse(raw); } catch { arg = raw.trim(); }\n"
        "}\n"
        "let out;\n"
        "if (fn.length === 0) out = fn();\n"
        "else if (fn.length === 1) out = fn(arg);\n"
        "else if (Array.isArray(arg) && arg.length === fn.length) out = fn(...arg);\n"
        "else out = fn(arg);\n"
        "process.stdout.write(JSON.stringify(out));\n"
    )


def _execute_python(req: ExecuteRequest) -> ExecuteResponse:
    with tempfile.TemporaryDirectory(prefix="smile-py-") as tmpdir:
        sol_path = os.path.join(tmpdir, "solution.py")
        with open(sol_path, "w", encoding="utf-8") as handle:
            handle.write(req.code)
        syntax = _run_subprocess([sys.executable, "-m", "py_compile", sol_path], tmpdir, "", req.timeout_seconds)
        if syntax[0] != 0:
            return ExecuteResponse(language="python", total=len(req.cases), compile_error=syntax[2] or "Lỗi cú pháp Python")
        if not req.cases:
            free_path = os.path.join(tmpdir, "run_free.py")
            with open(free_path, "w", encoding="utf-8") as handle:
                handle.write(_python_free_runner(sol_path, tmpdir))
            rc, out, err, _ = _run_subprocess([sys.executable, "-I", free_path], tmpdir, "", req.timeout_seconds)
            return ExecuteResponse(language="python", compile_error=err if rc != 0 else "", stdout=out)
        if req.entry_point:
            harness_path = os.path.join(tmpdir, "harness.py")
            with open(harness_path, "w", encoding="utf-8") as handle:
                handle.write(_python_harness(req.entry_point, tmpdir))
            cmd = [sys.executable, "-I", harness_path]
        else:
            free_path = os.path.join(tmpdir, "run_free.py")
            with open(free_path, "w", encoding="utf-8") as handle:
                handle.write(_python_free_runner(sol_path, tmpdir))
            cmd = [sys.executable, "-I", free_path]
        results = _run_cases(cmd, tmpdir, req.cases, req.timeout_seconds)
        passed = sum(1 for item in results if item.passed)
        return ExecuteResponse(language="python", passed=passed, total=len(results), results=results)


def _execute_javascript(req: ExecuteRequest) -> ExecuteResponse:
    node_bin = shutil.which("node")
    if not node_bin:
        return ExecuteResponse(language="javascript", total=len(req.cases), compile_error="Node.js runtime không khả dụng.")
    with tempfile.TemporaryDirectory(prefix="smile-js-") as tmpdir:
        sol_path = os.path.join(tmpdir, "solution.js")
        source = req.code
        if req.entry_point and "module.exports" not in source:
            source = f"{source}\n;if (typeof {req.entry_point} === 'function') module.exports = {{ {req.entry_point} }};\n"
        with open(sol_path, "w", encoding="utf-8") as handle:
            handle.write(source)
        check = _run_subprocess([node_bin, "--check", sol_path], tmpdir, "", req.timeout_seconds)
        if check[0] != 0:
            return ExecuteResponse(language="javascript", total=len(req.cases), compile_error=check[2] or "Lỗi cú pháp JavaScript")
        if not req.cases:
            rc, out, err, _ = _run_subprocess([node_bin, sol_path], tmpdir, "", req.timeout_seconds)
            return ExecuteResponse(language="javascript", compile_error=err if rc != 0 else "", stdout=out)
        if req.entry_point:
            harness_path = os.path.join(tmpdir, "harness.js")
            with open(harness_path, "w", encoding="utf-8") as handle:
                handle.write(_node_harness(req.entry_point))
            cmd = [node_bin, harness_path]
        else:
            cmd = [node_bin, sol_path]
        results = _run_cases(cmd, tmpdir, req.cases, req.timeout_seconds)
        passed = sum(1 for item in results if item.passed)
        return ExecuteResponse(language="javascript", passed=passed, total=len(results), results=results)


def _run_cases(cmd: list[str], cwd: str, cases: list[TestCaseInput], timeout: float) -> list[CaseResult]:
    results: list[CaseResult] = []
    for case in cases:
        rc, out, err, elapsed = _run_subprocess(cmd, cwd, case.input_data, timeout)
        if rc != 0:
            results.append(CaseResult(
                name=case.name, passed=False, actual_output=out.strip(),
                expected_output=case.expected_output.strip(), error=err.strip() or f"Exit code {rc}", elapsed_ms=elapsed,
            ))
        else:
            ok = _normalize_compare(out, case.expected_output)
            results.append(CaseResult(
                name=case.name, passed=ok, actual_output=out.strip(),
                expected_output=case.expected_output.strip(), elapsed_ms=elapsed,
            ))
    return results


def _run_sql_once(setup_sql: str, extra_sql: str, candidate_sql: str) -> tuple[str, str]:
    if _FORBIDDEN_SQL.search(candidate_sql):
        return "", "Câu lệnh SQL chứa từ khóa không được phép trong sandbox."
    conn = sqlite3.connect(":memory:")
    try:
        if setup_sql.strip():
            conn.executescript(setup_sql)
        if extra_sql.strip():
            conn.executescript(extra_sql)
        cursor = conn.execute(candidate_sql)
        rows = [list(row) for row in cursor.fetchall()] if cursor.description else []
        return _clip(json.dumps(rows, ensure_ascii=False)), ""
    except sqlite3.Error as exc:
        return "", str(exc)
    finally:
        conn.close()


def _execute_sql(req: ExecuteRequest) -> ExecuteResponse:
    if not req.cases:
        out, err = _run_sql_once(req.setup_sql, "", req.code)
        return ExecuteResponse(language="sql", compile_error=err, stdout=out)
    results: list[CaseResult] = []
    for case in req.cases:
        started = perf_counter()
        out, err = _run_sql_once(req.setup_sql, case.input_data, req.code)
        elapsed = int((perf_counter() - started) * 1000)
        ok = (not err) and _normalize_compare(out, case.expected_output)
        results.append(CaseResult(
            name=case.name, passed=ok, actual_output=out,
            expected_output=case.expected_output.strip(), error=err, elapsed_ms=elapsed,
        ))
    passed = sum(1 for item in results if item.passed)
    return ExecuteResponse(language="sql", passed=passed, total=len(results), results=results)


@app.get("/health")
def health():
    return {"status": "ok", "languages": ["python", "javascript", "sql"], "shims": active_shims()}


@app.post("/execute", response_model=ExecuteResponse)
def execute(request: ExecuteRequest) -> ExecuteResponse:
    if request.language == "python":
        return _execute_python(request)
    if request.language == "javascript":
        return _execute_javascript(request)
    return _execute_sql(request)
