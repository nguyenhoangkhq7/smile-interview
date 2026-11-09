"""Provider contract failures are retried, never converted into candidate performance."""
import json
import unicodedata

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from adaptive_questioning.evidence.errors import JudgmentUnavailableError
from adaptive_questioning.evidence.models import Judgment, Snapshot
from adaptive_questioning.evidence.excerpts import source_excerpt, source_lines
from adaptive_questioning.evidence.routes import router
from test_evidence_workflow import setup, start, answer


@pytest.mark.parametrize("failure", ["missing", "extra", "duplicate", "renamed", "schema", "quote"])
def test_invalid_judgment_is_retried_with_exact_targets_without_double_counting(setup, monkeypatch, failure):
    provider, engine, _ = setup
    provider.limit_criteria = True
    initial = start(engine).snapshot
    original = initial.model_dump_json()
    original_judge = provider.judge
    calls = []

    def judge(context):
        values = json.loads(context)
        calls.append(values)
        valid = original_judge(context)
        if len(calls) > 1:
            return valid
        if failure == "schema":
            return Judgment.model_validate({"observations": "not a list"})
        broken = valid.model_copy(deep=True)
        if failure == "missing":
            broken.observations = []
        elif failure == "extra":
            state = initial.objectives[initial.pending_turn.objective_id]
            unused = next(c.criterion_id for c in state.objective.criteria if c.criterion_id not in initial.pending_turn.question.criterion_ids)
            broken.observations.append(broken.observations[0].model_copy(update={"criterion_id": unused}))
        elif failure == "duplicate":
            broken.observations.append(broken.observations[0].model_copy())
        elif failure == "renamed":
            broken.observations[0].criterion_id = "invented-criterion"
        elif failure == "quote":
            broken.observations[0].response_excerpt = "invented excerpt"
        return broken

    monkeypatch.setattr(provider, "judge", judge)
    result = answer(engine, initial)
    assert len(calls) == 2
    expected = initial.pending_turn.question.criterion_ids
    for context in calls:
        assert context["required_criterion_ids"] == expected
        assert [c["criterion_id"] for c in context["target_criteria"]] == expected
        assert [c["criterion_id"] for c in context["objective"]["criteria"]] == expected
        assert context["turn"]["answer"] == "EXPLAIN ANALYZE"
    assert "validation_error" in calls[1]
    if failure == "quote":
        assert calls[1]["previous_invalid_judgment"]["observations"][0]["response_excerpt"] == "invented excerpt"
        assert "ONE contiguous passage" in calls[1]["validation_error"]
    assert result.snapshot.state_version == initial.state_version + 1
    assert len(result.snapshot.turns) == 1
    assert result.snapshot.objectives[initial.pending_turn.objective_id].turns_spent == 1
    assert initial.model_dump_json() == original


def test_exhausted_judge_returns_503_and_same_answer_can_be_retried(setup, monkeypatch):
    provider, engine, _ = setup
    initial = start(engine).snapshot
    saved = initial.model_dump_json()
    original_judge = provider.judge
    calls = []

    def invalid(context):
        calls.append(json.loads(context))
        result = original_judge(context)
        result.observations = []
        return result

    monkeypatch.setattr(provider, "judge", invalid)
    app = FastAPI()
    app.include_router(router)
    app.state.evidence_workflow = engine
    payload = {"snapshot": initial.model_dump(mode="json"), "turn_id": initial.pending_turn.turn_id,
               "expected_state_version": initial.state_version, "candidate_response": "EXPLAIN ANALYZE"}
    with TestClient(app) as client:
        response = client.post('/api/v2/interview/respond', json=payload)
        assert response.status_code == 503
        assert "chưa bị chấm điểm" in response.json()["detail"]
        assert "targeted criteria" not in response.json()["detail"]
        assert len(calls) == initial.policy.judgment_attempts
        assert initial.model_dump_json() == saved
        monkeypatch.setattr(provider, "judge", original_judge)
        retried = client.post('/api/v2/interview/respond', json=payload)
        assert retried.status_code == 200
        assert retried.json()["snapshot"]["state_version"] == initial.state_version + 1
        assert len(retried.json()["snapshot"]["turns"]) == 1


def test_judgment_retry_stops_at_deadline_without_mutating_input(setup, monkeypatch):
    provider, engine, now = setup
    initial = start(engine).snapshot
    saved = initial.model_dump_json()
    original_judge = provider.judge
    calls = []

    def invalid(context):
        calls.append(context)
        now[0] = initial.deadline_at
        result = original_judge(context)
        result.observations = []
        return result

    monkeypatch.setattr(provider, "judge", invalid)
    with pytest.raises(JudgmentUnavailableError):
        answer(engine, initial)
    assert len(calls) == 1
    assert initial.model_dump_json() == saved


def test_old_snapshots_default_to_bounded_judgment_retries(setup):
    _, engine, _ = setup
    value = start(engine).snapshot.model_dump(mode="json")
    del value["policy"]["judgment_attempts"]
    assert Snapshot.model_validate(value).policy.judgment_attempts == 2


@pytest.mark.parametrize("excerpt, response", [
    ("kiểm tra log", "Em sẽ kiểm tra log trước."),
    ("kiểm tra log", "Em sẽ kiểm\ntra  log trước."),
    ("kiểm tra log", "Em kiểm\ntra log."),
    ("kiểm tra log", unicodedata.normalize("NFD", "Em kiểm\ntra log.")),
    ("kiểm tra log", unicodedata.normalize("NFD", "Em sẽ kiểm tra log trước.")),
    ("  kiểm tra log  ", "Em sẽ kiểm tra log trước."),
])
def test_formatting_only_quotes_resolve_to_original_source(excerpt, response):
    resolved = source_excerpt(excerpt, response)
    assert resolved is not None
    assert resolved in response


