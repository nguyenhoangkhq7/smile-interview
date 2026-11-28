"""Isolated HTTP sandbox service executing bounded Python, JavaScript, and SQL snippets."""
from __future__ import annotations

from collections import Counter
import json
import math
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
_SQL_ORDER_BY = re.compile(r"\border\s+by\b", re.IGNORECASE)
_SQL_LINE_COMMENT = re.compile(r"--[^\n]*")
_SQL_BLOCK_COMMENT = re.compile(r"/\*[\s\S]*?\*/")

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


def _values_equal(a: object, b: object) -> bool:
    if isinstance(a, bool) or isinstance(b, bool):
        return isinstance(a, bool) and isinstance(b, bool) and a == b
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        return math.isclose(float(a), float(b), rel_tol=1e-6, abs_tol=1e-9)
    if isinstance(a, list) and isinstance(b, list):
        return len(a) == len(b) and all(_values_equal(x, y) for x, y in zip(a, b))
    if isinstance(a, dict) and isinstance(b, dict):
        return a.keys() == b.keys() and all(_values_equal(a[k], b[k]) for k in a)
    return a == b


def _unordered_rows_equal(actual_rows: list[object], expected_rows: list[object]) -> bool:
    if len(actual_rows) != len(expected_rows):
        return False
    if len(actual_rows) > 200:
        a_counts = Counter(json.dumps(r, sort_keys=True, ensure_ascii=False) for r in actual_rows)
        e_counts = Counter(json.dumps(r, sort_keys=True, ensure_ascii=False) for r in expected_rows)
        return a_counts == e_counts
    used = [False] * len(actual_rows)
    for exp in expected_rows:
        matched = False
        for idx, act in enumerate(actual_rows):
            if not used[idx] and _values_equal(act, exp):
                used[idx] = True
                matched = True
                break
        if not matched:
            return False
    return True


