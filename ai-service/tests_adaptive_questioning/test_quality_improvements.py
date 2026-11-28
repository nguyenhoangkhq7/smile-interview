"""Regression tests for mode-aware questioning, hybrid coding judging, clarifications, and fair scoring."""
import json
import shutil

import dspy
import pytest

from adaptive_questioning.evidence.code_runner import CodingSpec, CodingTestCase, LocalSubprocessCodeRunner
from adaptive_questioning.evidence.coding_verification import sanitize_coding_spec
from adaptive_questioning.evidence.dspy_modules import build_judge_stage1_inputs
from adaptive_questioning.evidence.models import (
    Action, Assessment, BlueprintDraft, ClarifyRequest, CriterionDraft, InterviewOpening, Mode, ObjectiveDraft,
    Question, StartRequest, SuitableMode, TransitionRequest,
)
from adaptive_questioning.evidence.policy_config import InterviewPolicy
from adaptive_questioning.evidence.provider import DSPyAssessmentProvider
from skill_gap.domain.models import JobTask
from test_evidence_workflow import answer, setup, skill, start


def test_judge_receives_turn_clarifications_and_session_purpose(setup, monkeypatch):
    provider, engine, _ = setup
    started = engine.start(StartRequest(
        session_id="clarify-to-judge",
        skills=[skill("postgresql")],
        config={"session_purpose": "PRACTICE", "max_questions": 2},
    ))
    clarified = engine.clarify(ClarifyRequest(
        snapshot=started.snapshot,
        turn_id=started.snapshot.pending_turn.turn_id,
        expected_state_version=started.snapshot.state_version,
        kind="CLARIFY_PROMPT",
        candidate_question="Có cần xử lý đa vùng địa lý không?",
    ))
    captured_stage1 = []
    original_judge = provider.judge

    def spy_judge(context):
        captured_stage1.append(build_judge_stage1_inputs(context))
        return original_judge(context)

    monkeypatch.setattr(provider, "judge", spy_judge)
    answer(engine, clarified.snapshot, "Dùng ràng buộc UNIQUE trên một cụm PostgreSQL duy nhất.")
    assert len(captured_stage1) == 1
    turn_ctx = json.loads(captured_stage1[0]["turn_context"])
    assert turn_ctx["session_purpose"] == "PRACTICE"
    assert len(turn_ctx["turn_clarifications"]) == 1
    assert "đa vùng" in turn_ctx["turn_clarifications"][0]["question"]


def test_coding_partial_failure_runs_hybrid_judge_and_triggers_code_repair(setup, monkeypatch):
    from test_interview_quality_upgrade import LAST_RECORD, start_coding

    provider, engine, _ = setup
    snapshot = start_coding(provider, engine, monkeypatch)
    provider.observation, provider.performance = "CONTRADICTS", "BELOW"
    seen_q_contexts = []
    orig_q = provider.question
    monkeypatch.setattr(provider, "question", lambda ctx: (seen_q_contexts.append(json.loads(ctx)), orig_q(ctx))[1])

    result = answer(engine, snapshot, LAST_RECORD + "\n\nEm dùng dict để đạt O(n).")
    assert result.snapshot.turns[0].judgment.feedback == "Assessment feedback"
    assert result.snapshot.pending_turn.action == Action.CLARIFY
    assert "passed some automated tests" in seen_q_contexts[-1]["question_guidance"]


def test_sanitize_coding_spec_strips_mismatched_entry_point_and_bad_sql_cases():
    def make_q(spec: CodingSpec) -> Question:
        return Question(
            text="Hãy viết hàm giải quyết yêu cầu.",
            criterion_ids=["c1"], mode=Mode.CODING, depth=2, evidence_scope="sanitize-check", coding_spec=spec,
        )

    missing_py_fn = make_q(CodingSpec(
        language="python",
        entry_point="expected_fn",
        starter_code="def other_fn(x):\n    return x\n",
        sample_tests=[CodingTestCase(name="s1", input_data="1", expected_output="1")],
    ))
    assert sanitize_coding_spec(missing_py_fn).coding_spec is None

    empty_expected = make_q(CodingSpec(
        language="python",
        entry_point="ok_fn",
        starter_code="def ok_fn(x):\n    return x\n",
        sample_tests=[CodingTestCase(name="s1", input_data="1", expected_output="   ")],
    ))
    assert sanitize_coding_spec(empty_expected).coding_spec is None

    bad_sql_case = make_q(CodingSpec(
        language="sql",
        setup_sql="CREATE TABLE items(id INT);",
        sample_tests=[CodingTestCase(name="s1", input_data="INSERT INTO missing_table VALUES (1);", expected_output="[[1]]")],
    ))
    assert sanitize_coding_spec(bad_sql_case).coding_spec is None


