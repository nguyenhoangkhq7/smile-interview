#!/usr/bin/env python3
"""
Staging two-account security verification & baseline performance measurement harness.

Usage:
  1) Two-account authorization / IDOR verification:
     python scripts/staging-baseline-check.py --mode authz --base-url https://api-staging.example.com \
       --email-a usera@example.com --pass-a Pass123! --email-b userb@example.com --pass-b Pass123!

  2) Baseline contention benchmark (CV/JD analysis + polling concurrently with voice/interview probes):
     python scripts/staging-baseline-check.py --mode benchmark --base-url https://api-staging.example.com \
       --email-a usera@example.com --pass-a Pass123! --voice-session-id <active-voice-session-id> \
       --cv-file path/to/cv.pdf --jd-file path/to/jd.pdf --analysis-concurrency 2
"""
from __future__ import annotations

import argparse
import concurrent.futures
import json
import math
import statistics
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class HttpResult:
    status: int
    elapsed_ms: float
    body: str
    json_data: Any = None


def http_json(
    base_url: str,
    method: str,
    path: str,
    token: str | None = None,
    payload: Any = None,
    timeout: float = 30.0,
) -> HttpResult:
    url = base_url.rstrip("/") + path
    headers = {"Accept": "application/json"}
    data = None
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if payload is not None:
        headers["Content-Type"] = "application/json"
        data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    started = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
            elapsed = (time.perf_counter() - started) * 1000.0
            parsed = _try_json(raw)
            return HttpResult(resp.status, elapsed, raw, parsed)
    except urllib.error.HTTPError as err:
        raw = err.read().decode("utf-8", errors="replace")
        elapsed = (time.perf_counter() - started) * 1000.0
        return HttpResult(err.code, elapsed, raw, _try_json(raw))


def http_multipart(
    base_url: str,
    path: str,
    token: str,
    fields: dict[str, str],
    files: dict[str, tuple[str, bytes, str]] | None = None,
    timeout: float = 60.0,
) -> HttpResult:
    boundary = f"----SmileBaseline{uuid.uuid4().hex}"
    parts: list[bytes] = []
    for key, value in fields.items():
        parts.append(
            f"--{boundary}\r\nContent-Disposition: form-data; name=\"{key}\"\r\n\r\n{value}\r\n".encode("utf-8")
        )
    for key, (filename, content, content_type) in (files or {}).items():
        parts.append(
            f"--{boundary}\r\nContent-Disposition: form-data; name=\"{key}\"; filename=\"{filename}\"\r\n"
            f"Content-Type: {content_type}\r\n\r\n".encode("utf-8")
            + content
            + b"\r\n"
        )
    parts.append(f"--{boundary}--\r\n".encode("utf-8"))
    body = b"".join(parts)
    req = urllib.request.Request(
        base_url.rstrip("/") + path,
        data=body,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": f"multipart/form-data; boundary={boundary}",
        },
        method="POST",
    )
    started = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
            elapsed = (time.perf_counter() - started) * 1000.0
            return HttpResult(resp.status, elapsed, raw, _try_json(raw))
    except urllib.error.HTTPError as err:
        raw = err.read().decode("utf-8", errors="replace")
        elapsed = (time.perf_counter() - started) * 1000.0
        return HttpResult(err.code, elapsed, raw, _try_json(raw))


def _try_json(raw: str) -> Any:
    try:
        return json.loads(raw)
    except Exception:
        return None


def login(base_url: str, email: str, password: str) -> str:
    res = http_json(base_url, "POST", "/api/auth/login", payload={"email": email, "password": password})
    if res.status != 200 or not isinstance(res.json_data, dict) or not res.json_data.get("token"):
        raise RuntimeError(f"Login failed for {email}: HTTP {res.status} {res.body[:200]}")
    return str(res.json_data["token"])