def _normalize_compare(actual: str, expected: str, *, unordered_rows: bool = False) -> bool:
    a_clean = actual.strip()
    e_clean = expected.strip()
    if a_clean == e_clean:
        return True
    try:
        a_val = json.loads(a_clean)
        e_val = json.loads(e_clean)
    except (ValueError, TypeError):
        return False
    if _values_equal(a_val, e_val):
        return True
    if unordered_rows and isinstance(a_val, list) and isinstance(e_val, list):
        return _unordered_rows_equal(a_val, e_val)
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
        "function parseParams(target) {\n"
        "  const src = Function.prototype.toString.call(target)\n"
        "    .replace(/\\/\\*[\\s\\S]*?\\*\\//g, '')\n"
        "    .replace(/\\/\\/[^\\n]*/g, '')\n"
        "    .trim();\n"
        "  const singleArrow = /^(?:async\\s+)?([A-Za-z_$][\\w$]*)\\s*=>/.exec(src);\n"
        "  if (singleArrow) {\n"
        "    return { names: [singleArrow[1]], requiredNames: [singleArrow[1]], requiredCount: 1, destructured: false, hasRest: false };\n"
        "  }\n"
        "  const start = src.indexOf('(');\n"
        "  if (start === -1) return { names: [], requiredNames: [], requiredCount: target.length, destructured: false, hasRest: false };\n"
        "  let depth = 0, quote = '', escaped = false, end = -1;\n"
        "  for (let i = start; i < src.length; i++) {\n"
        "    const ch = src[i];\n"
        "    if (quote) {\n"
        "      if (escaped) escaped = false;\n"
        "      else if (ch === '\\\\') escaped = true;\n"
        "      else if (ch === quote) quote = '';\n"
        "      continue;\n"
        "    }\n"
        "    if (ch === '\\'' || ch === '\"' || ch === '`') { quote = ch; continue; }\n"
        "    if (ch === '(' || ch === '[' || ch === '{') depth++;\n"
        "    else if (ch === ')' || ch === ']' || ch === '}') {\n"
        "      depth--;\n"
        "      if (depth === 0 && ch === ')') { end = i; break; }\n"
        "    }\n"
        "  }\n"
        "  if (end === -1) return { names: [], requiredNames: [], requiredCount: target.length, destructured: false, hasRest: false };\n"
        "  const body = src.slice(start + 1, end).trim();\n"
        "  if (!body) return { names: [], requiredNames: [], requiredCount: 0, destructured: false, hasRest: false };\n"
        "  const parts = [];\n"
        "  let cur = '', d = 0; quote = ''; escaped = false;\n"
        "  for (let i = 0; i < body.length; i++) {\n"
        "    const ch = body[i];\n"
        "    if (quote) {\n"
        "      cur += ch;\n"
        "      if (escaped) escaped = false;\n"
        "      else if (ch === '\\\\') escaped = true;\n"
        "      else if (ch === quote) quote = '';\n"
        "      continue;\n"
        "    }\n"
        "    if (ch === '\\'' || ch === '\"' || ch === '`') { quote = ch; cur += ch; continue; }\n"
        "    if (ch === '(' || ch === '[' || ch === '{') { d++; cur += ch; continue; }\n"
        "    if (ch === ')' || ch === ']' || ch === '}') { d--; cur += ch; continue; }\n"
        "    if (ch === ',' && d === 0) { parts.push(cur.trim()); cur = ''; continue; }\n"
        "    cur += ch;\n"
        "  }\n"
        "  if (cur.trim()) parts.push(cur.trim());\n"
        "  const names = [], requiredNames = [];\n"
        "  let requiredCount = 0, destructured = false, hasRest = false;\n"
        "  for (const p of parts) {\n"
        "    let eqIdx = -1, pd = 0; quote = ''; escaped = false;\n"
        "    for (let i = 0; i < p.length; i++) {\n"
        "      const ch = p[i];\n"
        "      if (quote) {\n"
        "        if (escaped) escaped = false;\n"
        "        else if (ch === '\\\\') escaped = true;\n"
        "        else if (ch === quote) quote = '';\n"
        "        continue;\n"
        "      }\n"
        "      if (ch === '\\'' || ch === '\"' || ch === '`') { quote = ch; continue; }\n"
        "      if (ch === '(' || ch === '[' || ch === '{') pd++;\n"
        "      else if (ch === ')' || ch === ']' || ch === '}') pd--;\n"
        "      else if (ch === '=' && pd === 0 && p[i + 1] !== '>') { eqIdx = i; break; }\n"
        "    }\n"
        "    const lhs = (eqIdx >= 0 ? p.slice(0, eqIdx) : p).trim();\n"
        "    const isRest = lhs.startsWith('...');\n"
        "    if (isRest) hasRest = true;\n"
        "    if (lhs.startsWith('{') || lhs.startsWith('[')) {\n"
        "      destructured = true;\n"
        "      names.push('');\n"
        "      if (eqIdx === -1 && !isRest) requiredCount++;\n"
        "    } else {\n"
        "      const paramName = lhs.replace(/^\\.\\.\\./, '').trim();\n"
        "      names.push(paramName);\n"
        "      if (eqIdx === -1 && !isRest) {\n"
        "        requiredCount++;\n"
        "        requiredNames.push(paramName);\n"
        "      }\n"
        "    }\n"
        "  }\n"
        "  return { names, requiredNames, requiredCount, destructured, hasRest };\n"
        "}\n"
        "const raw = fs.readFileSync(0, 'utf8');\n"
        "let arg;\n"
        "if (raw.trim()) {\n"
        "  try { arg = JSON.parse(raw); } catch { arg = raw.trim(); }\n"
        "}\n"
        "const meta = parseParams(fn);\n"
        "const totalParams = meta.names.length;\n"
        "const paramSet = new Set(meta.names.filter(Boolean));\n"
        "(async () => {\n"
        "  let out;\n"
        "  if (totalParams === 0 && !meta.hasRest) {\n"
        "    out = await fn();\n"
        "  } else if (\n"
        "    arg !== null && typeof arg === 'object' && !Array.isArray(arg)\n"
        "    && !meta.destructured && totalParams > 1\n"
        "    && Object.keys(arg).length > 0\n"
        "    && Object.keys(arg).every(k => paramSet.has(k))\n"
        "    && meta.requiredNames.every(k => Object.prototype.hasOwnProperty.call(arg, k))\n"
        "  ) {\n"
        "    const vals = meta.names.map(k => Object.prototype.hasOwnProperty.call(arg, k) ? arg[k] : undefined);\n"
        "    out = await fn(...vals);\n"
        "  } else if (totalParams === 1 && !meta.hasRest) {\n"
        "    out = await fn(arg);\n"
        "  } else if (\n"
        "    Array.isArray(arg)\n"
        "    && ((meta.hasRest && arg.length >= meta.requiredCount)\n"
        "      || (arg.length >= meta.requiredCount && arg.length <= totalParams))\n"
        "  ) {\n"
        "    out = await fn(...arg);\n"
        "  } else {\n"
        "    out = await fn(arg);\n"
        "  }\n"
        "  process.stdout.write(JSON.stringify(out === undefined ? null : out));\n"
        "})().catch(err => {\n"
        "  process.stderr.write(String(err && err.stack ? err.stack : err));\n"
        "  process.exit(1);\n"
        "});\n"
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


