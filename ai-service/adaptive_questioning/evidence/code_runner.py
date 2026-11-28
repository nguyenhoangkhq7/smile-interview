"""Pluggable code execution abstraction supporting isolated HTTP runner and local subprocess fallback."""
from __future__ import annotations

from collections import Counter
import json
import logging
import math
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
_SQL_ORDER_BY = re.compile(r"\border\s+by\b", re.IGNORECASE)
_SQL_LINE_COMMENT = re.compile(r"--[^\n]*")
_SQL_BLOCK_COMMENT = re.compile(r"/\*[\s\S]*?\*/")
_CODE_FENCE = re.compile(r"^```(?:[a-zA-Z0-9_+#.-]+)?[ \t]*\n(.*?)^```[ \t]*$", re.MULTILINE | re.DOTALL)
_TRAILING_PROSE = re.compile(r"(?m)^\s*\n(?:Em|Tôi|Mình|I|This)\s+[^\n]+")


class CodingTestCase(BaseModel):
    name: str = Field(default="case", min_length=1, max_length=80)
    input_data: str = Field(
        default="",
        max_length=4000,
        description="For python/javascript: JSON args array/object; for sql: INSERT statements seeding test rows for this case.",
    )
    expected_output: str = Field(
        default="",
        max_length=4000,
        description="Valid JSON expected output (for sql: JSON 2D array of result rows, e.g. [[1, \"An\"]]).",
    )


class PublicCodingSpec(BaseModel):
    language: SupportedLanguage = "python"
    entry_point: str = Field(
        default="",
        max_length=80,
        description="Function name for python/javascript; empty string '' for sql.",
    )
    starter_code: str = Field(
        default="",
        max_length=4000,
        description="Starter function signature or SQL comment shown in the editor.",
    )
    setup_sql: str = Field(
        default="",
        max_length=8000,
        description="For language='sql' only: SQLite CREATE TABLE DDL (and optional base INSERTs) executed before every test case.",
    )
    sample_tests: list[CodingTestCase] = Field(default_factory=list, max_length=3)


class CodingSpec(PublicCodingSpec):
    hidden_tests: list[CodingTestCase] = Field(default_factory=list, max_length=5)
    reference_solution: str = Field(default="", max_length=8000)

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
    a_clean, e_clean = actual.strip(), expected.strip()
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


def _split_sql_statements(sql_text: str) -> list[str]:
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
        "import asyncio, inspect, json, sys\n"
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
        "if inspect.isawaitable(out): out = asyncio.run(out)\n"
        "def _norm(v):\n"
        "    if isinstance(v, bytes): return v.decode('utf-8', errors='replace')\n"
        "    if isinstance(v, set): return sorted((_norm(x) for x in v), key=lambda item: json.dumps(item, sort_keys=True, ensure_ascii=False, default=str))\n"
        "    if isinstance(v, (tuple, list)): return [_norm(x) for x in v]\n"
        "    if isinstance(v, dict): return {(k.decode('utf-8', errors='replace') if isinstance(k, bytes) else k): _norm(val) for k, val in v.items()}\n"
        "    return v\n"
        "sys.stdout.write(json.dumps(_norm(out), ensure_ascii=False, default=str))\n"
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


_JS_EXPORT_DEFAULT_FN = re.compile(r"(?m)^(\s*)export\s+default\s+(?=(?:async\s+)?function\b|class\b)")
_JS_EXPORT_DEFAULT_EXPR = re.compile(r"(?m)^(\s*)export\s+default\s+")
_JS_EXPORT_DECL = re.compile(r"(?m)^(\s*)export\s+(?=(?:async\s+)?function\b|const\b|let\b|var\b|class\b)")
_JS_EXPORT_NAMED = re.compile(r"(?m)^(\s*)export\s*\{([^}]+)\}\s*;?")


def _normalize_js_exports(source: str, entry_point: str) -> str:
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
            source = _normalize_js_exports(code, entry_point)
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
            statements = _split_sql_statements(code)
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
                return json.dumps(last_rows, ensure_ascii=False)[:MAX_OUTPUT_CHARS], ""
            except sqlite3.Error as exc:
                return "", str(exc)
            finally:
                conn.close()

        if not cases:
            out, err = run_one("")
            return ExecutionResult(language="sql", compile_error=err, stdout=out)
        cleaned_sql = _SQL_LINE_COMMENT.sub("", _SQL_BLOCK_COMMENT.sub("", code))
        unordered_rows = not bool(_SQL_ORDER_BY.search(cleaned_sql))
        results: list[CodingCaseResult] = []
        for case in cases:
            started = perf_counter()
            out, err = run_one(case.input_data)
            elapsed = int((perf_counter() - started) * 1000)
            results.append(CodingCaseResult(
                name=case.name, passed=(not err) and _normalize_compare(out, case.expected_output, unordered_rows=unordered_rows),
                actual_output=out, expected_output=case.expected_output.strip(), error=err, elapsed_ms=elapsed,
            ))
        return ExecutionResult(language="sql", passed=sum(r.passed for r in results), total=len(results), results=results)


def default_code_runner() -> CodeExecutionProvider:
    url = os.environ.get("CODE_RUNNER_URL", "").strip()
    if url:
        return HttpCodeRunner(url, api_key=os.environ.get("CODE_RUNNER_API_KEY", "").strip())
    return LocalSubprocessCodeRunner()