def run_authz_suite(base_url: str, email_a: str, pass_a: str, email_b: str, pass_b: str) -> int:
    token_a = login(base_url, email_a, pass_a)
    token_b = login(base_url, email_b, pass_b)

    checks: list[tuple[str, bool, str]] = []

    def check(name: str, res: HttpResult, expected: set[int]) -> None:
        ok = res.status in expected
        checks.append((name, ok, f"got HTTP {res.status}, expected {sorted(expected)}"))

    # 1. Unauthenticated /api/auth/me must return 401
    check("Unauthenticated GET /api/auth/me -> 401", http_json(base_url, "GET", "/api/auth/me"), {401})

    # 2. User A creates temporary CV, JD, and Session
    cv_a = http_json(base_url, "POST", "/api/v1/resumes", token_a, {
        "file_name": "staging-authz-cv.txt",
        "raw_text": "Staging secret CV A: Java 21, Spring Boot, PostgreSQL",
        "file_url": "https://spoofed.example.com/should-be-ignored.pdf",
    })
    check("User A creates CV -> 201", cv_a, {201})
    resume_id = cv_a.json_data["id"]
    checks.append(("JSON CV ignores untrusted file_url", cv_a.json_data.get("fileUrl") is None, f"fileUrl={cv_a.json_data.get('fileUrl')}"))

    jd_a = http_json(base_url, "POST", "/api/v1/job-descriptions", token_a, {
        "title": "Staging Authz JD A",
        "raw_text": "Staging secret JD A: Distributed systems and SQL tuning",
    })
    check("User A creates JD -> 201", jd_a, {201})
    jd_id = jd_a.json_data["id"]

    session_id = f"staging-authz-{uuid.uuid4().hex[:10]}"
    sess_a = http_json(base_url, "POST", "/api/v1/sessions", token_a, {
        "id": session_id,
        "resumeId": resume_id,
        "jdId": jd_id,
        "roleTitle": "Backend Engineer",
        "interviewType": "Technical",
    })
    check("User A creates Session -> 201", sess_a, {201})

    try:
        # 3. User B attacks every read/raw/update/clone/delete/default-CV endpoint
        check("User B GET /resumes/{idA} -> 403", http_json(base_url, "GET", f"/api/v1/resumes/{resume_id}", token_b), {403})
        check("User B GET /resumes/{idA}/raw -> 403", http_json(base_url, "GET", f"/api/v1/resumes/{resume_id}/raw", token_b), {403})
        check("User B DELETE /resumes/{idA} -> 403", http_json(base_url, "DELETE", f"/api/v1/resumes/{resume_id}", token_b), {403})

        check("User B GET /job-descriptions/{idA} -> 403", http_json(base_url, "GET", f"/api/v1/job-descriptions/{jd_id}", token_b), {403})
        check("User B GET /job-descriptions/{idA}/raw -> 403", http_json(base_url, "GET", f"/api/v1/job-descriptions/{jd_id}/raw", token_b), {403})
        check("User B DELETE /job-descriptions/{idA} -> 403", http_json(base_url, "DELETE", f"/api/v1/job-descriptions/{jd_id}", token_b), {403})

        check("User B GET /sessions/raw-texts?resumeId=A -> 403",
              http_json(base_url, "GET", f"/api/v1/sessions/raw-texts?resumeId={resume_id}&jdId={jd_id}", token_b), {403})
        check("User B GET /sessions/{sessA} -> 403", http_json(base_url, "GET", f"/api/v1/sessions/{session_id}", token_b), {403})
        check("User B PUT /sessions/{sessA} -> 403",
              http_json(base_url, "PUT", f"/api/v1/sessions/{session_id}", token_b, {"roleTitle": "Hijack"}), {403})
        check("User B DELETE /sessions/{sessA} -> 403", http_json(base_url, "DELETE", f"/api/v1/sessions/{session_id}", token_b), {403})
        check("User B POST /sessions/{sessA}/clone -> 403", http_json(base_url, "POST", f"/api/v1/sessions/{session_id}/clone", token_b), {403})
        check("User B PUT /auth/profile defaultResumeId=A -> 403",
              http_json(base_url, "PUT", "/api/auth/profile", token_b, {"defaultResumeId": resume_id}), {403})
        check("User B POST /sessions/{sessA}/documents -> 403",
              http_multipart(base_url, f"/api/v1/sessions/{session_id}/documents", token_b, {"cvText": "x", "jdText": "y"}), {403})
    finally:
        # Cleanup User A's test artifacts
        http_json(base_url, "DELETE", f"/api/v1/sessions/{session_id}", token_a)
        http_json(base_url, "DELETE", f"/api/v1/resumes/{resume_id}", token_a)
        http_json(base_url, "DELETE", f"/api/v1/job-descriptions/{jd_id}", token_a)

    failed = [c for c in checks if not c[1]]
    for name, ok, detail in checks:
        mark = "PASS" if ok else "FAIL"
        print(f"[{mark}] {name} ({detail})")
    print(f"\nSummary: {len(checks) - len(failed)}/{len(checks)} checks passed.")
    return 1 if failed else 0


@dataclass
class AnalysisTiming:
    session_id: str
    status: str
    total_ms: float
    poll_count: int
    poll_latencies_ms: list[float] = field(default_factory=list)