def test_behavioral_below_probes_star_followup_instead_of_dropping_to_l1(setup):
    provider, engine, _ = setup
    started = engine.start(StartRequest(
        session_id="behavioral-star-probe",
        skills=[skill("postgresql")],
        opening=InterviewOpening(role_title="Backend Intern"),
        config={"focused_question_mode": Mode.BEHAVIORAL, "max_questions": 3},
    ))
    assert started.snapshot.pending_turn is None  # opening phase first
    from adaptive_questioning.evidence.models import ConversationRequest
    started = engine.converse(ConversationRequest(
        snapshot=started.snapshot,
        message_id=started.snapshot.conversation.message.message_id,
        expected_state_version=started.snapshot.state_version,
        action="SKIP_INTRODUCTION",
    ))
    provider.observation, provider.performance = "CONTRADICTS", "BELOW"
    next_turn = answer(engine, started.snapshot, "Cả nhóm em cố gắng sửa lỗi trong đêm.")
    assert next_turn.snapshot.pending_turn.action == Action.CLARIFY
    assert next_turn.snapshot.pending_turn.question_depth == 2  # stays at L2 STAR, never drops to L1 theory


def test_mixed_mode_optional_behavioral_and_criteria_aware_budget_allocation(setup):
    provider, engine, _ = setup
    provider.criterion_count = 2
    skills = [
        skill("java", importance_weight=0.95, priority=0.5),
        skill("spring", importance_weight=0.90, priority=0.4),
        skill("sql", importance_weight=0.85, priority=0.3),
        skill("redis", importance_weight=0.80, priority=0.2),
    ]
    # 10 questions => initial_limit = 7; each skill has 2 essential criteria => at most 3 objectives (6 slots) + 1 STAR (1 slot) = 7
    res = engine.start(StartRequest(
        session_id="criteria-budget",
        skills=skills,
        config={"max_questions": 10, "include_behavioral_in_mixed": True},
    ))
    queued_skills = [res.snapshot.objectives[oid].objective.skill_id for oid in res.snapshot.queue]
    assert len(queued_skills) == 4  # 3 technical (6 criteria) + 1 STAR (1 criterion) = 7 slots
    assert "behavioral_competency" in queued_skills
    assert "redis" not in queued_skills  # cleanly held in PLAN_BUDGET instead of over-queuing


def test_l1_explicit_inability_concludes_not_demonstrated(setup):
    provider, engine, _ = setup
    engine.policy = InterviewPolicy(fallback_depth=1)
    started = start(engine, [skill("postgresql")])
    assert started.snapshot.pending_turn.question_depth == 1
    finished = answer(engine, started.snapshot, "Em không biết.")
    assert finished.public.is_finished
    assert finished.public.report.objectives[0].assessment == Assessment.NOT_DEMONSTRATED


def test_l4_design_objective_can_achieve_above_target_via_deeper_probe(setup, monkeypatch):
    provider, engine, _ = setup
    engine.policy = InterviewPolicy(allow_extension_probes=True)

    def l4_design_blueprint(context):
        req_id, req = next(iter(json.loads(context)["requirements"].items()))
        return BlueprintDraft(objectives=[ObjectiveDraft(
            requirement_id=req_id,
            skill_id=req["skill_id"],
            target_depth=4,
            extension_depth=4,
            depth_basis="TASK",
            depth_rationale="Senior system design task",
            depth_evidence_spans=[req["description"]],
            criteria=[CriterionDraft(
                description="Thiết kế hệ thống phân tán chịu tải cao",
                expected_evidence="Đề xuất kiến trúc phân tán đáp ứng ràng buộc tải và độ trễ",
                below_target="Thiết kế đơn nút không xử lý điểm nghẽn",
                at_target="Đề xuất kiến trúc phân tán rõ ràng cùng đánh đổi nhất quán",
                above_target="Phân tích chiến lược chịu lỗi đa vùng, backpressure và kế hoạch phục hồi sự cố",
                essential=True,
            )],
            suitable_modes=[SuitableMode(mode=Mode.DESIGN)],
        )])

    monkeypatch.setattr(provider, "blueprint", l4_design_blueprint)
    task = JobTask(description="Design distributed payment architecture", evidence_spans=["Design distributed payment architecture"], required_level=5)
    initial = start(engine, [skill("architecture", job_tasks=[task])])
    after_target = answer(engine, initial.snapshot, "Dùng outbox pattern, partition theo merchant_id và đánh đổi eventual consistency.")
    assert after_target.snapshot.pending_turn.action == Action.DEEPER
    assert after_target.snapshot.pending_turn.question_depth == 4
    provider.performance = "ABOVE"
    after_ext = answer(engine, after_target.snapshot, "Áp dụng active-active failover, circuit breaker và backpressure ở queue.")
    assert after_ext.public.is_finished
    assert after_ext.public.report.objectives[0].assessment == Assessment.ABOVE
    assert [ev.depth_role for ev in after_ext.public.report.objectives[0].evidence] == ["TARGET", "EXTENSION"]


def test_unclear_stagnation_with_gaps_generates_study_recommendations(setup, monkeypatch):
    provider, engine, _ = setup
    provider.observation, provider.performance = "UNCLEAR", "UNDETERMINED"
    orig_judge = provider.judge

    def vague_judge(context):
        j = orig_judge(context)
        j.observations[0].unresolved_aspects = ["chưa nêu rõ chiến lược đánh chỉ mục tổng hợp"]
        return j

    monkeypatch.setattr(provider, "judge", vague_judge)
    res = start(engine)
    for _ in range(3):
        res = answer(engine, res.snapshot, "Em sẽ tối ưu truy vấn để chạy nhanh hơn.")
    assert res.public.is_finished
    obj = res.public.report.objectives[0]
    assert obj.stop_reason == "NO_PROGRESS"
    assert any("chỉ mục tổng hợp" in rec for rec in obj.study_recommendations)


