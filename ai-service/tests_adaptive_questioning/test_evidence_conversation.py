"""Feedback precedes the next task without changing the assessed question."""
import json

import pytest

from adaptive_questioning.evidence.conversation import ACKNOWLEDGMENT, MAX_FEEDBACK_LENGTH
from adaptive_questioning.evidence.models import Action, Question, Snapshot
from adaptive_questioning.evidence.reporting import public_session
from adaptive_questioning.evidence.question_validation import question_errors
from test_evidence_workflow import setup, start, answer, skill

FEEDBACK = "Bạn đã đề cập việc kiểm tra kế hoạch thực thi."


@pytest.mark.parametrize("response", ["tôi không biết", "Dạ, em chưa biết ạ."])
def test_standalone_inability_gets_one_simpler_probe(setup, monkeypatch, response):
    provider, engine, _ = setup
    monkeypatch.setattr(provider, "judge", lambda _: pytest.fail("An unambiguous admission needs no judge"))
    initial = start(engine).snapshot
    result = answer(engine, initial, response)
    assert result.snapshot.turns[-1].judgment.inability_excerpt == response
    assert result.public.pending_turn.introduction == result.public.turns[-1].feedback == "Cảm ơn bạn đã chia sẻ."
    assert result.snapshot.pending_turn.action == Action.EASIER
    assert result.snapshot.pending_turn.question_depth < initial.pending_turn.question_depth
    assert answer(engine, result.snapshot, response).snapshot.pending_turn is None


def test_partial_answer_after_admission_is_still_assessed(setup):
    _, engine, _ = setup
    result = answer(engine, start(engine).snapshot, "Tôi không biết cú pháp, nhưng sẽ kiểm tra log trước.")
    assert result.snapshot.turns[-1].judgment.observations[0].observation == "SUPPORTS"


def test_clarifying_an_easier_answer_keeps_its_depth_and_case(setup):
    provider, engine, _ = setup
    task = "Diagnose slow SQL queries"
    initial = start(engine, [skill(job_tasks=[
        {"description": task, "required_level": 4, "evidence_spans": [task]},
    ])]).snapshot
    assert initial.pending_turn.question_depth == 3
    easier = answer(engine, initial, "Em chưa biết.").snapshot
    assert easier.pending_turn.question_depth == 2
    provider.observation, provider.performance = "UNCLEAR", "UNDETERMINED"
    clarification = answer(engine, easier, "Em sẽ xem đầu vào.").snapshot
    assert clarification.pending_turn.action == Action.CLARIFY
    assert clarification.pending_turn.question_depth == easier.pending_turn.question_depth
    assert clarification.pending_turn.question.evidence_scope == easier.pending_turn.question.evidence_scope
    provider.observation, provider.performance = "SUPPORTS", "AT_TARGET"
    recovered = answer(engine, clarification, "Em sẽ thử chuỗi rỗng.").snapshot
    assert recovered.pending_turn.action == Action.FOLLOW_UP
    assert recovered.pending_turn.question_depth == initial.pending_turn.question_depth
    assert not recovered.objectives[initial.pending_turn.objective_id].criterion_results


def test_feedback_can_be_omitted(setup, monkeypatch):
    provider, engine, _ = setup
    provider.criterion_count = 2
    initial = start(engine).snapshot
    original = provider.judge

    def judge(context):
        judgment = original(context)
        judgment.feedback = ""
        return judgment

    monkeypatch.setattr(provider, "judge", judge)
    result = answer(engine, initial)
    assert result.public.pending_turn.introduction == ""
    assert not result.public.turns[-1].feedback


def test_external_tool_assignment_is_rejected(setup):
    _, engine, _ = setup
    turn = start(engine).snapshot.pending_turn
    question = Question.model_validate(turn.question.model_dump() | {"mode": turn.mode, "depth": turn.question_depth})
    context = {"required_question_contract": {
        "mode": question.mode, "depth": question.depth, "criterion_ids": question.criterion_ids,
    }}
    question.text = "Hãy thử dùng ChatGPT để tạo hàm kiểm tra email. Sau đó, hãy mô tả cách kiểm tra kết quả."
    errors = question_errors(question, context)
    assert len(errors) == 2
    question.text = "ChatGPT cho rằng địa chỉ an@ hợp lệ. Theo bạn, kết quả này sai ở đâu?"
    assert not question_errors(question, context)


