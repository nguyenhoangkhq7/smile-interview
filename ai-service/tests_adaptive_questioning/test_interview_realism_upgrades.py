"""Tests for Batch 1 interview realism & reliability upgrades (#1–#5)."""
import json

import pytest

from adaptive_questioning.evidence.conversation import (
    ACKNOWLEDGMENT,
    MAX_FEEDBACK_LENGTH,
    MAX_PRACTICE_FEEDBACK_LENGTH,
    fit_feedback_length,
)
from adaptive_questioning.evidence.excerpts import source_excerpt
from adaptive_questioning.evidence.mode_strategy import question_guidance_for
from adaptive_questioning.evidence.models import Action, Mode, Question, StartRequest
from adaptive_questioning.evidence.question_validation import (
    VOICE_FRAMING_WORD_ALLOWANCE,
    VOICE_MAX_WORDS,
    VOICE_SOFT_MAX_WORDS,
    single_question,
    validate_question,
    voice_word_limits,
)
from adaptive_questioning.optimization.compiler import DEFAULT_COMPILED_DIR, load_all_compiled_modules
from test_evidence_workflow import answer, setup, skill, start


def test_practice_feedback_trims_at_sentence_boundary_instead_of_discarding(setup, monkeypatch):
    s1 = "Bạn đã chọn đúng hướng dùng composite index theo cột lọc trước và sắp xếp sau."
    s2 = "Cách lý giải về chi phí ghi thêm trên mỗi lệnh INSERT và UPDATE cũng rất sát thực tế vận hành."
    s3 = "Tuy nhiên bạn cần kiểm tra thêm ca truy vấn chỉ lọc theo cột thứ hai trong chỉ mục để tránh bỏ sót."
    s4 = " " + "Phần mở rộng thêm quá giới hạn độ dài để kiểm tra cắt gọn theo ranh giới câu hoàn chỉnh. " * 6
    overlong = f"{s1} {s2} {s3}{s4}"
    assert len(overlong) > MAX_PRACTICE_FEEDBACK_LENGTH

    trimmed = fit_feedback_length(overlong, max_length=MAX_PRACTICE_FEEDBACK_LENGTH, allow_sentence_trim=True)
    assert len(trimmed) <= MAX_PRACTICE_FEEDBACK_LENGTH
    assert trimmed.startswith(s1)
    assert trimmed.endswith((".", "!", "?"))
    assert trimmed != ACKNOWLEDGMENT

    # Without sentence boundary, PRACTICE still safely falls back to ACKNOWLEDGMENT.
    no_punct = "a" * (MAX_PRACTICE_FEEDBACK_LENGTH + 20)
    assert fit_feedback_length(no_punct, max_length=MAX_PRACTICE_FEEDBACK_LENGTH, allow_sentence_trim=True) == ACKNOWLEDGMENT

    # ASSESSMENT keeps strict fallback without partial trimming.
    assert fit_feedback_length(overlong, max_length=MAX_FEEDBACK_LENGTH, allow_sentence_trim=False) == ACKNOWLEDGMENT

    # End-to-end PRACTICE turn preserves trimmed coaching feedback.
    provider, engine, _ = setup
    original_judge = provider.judge

    def long_practice_judge(context):
        judgment = original_judge(context)
        judgment.feedback = overlong
        return judgment

    monkeypatch.setattr(provider, "judge", long_practice_judge)
    started = engine.start(StartRequest(
        session_id="practice-trim-fb",
        skills=[skill("postgresql")],
        config={"session_purpose": "PRACTICE", "max_questions": 2},
    ))
    graded = answer(engine, started.snapshot, "Em dùng EXPLAIN ANALYZE và đánh chỉ mục phù hợp.")
    saved_fb = graded.public.turns[0].feedback
    assert saved_fb == trimmed
    assert saved_fb != ACKNOWLEDGMENT


