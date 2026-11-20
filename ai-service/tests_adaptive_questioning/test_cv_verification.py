"""Source-grounded questions and recovery through the normal interview workflow."""
import json
from threading import Event
from uuid import NAMESPACE_URL, uuid5

import dspy
import pytest

from adaptive_questioning.evidence import verification
from adaptive_questioning.evidence.dspy_modules import build_question_inputs
from adaptive_questioning.evidence.models import (
    Action, Assessment, ConversationRequest, InterviewOpening, Mode, Snapshot, StartRequest, SuitableMode,
    VerificationBatchDraft,
)
from adaptive_questioning.evidence.provider import DSPyAssessmentProvider
from adaptive_questioning.evidence.workflow import EvidenceWorkflow
from adaptive_questioning.optimization.compiler import DEFAULT_COMPILED_DIR
from scripts.verify_cv_verification import CV, JD, scenario
from test_evidence_workflow import ScriptedProvider, answer, skill

SOURCE_CV = CV.replace("đơn hàng", "đơn\nhàng")
CV_RESULT = "Đã lưu phản hồi của lần xử lý gốc."
DETAIL = "Thông tin dùng để nhận diện hai lần gửi thuộc cùng yêu cầu."
UNRESOLVED = "Trường dùng để kiểm tra trong database."


class VerificationProvider(ScriptedProvider):
    def __init__(self):
        super().__init__()
        self.batches = []
        self.questions = []
        self.reviews = []
        self.judgments = []

    def prepare_verification(self, context, *, deadline):
        batch = json.loads(context)["objectives"]
        self.batches.append(batch)
        return VerificationBatchDraft.model_validate({"focuses": [
            {"criterion_id": criterion["criterion_id"],
             "cv_span_index": min(index, len(item["cv_spans"]) - 1),
             "jd_span_index": 0 if item["jd_spans"] else None, "detail_to_verify": DETAIL}
            for item in batch for index, criterion in enumerate(item["criteria"])
        ]})

    def question(self, context):
        values = json.loads(context)
        self.questions.append(values)
        question = super().question(context)
        sources = values.get("verification_context", {})
        if not values["history"]:
            if sources.get("jd_excerpt"):
                question.text = f"Vị trí này cần xử lý yêu cầu gửi lại. {question.text}"
            if sources.get("detail_to_verify"):
                question.text = f"Trong CV, bạn có nêu kinh nghiệm xử lý đơn hàng. {question.text}"
        return question

    def review_question(self, context):
        self.reviews.append(json.loads(context))
        return super().review_question(context)

    def judge(self, context):
        self.judgments.append(json.loads(context))
        judgment = super().judge(context)
        if self.observation == "UNCLEAR":
            judgment.observations[0].unresolved_aspects = [UNRESOLVED]
        return judgment


def request_with_quotes() -> StartRequest:
    request = scenario()
    request.skills[0].cv_evidence_spans.extend([CV_RESULT, "Thông tin CV chưa được xác minh."])
    request.verification_sources.cv.update({CV: SOURCE_CV, CV_RESULT: CV_RESULT})
    return request


