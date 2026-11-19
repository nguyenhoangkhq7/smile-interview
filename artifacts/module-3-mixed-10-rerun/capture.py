"""Run the installed Module 3 API with read-only observers in a separate process."""

import functools
import hashlib
import inspect
import json
import logging
import sys
import threading
import time
from collections.abc import Mapping
from contextvars import ContextVar
from dataclasses import asdict, is_dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path


ROOT = Path(__file__).resolve().parent
INBOX = ROOT / "inbox"
RUN = ROOT / "run"
STEP = ContextVar("trace_step", default=None)
TRACE_LOCK = threading.Lock()
CALL_NUMBER = 0


def now():
    return datetime.now(timezone.utc).isoformat()


def write_json(path, value):
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def data(value):
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    if is_dataclass(value):
        return data(asdict(value))
    if isinstance(value, Mapping):
        return {str(key.value if isinstance(key, Enum) else key): data(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set, frozenset)):
        return [data(item) for item in value]
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, datetime):
        return value.isoformat()
    if value is None or isinstance(value, (str, bool, int, float)):
        return value
    return {"type": type(value).__name__}


def append_event(record):
    global CALL_NUMBER
    with TRACE_LOCK:
        CALL_NUMBER += 1
        row = {"seq": CALL_NUMBER, "at_utc": now(), "step": STEP.get(), **record}
        with (RUN / "components.jsonl").open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(row, ensure_ascii=False) + "\n")
        return CALL_NUMBER


def error_data(error):
    details = {"type": type(error).__name__}
    status = getattr(error, "status", None) or getattr(error, "status_code", None)
    if isinstance(status, int):
        details["status"] = status
    if isinstance(error, ValueError):
        if hasattr(error, "errors"):
            details["validation"] = data(error.errors(include_input=False, include_url=False))
        else:
            details["message"] = str(error)
    return details


def trace(name, input_value, operation, output_fn=data, after=None):
    if STEP.get() is None:
        return operation()
    call_id = append_event({"event": "call", "component": name, "input": input_value})
    started = time.monotonic()
    try:
        result = operation()
    except Exception as error:
        append_event({"event": "error", "component": name, "call_id": call_id,
                      "elapsed_seconds": round(time.monotonic() - started, 4), "error": error_data(error)})
        raise
    record = {"event": "return", "component": name, "call_id": call_id,
              "elapsed_seconds": round(time.monotonic() - started, 4), "output": output_fn(result)}
    if after:
        record["mutated_arguments"] = after()
    append_event(record)
    return result


def observe(owner, attribute, *, label=None, method=False, context=False, mutations=()):
    original = getattr(owner, attribute)
    signature = inspect.signature(original)
    name = label or f"{owner.__name__.rsplit('.', 1)[-1]}.{attribute}"

    @functools.wraps(original)
    def observed(*args, **kwargs):
        bound = dict(signature.bind(*args, **kwargs).arguments)
        if method:
            bound.pop("self")
        if context and isinstance(bound.get("context"), str):
            bound["context"] = json.loads(bound["context"])
        after = (lambda: {key: data(bound[key]) for key in mutations}) if mutations else None
        return trace(name, data(bound), lambda: original(*args, **kwargs), after=after)

    setattr(owner, attribute, observed)


class InterviewLogs(logging.Handler):
    def emit(self, record):
        message = record.getMessage()
        if STEP.get() and (message.startswith("interview.") or record.levelno >= logging.WARNING):
            if record.name.endswith(".workflow") and message.startswith("Falling back to template"):
                message = message.split("):", maxsplit=1)[0] + ")"
            append_event({"event": "log", "logger": record.name, "level": record.levelname, "message": message})


def observe_model():
    from dspy._vendor.lm15.serde import request_to_dict, response_to_dict
    from dspy.clients import execution

    original = execution.execute

    def completion(result):
        responses = [response_to_dict(response) for response in result.responses]
        for response in responses:
            if "parts" in response.get("message", {}):
                response["message"]["parts"] = [part for part in response["message"]["parts"]
                                                if part.get("type") != "thinking"]
        return data({"responses": responses, "usage": result.usage, "cost": result.cost,
                     "response_model": result.response_model, "cache_hit": result.cache_hit})

    @functools.wraps(original)
    def execute(lm, call):
        request = request_to_dict(call.request)
        safe_fields = ("model", "messages", "config", "system", "format")
        visible = {key: request[key] for key in safe_fields if key in request}
        return trace("dspy.execution.execute", data(visible), lambda: original(lm, call), output_fn=completion)

    execution.execute = execute


