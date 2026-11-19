"""Recoverable generation failures and precise repair feedback, without weakened contracts."""
import json

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from adaptive_questioning.evidence.question_validation import (
    VOICE_MAX_WORDS, question_errors, single_question,
)
from adaptive_questioning.evidence.models import ConversationRequest, InterviewOpening, NextQuestionRequest, Question, StartRequest
from adaptive_questioning.evidence.errors import QuestionUnavailableError
from adaptive_questioning.evidence.provider import DSPyAssessmentProvider
import dspy
from adaptive_questioning.evidence.routes import router
from adaptive_questioning.optimization.compiler import DEFAULT_COMPILED_DIR
from test_evidence_workflow import setup, skill, start, answer


_MISSING_SNIPPET = (
    "Đoạn mã sau tìm chỉ số của phần tử dương đầu tiên trong danh sách. "
    "Hãy chỉ ra dòng hoặc logic sai và đưa ra một ví dụ đầu vào cụ thể khiến hàm trả về kết quả sai."
)
_WITH_SNIPPET = (
    "Đoạn mã sau tìm chỉ số của phần tử dương đầu tiên, hoặc trả -1 nếu không có.\n\n"
    "```python\n"
    "def first_positive_index(values):\n"
    "    for i, value in enumerate(values):\n"
    "        if value >= 0:\n"
    "            return i\n"
    "    return -1\n"
    "```\n\n"
    "Đầu vào nào khiến hàm trả sai chỉ số?"
)


@pytest.mark.parametrize("repair", [True, False])
def test_correct_metadata_cannot_bypass_criterion_review(setup, monkeypatch, repair):
    provider, engine, _ = setup
    blueprint = provider.blueprint
    generate = provider.question
    criterion = "Chọn dữ liệu thử để phát hiện hàm kiểm tra email chấp nhận đầu vào sai."
    wrong = "Bạn viết hàm kiểm tra email bằng Python thế nào?"
    focused = "Hàm chấp nhận mọi chuỗi có @. Theo yêu cầu email phải có tên miền. Bạn chọn đầu vào nào để phát hiện lỗi?"

    def plan(context):
        result = blueprint(context)
        target = result.objectives[0].criteria[0]
        target.description = criterion
        target.expected_evidence = target.at_target = "Một đầu vào có @ nhưng thiếu tên miền."
        return result

    def draft(context):
        result = generate(context)
        previous = json.loads(context).get("rejected_draft")
        result.text = focused if repair and previous == wrong else wrong
        return result

    # Exercise the DSPy reviewer interface offline, including rejection and regeneration.
    lm = dspy.utils.DummyLM([
        {"review": {"verdict": "WRONG_SKILL", "reason": "Yêu cầu viết hàm thay vì chọn ca kiểm thử."}},
        {"review": {"verdict": "ALIGNED" if repair else "WRONG_SKILL", "reason": ""}},
        {"review": {"verdict": "WRONG_SKILL", "reason": "Vẫn sai kỹ năng."}},
    ])
    lm.adapter = dspy.JSONAdapter()
    review = DSPyAssessmentProvider(lm=lm)
    reviewed = []

    def inspect(context):
        data = json.loads(context)
        assert data["criterion"]["description"] == criterion
        reviewed.append(data["question"])
        return review.review_question(context)

    monkeypatch.setattr(provider, "blueprint", plan)
    monkeypatch.setattr(provider, "question", draft)
    monkeypatch.setattr(provider, "review_question", inspect)
    if repair:
        assert start(engine).public.pending_turn.question == focused
    else:
        with pytest.raises(QuestionUnavailableError):
            start(engine)
    assert reviewed == ([wrong, focused] if repair else [wrong])