def test_practice_hint_requires_independent_transfer_after_retry(setup, monkeypatch):
    provider, engine, _ = setup
    started = engine.start(StartRequest(
        session_id="practice-hint-track",
        skills=[skill("postgresql")],
        config={"session_purpose": "PRACTICE", "max_questions": 3},
    ))
    hinted = engine.clarify(ClarifyRequest(
        snapshot=started.snapshot,
        turn_id=started.snapshot.pending_turn.turn_id,
        expected_state_version=started.snapshot.state_version,
        kind="HINT",
    ))
    cid = started.snapshot.pending_turn.question.criterion_ids[0]
    state = next(iter(hinted.snapshot.objectives.values()))
    assert cid in state.hinted_criteria

    retry = answer(engine, hinted.snapshot, "EXPLAIN ANALYZE giúp phát hiện sequential scan.")
    assert retry.snapshot.pending_turn.practice_step == "RETRY"
    assert retry.snapshot.pending_turn.question.text == started.snapshot.pending_turn.question.text
    assert retry.public.report.objectives[0].assessment == Assessment.INSUFFICIENT
    original = provider.question
    def new_case(context):
        generated = original(context)
        generated.text = "How would you identify why this sales aggregate suddenly reads the entire orders table?"
        return generated
    monkeypatch.setattr(provider, "question", new_case)
    transfer = answer(engine, retry.snapshot, "EXPLAIN ANALYZE")
    assert transfer.snapshot.pending_turn.practice_step == "TRANSFER"
    assert transfer.public.report.objectives[0].assessment == Assessment.INSUFFICIENT
    assert transfer.snapshot.pending_turn.question.evidence_scope != retry.snapshot.pending_turn.question.evidence_scope
    finished = answer(engine, transfer.snapshot, "I would inspect EXPLAIN ANALYZE for this aggregate.")
    assert finished.public.is_finished
    obj = finished.public.report.objectives[0]
    assert obj.assessment == Assessment.AT
    assert obj.criteria[0].transfer_verified
    assert finished.public.report.turn_reviews[0].level_up_tip
    assert any("gợi ý" in note.lower() for note in finished.public.report.turn_reviews[0].delivery_notes)


def test_provider_selects_deep_judge_lm_for_l3_l4_and_design_turns(monkeypatch):
    monkeypatch.delenv("OPENROUTER_JUDGE_REASONING_EFFORT", raising=False)
    lm = dspy.LM("openai/gpt-4o-mini", api_key="test-key")
    provider = DSPyAssessmentProvider(lm=lm)
    assert provider.judge_lm.kwargs["extra_body"] == {"reasoning": {"effort": "none"}}
    assert provider.judge_deep_lm.kwargs["extra_body"] == {"reasoning": {"effort": "low"}}

    l2_tech = json.dumps({"turn": {"question_depth": 2, "mode": "TECHNICAL_EXPLANATION"}})
    l3_debug = json.dumps({"turn": {"question_depth": 3, "mode": "DEBUGGING"}})
    l2_design = json.dumps({"turn": {"question_depth": 2, "mode": "DESIGN"}})
    l2_code_nosandbox = json.dumps({"turn": {"question_depth": 2, "mode": "CODING"}})
    l2_code_sandbox = json.dumps({"turn": {"question_depth": 2, "mode": "CODING"}, "coding_checks": {"passed": 2, "total": 2}})

    assert provider._select_judge_lm(l2_tech) is provider.judge_lm
    assert provider._select_judge_lm(l3_debug) is provider.judge_deep_lm
    assert provider._select_judge_lm(l2_design) is provider.judge_deep_lm
    assert provider._select_judge_lm(l2_code_nosandbox) is provider.judge_deep_lm
    assert provider._select_judge_lm(l2_code_sandbox) is provider.judge_lm


def test_coding_clarify_inherits_coding_spec_prefills_prior_code_and_recovers_without_contradiction(setup, monkeypatch):
    from test_interview_quality_upgrade import FIRST_RECORD, LAST_RECORD, start_coding

    provider, engine, _ = setup
    snapshot = start_coding(provider, engine, monkeypatch)
    initial_spec = snapshot.pending_turn.question.coding_spec
    assert initial_spec is not None and len(initial_spec.hidden_tests) > 0

    provider.observation, provider.performance = "CONTRADICTS", "BELOW"
    after_buggy = engine.respond(TransitionRequest(
        snapshot=snapshot,
        turn_id=snapshot.pending_turn.turn_id,
        expected_state_version=snapshot.state_version,
        candidate_response="Em dùng dict để giữ bản ghi.",
        submitted_code=LAST_RECORD,
    ))
    clarify_turn = after_buggy.snapshot.pending_turn
    assert clarify_turn is not None
    assert clarify_turn.action == Action.CLARIFY
    assert clarify_turn.question.requires_code is True
    assert clarify_turn.question.coding_spec is not None
    assert clarify_turn.question.coding_spec.starter_code == LAST_RECORD.strip()
    assert clarify_turn.question.coding_spec.hidden_tests == initial_spec.hidden_tests

    provider.observation, provider.performance = "SUPPORTS", "AT_TARGET"
    after_fix = engine.respond(TransitionRequest(
        snapshot=after_buggy.snapshot,
        turn_id=clarify_turn.turn_id,
        expected_state_version=after_buggy.snapshot.state_version,
        candidate_response="Em đã sửa để giữ bản ghi đầu tiên.",
        submitted_code=FIRST_RECORD,
    ))
    state = next(iter(after_fix.snapshot.objectives.values()))
    assert state.contradictions == []
    assert after_fix.public.is_finished
    assert after_fix.public.report.objectives[0].assessment == Assessment.AT