_JS_EXPORT_DEFAULT_FN = re.compile(r"(?m)^(\s*)export\s+default\s+(?=(?:async\s+)?function\b|class\b)")
_JS_EXPORT_DEFAULT_EXPR = re.compile(r"(?m)^(\s*)export\s+default\s+")
_JS_EXPORT_DECL = re.compile(r"(?m)^(\s*)export\s+(?=(?:async\s+)?function\b|const\b|let\b|var\b|class\b)")
_JS_EXPORT_NAMED = re.compile(r"(?m)^(\s*)export\s*\{([^}]+)\}\s*;?")


def _normalize_js_exports(source: str, entry_point: str) -> str:
    """Convert common top-level ES module export syntax so Node CommonJS sandbox runs modern JS smoothly."""
    exported_names: list[str] = []
    out = source
    for match in re.finditer(r"(?m)^\s*export\s+(?:async\s+)?(?:function|class|const|let|var)\s+([A-Za-z_$][\w$]*)", out):
        exported_names.append(match.group(1))
    out = _JS_EXPORT_DECL.sub(r"\1", out)
    if _JS_EXPORT_DEFAULT_FN.search(out):
        default_name = re.search(r"(?m)^\s*export\s+default\s+(?:async\s+)?(?:function|class)\s+([A-Za-z_$][\w$]*)", source)
        if default_name:
            out = _JS_EXPORT_DEFAULT_FN.sub(r"\1", out, count=1)
            out += f"\n;module.exports = {default_name.group(1)};\n"
        else:
            out = _JS_EXPORT_DEFAULT_EXPR.sub(r"\1module.exports = ", out, count=1)
    elif _JS_EXPORT_DEFAULT_EXPR.search(out):
        out = _JS_EXPORT_DEFAULT_EXPR.sub(r"\1module.exports = ", out, count=1)

    def _replace_named(m: re.Match[str]) -> str:
        raw_items = [part.strip() for part in m.group(2).split(",") if part.strip()]
        pairs = []
        for item in raw_items:
            if " as " in item:
                src_name, alias = (p.strip() for p in item.split(" as ", 1))
                pairs.append(f"{alias}: {src_name}")
            else:
                pairs.append(item)
        return f"{m.group(1)}Object.assign(module.exports, {{ {', '.join(pairs)} }});"

    out = _JS_EXPORT_NAMED.sub(_replace_named, out)
    if "module.exports" not in out:
        exports: list[str] = []
        if exported_names:
            unique_names = list(dict.fromkeys(exported_names))
            exports.append(f"Object.assign(module.exports, {{ {', '.join(unique_names)} }});")
        if entry_point and entry_point not in exported_names:
            exports.append(f"if (typeof {entry_point} === 'function') Object.assign(module.exports, {{ {entry_point} }});")
        if exports:
            out = f"{out}\n;{' '.join(exports)}\n"
    return out