@pytest.mark.parametrize("interaction_mode", ["TEXT", "VOICE"])
def test_first_question_and_clarification_use_their_own_evidence(interaction_mode):
    provider = VerificationProvider()
    engine = EvidenceWorkflow(provider)
    request = request_with_quotes()
    request.config.interaction_mode = interaction_mode

    initial = engine.start(request)
    snapshot = Snapshot.model_validate_json(initial.snapshot.model_dump_json())
    first = provider.questions[-1]
    assert first["cv_evidence"] == [SOURCE_CV]
    assert first["verification_context"] == {"jd_excerpt": JD, "detail_to_verify": DETAIL}
    _, first_inputs = build_question_inputs(json.dumps(first))
    assert json.loads(first_inputs["question_contract"])["required_source_framing"] == ["JD", "CV"]
    assert provider.reviews[-1]["verification_context"] == first["verification_context"]
    assert "verification" not in initial.public.model_dump()
    assert DETAIL not in initial.public.model_dump_json()
    assert provider.batches[0][0]["cv_spans"] == [SOURCE_CV, CV_RESULT]
    assert initial.public.report.objectives[0].criteria[1].assessment == Assessment.NOT_ASSESSED

    provider.observation, provider.performance = "UNCLEAR", "UNDETERMINED"
    next_result = answer(engine, snapshot, "Em kiểm tra trong database.")
    assert next_result.snapshot.pending_turn.action == Action.CLARIFY
    followup = provider.questions[-1]
    assert followup["criterion_progress"]["unresolved_aspects"] == [UNRESOLVED.casefold()]
    assert followup["history"][0]["answer"] == "Em kiểm tra trong database."
    assert followup["cv_evidence"] == []
    assert followup["verification_context"] == {"jd_excerpt": JD}
    _, followup_inputs = build_question_inputs(json.dumps(followup))
    assert "required_source_framing" not in json.loads(followup_inputs["question_contract"])
    assert "verification_context" not in provider.judgments[-1]
    assert next_result.public.report.objectives[0].criteria[0].assessment == Assessment.INSUFFICIENT

    provider.observation, provider.performance = "SUPPORTS", "AT_TARGET"
    result = answer(engine, next_result.snapshot, "Client giữ nguyên khóa định danh và server đối chiếu khóa đã lưu.")
    assert result.snapshot.pending_turn.action == Action.FOLLOW_UP
    next_criterion = provider.questions[-1]
    assert next_criterion["history"] == []
    assert next_criterion["cv_evidence"] == [CV_RESULT]
    assert result.public.report.objectives[0].criteria[0].assessment == Assessment.AT


def test_invalid_draft_indices_and_foreign_criteria_are_discarded(monkeypatch):
    provider = VerificationProvider()
    original = provider.prepare_verification

    def invalid(context, *, deadline):
        draft = original(context, deadline=deadline)
        draft.focuses[0].cv_span_index = 5
        draft.focuses.append(draft.focuses[1].model_copy(update={"criterion_id": "other:c1"}))
        return draft

    monkeypatch.setattr(provider, "prepare_verification", invalid)
    result = EvidenceWorkflow(provider).start(request_with_quotes())
    assert list(result.snapshot.verification.focus_by_criterion) == [
        next(iter(result.snapshot.objectives.values())).objective.criteria[1].criterion_id,
    ]
    assert provider.questions[-1]["cv_evidence"] == []
    assert provider.questions[-1]["verification_context"] == {"jd_excerpt": JD}


@pytest.mark.parametrize("reason", ["missing", "no_source", "failed"])
def test_absent_or_unavailable_verification_uses_the_jd(reason, monkeypatch):
    provider = VerificationProvider()
    request = request_with_quotes()
    if reason == "missing":
        request.skills[0].semantic_alignment = "MISSING"
    elif reason == "no_source":
        request.verification_sources.cv.clear()
    else:
        def unavailable(*args, **kwargs):
            raise RuntimeError("private provider details")
        monkeypatch.setattr(provider, "prepare_verification", unavailable)

    result = EvidenceWorkflow(provider).start(request)
    assert result.snapshot.verification.focus_by_criterion == {}
    assert provider.questions[-1]["cv_evidence"] == []
    assert provider.questions[-1]["verification_context"] == {"jd_excerpt": JD}
    assert provider.batches == []


def test_preparation_deadline_uses_jd_and_discards_late_focus(monkeypatch):
    provider = VerificationProvider()
    original = provider.prepare_verification
    started, release, returned = Event(), Event(), Event()

    def slow(context, *, deadline):
        started.set()
        try:
            assert release.wait(timeout=3)
            return original(context, deadline=deadline)
        finally:
            returned.set()

    def timeout(futures, *, timeout):
        assert started.wait(2)
        assert 0 < timeout <= verification.PREPARATION_SECONDS
        return set(), set(futures)

    monkeypatch.setattr(provider, "prepare_verification", slow)
    monkeypatch.setattr(verification, "wait", timeout)
    try:
        result = EvidenceWorkflow(provider).start(request_with_quotes())
    finally:
        release.set()
    assert returned.wait(2)
    assert result.snapshot.verification.focus_by_criterion == {}
    assert provider.questions[-1]["verification_context"] == {"jd_excerpt": JD}


