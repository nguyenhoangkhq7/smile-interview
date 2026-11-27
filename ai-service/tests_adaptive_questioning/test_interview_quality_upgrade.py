"""Regression coverage for previously observed grading and question defects."""

import json

import dspy
import pytest

from adaptive_questioning.evidence.code_runner import CodingSpec, CodingTestCase
from adaptive_questioning.evidence.models import Action, Assessment, BlueprintDraft, CriterionDraft, Mode, ObjectiveDraft, SuitableMode
from adaptive_questioning.evidence.policy_config import InterviewPolicy
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


EVENT_SPEC = CodingSpec(
    language="python",
    entry_point="deduplicate_events",
    starter_code="def deduplicate_events(events):\n    pass\n",
    sample_tests=[
        CodingTestCase(name="empty", input_data="[]", expected_output="[]"),
        CodingTestCase(
            name="unique",
            input_data='[{"event_id":"B","value":10},{"event_id":"A","value":20}]',
            expected_output='[{"event_id":"B","value":10},{"event_id":"A","value":20}]',
        ),
    ],
    hidden_tests=[
        CodingTestCase(
            name="keep-first",
            input_data='[{"event_id":"B","value":10},{"event_id":"A","value":20},{"event_id":"B","value":30}]',
            expected_output='[{"event_id":"B","value":10},{"event_id":"A","value":20}]',
        ),
    ],
)


def start_coding(provider, engine, monkeypatch, **config):
    generate = provider.question

    def draft(context):
        question = generate(context)
        if json.loads(context)["action"] == "INITIAL":
            question.text = EVENT_TASK
            question.coding_spec = EVENT_SPEC
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


@pytest.mark.parametrize(("code", "interaction_mode", "expected_passed"), [
    (FIRST_RECORD, "TEXT", 3),
    ("```python\r\n" + FIRST_RECORD.replace("\n", "\r\n") + "\r\n```", "TEXT", 3),
    (LAST_RECORD, "VOICE", None),
])
def test_passed_checks_are_evidence_and_voice_without_code_uses_judge(
    setup, monkeypatch, code, interaction_mode, expected_passed,
):
    provider, engine, _ = setup
    snapshot = start_coding(provider, engine, monkeypatch, interaction_mode=interaction_mode)
    if interaction_mode == "VOICE":
        snapshot.pending_turn.question.requires_code = False
    original = provider.judge
    contexts = []

    def judge(context):
        contexts.append(json.loads(context))
        return original(context)

    monkeypatch.setattr(provider, "judge", judge)
    result = answer(engine, snapshot, code)
    checks = result.public.turns[0].coding_checks
    if expected_passed is None:
        assert checks is None
    else:
        assert checks is not None
        assert checks.passed == expected_passed and checks.total == 3
        assert len(checks.sample_results) == 2  # hidden test details stay private
    assert len(contexts) == 1


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


def test_coding_deeper_probe_omits_initial_dedup_guidance_and_guides_adaptation(setup, monkeypatch):
    provider, engine, _ = setup
    engine.policy = InterviewPolicy(allow_extension_probes=True)
    generate = provider.question
    question_contexts = []

    def blueprint(context):
        req_id, req = next(iter(json.loads(context)["requirements"].items()))
        return BlueprintDraft(objectives=[ObjectiveDraft(
            requirement_id=req_id,
            skill_id=req["skill_id"],
            target_depth=2,
            extension_depth=3,
            criteria=[CriterionDraft(
                description="Viết hàm khử trùng lặp event_id giữ thứ tự đầu tiên",
                expected_evidence="Cài đặt hàm giữ bản ghi đầu tiên theo event_id",
                below_target="Ghi đè bản ghi sau",
                at_target="Giữ bản ghi đầu tiên theo thứ tự đầu vào",
                above_target="Điều chỉnh cấu trúc dữ liệu khi dữ liệu lớn vượt RAM và nêu đánh đổi",
            )],
            suitable_modes=[SuitableMode(mode=Mode.CODING)],
        )])

    def capture_question(context):
        data = json.loads(context)
        question_contexts.append(data)
        question = generate(context)
        if data["action"] == "INITIAL":
            question.text = EVENT_TASK
        return question

    monkeypatch.setattr(provider, "blueprint", blueprint)
    monkeypatch.setattr(provider, "question", capture_question)

    task = JobTask(description=EVENT_TASK, evidence_spans=[EVENT_TASK], required_level=2)
    initial = start(engine, [skill("python", job_tasks=[task])])
    deeper = answer(engine, initial.snapshot, FIRST_RECORD)

    assert len(question_contexts) == 2
    assert "coding_spec" in question_contexts[0]["question_guidance"]
    assert deeper.snapshot.pending_turn.action == Action.DEEPER
    assert deeper.snapshot.pending_turn.mode == Mode.CODING
    deeper_guidance = question_contexts[1]["question_guidance"]
    assert "coding_spec" not in deeper_guidance
    assert "Build on the prior coding problem/solution in history" in deeper_guidance