def test_voice_word_limits_grant_framing_budget_only_when_jd_or_cv_framing_required():
    base_contract = {"mode": Mode.DESIGN, "depth": 3, "criterion_ids": ["c1"]}
    assert voice_word_limits({"required_question_contract": base_contract}) == (VOICE_MAX_WORDS, VOICE_SOFT_MAX_WORDS)

    jd_ctx = {
        "required_question_contract": base_contract,
        "interaction_mode": "VOICE",
        "verification_context": {"jd_excerpt": "Thiết kế API chịu tải cao."},
        "history": [],
    }
    assert voice_word_limits(jd_ctx) == (
        VOICE_MAX_WORDS + VOICE_FRAMING_WORD_ALLOWANCE,
        VOICE_SOFT_MAX_WORDS + VOICE_FRAMING_WORD_ALLOWANCE,
    )

    both_ctx = {
        **jd_ctx,
        "verification_context": {"jd_excerpt": "Thiết kế API chịu tải cao.", "detail_to_verify": "Cơ chế idempotency"},
        "cv_evidence": ["Từng xây dựng hệ thống xử lý đơn hàng."],
    }
    assert voice_word_limits(both_ctx) == (
        VOICE_MAX_WORDS + 2 * VOICE_FRAMING_WORD_ALLOWANCE,
        VOICE_SOFT_MAX_WORDS + 2 * VOICE_FRAMING_WORD_ALLOWANCE,
    )

    # 110 Vietnamese tokens with valid JD + CV lead-in passes cleanly without retry.
    lead = "Vị trí này yêu cầu xử lý tải cao. Trong CV bạn có làm hệ thống đơn hàng."
    filler_count = 110 - len(lead.split()) - 1
    q_text = f"{lead} " + " ".join(["hệ"] * filler_count) + " sao?"
    assert len(q_text.split()) == 110
    outcome = validate_question(
        Question(text=q_text, criterion_ids=["c1"], mode=Mode.DESIGN, depth=3, evidence_scope="jd-cv-voice"),
        both_ctx,
    )
    assert outcome.all_errors == []

    # Follow-up turns (non-empty history) do not receive the initial framing bonus.
    followup_ctx = {**both_ctx, "history": [{"question": {"text": "Q1"}, "answer": "A1"}]}
    assert voice_word_limits(followup_ctx) == (VOICE_MAX_WORDS, VOICE_SOFT_MAX_WORDS)


@pytest.mark.parametrize("text", [
    "Hãy thiết kế cơ chế phân vùng dữ liệu và so sánh đánh đổi độ trễ với tính nhất quán?",
    "Bạn sẽ đề xuất chiến lược cache nào và so sánh chi phí bộ nhớ với phương án truy vấn trực tiếp?",
    "Hãy đề xuất cấu trúc hàng đợi và so sánh ưu nhược điểm với xử lý đồng bộ?",
    "Hãy điều chỉnh giải pháp lưu trạng thái và so sánh trade-offs khi lưu lượng tăng gấp mười?",
])
def test_single_question_allows_integrated_tradeoff_justification(text):
    assert single_question(text)


@pytest.mark.parametrize("text", [
    "Em hãy phân tích nguyên nhân chính gây chậm và đề xuất một câu lệnh SQL cụ thể để tối ưu truy vấn.",
    "Hãy viết hàm kiểm tra email và so sánh hai hệ quản trị PostgreSQL với MySQL.",
    "Hãy viết hàm sắp xếp và kiểm thử các ca biên.",
])
def test_single_question_still_rejects_separate_work_products(text):
    assert not single_question(text)


def test_voice_excerpt_punctuation_tolerance_preserves_verbatim_source_and_rejects_alterations():
    transcript = "Em nghĩ là, dùng composite index, theo cột status rồi mới tới created_at."
    no_commas = "dùng composite index theo cột status rồi mới tới created_at"

    # Strict TEXT mode still rejects missing internal commas.
    assert source_excerpt(no_commas, transcript, allow_punctuation_tolerance=False) is None

    # VOICE mode resolves to the exact verbatim substring from the original transcript.
    resolved = source_excerpt(no_commas, transcript, allow_punctuation_tolerance=True)
    assert resolved is not None
    assert resolved in transcript
    assert resolved == "dùng composite index, theo cột status rồi mới tới created_at."

    # Guardrails remain strict even with voice punctuation tolerance enabled.
    for bad in [
        "dùng composite index ... created_at",
        "dùng composite index… created_at",
        "dùng composite indexes theo cột status",
        "dung composite index theo cot status",
        "DÙNG COMPOSITE INDEX theo cột status",
        "dùng composite index và Redis",
    ]:
        assert source_excerpt(bad, transcript, allow_punctuation_tolerance=True) is None