@pytest.mark.parametrize("excerpt", [
    "kiểm tra log và CPU",  # added evidence
    "Em sẽ trước.",  # stitched passages
    "kiểm tra logs",  # corrected or changed word
    "kiem tra log",  # removed accents
    "KIỂM TRA LOG",  # case changes could change code/identifiers
    "kiểm tra log...",  # added punctuation
    "", " \n ",
])
def test_changed_or_invented_quotes_are_rejected(excerpt):
    assert source_excerpt(excerpt, "Em sẽ kiểm tra log trước.") is None


@pytest.mark.parametrize("inability", [False, True])
def test_formatting_repair_stores_original_evidence_without_retry(setup, monkeypatch, inability):
    provider, engine, _ = setup
    initial = start(engine).snapshot
    original_judge = provider.judge
    calls = []
    response = unicodedata.normalize("NFD", "Em chưa biết\n  cách kiểm tra log.")

    def judge(context):
        calls.append(context)
        result = original_judge(context)
        result.observations[0].response_excerpt = "cách kiểm tra log."
        if inability:
            result.explicit_inability = True
            result.inability_excerpt = "Em chưa biết cách kiểm tra log."
        return result

    monkeypatch.setattr(provider, "judge", judge)
    result = answer(engine, initial, response)
    assert len(calls) == 1
    judgment = result.snapshot.turns[0].judgment
    assert judgment.observations[0].response_excerpt in response
    if inability:
        assert judgment.inability_excerpt == response


def test_invented_quote_remains_an_error_and_preserves_answer(setup, monkeypatch):
    provider, engine, _ = setup
    initial = start(engine).snapshot
    saved = initial.model_dump_json()
    original_judge = provider.judge

    def judge(context):
        result = original_judge(context)
        result.observations[0].response_excerpt = "Em kiểm tra log và CPU."
        return result

    monkeypatch.setattr(provider, "judge", judge)
    with pytest.raises(JudgmentUnavailableError):
        answer(engine, initial, "Em kiểm tra log.")
    assert initial.model_dump_json() == saved


TODO_CODE = '''<!DOCTYPE html>
<html lang="vi">
<body>
    <input id="taskInput"><button onclick="addTask()">Thêm</button>
    <ul id="taskList"></ul>
    <script>
        const taskList = document.getElementById("taskList");
        let tasks = JSON.parse(localStorage.getItem("tasks")) || [];
        function saveTasks() {
            localStorage.setItem("tasks", JSON.stringify(tasks));
        }
        function render() {
            taskList.innerHTML = "";
            tasks.forEach((task, index) => {
                const li = document.createElement("li");
                li.innerHTML = `${task}<button onclick="deleteTask(${index})">Xóa</button>`;
                taskList.appendChild(li);
            });
        }
        function addTask() {
            const input = document.getElementById("taskInput");
            const task = input.value.trim();
            if (!task) return;
            tasks.push(task);
            saveTasks();
            render();
            input.value = "";
        }
        function deleteTask(index) {
            tasks.splice(index, 1);
            saveTasks();
            render();
        }
        render();
    </script>
</body>
</html>'''


def test_code_judgment_recovers_with_source_lines_and_long_feedback(setup, monkeypatch):
    provider, engine, _ = setup
    initial = start(engine).snapshot
    initial.pending_turn.question.text = "Viết trang HTML To-Do List với JavaScript, thêm, xóa và localStorage."
    saved = initial.model_dump_json()
    original = provider.judge
    calls = []

    def judge(context):
        values = json.loads(context)
        calls.append(values)
        result = original(context)
        result.feedback = "Nhận xét quá dài. " * 40
        # First output stitches separate statements; retry selects original lines.
        result.observations[0].response_excerpt = "tasks.push(task); tasks.splice(index, 1);"
        if len(calls) > 1:
            result.observations[0].response_excerpt = ""
            result.observations[0].response_line_range = (20, 33)
        return result

    monkeypatch.setattr(provider, "judge", judge)
    result = answer(engine, initial, TODO_CODE)
    assert len(calls) == 2
    assert calls[0]["answer_lines"][15] == {
        "line": 16, "text": '                li.innerHTML = `${task}<button onclick="deleteTask(${index})">Xóa</button>`;'}
    assert "response_line_range" in calls[1]["validation_error"]
    judgment = result.snapshot.turns[0].judgment
    assert judgment.observations[0].response_excerpt == source_lines((20, 33), TODO_CODE)
    assert judgment.observations[0].response_excerpt in TODO_CODE
    assert judgment.observations[0].performance == "AT_TARGET"
    assert len(judgment.feedback) <= 300
    assert len(result.snapshot.turns) == 1
    assert initial.model_dump_json() == saved


@pytest.mark.parametrize("line_range", [(0, 2), (-1, 2), (3, 2), (1, 999), (2, 2)])
def test_invalid_or_blank_source_line_ranges_remain_ungraded(setup, monkeypatch, line_range):
    provider, engine, _ = setup
    initial = start(engine).snapshot
    saved = initial.model_dump_json()
    original = provider.judge

    def judge(context):
        result = original(context)
        result.observations[0].response_line_range = line_range
        return result

    monkeypatch.setattr(provider, "judge", judge)
    with pytest.raises(JudgmentUnavailableError):
        answer(engine, initial, "const tasks = [];\n\nrender();")
    assert initial.model_dump_json() == saved


def test_source_lines_preserve_windows_newlines_and_code_punctuation():
    code = TODO_CODE.replace("\n", "\r\n")
    excerpt = source_lines((15, 17), code)
    assert excerpt in code
    assert '${task}<button onclick="deleteTask(${index})">Xóa</button>' in excerpt
    assert "\r\n" in excerpt