def test_ambiguous_debugging_spec_is_repaired_before_delivery(setup, monkeypatch):
    from adaptive_questioning.evidence.dspy_modules import InitialQuestionSignature
    provider, engine, _ = setup
    generate = provider.question
    task = (
        "\n\n```python\ndef second_largest(nums):\n"
        "    return sorted(set(nums))[-2]\n```\n\n"
        "Hãy nêu một đầu vào mà hàm chạy sai và giải thích vì sao."
    )
    ambiguous = "Hàm sau tìm số lớn thứ hai trong danh sách số nguyên." + task
    clarified = (
        "Hàm nhận một danh sách số nguyên và trả về giá trị lớn thứ hai phân biệt. "
        "Nếu không tồn tại giá trị đó, hàm phải trả `None`."
    ) + task
    lm = dspy.utils.DummyLM([
        {"review": {"verdict": "UNANSWERABLE", "reason": "Thiếu quy tắc xử lý phần tử trùng và khi không có số lớn thứ hai."}},
        {"review": {"verdict": "ALIGNED", "reason": "Đã nêu đủ quy tắc biên."}},
    ])
    lm.adapter = dspy.JSONAdapter()
    reviewer = DSPyAssessmentProvider(lm=lm, compiled_dir=str(DEFAULT_COMPILED_DIR))
    reviewed = []

    assert "boundary" in InitialQuestionSignature.instructions.lower()

    def draft(context):
        data = json.loads(context)
        result = generate(context)
        if "validation_error" in data:
            assert data["rejected_draft"] == ambiguous
            assert "definitions, or expected behavior" in data["validation_error"]
            assert "Thiếu quy tắc xử lý phần tử trùng" in data["validation_error"]
            result.text = clarified
        else:
            result.text = ambiguous
        return result

    def review(context):
        reviewed.append(json.loads(context)["question"])
        return reviewer.review_question(context)

    monkeypatch.setattr(provider, "question", draft)
    monkeypatch.setattr(provider, "review_question", review)
    assert start(engine, skills=[skill("ai_tools_usage")]).public.pending_turn.question == clarified
    assert reviewed == [ambiguous, clarified]
    assert "change the correct answer" in str(lm.history[0]["messages"])


@pytest.mark.parametrize("text", [
    "Đầu vào:\n1. Nếu chuỗi rỗng, trả về False.\n2. Nếu hợp lệ, trả về True.\nBạn sẽ viết prompt ra sao?",
    'Với URL https://a.example/?x=1 và https://b.example/?x=2, bạn sẽ kiểm thử ra sao?',
    '''Với chuỗi "a?b@example.com" và 'c?d@example.com', bạn kiểm thử hàm ra sao?''',
])
def test_data_question_marks_and_conditional_constraints_are_not_extra_tasks(text):
    assert single_question(text)


@pytest.mark.parametrize("text", [
    "Bạn viết prompt gì? Bạn sẽ review mã ra sao?",
    "1. Hãy viết prompt.\n2. Sau khi AI trả lời, hãy review mã.",
    "1. Viết prompt.\n2. Nếu mã sai, hãy mô tả cách sửa lỗi.",
    "Em hãy phân tích nguyên nhân chính gây chậm và đề xuất một câu lệnh SQL cụ thể để tối ưu truy vấn.",
])
def test_independent_response_tasks_are_still_rejected(text):
    assert not single_question(text)


@pytest.mark.parametrize(("text", "mode", "missing"), [
    (_MISSING_SNIPPET, "TEXT", True),
    (_MISSING_SNIPPET, "VOICE", True),
    ("Đoạn mã `first_positive_index(values)` dưới đây sai ở đâu?", "TEXT", True),
    ("Đoạn mã C# bên dưới trả về giá trị sai. Đầu vào nào cho thấy lỗi?", "TEXT", True),
    ("The following code returns the wrong index. Which input demonstrates the bug?", "TEXT", True),
    (_MISSING_SNIPPET + "\n\n```python\n# TODO\n...\n```", "TEXT", True),
    (_WITH_SNIPPET, "TEXT", False),
    ("Đoạn mã sau trả về giá trị sai: `return len(values) - 1`. Đầu vào nào cho thấy lỗi?", "TEXT", False),
    ("Hàm trả vị trí đầu tiên có giá trị lớn hơn hoặc bằng 0. Đầu vào nào cho thấy hàm bỏ sót yêu cầu chỉ tìm số dương?",
     "VOICE", False),
    ("Bạn sẽ kiểm thử đoạn mã sau khi đồng đội sửa lỗi bằng cách nào?", "TEXT", False),
])
def test_referenced_code_requires_actual_snippet(text, mode, missing):
    contract = {"mode": "DEBUGGING", "depth": 2, "criterion_ids": ["c1"]}
    question = Question(text=text, evidence_scope="first-positive", **contract)
    errors = question_errors(question, {"required_question_contract": contract, "interaction_mode": mode})
    if missing:
        assert any("missing code snippet" in error for error in errors)
    else:
        assert not errors