def test_preparation_batches_include_reserve_in_plan_order():
    provider = VerificationProvider()
    request = StartRequest(
        session_id="verification-batches", config={"max_questions": 4},
        skills=[skill(str(i), importance_weight=0.6 - i / 100, cv_evidence_spans=[CV]) for i in range(6)],
        verification_sources={"cv": {CV: CV}},
    )
    result = EvidenceWorkflow(provider).start(request)
    assert sorted(len(batch) for batch in provider.batches) == [1, 3]
    assert len(result.snapshot.queue) == 2
    prepared = result.snapshot.verification.focus_by_criterion
    assert [state.objective.skill_id for state in result.snapshot.objectives.values()
            if state.objective.criteria[0].criterion_id in prepared] == ["0", "1", "2", "3"]


def test_two_rejected_cv_questions_trigger_jd_only_last_attempt(monkeypatch, caplog):
    provider = VerificationProvider()
    original = provider.review_question

    def reject_cv(context):
        original(context)
        if json.loads(context)["cv_evidence"]:
            return {"verdict": "INSUFFICIENT_EVIDENCE", "reason": CV}
        return "ALIGNED"

    monkeypatch.setattr(provider, "review_question", reject_cv)
    result = EvidenceWorkflow(provider).start(request_with_quotes())
    assert len(provider.questions) == len(provider.reviews) == 3
    assert [item["cv_evidence"] for item in provider.questions] == [[SOURCE_CV], [SOURCE_CV], []]
    assert provider.questions[-1]["verification_context"] == {"jd_excerpt": JD}
    assert provider.reviews[-1]["verification_context"] == {"jd_excerpt": JD}
    assert "rejected_draft" not in provider.questions[-1]
    assert result.snapshot.pending_turn.question.criterion_ids == provider.questions[0]["required_question_contract"]["criterion_ids"]
    assert CV not in caplog.text


def test_prewarmed_question_uses_saved_focus_and_legacy_snapshot_can_resume():
    provider = VerificationProvider()
    request = request_with_quotes()
    request.opening = InterviewOpening()
    engine = EvidenceWorkflow(provider, prewarm_q1=True)
    initial = engine.start(request).snapshot
    command = ConversationRequest(
        snapshot=Snapshot.model_validate_json(initial.model_dump_json()), action="SKIP_INTRODUCTION",
        message_id=initial.conversation.message.message_id, expected_state_version=initial.state_version,
    )
    result = engine.converse(command)
    assert result.snapshot.pending_turn is not None
    assert provider.question_number == 1
    assert provider.questions[0]["cv_evidence"] == [SOURCE_CV]

    legacy = result.snapshot.model_dump(mode="json")
    legacy.pop("verification")
    restored = Snapshot.model_validate(legacy)
    legacy_result = answer(engine, restored, "Client giữ khóa cũ khi gửi lại.")
    assert legacy_result.snapshot.verification is None
    assert "verification_context" not in provider.questions[-1]
    assert provider.questions[-1]["cv_evidence"] == request.skills[0].cv_evidence_spans
    assert len(provider.batches) == 1


def test_compiled_dspy_predictors_receive_prepared_evidence():
    request = request_with_quotes()
    key = request.blueprint.objectives[0].requirement_id
    criterion_id = f"{uuid5(NAMESPACE_URL, key)}:c1"
    lm = dspy.utils.DummyLM([
        {"draft": {"focuses": [{"criterion_id": criterion_id, "cv_span_index": 0,
                                "jd_span_index": 0, "detail_to_verify": DETAIL}]}},
        {"reasoning": "Hỏi đúng trường định danh của yêu cầu.", "question": {
            "text": ("Trong CV, bạn có nêu việc xử lý đơn trùng. Vị trí này cần xử lý gửi lại sau timeout. "
                     "API của bạn dựa vào dữ liệu nào để nhận diện lần gửi lại?"),
            "criterion_ids": [criterion_id], "evidence_scope": "create-order",
            "mode": "TECHNICAL_EXPLANATION", "depth": 2,
        }},
        {"review": {"verdict": "ALIGNED", "reason": ""}},
    ])
    lm.adapter = dspy.JSONAdapter()
    provider = DSPyAssessmentProvider(lm=lm, compiled_dir=str(DEFAULT_COMPILED_DIR))

    result = EvidenceWorkflow(provider).start(request)
    assert result.snapshot.pending_turn.question.criterion_ids == [criterion_id]
    assert len(lm.history) == 3
    for call in lm.history[1:]:
        messages = json.dumps(call["messages"], ensure_ascii=False)
        assert "verification_context" in messages and DETAIL in messages
        assert JD in messages


