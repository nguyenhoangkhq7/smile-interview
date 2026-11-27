"""Verify generic Python/JavaScript/SQL code sandbox execution and dry-run isolation."""
import json
import shutil

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from adaptive_questioning.evidence.code_runner import (
    CodingSpec, CodingTestCase, LocalSubprocessCodeRunner,
)
from adaptive_questioning.evidence.routes import router
from skill_gap.domain.models import JobTask
from test_evidence_workflow import setup, skill, start


def test_python_sandbox_executes_cases_syntax_errors_and_timeouts():
    runner = LocalSubprocessCodeRunner()
    cases = [
        CodingTestCase(name="basic", input_data="[1, 2, 3]", expected_output="6"),
        CodingTestCase(name="empty", input_data="[]", expected_output="0"),
    ]
    passed = runner.execute(language="python", code="def total(xs):\n    return sum(xs)\n", entry_point="total", cases=cases)
    assert passed.passed == 2 and passed.total == 2 and not passed.compile_error

    syntax_err = runner.execute(language="python", code="def total(xs)\n return 0", entry_point="total", cases=cases)
    assert syntax_err.passed == 0 and syntax_err.compile_error

    timed_out = runner.execute(
        language="python", code="def total(xs):\n    while True:\n        pass\n",
        entry_point="total", cases=cases[:1], timeout_seconds=0.4,
    )
    assert timed_out.passed == 0 and "thời gian" in timed_out.results[0].error.lower()


@pytest.mark.skipif(shutil.which("node") is None, reason="Node.js not installed on host")
def test_javascript_sandbox_executes_cases_and_syntax_errors():
    runner = LocalSubprocessCodeRunner()
    cases = [CodingTestCase(name="sum", input_data="[2, 5]", expected_output="7")]
    ok = runner.execute(language="javascript", code="function add(a, b) { return a + b; }", entry_point="add", cases=cases)
    assert ok.passed == 1 and ok.total == 1 and not ok.compile_error

    bad = runner.execute(language="javascript", code="function add(a, b { return a; }", entry_point="add", cases=cases)
    assert bad.passed == 0 and bad.compile_error


def test_sql_sandbox_executes_queries_and_blocks_forbidden_statements():
    runner = LocalSubprocessCodeRunner()
    setup_sql = "CREATE TABLE events(id INT, status TEXT); INSERT INTO events VALUES (1,'active'),(2,'done'),(3,'active');"
    cases = [CodingTestCase(name="active", input_data="", expected_output="[[1], [3]]")]

    ok = runner.execute(
        language="sql",
        code="SELECT id FROM events WHERE status = 'active' ORDER BY id;",
        setup_sql=setup_sql,
        cases=cases,
    )
    assert ok.passed == 1 and ok.total == 1

    blocked = runner.execute(language="sql", code="PRAGMA table_info(events);", setup_sql=setup_sql, cases=cases)
    assert blocked.passed == 0 and "không được phép" in blocked.results[0].error.lower()


def test_run_code_endpoint_hides_hidden_tests_and_preserves_state_version(setup, monkeypatch):
    provider, engine, _ = setup
    original_question = provider.question
    spec = CodingSpec(
        language="python",
        entry_point="double",
        starter_code="def double(n):\n    return 0\n",
        sample_tests=[CodingTestCase(name="sample1", input_data="4", expected_output="8")],
        hidden_tests=[CodingTestCase(name="secret1", input_data="-3", expected_output="-6")],
    )

    def with_spec(context):
        q = original_question(context)
        q.coding_spec = spec
        return q

    monkeypatch.setattr(provider, "question", with_spec)
    task = JobTask(description="Implement double(n) in Python", evidence_spans=["Implement double(n)"], required_level=2)
    started = start(engine, [skill("python", job_tasks=[task])])

    # Hidden tests must never leak through PendingTurn
    public_pending = started.public.pending_turn.model_dump()
    assert public_pending["coding_spec"]["entry_point"] == "double"
    assert "hidden_tests" not in public_pending["coding_spec"]
    assert "secret1" not in json.dumps(public_pending)

    app = FastAPI()
    app.include_router(router)
    app.state.evidence_workflow = engine
    with TestClient(app) as client:
        res = client.post("/api/v2/interview/run-code", json={
            "snapshot": started.snapshot.model_dump(mode="json"),
            "turn_id": started.snapshot.pending_turn.turn_id,
            "code": "def double(n):\n    return n * 2\n",
        })
        assert res.status_code == 200
        body = res.json()
        assert body["passed"] == 1 and body["total"] == 1
        assert [r["name"] for r in body["results"]] == ["sample1"]

        wrong_turn = client.post("/api/v2/interview/run-code", json={
            "snapshot": started.snapshot.model_dump(mode="json"),
            "turn_id": "stale-turn-id",
            "code": "def double(n):\n    return n * 2\n",
        })
        assert wrong_turn.status_code == 422