def install():
    from adaptive_questioning.evidence import assessment, lifecycle, planning, provider, reporting, workflow

    handler = InterviewLogs()
    for name in ("uvicorn.error", workflow.__name__, planning.__name__):
        logger = logging.getLogger(name)
        logger.setLevel(logging.INFO)
        logger.addHandler(handler)
    observe_model()
    for name in ("blueprint", "opening_greeting", "question", "review_question", "judge", "closing_farewell"):
        observe(provider.DSPyAssessmentProvider, name, method=True, context=True)
    for name in ("requirements_for", "plan", "select_mode"):
        observe(planning, name)
    for name in ("build", "_prepare_batch", "_generate_batch", "validate"):
        observe(planning.BlueprintBuilder, name, method=True)
    for owner, name, mutations in (
        (assessment, "validate_judgment", ("judgment",)), (assessment, "record_progress", ("state",)),
        (assessment, "assess", ()), (workflow, "validate_judgment", ("judgment",)),
        (workflow, "apply_judgment", ("state",)), (workflow, "next_action", ("state",)),
        (workflow, "standalone_inability", ()), (workflow, "question_errors", ()),
        (workflow, "check_coding_answer", ()),
        (lifecycle, "begin", ()), (lifecycle, "close", ("snapshot",)), (reporting, "report", ()),
    ):
        observe(owner, name, mutations=mutations)
    for name, mutations in (("_advance", ("snapshot",)), ("_should_yield", ()), ("_reallocate", ("snapshot",)),
                            ("_question_context", ()), ("_question_attempt", ()), ("_finish", ("snapshot",))):
        observe(workflow.EvidenceWorkflow, name, method=True, mutations=mutations)
    workflow.plan = planning.plan
    workflow.select_mode = planning.select_mode


def build_request(command):
    operation = command["operation"]
    if operation == "start":
        return command["payload"]
    previous = json.loads((RUN / "http" / f"{command['from']}.json").read_text(encoding="utf-8"))
    snapshot = previous["response"]["body"]["snapshot"]
    payload = {"snapshot": snapshot, "expected_state_version": snapshot["state_version"]}
    if operation == "respond":
        payload.update(turn_id=snapshot["pending_turn"]["turn_id"], candidate_response=command["answer"])
    else:
        payload.update(message_id=snapshot["conversation"]["message"]["message_id"], action=command["action"])
        if "introduction" in command:
            payload["introduction"] = command["introduction"]
    return payload


def execute(client, path):
    command = json.loads(path.read_text(encoding="utf-8-sig"))
    payload = build_request(command)
    route = f"/api/v2/interview/{command['operation']}"
    request = client.build_request("POST", route, json=payload)
    token = STEP.set(path.stem)
    started, clock = now(), time.monotonic()
    try:
        response = client.send(request)
        try:
            body = response.json()
        except ValueError:
            body = response.text
        write_json(RUN / "http" / path.name, {
            "step": path.stem, "started_at_utc": started, "completed_at_utc": now(),
            "elapsed_seconds": round(time.monotonic() - clock, 3),
            "scenario": command.get("scenario"), "snapshot_source_step": command.get("from"),
            "request": {"method": request.method, "path": route, "body": json.loads(request.content)},
            "response": {"status": response.status_code, "body": body},
        })
    finally:
        STEP.reset(token)


def serve():
    import importlib.metadata
    from fastapi.testclient import TestClient
    from app.main import app

    (RUN / "http").mkdir(parents=True, exist_ok=True)
    INBOX.mkdir(exist_ok=True)
    install()
    with TestClient(app, raise_server_exceptions=False) as client:
        files = sorted(Path("adaptive_questioning/evidence").glob("*.py"))
        write_json(RUN / "runtime.json", {
            "started_at_utc": now(), "entrypoint": "app.main:app", "transport": "FastAPI TestClient / ASGI",
            "health": client.get("/health").json(),
            "versions": {name: importlib.metadata.version(name) for name in ("fastapi", "httpx", "dspy", "pydantic", "litellm")},
            "sources_sha256": {path.as_posix(): hashlib.sha256(path.read_bytes()).hexdigest() for path in files},
        })
        while not (INBOX / "stop").exists():
            for path in sorted(INBOX.glob("*.json")):
                if not (RUN / "http" / path.name).exists():
                    command = json.loads(path.read_text(encoding="utf-8-sig"))
                    if source := command.get("from"):
                        previous = RUN / "http" / f"{source}.json"
                        if not previous.exists():
                            continue
                        saved = json.loads(previous.read_text(encoding="utf-8"))
                        if saved["response"]["status"] != 200:
                            continue
                    execute(client, path)
            time.sleep(0.25)


def status(step):
    path = RUN / "http" / f"{step}.json"
    if not path.exists():
        print("PENDING")
        return
    row = json.loads(path.read_text(encoding="utf-8"))
    payload = row["response"]["body"]
    summary = {key: row[key] for key in ("step", "elapsed_seconds", "scenario")}
    summary["status"] = row["response"]["status"]
    if summary["status"] != 200:
        summary["error"] = payload
    else:
        s = payload["snapshot"]
        summary.update(version=s["state_version"], phase=(s["conversation"] or {}).get("phase"),
                       message=(s["conversation"] or {}).get("message"),
                       answered=len(s["turns"]), pending=s["pending_turn"], termination=s["termination_reason"],
                       objectives=[{key: state[key] for key in ("selected_mode", "assessment", "lifecycle", "turns_spent",
                                                                "stop_reason", "excluded_reason")}
                                   | {"skill": state["objective"]["skill_id"], "depth": state["objective"]["target_depth"]}
                                   for state in s["objectives"].values()],
                       latest_judgment=s["turns"][-1]["judgment"] if s["turns"] else None)
        pending = s["pending_turn"]
        if pending:
            state = s["objectives"][pending["objective_id"]]
            summary["probe_reason"] = state["probe_reason"]
            summary["target_criteria"] = [item for item in state["objective"]["criteria"]
                                          if item["criterion_id"] in pending["question"]["criterion_ids"]]
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    if sys.argv[1] == "serve":
        serve()
    else:
        status(sys.argv[2])
