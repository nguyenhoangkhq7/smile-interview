"""Compare paired Module 3 JSONL runs offline, without another model call."""
import argparse
from collections import Counter, defaultdict
import json
import math
from pathlib import Path


def read_runs(path):
    runs = defaultdict(list)
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        if line.strip():
            row = json.loads(line)
            runs[row["condition"], row["case_id"]].append(row)
    return runs


def job(row):
    turns = [row.get(name) or {} for name in ("turn1", "turn2")]
    events = row.get("telemetry", {}).get("events", [])
    waits = [float(e["fields"].get("wait_seconds", 0)) for e in events if e["event"] == "model.retry"]
    error = (row.get("error_message") or "").split(":", 2)
    kind = row.get("error_type") or (error[1] if len(error) > 1 else None)
    stage = row.get("failure_stage")
    if kind and not stage:
        if row["condition"] == "one_shot":
            stage = error[0]
        elif not turns[0]:
            stage = "start"
        else:
            stage = "next_question" if row.get("turn1_judgment") else "judge"
    if kind in {"ProviderUnavailableError", "TimeoutError", "APITimeoutError", "APIConnectionError",
                "RateLimitError", "APIStatusError", "InternalServerError"}:
        category = "provider"
    elif kind in {"QuestionUnavailableError", "JudgmentUnavailableError", "ValidationError", "JSONDecodeError"}:
        category = "validation"
    else:
        category = "other" if kind else None
    ok = row["status"] == "OK"
    # Both benchmark versions time Q1 (excluding preparation) and the answer-to-Q2 transition.
    measured = round(row.get("prep_seconds", 0) + sum(t["generation_seconds"] for t in turns), 3) if ok else None
    regenerated = any(t.get("question_calls", 0) > 1 for t in turns)
    judges = sum(e["event"] == "model.started" and e["fields"].get("operation") == "judge" for e in events)
    retried = bool(waits or regenerated or judges > 1)
    last_action = next((e["fields"].get("action") for e in reversed(events) if e["event"] == "question.started"), None)
    return dict(status=row["status"], stage=stage, error_type=kind, category=category,
                failure_question_action=last_action if kind == "QuestionUnavailableError" else None,
                completed_seconds=measured, elapsed_seconds=row.get("elapsed_seconds"),
                model_retry_wait_seconds=round(sum(waits), 3), retry_events=len(waits),
                verification_timed_out=row.get("telemetry", {}).get("verification_timed_out", False),
                has_question_regeneration=regenerated, observed_chain_retry=retried)


def percentiles(values):
    ordered = sorted(values)
    if not ordered:
        return {"n": 0, "p50": None, "p95": None}
    return {"n": len(ordered), **{f"p{p}": ordered[math.ceil(len(ordered) * p / 100) - 1] for p in (50, 95)}}


def summarize(rows):
    first = [runs[0] for runs in rows]
    ok = [r for r in first if r["status"] == "OK"]
    failures = [r for r in first if r["status"] != "OK"]
    return dict(cases=len(first), first_run_ok=len(ok),
                ok_without_observed_retry=sum(not r["observed_chain_retry"] for r in ok),
                ok_after_observed_retry=sum(r["observed_chain_retry"] for r in ok),
                whole_case_replays=sum(len(runs) > 1 for runs in rows),
                recovered_on_replay=sum(runs[0]["status"] != "OK" and any(r["status"] == "OK" for r in runs[1:]) for runs in rows),
                failed=len(failures), failures_by_category=dict(Counter(r["category"] for r in failures)),
                failures_by_question_action=dict(Counter(r["failure_question_action"] for r in failures if r["failure_question_action"])),
                failures_by_stage=dict(Counter(r["stage"] for r in failures)),
                failures_by_type=dict(Counter(r["error_type"] for r in failures)),
                completed_seconds=percentiles(r["completed_seconds"] for r in ok))


def compare(before, after):
    if before.keys() != after.keys():
        raise ValueError(f"Unpaired input: {len(before.keys() ^ after.keys())} missing case/condition pairs")
    cases = []
    summary = {}
    for condition in sorted({c for c, _ in before}):
        keys = sorted(key for key in before if key[0] == condition)
        paired = [{"case_id": key[1], "condition": condition, "before": list(map(job, before[key])),
                   "after": list(map(job, after[key]))} for key in keys]
        cases.extend(paired)
        both_ok = [p for p in paired if all(p[phase][0]["status"] == "OK" for phase in ("before", "after"))]
        summary[condition] = {}
        for phase in ("before", "after"):
            stats = summarize([p[phase] for p in paired])
            stats["paired_completed_seconds"] = percentiles(p[phase][0]["completed_seconds"] for p in both_ok)
            summary[condition][phase] = stats
        summary[condition]["failed_then_ok"] = sum(p["before"][0]["status"] != "OK" and p["after"][0]["status"] == "OK" for p in paired)
        summary[condition]["ok_then_failed"] = sum(p["before"][0]["status"] == "OK" and p["after"][0]["status"] != "OK" for p in paired)
    return {"conditions": summary, "cases": cases}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("before", "after", "output"):
        parser.add_argument(name, type=Path)
    args = parser.parse_args()
    result = compare(read_runs(args.before), read_runs(args.after))
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
