"""Regression coverage for previously observed grading and question defects."""

import json

import dspy
import pytest

from adaptive_questioning.evidence.models import Assessment
from adaptive_questioning.evidence.provider import DSPyAssessmentProvider
from skill_gap.domain.models import JobTask
from test_evidence_workflow import answer, setup, skill, start


EVENT_TASK = ("Hãy viết hàm Python `deduplicate_events(events)` nhận danh sách dict có khóa `event_id`. "
              "Giữ bản ghi xuất hiện đầu tiên của mỗi mã và duy trì thứ tự ban đầu.")
LAST_RECORD = ("def deduplicate_events(events):\n"
               "    by_id = {event['event_id']: event for event in events}\n"
               "    return list(by_id.values())")
FIRST_RECORD = ("def deduplicate_events(events):\n"
                "    seen = {}\n"
                "    for event in events:\n"
                "        seen.setdefault(event['event_id'], event)\n"
                "    return list(seen.values())")


def start_coding(provider, engine, monkeypatch, **config):
    generate = provider.question

    def draft(context):
        question = generate(context)
        if json.loads(context)["action"] == "INITIAL":
            question.text = EVENT_TASK
        return question

    monkeypatch.setattr(provider, "question", draft)
    task = JobTask(description=EVENT_TASK, evidence_spans=[EVENT_TASK], required_level=3)
    return start(engine, [skill("python", job_tasks=[task])], **config).snapshot


def test_duplicate_payload_counterexample_prevents_false_pass(setup, monkeypatch):
    provider, engine, _ = setup
    snapshot = start_coding(provider, engine, monkeypatch)
    monkeypatch.setattr(provider, "judge", lambda _: pytest.fail("A verified mismatch needs no model judgment"))
    text = LAST_RECORD + "\n\nEm dùng dict để giữ thứ tự chèn."

    result = answer(engine, snapshot, text)

    record = result.snapshot.turns[0].judgment.observations[0]
    assert (record.observation, record.performance) == ("CONTRADICTS", "BELOW")
    assert record.response_excerpt.rstrip() == LAST_RECORD
    assert "1/3" in record.rationale
    assert result.public.report.objectives[0].assessment == Assessment.INSUFFICIENT
    assert result.snapshot.pending_turn.action == "ASK_EASIER"


@pytest.mark.parametrize(("code", "interaction_mode", "expected_cases"), [
    (FIRST_RECORD, "TEXT", {"passed": 3, "total": 3}),
    ("```python\r\n" + FIRST_RECORD.replace("\n", "\r\n") + "\r\n```", "TEXT", {"passed": 3, "total": 3}),
    ("def deduplicate_events(events):\n    raise RuntimeError('unsupported')", "TEXT", None),
    ("def deduplicate_events(events):\n    for event in events:\n        events.append(event)", "TEXT", None),
    (LAST_RECORD, "VOICE", None),
])
def test_passed_checks_are_evidence_and_unsupported_submissions_use_judge(
    setup, monkeypatch, code, interaction_mode, expected_cases,
):
    provider, engine, _ = setup
    snapshot = start_coding(provider, engine, monkeypatch, interaction_mode=interaction_mode)
    original = provider.judge
    contexts = []

    def judge(context):
        contexts.append(json.loads(context))
        return original(context)

    monkeypatch.setattr(provider, "judge", judge)
    answer(engine, snapshot, code)
    assert len(contexts) == 1
    assert contexts[0].get("coding_checks") == expected_cases


def test_answer_embedded_in_question_is_repaired(setup, monkeypatch):
    provider, engine, _ = setup
    generate = provider.question
    rejected = "Hãy đề xuất một câu lệnh SQL tạo composite index cho truy vấn sau: lọc theo status và sắp xếp theo created_at."
    replacement = "Truy vấn lọc đơn theo status và sắp xếp theo created_at. Bạn sẽ tạo chỉ mục nào?"
    reviews = []

    def draft(context):
        question = generate(context)
        data = json.loads(context)
        if "validation_error" in data:
            assert data["rejected_draft"] == rejected
            assert "Remove the method" in data["validation_error"]
        question.text = replacement if "validation_error" in data else rejected
        return question

    def review(context):
        question = json.loads(context)["question"]
        reviews.append(question)
        return "GIVES_SOLUTION" if question == rejected else "ALIGNED"

    monkeypatch.setattr(provider, "question", draft)
    monkeypatch.setattr(provider, "review_question", review)
    assert start(engine).public.pending_turn.question == replacement
    assert reviews == [rejected, replacement]


def test_above_grade_is_capped_when_extension_was_not_asked(setup):
    provider, engine, _ = setup
    provider.performance = "ABOVE"
    result = answer(engine, start(engine).snapshot)
    assert result.snapshot.turns[0].judgment.observations[0].performance == "AT_TARGET"
    assert result.public.report.objectives[0].evidence[0].performance == "AT_TARGET"


def test_structured_judge_uses_json_adapter_on_first_invocation():
    lm = dspy.utils.DummyLM([{"plan": "No observations to record", "reasoning": "No observations to record", "assessment": {"observations": []}}])
    lm.adapter = dspy.JSONAdapter()
    provider = DSPyAssessmentProvider(lm=lm)
    original = provider.judge_module

    def judge(*, context):
        assert isinstance(dspy.settings.adapter, dspy.JSONAdapter)
        return original(context=context)

    provider.judge_module = judge
    assert provider.judge("{}").feedback == ""
    assert len(lm.history) == 1