def test_next_question_repairs_missing_code_before_delivery(setup, monkeypatch):
    provider, engine, _ = setup
    generate = provider.question
    calls, reviewed = [], []

    def draft(context):
        calls.append(json.loads(context))
        result = generate(context)
        result.text = _MISSING_SNIPPET if len(calls) == 1 else _WITH_SNIPPET
        return result

    def review(context):
        reviewed.append(json.loads(context)["question"])
        return "ALIGNED"

    monkeypatch.setattr(provider, "question", draft)
    monkeypatch.setattr(provider, "review_question", review)
    first = engine.start(StartRequest(session_id="test", skills=[skill("ai_tools_usage")], opening=InterviewOpening()))
    queued = engine.converse(ConversationRequest(
        snapshot=first.snapshot, expected_state_version=first.snapshot.state_version,
        message_id=first.snapshot.conversation.message.message_id, action="SKIP_INTRODUCTION", defer_question=True,
    ))
    result = engine.next_question(NextQuestionRequest(snapshot=queued.snapshot, expected_state_version=queued.snapshot.state_version))
    assert result.public.pending_turn.question == _WITH_SNIPPET
    assert reviewed == [_WITH_SNIPPET]
    assert "missing code snippet" in calls[1]["validation_error"]
    assert calls[0]["required_question_contract"] == calls[1]["required_question_contract"]


@pytest.mark.parametrize("word_count, rejected", [(VOICE_MAX_WORDS, False), (VOICE_MAX_WORDS + 1, True)])
def test_voice_length_boundary(word_count, rejected):
    question = Question(text=" ".join(["API"] * (word_count - 1) + ["chậm?"]),
                        criterion_ids=["c1"], mode="DEBUGGING", depth=3, evidence_scope="slow-api")
    context = {"required_question_contract": {"mode": "DEBUGGING", "depth": 3, "criterion_ids": ["c1"]},
               "interaction_mode": "VOICE"}
    errors = question_errors(question, context)
    assert bool(errors) == rejected
    if rejected:
        assert "Do not truncate" in errors[0]


def test_long_voice_question_is_rewritten_with_same_target_and_depth(setup, monkeypatch):
    provider, engine, _ = setup
    original = provider.question
    calls = []
    concise = "API phản hồi chậm nhưng CPU vẫn bình thường. Bạn sẽ kiểm tra gì đầu tiên?"

    def question(context):
        calls.append(json.loads(context))
        result = original(context)
        result.evidence_scope = "slow-api"
        result.text = ("Bối cảnh hệ thống đang phục vụ nhiều người dùng. " * 12 + concise
                       if len(calls) == 1 else concise)
        return result

    monkeypatch.setattr(provider, "question", question)
    result = start(engine, interaction_mode="VOICE")
    turn = result.snapshot.pending_turn
    pending = turn.question
    assert len(calls) == 2
    assert "VOICE question must use at most" in calls[1]["validation_error"]
    assert calls[0]["required_question_contract"] == calls[1]["required_question_contract"]
    assert pending.text == concise
    assert turn.question_depth == calls[0]["required_question_contract"]["depth"]
    assert turn.mode == calls[0]["required_question_contract"]["mode"]
    assert pending.criterion_ids == calls[0]["required_question_contract"]["criterion_ids"]
    assert {"mode", "question_depth", "target_criteria", "required_evidence_scope", "remaining_questions"}.isdisjoint(calls[0])
    assert pending.evidence_scope == "slow-api"


def test_text_problem_data_is_not_subject_to_voice_limit(setup, monkeypatch):
    provider, engine, _ = setup
    original = provider.question
    text = "Log hệ thống:\n```\n" + "request duration=5000ms\n" * 100 + "```\nBạn chẩn đoán nguyên nhân nào?"

    def question(context):
        result = original(context)
        result.text = text
        return result

    monkeypatch.setattr(provider, "question", question)
    result = start(engine, interaction_mode="TEXT")
    assert result.snapshot.pending_turn.question.text == text


def test_retry_identifies_the_exact_invalid_field_and_keeps_the_contract(setup, monkeypatch, caplog):
    provider, engine, _ = setup
    original = provider.question
    calls = []

    def question(context):
        calls.append(json.loads(context))
        result = original(context)
        if len(calls) == 1:
            result.depth = 4
        return result

    monkeypatch.setattr(provider, "question", question)
    result = start(engine)
    assert result.public.pending_turn
    assert len(calls) == 2
    assert "depth must equal" in calls[1]["validation_error"]
    assert "criterion_ids" not in calls[1]["validation_error"]
    assert calls[1]["required_question_contract"] == calls[0]["required_question_contract"]
    assert "depth must equal" in caplog.text
    assert result.public.pending_turn.question not in caplog.text