def test_voice_workflow_accepts_stt_punctuation_difference_without_retry(setup, monkeypatch):
    provider, engine, _ = setup
    started = start(engine, interaction_mode="VOICE")
    transcript = "Em dùng, EXPLAIN ANALYZE, để xem kế hoạch thực thi."
    original_judge = provider.judge
    calls = []

    def voice_judge(context):
        calls.append(json.loads(context))
        judgment = original_judge(context)
        judgment.observations[0].response_excerpt = "Em dùng EXPLAIN ANALYZE để xem kế hoạch thực thi"
        return judgment

    monkeypatch.setattr(provider, "judge", voice_judge)
    result = answer(engine, started.snapshot, transcript)
    assert len(calls) == 1
    assert result.snapshot.turns[0].judgment.observations[0].response_excerpt == transcript


def test_design_guidance_expands_prose_budget_for_text_only():
    text_guidance = " ".join(question_guidance_for(
        mode=Mode.DESIGN, action=Action.INITIAL, interaction_mode="TEXT", depth=4, has_history=False,
    ))
    voice_guidance = " ".join(question_guidance_for(
        mode=Mode.DESIGN, action=Action.INITIAL, interaction_mode="VOICE", depth=4, has_history=False,
    ))
    assert "110 Vietnamese words" in text_guidance
    assert "110 Vietnamese words" not in voice_guidance


def test_batch1_upgrades_keep_compiled_dspy_manifest_valid():
    q_mod, j_mod, a_mod, b_mod = load_all_compiled_modules(DEFAULT_COMPILED_DIR)
    assert len(q_mod.diagnostic.predict.demos) == 3
    assert len(j_mod.assess.predict.demos) == 3
    assert len(a_mod.demos) == 4
    assert len(b_mod.demos) == 2


def test_opportunistic_secondary_evidence_resolves_sibling_criterion_and_skips_reasking(setup, monkeypatch):
    from adaptive_questioning.evidence.models import Assessment, Observation

    provider, engine, _ = setup
    provider.criterion_count = 2
    started = start(engine, [skill("python", importance_weight=0.9), skill("redis", importance_weight=0.8)])
    obj_id = started.snapshot.queue[0]
    state = started.snapshot.objectives[obj_id]
    c1, c2 = [c.criterion_id for c in state.objective.criteria]
    assert started.snapshot.pending_turn.question.criterion_ids == [c1]

    candidate_answer = (
        "Em dùng dictionary giữ bản ghi đầu tiên bằng setdefault. "
        "Độ phức tạp thời gian là O(n) vì duyệt mảng đúng một lần và tra cứu dict trung bình O(1)."
    )
    secondary_quote = "Độ phức tạp thời gian là O(n) vì duyệt mảng đúng một lần và tra cứu dict trung bình O(1)."
    seen_contexts = []
    original_judge = provider.judge

    def multi_signal_judge(context):
        seen_contexts.append(json.loads(context))
        judgment = original_judge(context)
        judgment.secondary_observations = [Observation(
            criterion_id=c2,
            response_excerpt=secondary_quote,
            observation="SUPPORTS",
            performance="AT_TARGET",
            rationale="Ứng viên chủ động chứng minh đúng độ phức tạp thời gian O(n) kèm lý do duyệt một lần.",
        )]
        return judgment

    monkeypatch.setattr(provider, "judge", multi_signal_judge)
    after = answer(engine, started.snapshot, candidate_answer)

    assert len(seen_contexts) == 1
    assert [c["criterion_id"] for c in seen_contexts[0]["objective"]["criteria"]] == [c1]
    assert [c["criterion_id"] for c in seen_contexts[0]["secondary_criteria"]] == [c2]

    updated_state = after.snapshot.objectives[obj_id]
    assert updated_state.assessment == Assessment.AT
    assert c2 in updated_state.criterion_results
    assert updated_state.criterion_results[c2].performance == "AT_TARGET"
    assert updated_state.criterion_results[c2].response_excerpt == secondary_quote
    # Secondary credit must NOT consume criterion_progress turn budget.
    assert updated_state.criterion_progress.get(c2) is None or updated_state.criterion_progress[c2].turns_spent == 0
    # Objective 1 closed immediately and advanced directly to the second skill (redis).
    assert after.snapshot.pending_turn is not None
    assert after.snapshot.pending_turn.skill_id == "redis"

    obj_report = next(o for o in after.public.report.objectives if o.objective_id == obj_id)
    assert obj_report.assessment == Assessment.AT
    assert {c.criterion_id: c.assessment for c in obj_report.criteria} == {c1: Assessment.AT, c2: Assessment.AT}
    assert any(ev.criterion_id == c2 and ev.turn_id == after.snapshot.turns[0].turn_id for ev in obj_report.evidence)