def test_prewarmed_question_from_different_verification_is_discarded():
    provider = VerificationProvider()
    request = request_with_quotes()
    request.opening = InterviewOpening()
    engine = EvidenceWorkflow(provider, prewarm_q1=True)
    snapshot = engine.start(request).snapshot
    engine._prewarmed_q1[snapshot.session_id].future.result(timeout=3)
    focus = next(iter(snapshot.verification.focus_by_criterion.values()))
    focus.detail_to_verify = "Trường dữ liệu ổn định được gửi kèm yêu cầu."

    engine.converse(ConversationRequest(
        snapshot=snapshot, action="SKIP_INTRODUCTION", message_id=snapshot.conversation.message.message_id,
        expected_state_version=snapshot.state_version,
    ))

    assert provider.question_number == 2
    assert provider.questions[-1]["verification_context"]["detail_to_verify"] == focus.detail_to_verify


@pytest.mark.parametrize(("jd", "go_is_alternative"), [
    ("Kinh nghiệm lập trình Golang hoặc TypeScript từ đồ án hoặc dự án cá nhân.", True),
    ("Yêu cầu kinh nghiệm Golang. Có thể dùng đồ án hoặc dự án cá nhân.", False),
])
def test_go_exercise_links_to_jd_even_when_cv_has_no_go_evidence(monkeypatch, jd, go_is_alternative):
    generic = ("Viết hàm Go `func DeduplicateIDs(ids []int) []int` để loại bỏ ID trùng, "
               "giữ thứ tự xuất hiện đầu tiên.")
    requires_go = f"JD yêu cầu kinh nghiệm Golang. {generic}"
    drafts = [generic, requires_go]
    if go_is_alternative:
        drafts.append(f"JD chấp nhận kinh nghiệm Golang hoặc TypeScript. {generic}")
    provider = VerificationProvider()
    build = provider.blueprint

    def coding_blueprint(context):
        draft = build(context)
        draft.objectives[0].suitable_modes = [SuitableMode(mode=Mode.CODING)]
        return draft

    generate = provider.question

    def question(context):
        result = generate(context)
        result.text = drafts[len(provider.questions) - 1]
        return result

    monkeypatch.setattr(provider, "blueprint", coding_blueprint)
    monkeypatch.setattr(provider, "question", question)
    request = StartRequest(
        session_id="go-without-cv", config={"focused_question_mode": Mode.CODING},
        skills=[skill("golang", semantic_alignment="MISSING", jd_evidence_spans=[jd])],
        verification_sources={"jd": {jd: jd}},
    )

    result = EvidenceWorkflow(provider).start(request)

    assert provider.batches == []
    assert provider.questions[0]["cv_evidence"] == []
    assert provider.questions[0]["verification_context"] == {"jd_excerpt": jd}
    assert "link to a specific fact in the JD" in provider.questions[1]["validation_error"]
    if go_is_alternative:
        assert "Preserve the alternatives" in provider.questions[2]["validation_error"]
    grounded = drafts[-1]
    assert [review["question"] for review in provider.reviews] == [grounded]
    assert result.public.pending_turn.question == grounded


def test_question_for_prepared_focus_must_show_the_cv_connection(monkeypatch):
    provider = VerificationProvider()
    generate = provider.question

    def question(context):
        result = generate(context)
        if len(provider.questions) == 1:
            result.text = "Vị trí này cần xử lý lần gửi lại. Bạn đã dùng định danh nào trong CV để nhận diện yêu cầu lặp?"
        return result

    monkeypatch.setattr(provider, "question", question)

    result = EvidenceWorkflow(provider).start(request_with_quotes())

    assert "candidate's CV excerpt" in provider.questions[1]["validation_error"]
    assert len(provider.reviews) == 1
    assert provider.reviews[0]["cv_evidence"] == [SOURCE_CV]
    assert "Trong CV" in result.public.pending_turn.question
