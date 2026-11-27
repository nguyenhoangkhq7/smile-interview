"""Verify generic Python/JavaScript/SQL code sandbox execution and dry-run isolation."""
import json
import shutil

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from adaptive_questioning.evidence.code_runner import (
    CodingCaseResult, CodingSpec, CodingTestCase, ExecutionResult, LocalSubprocessCodeRunner,
)
from adaptive_questioning.evidence.coding_verification import (
    check_coding_answer, is_sandbox_environment_error, run_sample_code, sanitize_coding_spec,
)
from adaptive_questioning.evidence.models import Action, Mode, Question, TransitionRequest, Turn
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


def test_python_local_runner_supports_dict_kwargs_and_bytes():
    runner = LocalSubprocessCodeRunner()
    cases = [
        CodingTestCase(name="dict_input", input_data='{"user_id": "u9", "data": "Nam"}', expected_output='"u9:Nam"'),
        CodingTestCase(name="list_input", input_data='["u1", "An"]', expected_output='"u1:An"'),
    ]
    res = runner.execute(
        language="python",
        code="def format_user(user_id, data):\n    return f'{user_id}:{data}'.encode('utf-8')\n",
        entry_point="format_user",
        cases=cases,
    )
    assert res.passed == 2 and res.total == 2


def test_sanitize_coding_spec_keeps_curated_and_strips_unsupported():
    def make_q(spec: CodingSpec) -> Question:
        return Question(
            text="Hãy viết hàm xử lý dữ liệu theo yêu cầu.",
            criterion_ids=["c1"],
            mode=Mode.CODING,
            depth=2,
            evidence_scope="cache",
            coding_spec=spec,
        )

    redis_q = make_q(CodingSpec(
        language="python",
        entry_point="save_user",
        starter_code="import redis\ndef save_user(uid, data):\n    pass\n",
        sample_tests=[CodingTestCase(name="c1", input_data='["1","a"]', expected_output='"a"')],
    ))
    assert sanitize_coding_spec(redis_q).coding_spec is not None

    psycopg_q = make_q(CodingSpec(
        language="python",
        entry_point="fetch_user",
        starter_code="import psycopg2\ndef fetch_user(uid):\n    pass\n",
        sample_tests=[CodingTestCase(name="c1", input_data="1", expected_output="null")],
    ))
    assert sanitize_coding_spec(psycopg_q).coding_spec is None

    express_q = make_q(CodingSpec(
        language="javascript",
        entry_point="handler",
        starter_code="const express = require('express');\nfunction handler(req) { return req; }\n",
        sample_tests=[CodingTestCase(name="c1", input_data="{}", expected_output="{}")],
    ))
    assert sanitize_coding_spec(express_q).coding_spec is None

    pg_sql_q = make_q(CodingSpec(
        language="sql",
        setup_sql="CREATE EXTENSION IF NOT EXISTS pg_trgm; CREATE TABLE t(id SERIAL PRIMARY KEY);",
        sample_tests=[CodingTestCase(name="c1", input_data="", expected_output="[]")],
    ))
    assert sanitize_coding_spec(pg_sql_q).coding_spec is None

    sqlite_q = make_q(CodingSpec(
        language="sql",
        setup_sql="CREATE TABLE t(id INT); INSERT INTO t VALUES (1);",
        sample_tests=[CodingTestCase(name="c1", input_data="", expected_output="[[1]]")],
    ))
    assert sanitize_coding_spec(sqlite_q).coding_spec is not None


def test_sandbox_env_errors_do_not_auto_fail_and_emit_dry_run_notice():
    class _StubRunner:
        def __init__(self, outcome: ExecutionResult):
            self.outcome = outcome

        def execute(self, **_kwargs) -> ExecutionResult:
            return self.outcome

    spec = CodingSpec(
        language="python",
        entry_point="fn",
        sample_tests=[CodingTestCase(name="t1", input_data="1", expected_output="2")],
    )
    q = Question(
        text="Viết hàm fn(x).",
        criterion_ids=["c1"],
        mode=Mode.CODING,
        depth=2,
        evidence_scope="fn",
        coding_spec=spec,
    )
    turn = Turn(
        turn_id="t1",
        objective_id="obj1",
        skill_id="python",
        action=Action.INITIAL,
        mode=Mode.CODING,
        question_depth=2,
        question=q,
        answer="import some_external_sdk\ndef fn(x): return x + 1\n",
    )

    missing_mod = ExecutionResult(
        language="python",
        passed=0,
        total=1,
        results=[CodingCaseResult(
            name="t1", passed=False,
            error="ModuleNotFoundError: No module named 'some_external_sdk'",
        )],
    )
    assert is_sandbox_environment_error(missing_mod) is True
    assert check_coding_answer(turn, "TEXT", runner=_StubRunner(missing_mod)) is None

    dry_run = run_sample_code(code=turn.answer or "", spec=spec, runner=_StubRunner(missing_mod))
    assert "Môi trường chạy thử cô lập" in dry_run.environment_notice

    real_bug = ExecutionResult(
        language="python",
        passed=0,
        total=1,
        results=[CodingCaseResult(name="t1", passed=False, actual_output="3", expected_output="2")],
    )
    assert is_sandbox_environment_error(real_bug) is False
    checked = check_coding_answer(turn, "TEXT", runner=_StubRunner(real_bug))
    assert checked is not None and checked.passed == 0 and checked.total == 1
    dry_bug = run_sample_code(code="def fn(x): return x + 2", spec=spec, runner=_StubRunner(real_bug))
    assert dry_bug.environment_notice == ""


def test_text_coding_turn_accepts_submitted_code_even_when_requires_code_is_false(setup, monkeypatch):
    provider, engine, _ = setup
    original_question = provider.question

    def coding_without_requires_code(context):
        q = original_question(context)
        q.mode = Mode.CODING
        q.requires_code = False
        q.coding_spec = None
        return q

    monkeypatch.setattr(provider, "question", coding_without_requires_code)
    task = JobTask(description="Implement a Python Redis cache helper", evidence_spans=["Implement Redis helper"], required_level=2)
    started = start(
        engine,
        [skill("redis", job_tasks=[task])],
        interaction_mode="TEXT",
        focused_question_mode="CODING",
        max_questions=2,
        duration_seconds=600,
    )
    pending = started.public.pending_turn
    assert pending is not None and pending.mode == Mode.CODING and pending.requires_code is False

    answered = engine.respond(TransitionRequest(
        snapshot=started.snapshot,
        expected_state_version=started.snapshot.state_version,
        turn_id=pending.turn_id,
        candidate_response="",
        submitted_code="def save_and_get(k, v):\n    return v\n",
    ))
    assert len(answered.public.turns) == 1
    assert answered.public.turns[0].submitted_code == "def save_and_get(k, v):\n    return v\n"