def test_secondary_observations_enforce_all_safety_gates_without_failing_primary(setup, monkeypatch):
    from adaptive_questioning.evidence.models import ClarifyRequest, Observation

    provider, engine, _ = setup
    provider.criterion_count = 2
    started = start(engine, [skill("python")])
    obj_id = started.snapshot.queue[0]
    c1, c2 = [c.criterion_id for c in started.snapshot.objectives[obj_id].objective.criteria]

    candidate_answer = "Em dùng dict để giữ thứ tự. Độ phức tạp O(n). Và em dùng Redis."
    original_judge = provider.judge
    calls = []

    def noisy_secondary_judge(context):
        calls.append(json.loads(context))
        judgment = original_judge(context)
        judgment.secondary_observations = [
            # Gate 1: BELOW / CONTRADICTS must never be recorded on an unasked criterion.
            Observation(
                criterion_id=c2, response_excerpt="Em dùng dict để giữ thứ tự.",
                observation="CONTRADICTS", performance="BELOW",
                rationale="Ứng viên chưa phân tích độ phức tạp đầy đủ.",
            ),
            # Gate 1: ABOVE is forbidden for secondary observations.
            Observation(
                criterion_id=c2, response_excerpt="Em dùng dict để giữ thứ tự.",
                observation="SUPPORTS", performance="ABOVE",
                rationale="Ứng viên giải thích vượt chuẩn rất rõ ràng.",
            ),
            # Gate 3: Keyword-only snippet (< 25 chars / < 5 words) rejected by substance guard.
            Observation(
                criterion_id=c2, response_excerpt="Độ phức tạp O(n).",
                observation="SUPPORTS", performance="AT_TARGET",
                rationale="Ứng viên có nhắc tới độ phức tạp O(n).",
            ),
            # Gate 3: Fabricated excerpt must be soft-dropped without retrying primary judge.
            Observation(
                criterion_id=c2, response_excerpt="Đoạn bịa không hề có trong câu trả lời của ứng viên.",
                observation="SUPPORTS", performance="AT_TARGET",
                rationale="Ứng viên giải thích đúng độ phức tạp tuyến tính.",
            ),
            # Gate 3: English prose rationale rejected.
            Observation(
                criterion_id=c2, response_excerpt="Em dùng dict để giữ thứ tự. Độ phức tạp O(n).",
                observation="SUPPORTS", performance="AT_TARGET",
                rationale="The candidate correctly explains linear complexity without missing any edge case.",
            ),
        ]
        return judgment

    monkeypatch.setattr(provider, "judge", noisy_secondary_judge)
    after = answer(engine, started.snapshot, candidate_answer)

    # Gate 4: Primary grading succeeded on attempt 1 with ZERO retries despite 5 invalid secondary items.
    assert len(calls) == 1
    assert after.snapshot.turns[0].judgment.secondary_observations == []
    assert c2 not in after.snapshot.objectives[obj_id].criterion_results
    # Next turn must still ask c2 normally since none of the invalid secondary items passed.
    assert after.snapshot.pending_turn is not None
    assert after.snapshot.pending_turn.question.criterion_ids == [c2]

    # Gate 2: Hinted turns must not send secondary_criteria or accept secondary credit.
    practice = engine.start(StartRequest(
        session_id="practice-hint-no-secondary",
        skills=[skill("python")],
        config={"session_purpose": "PRACTICE", "max_questions": 3},
    ))
    hinted = engine.clarify(ClarifyRequest(
        snapshot=practice.snapshot,
        turn_id=practice.snapshot.pending_turn.turn_id,
        expected_state_version=practice.snapshot.state_version,
        kind="HINT",
    ))
    p_obj_id = hinted.snapshot.queue[0]
    _, p_c2 = [c.criterion_id for c in hinted.snapshot.objectives[p_obj_id].objective.criteria]
    hint_calls = []

    def hinted_judge(context):
        hint_calls.append(json.loads(context))
        judgment = original_judge(context)
        judgment.secondary_observations = [Observation(
            criterion_id=p_c2,
            response_excerpt="Độ phức tạp thời gian là O(n) vì duyệt mảng đúng một lần duy nhất.",
            observation="SUPPORTS",
            performance="AT_TARGET",
            rationale="Ứng viên phân tích rõ độ phức tạp thời gian tuyến tính.",
        )]
        return judgment

    monkeypatch.setattr(provider, "judge", hinted_judge)
    after_hint = answer(
        engine,
        hinted.snapshot,
        "Em dùng dict để lưu khóa. Độ phức tạp thời gian là O(n) vì duyệt mảng đúng một lần duy nhất.",
    )
    assert "secondary_criteria" not in hint_calls[0]
    assert after_hint.snapshot.turns[0].judgment.secondary_observations == []
    assert p_c2 not in after_hint.snapshot.objectives[p_obj_id].criterion_results