def test_behavioral_clarify_recovers_to_at_target_without_contradiction(setup):
    from adaptive_questioning.evidence.models import ConversationRequest

    provider, engine, _ = setup
    engine.policy = InterviewPolicy(allow_extension_probes=False)
    started = engine.start(StartRequest(
        session_id="behavioral-clarify-recovery",
        skills=[skill("postgresql")],
        opening=InterviewOpening(role_title="Backend Intern"),
        config={"focused_question_mode": Mode.BEHAVIORAL, "max_questions": 4},
    ))
    started = engine.converse(ConversationRequest(
        snapshot=started.snapshot,
        message_id=started.snapshot.conversation.message.message_id,
        expected_state_version=started.snapshot.state_version,
        action="SKIP_INTRODUCTION",
    ))
    obj_id = started.snapshot.pending_turn.objective_id
    provider.observation, provider.performance = "CONTRADICTS", "BELOW"
    after_vague = answer(engine, started.snapshot, "Cả nhóm em cố gắng sửa lỗi trong đêm.")
    assert after_vague.snapshot.pending_turn.action == Action.CLARIFY

    provider.observation, provider.performance = "SUPPORTS", "AT_TARGET"
    after_star = answer(
        engine,
        after_vague.snapshot,
        "Em trực tiếp truy vết query gây deadlock bằng pg_stat_activity, tách batch cập nhật và giảm lỗi 500 từ 8% xuống 0%.",
    )
    state = after_star.snapshot.objectives[obj_id]
    assert state.contradictions == []
    assert state.lifecycle == "CLOSED"
    assert state.assessment == Assessment.AT
    if after_star.snapshot.pending_turn is not None:
        assert after_star.snapshot.pending_turn.action != Action.VERIFY


def test_sanitize_coding_spec_oracle_verifies_reference_solution_and_hides_from_public():
    def make_q(spec: CodingSpec) -> Question:
        return Question(
            text="Hãy viết hàm giải quyết yêu cầu.",
            criterion_ids=["c1"], mode=Mode.CODING, depth=2, evidence_scope="oracle-check", coding_spec=spec,
        )

    valid_spec = CodingSpec(
        language="python",
        entry_point="add_pair",
        starter_code="def add_pair(a, b):\n    pass\n",
        sample_tests=[CodingTestCase(name="s1", input_data="[1, 2]", expected_output="3")],
        hidden_tests=[CodingTestCase(name="h1", input_data='{"a": -5, "b": 5}', expected_output="0")],
        reference_solution="def add_pair(a, b):\n    return a + b\n",
    )
    kept = sanitize_coding_spec(make_q(valid_spec))
    assert kept.coding_spec is not None
    public_dump = kept.coding_spec.to_public().model_dump()
    assert "reference_solution" not in public_dump
    assert "hidden_tests" not in public_dump

    broken_hidden = valid_spec.model_copy(update={
        "hidden_tests": [CodingTestCase(name="bad_h1", input_data="[2, 2]", expected_output="5")],
    })
    assert sanitize_coding_spec(make_q(broken_hidden)).coding_spec is None

    disallowed_ref = valid_spec.model_copy(update={
        "reference_solution": "import numpy as np\ndef add_pair(a, b):\n    return int(np.add(a, b))\n",
    })
    assert sanitize_coding_spec(make_q(disallowed_ref)).coding_spec is None


def test_blueprint_applies_mode_aware_default_estimated_seconds(setup, monkeypatch):
    provider, engine, _ = setup

    def multi_mode_blueprint(context):
        reqs = json.loads(context)["requirements"]
        modes = [Mode.CODING, Mode.DEBUGGING, Mode.DESIGN]
        estimates = [120, 120, 210]  # first two default -> mode defaults (240, 180); third explicit -> kept (210)
        objectives = []
        for (req_id, req), mode, est in zip(reqs.items(), modes, estimates):
            objectives.append(ObjectiveDraft(
                requirement_id=req_id,
                skill_id=req["skill_id"],
                target_depth=2,
                extension_depth=3,
                depth_basis="TASK",
                depth_rationale="Task rationale",
                depth_evidence_spans=[req["description"]],
                estimated_seconds=est,
                criteria=[CriterionDraft(
                    description="Tiêu chí cốt lõi",
                    expected_evidence="Bằng chứng cốt lõi",
                    below_target="Chưa đạt",
                    at_target="Đạt",
                    above_target="Vượt",
                    essential=True,
                )],
                suitable_modes=[SuitableMode(mode=mode)],
            ))
        return BlueprintDraft(objectives=objectives)

    monkeypatch.setattr(provider, "blueprint", multi_mode_blueprint)
    res = start(engine, [skill("python"), skill("sql"), skill("architecture")])
    by_skill = {state.objective.skill_id: state.objective.estimated_seconds for state in res.snapshot.objectives.values()}
    assert by_skill["python"] == 240
    assert by_skill["sql"] == 180
    assert by_skill["architecture"] == 210