def feedback_provider(provider, monkeypatch):
    original = provider.judge

    def judge(context):
        judgment = original(context)
        judgment.feedback = FEEDBACK
        return judgment

    monkeypatch.setattr(provider, "judge", judge)


def test_first_question_does_not_comment_on_a_nonexistent_answer(setup):
    _, engine, _ = setup
    result = start(engine)
    assert result.public.pending_turn.introduction == ""
    assert result.snapshot.pending_turn.introduction == ""


@pytest.mark.parametrize(("observation", "performance", "action"), [
    ("UNCLEAR", "UNDETERMINED", Action.CLARIFY),
    ("CONTRADICTS", "BELOW", Action.EASIER),
])
def test_feedback_precedes_followup_and_survives_reload(setup, monkeypatch, observation, performance, action):
    provider, engine, _ = setup
    feedback_provider(provider, monkeypatch)
    provider.observation, provider.performance = observation, performance
    initial = start(engine).snapshot
    saved = initial.model_dump_json()
    result = answer(engine, initial)
    assert result.snapshot.pending_turn.action == action
    introduction = result.public.pending_turn.introduction
    assert introduction == FEEDBACK
    assert FEEDBACK not in result.public.pending_turn.question
    assert result.public.turns[0].feedback == FEEDBACK
    assert len(result.snapshot.turns) == 1
    restored = Snapshot.model_validate_json(result.snapshot.model_dump_json())
    assert public_session(restored).pending_turn.introduction == introduction
    assert initial.model_dump_json() == saved


def test_switching_criteria_leaves_question_to_introduce_new_aspect(setup, monkeypatch):
    provider, engine, _ = setup
    provider.criterion_count = 2
    feedback_provider(provider, monkeypatch)
    result = answer(engine, start(engine).snapshot)
    assert result.public.pending_turn.introduction == FEEDBACK
    assert result.snapshot.pending_turn.question.criterion_ids != result.snapshot.turns[-1].question.criterion_ids


def test_switching_skills_acknowledges_the_actual_previous_answer(setup, monkeypatch):
    provider, engine, _ = setup
    feedback_provider(provider, monkeypatch)
    initial = start(
        engine,
        [
            skill(importance_weight=0.9),
            skill("sql_optimization", jd_skill_name="SQL Optimization", importance_weight=0.8),
        ],
    ).snapshot
    result = answer(engine, initial)
    skills_by_objective = {o.objective_id: o.skill_id for o in result.public.report.objectives}
    next_skill = skills_by_objective[result.public.pending_turn.objective_id]
    assert result.public.pending_turn.introduction == f"{FEEDBACK}\n\nTiếp theo, mình chuyển sang trao đổi về SQL Optimization nhé."
    assert next_skill != initial.pending_turn.skill_id
    assert "introduction" not in result.public.turns[0].model_dump()
    assert "skill_id" not in result.public.turns[0].model_dump()
    assert "skill_id" not in result.public.pending_turn.model_dump()


def test_hint_is_not_repeated_in_the_introduction_or_public_feedback(setup, monkeypatch):
    provider, engine, _ = setup
    provider.criterion_count = 2
    original = provider.judge

    def judge(context):
        result = original(context)
        result.feedback, result.feedback_contains_hint = "Đáp án cần dùng secret_solution.", True
        return result

    monkeypatch.setattr(provider, "judge", judge)
    result = answer(engine, start(engine).snapshot)
    assert result.public.turns[0].feedback == ACKNOWLEDGMENT
    assert result.public.pending_turn.introduction.startswith(ACKNOWLEDGMENT)
    assert "secret_solution" not in result.public.model_dump_json()


def test_overlong_feedback_uses_acknowledgment_without_regrading(setup, monkeypatch):
    provider, engine, _ = setup
    provider.criterion_count = 2
    original = provider.judge
    calls = []

    def judge(context):
        calls.append(json.loads(context))
        result = original(context)
        result.feedback = "x" * (MAX_FEEDBACK_LENGTH + 1) if len(calls) == 1 else FEEDBACK
        return result

    monkeypatch.setattr(provider, "judge", judge)
    result = answer(engine, start(engine).snapshot)
    assert len(calls) == 1
    assert len(result.snapshot.turns) == 1
    assert result.snapshot.turns[0].judgment.feedback == ACKNOWLEDGMENT
    assert result.snapshot.turns[0].judgment.observations[0].performance == "AT_TARGET"
    assert result.public.pending_turn.introduction.startswith(ACKNOWLEDGMENT)