def test_failed_next_question_returns_503_and_retry_preserves_answer_and_snapshot(setup, monkeypatch):
    provider, engine, _ = setup
    provider.criterion_count = 2
    initial = start(engine).snapshot
    saved = initial.model_dump_json()
    original = provider.question

    def invalid(context):
        question = original(context)
        question.evidence_scope = ""
        return question

    monkeypatch.setattr(provider, "question", invalid)
    app = FastAPI()
    app.include_router(router)
    app.state.evidence_workflow = engine
    payload = {"snapshot": initial.model_dump(mode="json"), "turn_id": initial.pending_turn.turn_id,
               "expected_state_version": initial.state_version, "candidate_response": "EXPLAIN ANALYZE"}
    with TestClient(app) as client:
        failed = client.post('/api/v2/interview/respond', json=payload)
        assert failed.status_code == 503
        assert "giữ nguyên" in failed.json()["detail"]
        assert "bounded retry" not in failed.json()["detail"]
        assert initial.model_dump_json() == saved
        monkeypatch.setattr(provider, "question", original)
        retried = client.post('/api/v2/interview/respond', json=payload)
        assert retried.status_code == 200
        result = retried.json()
        assert len(result["snapshot"]["turns"]) == 1
        assert result["snapshot"]["turns"][0]["answer"] == payload["candidate_response"]
        assert result["snapshot"]["state_version"] == initial.state_version + 1


def test_deferred_answer_is_graded_once_when_question_generation_fails(setup, monkeypatch):
    provider, engine, _ = setup
    provider.criterion_count = 2
    initial = start(engine).snapshot
    generate, judge = provider.question, provider.judge
    drafts, judgments = [], []

    def invalid(context):
        drafts.append(context)
        question = generate(context)
        question.evidence_scope = ""
        return question

    def count_judgment(context):
        judgments.append(context)
        return judge(context)

    monkeypatch.setattr(provider, "question", invalid)
    monkeypatch.setattr(provider, "judge", count_judgment)
    app = FastAPI()
    app.include_router(router)
    app.state.evidence_workflow = engine
    with TestClient(app) as client:
        submitted = client.post('/api/v2/interview/respond', json={
            "snapshot": initial.model_dump(mode="json"), "turn_id": initial.pending_turn.turn_id,
            "expected_state_version": initial.state_version, "candidate_response": "EXPLAIN ANALYZE",
            "defer_question": True,
        })
        assert submitted.status_code == 200
        saved = submitted.json()
        assert saved["public"]["awaiting_question"] and saved["public"]["pending_turn"] is None
        assert saved["public"]["turns"][0]["answer"] == "EXPLAIN ANALYZE"
        assert saved["snapshot"]["turns"][0]["judgment"]
        assert len(judgments) == 1 and not drafts

        generation = {"snapshot": saved["snapshot"], "expected_state_version": saved["public"]["state_version"]}
        failed = client.post('/api/v2/interview/next-question', json=generation)
        assert failed.status_code == 503
        assert len(judgments) == 1 and len(drafts) == 3
        stale = client.post('/api/v2/interview/next-question', json={**generation, "expected_state_version": 0})
        assert stale.status_code == 422
        assert len(drafts) == 3

        stopped = client.post('/api/v2/interview/stop', json=saved["snapshot"]).json()["public"]
        assert stopped["is_finished"] and not stopped["awaiting_question"]
        assert stopped["turns"] == saved["public"]["turns"]

        monkeypatch.setattr(provider, "question", generate)
        retried = client.post('/api/v2/interview/next-question', json=generation)
        assert retried.status_code == 200
        resumed = retried.json()["public"]
        assert not resumed["awaiting_question"] and resumed["pending_turn"]["turn_id"] != initial.pending_turn.turn_id
        assert resumed["state_version"] == saved["public"]["state_version"] + 1
        assert resumed["turns"] == saved["public"]["turns"]
        assert len(judgments) == 1


def test_clarification_retry_receives_the_exact_persisted_scope(setup, monkeypatch):
    provider, engine, _ = setup
    provider.observation, provider.performance = "UNCLEAR", "UNDETERMINED"
    initial = start(engine).snapshot
    original = provider.question
    calls = []

    def question(context):
        calls.append(json.loads(context))
        result = original(context)
        if len(calls) == 1:
            result.evidence_scope = "a-different-case"
        return result

    monkeypatch.setattr(provider, "question", question)
    result = answer(engine, initial)
    expected = initial.pending_turn.question.evidence_scope
    assert calls[1]["required_question_contract"]["evidence_scope"] == expected
    assert "CLARIFY must preserve" in calls[1]["validation_error"]
    assert result.snapshot.pending_turn.question.evidence_scope == expected
