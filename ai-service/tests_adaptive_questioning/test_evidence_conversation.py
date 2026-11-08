"""Feedback precedes the next task without changing the assessed question."""
import json

import pytest

from adaptive_questioning.evidence.conversation import ACKNOWLEDGMENT, MAX_FEEDBACK_LENGTH
from adaptive_questioning.evidence.models import Action, Snapshot
from adaptive_questioning.evidence.reporting import public_session
from test_evidence_workflow import setup, start, answer, skill

FEEDBACK = "Bạn đã đề cập việc kiểm tra kế hoạch thực thi."


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


@pytest.mark.parametrize(("observation", "performance", "action", "bridge"), [
    ("UNCLEAR", "UNDETERMINED", Action.CLARIFY, "làm rõ thêm một ý"),
    ("CONTRADICTS", "BELOW", Action.EASIER, "tình huống đơn giản hơn"),
])
def test_feedback_precedes_followup_and_survives_reload(setup, monkeypatch, observation, performance, action, bridge):
    provider, engine, _ = setup
    feedback_provider(provider, monkeypatch)
    provider.observation, provider.performance = observation, performance
    initial = start(engine).snapshot
    saved = initial.model_dump_json()
    result = answer(engine, initial)
    assert result.snapshot.pending_turn.action == action
    introduction = result.public.pending_turn.introduction
    assert introduction.startswith(FEEDBACK + "\n\n")
    assert bridge in introduction
    assert FEEDBACK not in result.public.pending_turn.question
    assert result.public.turns[0].feedback == FEEDBACK
    assert len(result.snapshot.turns) == 1
    restored = Snapshot.model_validate_json(result.snapshot.model_dump_json())
    assert public_session(restored).pending_turn.introduction == introduction
    assert initial.model_dump_json() == saved


def test_switching_criteria_introduces_another_aspect(setup, monkeypatch):
    provider, engine, _ = setup
    provider.criterion_count = 2
    feedback_provider(provider, monkeypatch)
    result = answer(engine, start(engine).snapshot)
    assert result.public.pending_turn.introduction.startswith(FEEDBACK)
    assert "khía cạnh khác" in result.public.pending_turn.introduction
    assert result.snapshot.pending_turn.question.criterion_ids != result.snapshot.turns[-1].question.criterion_ids


def test_switching_skills_acknowledges_the_actual_previous_answer(setup, monkeypatch):
    provider, engine, _ = setup
    feedback_provider(provider, monkeypatch)
    initial = start(engine, [skill(), skill("java")]).snapshot
    result = answer(engine, initial)
    next_skill = result.public.pending_turn.skill_id
    assert result.public.pending_turn.introduction == f"{FEEDBACK}\n\nTiếp theo, mình chuyển sang trao đổi về {next_skill} nhé."
    assert next_skill != initial.pending_turn.skill_id


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


def test_overlong_feedback_is_retried_without_an_extra_interview_turn(setup, monkeypatch):
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
    assert len(calls) == 2
    assert "300 characters" in calls[1]["validation_error"]
    assert len(result.snapshot.turns) == 1
    assert result.public.pending_turn.introduction.startswith(FEEDBACK)


def test_legacy_snapshots_default_introductions_and_accept_old_feedback(setup):
    provider, engine, _ = setup
    provider.criterion_count = 2
    result = answer(engine, start(engine).snapshot)
    value = result.snapshot.model_dump(mode="json")
    value["pending_turn"].pop("introduction")
    value["turns"][0].pop("introduction")
    value["turns"][0]["judgment"]["feedback"] = "x" * 1000
    restored = Snapshot.model_validate(value)
    assert public_session(restored).pending_turn.introduction == ""
    assert public_session(restored).turns[0].feedback == ACKNOWLEDGMENT