@pytest.mark.skipif(shutil.which("node") is None, reason="node runtime not installed in host test env")
def test_local_js_runner_supports_kwargs_defaults_and_async():
    runner = LocalSubprocessCodeRunner()
    res = runner.execute(
        language="javascript",
        code="async function greet(name, prefix = 'Hi') { return Promise.resolve(`${prefix} ${name}`); }",
        entry_point="greet",
        cases=[
            CodingTestCase(name="kwargs_default", input_data='{"name": "An"}', expected_output='"Hi An"'),
            CodingTestCase(name="kwargs_full", input_data='{"name": "An", "prefix": "Hello"}', expected_output='"Hello An"'),
            CodingTestCase(name="array_args", input_data='["Binh", "Hey"]', expected_output='"Hey Binh"'),
        ],
    )
    assert res.compile_error == ""
    assert res.passed == 3 and res.total == 3


def test_local_python_runner_supports_async_def():
    runner = LocalSubprocessCodeRunner()
    res = runner.execute(
        language="python",
        code="import asyncio\nasync def double_async(x, bonus=1):\n    await asyncio.sleep(0)\n    return x * 2 + bonus\n",
        entry_point="double_async",
        cases=[
            CodingTestCase(name="kwargs_default", input_data='{"x": 4}', expected_output="9"),
            CodingTestCase(name="list_args", input_data="[4, 2]", expected_output="10"),
        ],
    )
    assert res.compile_error == ""
    assert res.passed == 2 and res.total == 2


def test_behavioral_repeated_failures_diagnose_not_demonstrated_and_inability_skips_blank_clarify(setup):
    from adaptive_questioning.evidence.models import ConversationRequest

    provider, engine, _ = setup
    started = engine.start(StartRequest(
        session_id="behavioral-full-fail",
        skills=[skill("postgresql")],
        opening=InterviewOpening(role_title="Backend Intern"),
        config={"focused_question_mode": Mode.BEHAVIORAL, "max_questions": 6},
    ))
    started = engine.converse(ConversationRequest(
        snapshot=started.snapshot,
        message_id=started.snapshot.conversation.message.message_id,
        expected_state_version=started.snapshot.state_version,
        action="SKIP_INTRODUCTION",
    ))
    obj_id = started.snapshot.pending_turn.objective_id
    provider.observation, provider.performance = "CONTRADICTS", "BELOW"
    t1 = answer(engine, started.snapshot, "Cả nhóm em cố gắng sửa lỗi chung.")
    assert t1.snapshot.pending_turn.action == Action.CLARIFY
    t2 = answer(engine, t1.snapshot, "Em chỉ hỗ trợ chung chung cùng các bạn.")
    assert t2.snapshot.pending_turn.action == Action.FOLLOW_UP
    t3 = answer(engine, t2.snapshot, "Trong dự án khác em cũng chỉ xem các bạn làm.")
    state = t3.snapshot.objectives[obj_id]
    assert state.lifecycle == "CLOSED"
    assert state.assessment == Assessment.NOT_DEMONSTRATED

    started2 = engine.start(StartRequest(
        session_id="behavioral-inability",
        skills=[skill("postgresql")],
        opening=InterviewOpening(role_title="Backend Intern"),
        config={"focused_question_mode": Mode.BEHAVIORAL, "max_questions": 4},
    ))
    started2 = engine.converse(ConversationRequest(
        snapshot=started2.snapshot,
        message_id=started2.snapshot.conversation.message.message_id,
        expected_state_version=started2.snapshot.state_version,
        action="SKIP_INTRODUCTION",
    ))
    obj_id2 = started2.snapshot.pending_turn.objective_id
    after_inability = answer(engine, started2.snapshot, "Em không biết.")
    assert after_inability.snapshot.pending_turn.action == Action.FOLLOW_UP
    after_second_inability = answer(engine, after_inability.snapshot, "Em không biết.")
    state2 = after_second_inability.snapshot.objectives[obj_id2]
    assert state2.lifecycle == "CLOSED"
    assert state2.assessment == Assessment.NOT_DEMONSTRATED