def run_one_analysis(base_url: str, token: str, cv_bytes: bytes, cv_name: str, jd_bytes: bytes, jd_name: str) -> AnalysisTiming:
    session_id = f"bench-{uuid.uuid4().hex[:10]}"
    ingest = http_multipart(
        base_url,
        f"/api/v1/sessions/{session_id}/documents",
        token,
        {"roleTitle": "Backend Engineer", "interviewType": "Technical"},
        files={
            "cvFile": (cv_name, cv_bytes, "application/pdf"),
            "jdFile": (jd_name, jd_bytes, "application/pdf"),
        },
    )
    if ingest.status != 200:
        raise RuntimeError(f"Ingest failed: HTTP {ingest.status} {ingest.body[:200]}")

    started = time.perf_counter()
    submit = http_json(base_url, "POST", f"/api/v1/sessions/{session_id}/analyze-gap?forceRefresh=true", token)
    if submit.status == 200:
        return AnalysisTiming(session_id, "CACHED", (time.perf_counter() - started) * 1000.0, 0)
    if submit.status != 202 or not isinstance(submit.json_data, dict):
        return AnalysisTiming(session_id, f"SUBMIT_ERR_{submit.status}", (time.perf_counter() - started) * 1000.0, 0)

    job_id = submit.json_data["job_id"]
    polls: list[float] = []
    status = "TIMEOUT"
    deadline = time.perf_counter() + 240.0
    while time.perf_counter() < deadline:
        res = http_json(base_url, "GET", f"/api/v1/sessions/{session_id}/analyze-gap/{job_id}", token)
        polls.append(res.elapsed_ms)
        if res.status == 200 and isinstance(res.json_data, dict):
            st = res.json_data.get("status")
            if st in ("SUCCEEDED", "FAILED"):
                status = str(st)
                break
        time.sleep(1.5)
    total_ms = (time.perf_counter() - started) * 1000.0
    http_json(base_url, "DELETE", f"/api/v1/sessions/{session_id}", token)
    return AnalysisTiming(session_id, status, total_ms, len(polls), polls)


def percentile(values: list[float], p: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    idx = min(len(ordered) - 1, max(0, math.ceil((p / 100.0) * len(ordered)) - 1))
    return ordered[idx]


def run_benchmark(
    base_url: str,
    email: str,
    password: str,
    cv_path: Path,
    jd_path: Path,
    voice_session_id: str | None,
    concurrency: int,
) -> int:
    token = login(base_url, email, password)
    cv_bytes = cv_path.read_bytes()
    jd_bytes = jd_path.read_bytes()

    stop_probes = False
    probe_latencies: list[float] = []
    probe_errors = 0

    def run_probes() -> None:
        nonlocal probe_errors
        probe_path = f"/api/v2/sessions/{voice_session_id}/interview/voice/config" if voice_session_id else "/api/auth/me"
        while not stop_probes:
            res = http_json(base_url, "GET", probe_path, token, timeout=15.0)
            if res.status == 200:
                probe_latencies.append(res.elapsed_ms)
            else:
                probe_errors += 1
            time.sleep(0.5)

    with concurrent.futures.ThreadPoolExecutor(max_workers=concurrency + 1) as pool:
        probe_future = pool.submit(run_probes)
        analysis_futures = [
            pool.submit(run_one_analysis, base_url, token, cv_bytes, cv_path.name, jd_bytes, jd_path.name)
            for _ in range(concurrency)
        ]
        results = [f.result() for f in analysis_futures]
        stop_probes = True
        probe_future.result()

    all_polls = [ms for r in results for ms in r.poll_latencies_ms]
    report = {
        "analysis_concurrency": concurrency,
        "analyses": [
            {"session_id": r.session_id, "status": r.status, "total_ms": round(r.total_ms, 1), "poll_count": r.poll_count}
            for r in results
        ],
        "polling": {
            "total_requests": len(all_polls),
            "p50_ms": round(percentile(all_polls, 50), 1),
            "p95_ms": round(percentile(all_polls, 95), 1),
            "max_ms": round(max(all_polls) if all_polls else 0.0, 1),
        },
        "concurrent_realtime_probe": {
            "target": f"/voice/config ({voice_session_id})" if voice_session_id else "/api/auth/me",
            "samples": len(probe_latencies),
            "errors": probe_errors,
            "p50_ms": round(percentile(probe_latencies, 50), 1),
            "p95_ms": round(percentile(probe_latencies, 95), 1),
            "max_ms": round(max(probe_latencies) if probe_latencies else 0.0, 1),
            "mean_ms": round(statistics.mean(probe_latencies) if probe_latencies else 0.0, 1),
        },
    }
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0 if all(r.status in ("SUCCEEDED", "CACHED") for r in results) and probe_errors == 0 else 1


def main() -> int:
    parser = argparse.ArgumentParser(description="Staging authorization & baseline benchmark helper")
    parser.add_argument("--mode", choices=["authz", "benchmark"], required=True)
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--email-a", required=True)
    parser.add_argument("--pass-a", required=True)
    parser.add_argument("--email-b")
    parser.add_argument("--pass-b")
    parser.add_argument("--cv-file", type=Path)
    parser.add_argument("--jd-file", type=Path)
    parser.add_argument("--voice-session-id")
    parser.add_argument("--analysis-concurrency", type=int, default=2)
    args = parser.parse_args()

    if args.mode == "authz":
        if not args.email_b or not args.pass_b:
            parser.error("--email-b and --pass-b are required for --mode authz")
        return run_authz_suite(args.base_url, args.email_a, args.pass_a, args.email_b, args.pass_b)

    if not args.cv_file or not args.jd_file:
        parser.error("--cv-file and --jd-file are required for --mode benchmark")
    return run_benchmark(
        args.base_url, args.email_a, args.pass_a,
        args.cv_file, args.jd_file, args.voice_session_id, args.analysis_concurrency,
    )


if __name__ == "__main__":
    sys.exit(main())
