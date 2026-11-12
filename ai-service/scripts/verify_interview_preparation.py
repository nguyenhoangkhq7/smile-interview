"""Probe the real AI HTTP lifecycle using only synthetic skills, never user data."""
import argparse
import json
from time import monotonic, sleep
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from uuid import uuid4

SKILLS = ["python", "java", "javascript", "typescript", "csharp", "golang", "rust", "php", "ruby", "kotlin",
          "swift", "sql", "postgresql", "mysql", "mongodb", "redis", "docker", "kubernetes", "git", "linux",
          "react", "vue", "angular", "nextjs", "django", "fastapi", "spring", "nodejs", "graphql", "rest_api",
          "unit_testing", "ci_cd", "terraform", "aws", "azure", "system_design"]


def post(base_url, operation, payload):
    request = Request(f"{base_url}/api/v2/interview/{operation}", json.dumps(payload).encode(),
                      {"Content-Type": "application/json"}, method="POST")
    with urlopen(request, timeout=180) as response:
        return json.load(response)


def prepare(base_url, count):
    payload = {"session_id": f"synthetic-verification-{uuid4().hex[:8]}", "skills": [
        {"jd_skill_id": name, "required_proficiency": 3, "candidate_proficiency": 3, "importance_weight": 0.7,
         "priority": 0, "suggested_strategy": "PROBE_DEPTH", "job_tasks": [], "jd_evidence_spans": []}
        for name in SKILLS[:count]], "opening": {"company": "Synthetic Test", "role_title": "Backend Developer"}}
    print(f"Preparing synthetic session={payload['session_id']} skills={count}", flush=True)
    result = None
    for attempt in range(2):
        try:
            result = post(base_url, "start", payload)
            break
        except HTTPError as error:
            detail = json.load(error).get("detail", "AI request failed")
            print(f"Start attempt={attempt + 1} status={error.code} detail={detail}", flush=True)
            if error.code != 503 or attempt == 1:
                raise SystemExit(1) from error
            sleep(5)
    assert result is not None
    assert result["public"]["conversation"]["phase"] == "OPENING"
    print("Opening ready; requesting the first technical question", flush=True)
    snapshot = result["snapshot"]
    result = post(base_url, "conversation", {"snapshot": snapshot,
        "message_id": snapshot["conversation"]["message"]["message_id"],
        "expected_state_version": snapshot["state_version"], "action": "SKIP_INTRODUCTION", "introduction": ""})
    assert result["public"]["pending_turn"]["question"].strip()
    assert result["public"]["conversation"]["phase"] == "INTERVIEW"
    print(f"PASS: objectives={len(snapshot['objectives'])} phase=INTERVIEW has_question=true", flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--skills", type=int, default=36, choices=range(1, 37))
    args = parser.parse_args()
    started = monotonic()
    prepare(args.base_url.rstrip("/"), args.skills)
    print(f"Elapsed: {monotonic() - started:.2f}s", flush=True)