def test_reflective_judge_module_wires_secondary_criteria_and_clears_on_inability():
    import dspy
    from adaptive_questioning.evidence.dspy_modules import (
        EvidenceAssessment,
        ReflectiveJudgeModule,
        build_judge_stage1_inputs,
    )
    from adaptive_questioning.evidence.models import Observation

    ctx = json.dumps({
        "interaction_mode": "TEXT",
        "session_purpose": "ASSESSMENT",
        "objective": {
            "skill_id": "python",
            "claim": "Dedup",
            "target_depth": 2,
            "criteria": [{"criterion_id": "o1:c1", "description": "Code đúng"}],
        },
        "secondary_criteria": [{"criterion_id": "o1:c2", "description": "Phân tích Big-O"}],
        "turn": {
            "action": "INITIAL",
            "question_depth": 2,
            "question": {"text": "Viết hàm dedup", "criterion_ids": ["o1:c1"]},
            "answer": "Em dùng dict setdefault để giữ bản ghi đầu và độ phức tạp thời gian là O(n) vì duyệt một lần.",
        },
        "answer_lines": [{"line": 1, "text": "Em dùng dict setdefault để giữ bản ghi đầu và độ phức tạp thời gian là O(n) vì duyệt một lần."}],
    }, ensure_ascii=False)

    stage1 = build_judge_stage1_inputs(ctx)
    assert "o1:c2" in stage1["rubric_criterion"]

    assessment = EvidenceAssessment(
        observations=[Observation(
            criterion_id="o1:c1",
            response_excerpt="Em dùng dict setdefault để giữ bản ghi đầu",
            observation="SUPPORTS",
            performance="AT_TARGET",
            rationale="Đúng yêu cầu.",
        )],
        secondary_observations=[Observation(
            criterion_id="o1:c2",
            response_excerpt='"độ phức tạp thời gian là O(n) vì duyệt một lần."',
            observation="SUPPORTS",
            performance="AT_TARGET",
            rationale="Phân tích đúng Big-O O(n).",
        )],
        feedback="Đã ghi nhận cách làm và phân tích độ phức tạp của bạn.",
    )
    lm = dspy.utils.DummyLM([{"reasoning": "Đạt cả tiêu chí chính và phụ.", "assessment": assessment.model_dump(mode="json")}])
    lm.adapter = dspy.JSONAdapter()
    module = ReflectiveJudgeModule()
    with dspy.context(lm=lm, adapter=dspy.JSONAdapter()):
        pred = module(context=ctx)
    assert len(pred.judgment.secondary_observations) == 1
    assert pred.judgment.secondary_observations[0].criterion_id == "o1:c2"
    assert pred.judgment.secondary_observations[0].response_excerpt == "độ phức tạp thời gian là O(n) vì duyệt một lần."