def _execute_javascript(req: ExecuteRequest) -> ExecuteResponse:
    node_bin = shutil.which("node")
    if not node_bin:
        return ExecuteResponse(language="javascript", total=len(req.cases), compile_error="Node.js runtime không khả dụng.")
    with tempfile.TemporaryDirectory(prefix="smile-js-") as tmpdir:
        sol_path = os.path.join(tmpdir, "solution.js")
        source = _normalize_js_exports(req.code, req.entry_point)
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


def _split_sql_statements(sql_text: str) -> list[str]:
    """Split candidate SQL safely on top-level semicolons, respecting quotes and comments."""
    statements: list[str] = []
    cur: list[str] = []
    i, n = 0, len(sql_text)
    quote = ""
    while i < n:
        ch = sql_text[i]
        nxt = sql_text[i + 1] if i + 1 < n else ""
        if quote:
            cur.append(ch)
            if ch == quote:
                if nxt == quote:
                    cur.append(nxt)
                    i += 2
                    continue
                quote = ""
            i += 1
            continue
        if ch == "-" and nxt == "-":
            end = sql_text.find("\n", i)
            if end == -1:
                break
            cur.append("\n")
            i = end + 1
            continue
        if ch == "/" and nxt == "*":
            end = sql_text.find("*/", i + 2)
            if end == -1:
                break
            cur.append(" ")
            i = end + 2
            continue
        if ch in {"'", '"'}:
            quote = ch
            cur.append(ch)
            i += 1
            continue
        if ch == ";":
            stmt = "".join(cur).strip()
            if stmt:
                statements.append(stmt)
            cur = []
            i += 1
            continue
        cur.append(ch)
        i += 1
    tail = "".join(cur).strip()
    if tail:
        statements.append(tail)
    return statements


def _run_sql_once(setup_sql: str, extra_sql: str, candidate_sql: str) -> tuple[str, str]:
    if _FORBIDDEN_SQL.search(candidate_sql):
        return "", "Câu lệnh SQL chứa từ khóa không được phép trong sandbox."
    statements = _split_sql_statements(candidate_sql)
    if not statements:
        return "", "Câu lệnh SQL đang trống."
    conn = sqlite3.connect(":memory:")
    try:
        if setup_sql.strip():
            conn.executescript(setup_sql)
        if extra_sql.strip():
            conn.executescript(extra_sql)
        last_rows: list[list[object]] = []
        for stmt in statements:
            cursor = conn.execute(stmt)
            if cursor.description:
                last_rows = [list(row) for row in cursor.fetchall()]
        return _clip(json.dumps(last_rows, ensure_ascii=False)), ""
    except sqlite3.Error as exc:
        return "", str(exc)
    finally:
        conn.close()


def _execute_sql(req: ExecuteRequest) -> ExecuteResponse:
    if not req.cases:
        out, err = _run_sql_once(req.setup_sql, "", req.code)
        return ExecuteResponse(language="sql", compile_error=err, stdout=out)
    cleaned_sql = _SQL_LINE_COMMENT.sub("", _SQL_BLOCK_COMMENT.sub("", req.code))
    unordered_rows = not bool(_SQL_ORDER_BY.search(cleaned_sql))
    results: list[CaseResult] = []
    for case in req.cases:
        started = perf_counter()
        out, err = _run_sql_once(req.setup_sql, case.input_data, req.code)
        elapsed = int((perf_counter() - started) * 1000)
        ok = (not err) and _normalize_compare(out, case.expected_output, unordered_rows=unordered_rows)
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