def test_coding_reference_solution_flows_into_coaching_and_fallback_review_only_after_finish(setup, monkeypatch):
    from adaptive_questioning.evidence.reporting import coaching_context

    provider, engine, _ = setup
    ref_code = "def add_two(a, b):\n    return a + b\n"
    spec = CodingSpec(
        language="python",
        entry_point="add_two",
        starter_code="def add_two(a, b):\n    pass\n",
        sample_tests=[CodingTestCase(name="s1", input_data="[1, 2]", expected_output="3")],
        hidden_tests=[CodingTestCase(name="h1", input_data="[0, 5]", expected_output="5")],
        reference_solution=ref_code,
    )
    orig_q = provider.question

    def coding_q(ctx):
        q = orig_q(ctx)
        return q.model_copy(update={"coding_spec": spec})

    monkeypatch.setattr(provider, "question", coding_q)
    task = JobTask(description="Implement add_two helper function in Python", evidence_spans=["Implement add_two helper function in Python"], required_level=3)
    started = engine.start(StartRequest(
        session_id="coding-ref-coaching",
        skills=[skill("python", job_tasks=[task])],
        config={"max_questions": 1},
    ))
    assert "reference_solution" not in started.public.pending_turn.coding_spec.model_dump()

    provider.observation, provider.performance = "CONTRADICTS", "BELOW"
    finished = engine.respond(TransitionRequest(
        snapshot=started.snapshot,
        turn_id=started.snapshot.pending_turn.turn_id,
        expected_state_version=started.snapshot.state_version,
        candidate_response="Em cộng bị nhầm.",
        submitted_code="def add_two(a, b):\n    return a - b\n",
    ))
    assert finished.public.is_finished
    ctx = coaching_context(finished.snapshot)
    assert ctx["turns_needing_reference"][0]["verified_reference_code"]["code"] == ref_code.strip()
    review = finished.public.report.turn_reviews[0]
    assert "```python" in review.reference_answer
    assert "return a + b" in review.reference_answer


def test_clarify_passes_coding_contract_and_allows_all_modes_in_assessment(setup, monkeypatch):
    from adaptive_questioning.evidence.models import DialogueMessage
    from test_interview_quality_upgrade import start_coding

    provider, engine, _ = setup
    captured_clarify = []
    monkeypatch.setattr(
        provider,
        "clarify_prompt",
        lambda ctx: (captured_clarify.append(json.loads(ctx)), DialogueMessage(text="Bạn hãy trả về danh sách rỗng `[]` khi đầu vào rỗng."))[1],
        raising=False,
    )
    coding_snap = start_coding(provider, engine, monkeypatch)
    clarified = engine.clarify(ClarifyRequest(
        snapshot=coding_snap,
        turn_id=coding_snap.pending_turn.turn_id,
        expected_state_version=coding_snap.state_version,
        kind="CLARIFY_PROMPT",
        candidate_question="Nếu danh sách rỗng thì trả về gì?",
    ))
    assert len(captured_clarify) == 1
    contract = captured_clarify[0]["coding_contract"]
    assert contract["entry_point"] == "deduplicate_events"
    assert contract["hidden_test_names"] == ["keep-first"]
    assert len(contract["sample_tests"]) == 2
    assert len(clarified.public.pending_turn.clarifications) == 1

    # TECHNICAL_EXPLANATION in ASSESSMENT must also allow CLARIFY_PROMPT (while still blocking HINT).
    explain_task = JobTask(
        description="Explain PostgreSQL MVCC isolation levels",
        evidence_spans=["Explain PostgreSQL MVCC isolation levels"],
        required_level=2,
    )
    tech_started = engine.start(StartRequest(
        session_id="assess-clarify-tech",
        skills=[skill("postgresql", job_tasks=[explain_task])],
        config={"session_purpose": "ASSESSMENT", "focused_question_mode": Mode.TECHNICAL_EXPLANATION},
    ))
    tech_clarified = engine.clarify(ClarifyRequest(
        snapshot=tech_started.snapshot,
        turn_id=tech_started.snapshot.pending_turn.turn_id,
        expected_state_version=tech_started.snapshot.state_version,
        kind="CLARIFY_PROMPT",
        candidate_question="Câu hỏi đang xét hệ đơn nút hay cụm phân tán ạ?",
    ))
    assert len(tech_clarified.public.pending_turn.clarifications) == 1
    with pytest.raises(ValueError, match="Luyện tập"):
        engine.clarify(ClarifyRequest(
            snapshot=tech_clarified.snapshot,
            turn_id=tech_clarified.snapshot.pending_turn.turn_id,
            expected_state_version=tech_clarified.snapshot.state_version,
            kind="HINT",
        ))


def test_coding_zero_pass_offers_code_repair_clarify_instead_of_dropping_to_easier(setup, monkeypatch):
    from test_interview_quality_upgrade import start_coding

    provider, engine, _ = setup
    snapshot = start_coding(provider, engine, monkeypatch)
    provider.observation, provider.performance = "CONTRADICTS", "BELOW"
    seen_q_contexts = []
    orig_q = provider.question
    monkeypatch.setattr(provider, "question", lambda ctx: (seen_q_contexts.append(json.loads(ctx)), orig_q(ctx))[1])

    broken_code = "def deduplicate_events(events):\n    return None\n"
    result = engine.respond(TransitionRequest(
        snapshot=snapshot,
        turn_id=snapshot.pending_turn.turn_id,
        expected_state_version=snapshot.state_version,
        candidate_response="",
        submitted_code=broken_code,
    ))
    assert result.snapshot.turns[0].coding_checks.passed == 0
    assert result.snapshot.pending_turn is not None
    assert result.snapshot.pending_turn.action == Action.CLARIFY
    assert result.snapshot.pending_turn.question.coding_spec is not None
    assert result.snapshot.pending_turn.question.coding_spec.starter_code == broken_code.strip()
    assert "failed automated tests" in seen_q_contexts[-1]["question_guidance"]