def test_static_system_prompt_prefix_remains_byte_identical_for_prompt_caching():
    import dspy
    from adaptive_questioning.evidence.provider import DSPyAssessmentProvider

    base_q_ctx = {
        "objective": {
            "skill_id": "rest_api",
            "claim": "Thiết kế API idempotent",
            "target_depth": 3,
            "criteria": [{
                "criterion_id": "c1",
                "description": "Chống xử lý trùng khi retry",
                "expected_evidence": "Thiết kế khóa idempotency nhất quán",
                "below_target": "Tạo giao dịch mới mỗi lần retry",
                "at_target": "Dùng khóa định danh theo request ở kho dùng chung",
                "above_target": "Xử lý tranh chấp đồng thời",
                "essential": True,
            }],
        },
        "required_question_contract": {"mode": "DESIGN", "depth": 3, "criterion_ids": ["c1"]},
        "interaction_mode": "TEXT",
        "action": "INITIAL",
        "depth_definition": "Analysis & Problem Solving",
        "probe_reason": "Collect initial evidence",
        "history": [],
        "prior_observations": [],
        "other_questions": [],
    }
    verif_q_ctx = {
        **base_q_ctx,
        "cv_evidence": ["Xây dựng API thanh toán chống tạo đơn trùng."],
        "verification_context": {"jd_excerpt": "Vị trí cần xử lý retry sau timeout.", "detail_to_verify": "Khóa nhận diện retry"},
    }
    base_review_ctx = {
        "question": "API thanh toán xử lý retry thế nào để không trừ tiền hai lần?",
        "criterion": base_q_ctx["objective"]["criteria"][0],
        "action": "INITIAL",
        "question_depth": 3,
        "target_depth": 3,
        "depth_definition": "Analysis & Problem Solving",
        "mode": "DESIGN",
        "interaction_mode": "TEXT",
        "probe_reason": "Collect initial evidence",
        "unresolved": [],
        "history": [],
    }
    easier_review_ctx = {
        **base_review_ctx,
        "action": "ASK_EASIER",
        "question_depth": 2,
        "history": [{"question": "Q1", "answer": "Em chưa rõ.", "action": "INITIAL", "depth": 3}],
    }
    clarify_verif_review_ctx = {
        **base_review_ctx,
        "action": "CLARIFY",
        "unresolved": ["khóa nhận diện retry"],
        "verification_context": verif_q_ctx["verification_context"],
        "cv_evidence": verif_q_ctx["cv_evidence"],
        "history": [{"question": "Q1", "answer": "Em lưu database.", "action": "INITIAL", "depth": 3}],
    }

    q_reply = {"reasoning": "Hỏi đúng tiêu chí.", "question": {
        "text": "API thanh toán nhận diện retry thế nào?",
        "criterion_ids": ["c1"], "evidence_scope": "idempotency-key", "mode": "DESIGN", "depth": 3,
    }}
    rev_reply = {"review": {"verdict": "ALIGNED", "reason": ""}}
    lm = dspy.utils.DummyLM([q_reply, q_reply, rev_reply, rev_reply, rev_reply])
    lm.adapter = dspy.JSONAdapter()
    provider = DSPyAssessmentProvider(lm=lm, compiled_dir=str(DEFAULT_COMPILED_DIR))

    provider.question(json.dumps(base_q_ctx, ensure_ascii=False))
    provider.question(json.dumps(verif_q_ctx, ensure_ascii=False))
    assert lm.history[0]["messages"][:-1] == lm.history[1]["messages"][:-1]

    provider.review_question(json.dumps(base_review_ctx, ensure_ascii=False))
    provider.review_question(json.dumps(easier_review_ctx, ensure_ascii=False))
    provider.review_question(json.dumps(clarify_verif_review_ctx, ensure_ascii=False))
    assert lm.history[2]["messages"][:-1] == lm.history[3]["messages"][:-1] == lm.history[4]["messages"][:-1]
    assert "Reject an unrelated decision" in lm.history[2]["messages"][0]["content"]
    assert "change the correct answer" in lm.history[2]["messages"][0]["content"]


def test_compiled_demos_and_inputs_strip_redundant_boilerplate_without_reducing_counts():
    from adaptive_questioning.evidence.dspy_modules import build_judge_stage1_inputs

    q_mod, j_mod, a_mod, b_mod = load_all_compiled_modules(DEFAULT_COMPILED_DIR)
    assert len(q_mod.initial.predict.demos) == 3
    assert len(q_mod.followup.predict.demos) == 3
    assert len(q_mod.diagnostic.predict.demos) == 3
    assert len(j_mod.assess.predict.demos) == 3
    assert len(a_mod.demos) == 4
    assert len(b_mod.demos) == 2

    # Alignment demos use single-line depth_definition and strip empty boilerplate & non-signature verdict key.
    for demo in a_mod.demos:
        assert "verdict" not in demo
        ctx = json.loads(demo["context"])
        assert "depth_definitions" not in ctx
        assert isinstance(ctx.get("depth_definition"), str) and ctx["depth_definition"]
        for empty_key in ("unresolved", "history", "cv_evidence", "case_notes"):
            assert ctx.get(empty_key, "MISSING") != []

    # Question demos strip empty lists/default-zero progress and metadata clutter.
    assert q_mod.initial.predict.demos[0]["session_context"] == "{}"
    for branch in (q_mod.followup, q_mod.diagnostic):
        for demo in branch.predict.demos:
            sc = json.loads(demo["session_context"])
            for item in sc.get("history", []):
                assert "turn_id" not in item and "introduction" not in item and "coding_spec" not in item
            for obs in sc.get("prior_observations", []):
                assert "turn_id" not in obs and "independent" not in obs

    # Judge demos avoid duplicating answer/answer_lines and drop empty prior_and_repair boilerplate.
    for demo in j_mod.assess.predict.demos:
        assert demo["prior_and_repair_context"] == "{}"
        ans = json.loads(demo["candidate_answer"])
        assert ("answer_lines" in ans) ^ ("answer" in ans)

    # Live coding turn with submitted_code + transcript avoids 3x code duplication and strips coding_spec.
    code = "def solve(xs):\n    return list(dict.fromkeys(xs))"
    transcript = "Em dùng dict.fromkeys để giữ thứ tự O(n)."
    full_answer = f"{code}\n\n{transcript}"
    live_ctx = json.dumps({
        "interaction_mode": "VOICE",
        "objective": {"skill_id": "python", "claim": "Dedup", "target_depth": 2, "criteria": [{"criterion_id": "c1"}]},
        "turn": {
            "action": "INITIAL",
            "question_depth": 2,
            "question": {
                "text": "Viết hàm solve(xs)",
                "criterion_ids": ["c1"],
                "evidence_scope": "dedup",
                "requires_code": True,
                "coding_spec": {"reference_solution": "SECRET_REF", "hidden_tests": [{"name": "h1"}]},
            },
            "answer": full_answer,
            "submitted_code": code,
            "transcript": transcript,
        },
        "answer_lines": [{"line": i, "text": t} for i, t in enumerate(full_answer.splitlines(), start=1)],
        "prior_observations": [],
        "prior_turns": [],
        "case_notes": [],
    }, ensure_ascii=False)
    stage1 = build_judge_stage1_inputs(live_ctx)
    turn_ctx = json.loads(stage1["turn_context"])
    assert "coding_spec" not in turn_ctx["question"]
    assert "SECRET_REF" not in stage1["turn_context"]
    assert turn_ctx["question"]["requires_code"] is True
    assert "case_notes" not in turn_ctx
    cand = json.loads(stage1["candidate_answer"])
    assert "answer" not in cand and "submitted_code" not in cand and "transcript" not in cand
    assert cand["submitted_code_lines"] == [1, 2]
    assert "1: def solve(xs):" in cand["answer_lines"] and transcript in cand["answer_lines"]
    assert stage1["prior_and_repair_context"] == "{}"