def test_should_yield_does_not_interrupt_immediate_clarify_at_soft_limit(setup, monkeypatch):
    provider, engine, _ = setup
    provider.criterion_count = 2
    started = engine.start(StartRequest(
        session_id="no-yield-on-clarify",
        skills=[skill("postgresql", importance_weight=0.9), skill("redis", importance_weight=0.8)],
        config={"max_questions": 10},
    ))
    first_obj = started.snapshot.pending_turn.objective_id
    # Spend 2 turns resolving criterion 1 (1 unclear -> clarify -> pass)
    provider.observation, provider.performance = "UNCLEAR", "UNDETERMINED"
    t1 = answer(engine, started.snapshot, "Em dùng index.")
    provider.observation, provider.performance = "SUPPORTS", "AT_TARGET"
    t2 = answer(engine, t1.snapshot, "Em tạo composite index (status, created_at) phù hợp truy vấn.")
    assert t2.snapshot.pending_turn.objective_id == first_obj
    # Turn 3 on criterion 2 is UNCLEAR -> next action is CLARIFY at turns_spent == 3 (CRITERION_SOFT_LIMIT).
    # Plenty of budget remains for redis, so it must finish CLARIFY on criterion 2 instead of jumping away.
    provider.observation, provider.performance = "UNCLEAR", "UNDETERMINED"
    t3 = answer(engine, t2.snapshot, "Em kiểm tra sơ qua bằng EXPLAIN.")
    assert t3.snapshot.pending_turn.objective_id == first_obj
    assert t3.snapshot.pending_turn.action == Action.CLARIFY


def test_focus_skill_ids_filters_plan_and_allows_mastered_rehearsal_in_practice(setup):
    from adaptive_questioning.evidence.models import PriorAttemptContext

    provider, engine, _ = setup
    res = engine.start(StartRequest(
        session_id="focus-skills",
        skills=[skill("postgresql"), skill("redis"), skill("docker")],
        config={"focus_skill_ids": ["redis"], "max_questions": 6},
    ))
    queued_skills = [res.snapshot.objectives[oid].objective.skill_id for oid in res.snapshot.queue]
    assert queued_skills == ["redis"]
    excluded_reasons = {
        s.objective.skill_id: s.excluded_reason
        for s in res.snapshot.objectives.values()
        if s.lifecycle == "EXCLUDED"
    }
    assert excluded_reasons["postgresql"] == "SKILL_FILTER"
    assert excluded_reasons["docker"] == "SKILL_FILTER"

    # In PRACTICE mode, explicitly focusing a mastered skill allows rehearsing it immediately.
    practice = engine.start(StartRequest(
        session_id="focus-mastered-practice",
        skills=[skill("postgresql"), skill("redis")],
        prior_attempts=PriorAttemptContext(mastered_skill_ids={"postgresql"}),
        config={"session_purpose": "PRACTICE", "focus_skill_ids": ["postgresql"]},
    ))
    assert not practice.public.is_finished
    assert [practice.snapshot.objectives[oid].objective.skill_id for oid in practice.snapshot.queue] == ["postgresql"]

    with pytest.raises(ValueError, match="kỹ năng đã chọn"):
        engine.start(StartRequest(
            session_id="focus-invalid",
            skills=[skill("postgresql")],
            config={"focus_skill_ids": ["nonexistent_skill"]},
        ))


def test_ai_latency_compensates_deadline_without_extending_finished_session(setup, monkeypatch):
    from adaptive_questioning.evidence import workflow as wf_mod

    provider, engine, _ = setup
    started = engine.start(StartRequest(
        session_id="ai-wait-compensation",
        skills=[skill("postgresql"), skill("redis")],
        config={"max_questions": 4, "duration_seconds": 600},
    ))
    initial_deadline = started.snapshot.deadline_at

    ticks = iter([100.0, 114.0])
    monkeypatch.setattr(wf_mod, "monotonic", lambda: next(ticks, 114.0))
    after_clarify = engine.clarify(ClarifyRequest(
        snapshot=started.snapshot,
        turn_id=started.snapshot.pending_turn.turn_id,
        expected_state_version=started.snapshot.state_version,
        kind="CLARIFY_PROMPT",
        candidate_question="Có bao nhiêu dòng dữ liệu?",
    ))
    delta = (after_clarify.snapshot.deadline_at - initial_deadline).total_seconds()
    assert delta == 14