def test_sql_free_run_missing_table_attaches_helpful_notice_while_spec_runs_normally():
    from adaptive_questioning.evidence.code_runner import CodingSpec, CodingTestCase, LocalSubprocessCodeRunner
    from adaptive_questioning.evidence.coding_verification import (
        SQL_FREE_RUN_NO_SCHEMA_NOTICE,
        run_sample_code,
    )

    runner = LocalSubprocessCodeRunner()
    query = "SELECT id, name FROM users WHERE age >= 18 ORDER BY name ASC;"

    # Free-run SQL (coding_spec=None): empty in-memory SQLite reports no such table + clear Vietnamese guidance.
    free_res = run_sample_code(code=query, spec=None, language_override="sql", runner=runner)
    assert "no such table: users" in free_res.compile_error
    assert free_res.environment_notice == SQL_FREE_RUN_NO_SCHEMA_NOTICE

    # Proper SQLite coding_spec with setup_sql + sample_tests passes cleanly with zero notice.
    spec = CodingSpec(
        language="sql",
        entry_point="",
        setup_sql="CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT, age INTEGER);",
        sample_tests=[CodingTestCase(
            name="adults_sorted",
            input_data="INSERT INTO users VALUES (1, 'Chi', 22), (2, 'An', 16), (3, 'Binh', 18);",
            expected_output='[[3, "Binh"], [1, "Chi"]]',
        )],
    )
    spec_res = run_sample_code(code=query, spec=spec, language_override="sql", runner=runner)
    assert spec_res.compile_error == ""
    assert spec_res.environment_notice == ""
    assert spec_res.passed == 1 and spec_res.total == 1


def test_validate_question_blocks_raw_coding_harness_leakage_in_question_text():
    ctx = {"required_question_contract": {"mode": Mode.CODING, "depth": 1, "criterion_ids": ["c1"]}}
    leaked = (
        "Hãy viết truy vấn SQL lấy `product_name` và `price` từ bảng `products`.\n\n"
        "```sql\n-- Setup\nCREATE TABLE products (id INTEGER PRIMARY KEY, product_name TEXT, price REAL);\n"
        "INSERT INTO products VALUES (1, 'A', 50.0);\n-- Entry Point: Write your SELECT query here\n```\n\n"
        'Expected Output: [["D", 200.0], ["B", 150.0]]'
    )
    bad = validate_question(
        Question(text=leaked, criterion_ids=["c1"], mode=Mode.CODING, depth=1, evidence_scope="sql-products"),
        ctx,
    )
    assert any("Expected Output" in err for err in bad.hard_errors)

    clean = (
        "Bảng `products` gồm các cột `id`, `product_name` và `price`. "
        "Hãy viết truy vấn SQL lấy `product_name` và `price` của các sản phẩm có `price > 100`, "
        "sắp xếp giảm dần theo `price`."
    )
    good = validate_question(
        Question(text=clean, criterion_ids=["c1"], mode=Mode.CODING, depth=1, evidence_scope="sql-products"),
        ctx,
    )
    assert good.all_errors == []