def test_coaching_two_tier_retry_keeps_llm_summary_and_deterministic_reference_answers(setup, monkeypatch):
    from adaptive_questioning.evidence.models import SessionCoaching

    provider, engine, _ = setup
    started = engine.start(StartRequest(
        session_id="coaching-two-tier",
        skills=[skill("postgresql")],
        config={"max_questions": 1},
    ))
    coaching_calls = []

    def flaky_coaching(context_str):
        data = json.loads(context_str)
        coaching_calls.append(data)
        if data.get("turns_needing_reference"):
            raise ValueError("Truncated JSON on full coaching payload")
        return SessionCoaching(
            overall_summary="Tóm tắt từ tầng compact: bạn cần củng cố phần chỉ mục PostgreSQL.",
            top_strengths=[],
            priority_gaps=["Thiếu lý do chọn cột trong chỉ mục tổng hợp"],
            actionable_study_steps=["Luyện phân tích EXPLAIN ANALYZE trên bảng nhiều cột"],
        )

    monkeypatch.setattr(provider, "session_coaching", flaky_coaching, raising=False)
    provider.observation, provider.performance = "CONTRADICTS", "BELOW"
    finished = answer(engine, started.snapshot, "Em chỉ thêm index vào mọi cột.")
    assert finished.public.is_finished
    assert len(coaching_calls) == 2
    assert len(coaching_calls[0]["turns_needing_reference"]) == 1
    assert coaching_calls[1]["turns_needing_reference"] == []
    assert "tầng compact" in finished.public.report.coaching.overall_summary
    assert finished.public.report.turn_reviews[0].reference_answer  # deterministic fallback still fills reference answer


def test_hinted_flag_silent_coding_delivery_notes_and_mode_assessment_guidance(setup, monkeypatch):
    from test_interview_quality_upgrade import FIRST_RECORD, start_coding
    from adaptive_questioning.evidence.planning import MODE_PATTERNS
    import re

    # MODE_PATTERNS should not misclassify infra/process "implement" tasks as CODING
    assert not re.search(MODE_PATTERNS["CODING"], "Implement CI/CD pipeline for backend services", re.IGNORECASE)
    assert re.search(MODE_PATTERNS["DESIGN"], "Ensure high availability and schema design for orders", re.IGNORECASE)

    provider, engine, _ = setup
    snapshot = start_coding(provider, engine, monkeypatch, session_purpose="PRACTICE", max_questions=1)
    hinted = engine.clarify(ClarifyRequest(
        snapshot=snapshot,
        turn_id=snapshot.pending_turn.turn_id,
        expected_state_version=snapshot.state_version,
        kind="HINT",
    ))
    captured_stage1 = []
    orig_judge = provider.judge
    monkeypatch.setattr(provider, "judge", lambda ctx: (captured_stage1.append(build_judge_stage1_inputs(ctx)), orig_judge(ctx))[1])

    finished = engine.respond(TransitionRequest(
        snapshot=hinted.snapshot,
        turn_id=hinted.snapshot.pending_turn.turn_id,
        expected_state_version=hinted.snapshot.state_version,
        candidate_response="",
        submitted_code=FIRST_RECORD,
    ))
    assert finished.public.is_finished
    turn_ctx = json.loads(captured_stage1[0]["turn_context"])
    assert "CODING" in turn_ctx["mode_assessment_guidance"]
    obj_report = finished.public.report.objectives[0]
    assert obj_report.hinted is True
    assert obj_report.criteria[0].hinted is True
    assert any("Big-O" in note for note in finished.public.report.turn_reviews[0].delivery_notes)


@pytest.mark.parametrize("phrase", ["Em chưa làm được.", "bỏ qua câu này", "skip", "Tôi không nhớ ạ"])
def test_standalone_inability_handles_skip_and_inability_phrases(setup, phrase):
    provider, engine, _ = setup
    engine.policy = InterviewPolicy(fallback_depth=1)
    started = start(engine, [skill("postgresql")])
    finished = answer(engine, started.snapshot, phrase)
    assert finished.snapshot.turns[0].judgment.explicit_inability is True
    assert finished.public.report.objectives[0].assessment == Assessment.NOT_DEMONSTRATED


def test_local_runner_handles_sql_multi_statement_unordered_and_python_float_set():
    runner = LocalSubprocessCodeRunner()
    sql_res = runner.execute(
        language="sql",
        setup_sql="CREATE TABLE scores(team TEXT, pts REAL); INSERT INTO scores VALUES ('A', 0.1),('B', 0.2),('A', 0.2);",
        code="CREATE INDEX idx_team ON scores(team); SELECT team, SUM(pts) FROM scores GROUP BY team; -- done",
        cases=[CodingTestCase(name="unordered_float", input_data="", expected_output='[["B", 0.2], ["A", 0.3]]')],
    )
    assert sql_res.passed == 1 and sql_res.total == 1, sql_res

    py_res = runner.execute(
        language="python",
        code="def summary():\n    return {'v': 0.1 + 0.2, 's': {'z', 'a'}}\n",
        entry_point="summary",
        cases=[CodingTestCase(name="float_set", input_data="", expected_output='{"v": 0.3, "s": ["a", "z"]}')],
    )
    assert py_res.passed == 1 and py_res.total == 1, py_res


@pytest.mark.skipif(shutil.which("node") is None, reason="node runtime not installed in host test env")
def test_local_js_runner_supports_es_module_exports():
    runner = LocalSubprocessCodeRunner()
    for code in (
        "export function multiply(a, b) { return a * b; }",
        "export default async function (a, b) { return a * b; }",
        "const mul = (a, b) => a * b;\nexport { mul as multiply };",
    ):
        res = runner.execute(
            language="javascript",
            code=code,
            entry_point="multiply",
            cases=[CodingTestCase(name="esm", input_data="[3, 5]", expected_output="15")],
        )
        assert res.compile_error == "", (code, res)
        assert res.passed == 1 and res.total == 1, (code, res)
