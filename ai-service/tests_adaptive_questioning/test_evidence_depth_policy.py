"""Audit regressions through the real V2 workflow, with deterministic provider outputs."""
import json
from datetime import datetime, timedelta, timezone

import pytest

from adaptive_questioning.evidence.assessment import apply_judgment
from adaptive_questioning.evidence.models import Action, Assessment, Mode, Snapshot, SuitableMode
from adaptive_questioning.evidence.policy_config import InterviewPolicy
from adaptive_questioning.evidence.workflow import EvidenceWorkflow
from adaptive_questioning.evidence.errors import QuestionUnavailableError
from test_evidence_workflow import ScriptedProvider, answer, skill, start


class AuditProvider(ScriptedProvider):
    def __init__(self):
        super().__init__()
        self.contexts = []
        self.proposed_depth = None
        self.extension = None
        self.modes = None
        self.bad_question = None
        self.bad_attempts = 0
        self.fixed_scope = None
        self.feedback_hint = False

    def blueprint(self, context):
        blueprint = super().blueprint(context)
        requirements = json.loads(context)["requirements"]
        for objective in blueprint.objectives:
            requirement = requirements[objective.requirement_id]
            if self.proposed_depth is not None:
                objective.target_depth = self.proposed_depth
                objective.depth_basis = "TASK"
                objective.depth_rationale = "Concrete task thinking demands, independent of job title"
                objective.depth_evidence_spans = [requirement["description"]]
            objective.extension_depth = self.extension
            if self.modes is not None:
                objective.suitable_modes = self.modes
        return blueprint

    def question(self, context):
        values = json.loads(context)
        self.contexts.append(("question", values))
        question = super().question(context)
        if self.fixed_scope:
            question.evidence_scope = self.fixed_scope
        if self.bad_attempts:
            self.bad_attempts -= 1
            if self.bad_question == "mode":
                question.mode = Mode.BEHAVIORAL
            elif self.bad_question == "depth":
                question.depth = 4
            elif self.bad_question == "scope":
                question.evidence_scope = ""
        return question

    def judge(self, context):
        self.contexts.append(("judge", json.loads(context)))
        judgment = super().judge(context)
        judgment.feedback_contains_hint = self.feedback_hint
        return judgment


@pytest.fixture
def audit():
    provider = AuditProvider()
    now = [datetime(2026, 11, 7, tzinfo=timezone.utc)]
    engine = EvidenceWorkflow(provider, clock=lambda: now[0])
    return provider, engine, now


def task_skill(description="Use collections for a bounded task", name="java", **overrides):
    return skill(name, job_tasks=[dict(description=description, required_level=4,
                                     evidence_spans=[description], level_basis="EXPLICIT")], **overrides)


def current(result):
    return result.snapshot.objectives[result.snapshot.pending_turn.objective_id]


def test_l2_starts_directly_without_proficiency_conversion(audit):
    provider, engine, _ = audit
    result = start(engine, [task_skill()])
    assert result.snapshot.pending_turn.question_depth == 2
    assert current(result).objective.required_proficiency == 4
    assert current(result).objective.target_depth == 2
    assert current(result).objective.depth_basis == "TASK_HEURISTIC"
    question_context = provider.contexts[-1][1]
    assert question_context["question_depth"] == 2
    assert len(question_context["depth_definitions"]) == 4


def test_wrong_l2_diagnoses_l1_and_l1_success_does_not_pass_target(audit):
    provider, engine, _ = audit
    provider.performance = "BELOW"
    result = answer(engine, start(engine, [task_skill()]).snapshot)
    assert result.snapshot.pending_turn.action == Action.EASIER
    assert result.snapshot.pending_turn.question_depth == 1
    assert result.public.report.objectives[0].assessment == Assessment.INSUFFICIENT
    provider.performance = "AT_TARGET"
    result = answer(engine, result.snapshot, "foundation correct")
    assert result.public.report.objectives[0].assessment == Assessment.BELOW
    assert result.snapshot.pending_turn.action == Action.FOLLOW_UP
    assert result.snapshot.pending_turn.question_depth == 2
    state = next(iter(result.snapshot.objectives.values()))
    assert state.objective.target_depth == 2
    assert {e.question_depth for e in state.evidence_history} == {1, 2}
    result = answer(engine, result.snapshot, "independent application at L2")
    assert result.public.is_finished
    assert result.public.report.objectives[0].assessment == Assessment.AT
    assert result.public.report.objectives[0].study_recommendations


def test_ambiguous_l2_clarifies_same_depth_and_case(audit):
    provider, engine, _ = audit
    provider.observation, provider.performance = "UNCLEAR", "UNDETERMINED"
    initial = start(engine, [task_skill()])
    scope = initial.snapshot.pending_turn.question.evidence_scope
    result = answer(engine, initial.snapshot, "maybe")
    assert result.snapshot.pending_turn.action == Action.CLARIFY
    assert result.snapshot.pending_turn.question_depth == 2
    assert result.snapshot.pending_turn.question.evidence_scope == scope


def test_target_success_stops_without_mandatory_extension(audit):
    provider, engine, _ = audit
    provider.extension = 3
    result = answer(engine, start(engine, [task_skill()]).snapshot, "ok")
    assert result.public.is_finished
    assert result.public.report.objectives[0].assessment == Assessment.AT
    assert provider.question_number == 1


def extension_run(provider, engine):
    provider.extension = 3
    engine.policy = InterviewPolicy(allow_extension_probes=True)
    result = answer(engine, start(engine, [task_skill()]).snapshot, "target satisfied")
    assert result.snapshot.pending_turn.action == Action.DEEPER
    assert result.snapshot.pending_turn.question_depth == 3
    return result


def test_failed_l3_preserves_established_l2(audit):
    provider, engine, _ = audit
    result = extension_run(provider, engine)
    provider.performance, provider.observation = "BELOW", "CONTRADICTS"
    result = answer(engine, result.snapshot, "extension wrong")
    assert result.public.report.objectives[0].assessment == Assessment.AT
    assert len(result.public.report.objectives[0].evidence) == 1
    assert len(next(iter(result.snapshot.objectives.values())).evidence_history) == 2
    assert not next(iter(result.snapshot.objectives.values())).contradictions


def test_above_target_requires_predeclared_extension_and_its_evidence(audit):
    provider, engine, _ = audit
    provider.performance = "ABOVE"
    result = answer(engine, start(engine, [task_skill()]).snapshot, "long response at target")
    assert result.public.report.objectives[0].assessment == Assessment.AT
    result = extension_run(provider, engine)
    result = answer(engine, result.snapshot, "higher standard satisfied")
    assert result.public.report.objectives[0].assessment == Assessment.ABOVE


def test_hint_taints_same_criterion_even_on_later_unhinted_question(audit):
    provider, engine, _ = audit
    initial = start(engine, [task_skill()], max_questions_per_objective=2).snapshot
    initial.pending_turn.question.assistance = "HINT"
    first = answer(engine, initial, "repeat hinted solution")
    state = next(iter(first.snapshot.objectives.values()))
    assert not state.criterion_results
    assert not any(item.independent for item in state.evidence_history)
    assert state.assessment == Assessment.INSUFFICIENT
    assert first.public.is_finished  # no useful independent criterion remains
    assert state.stop_reason == "NO_INDEPENDENT_CRITERIA_IN_MODE"


def test_feedback_hint_is_not_mistaken_for_independent_followup(audit):
    provider, engine, _ = audit
    provider.observation, provider.performance = "NO_EVIDENCE", "UNDETERMINED"
    provider.feedback_hint = True
    first = answer(engine, start(engine, [task_skill()]).snapshot, "irrelevant")
    assert first.public.report.evidence_coverage == 0
    assert first.public.report.objectives[0].assessment == Assessment.INSUFFICIENT
    assert first.public.is_finished


def test_negative_and_positive_evidence_survive_contradiction(audit):
    provider, engine, _ = audit
    provider.limit_criteria = True
    first = answer(engine, start(engine, [task_skill()]).snapshot)
    key = first.snapshot.turns[0].question.criterion_ids[0]
    first.snapshot.pending_turn.question.criterion_ids = [key]
    provider.performance = "BELOW"
    second = answer(engine, first.snapshot)
    state = current(second)
    assert state.contradictions == [key]
    assert {item.performance for item in state.evidence_history} == {"AT_TARGET", "BELOW"}
    assert second.snapshot.pending_turn.action == Action.VERIFY
    assert second.snapshot.pending_turn.question_depth == state.objective.target_depth
    assert second.public.report.objectives[0].assessment == Assessment.INSUFFICIENT


def test_wrong_answers_can_be_not_demonstrated_without_saying_dont_know(audit):
    provider, engine, _ = audit
    provider.observation, provider.performance = "CONTRADICTS", "BELOW"
    first = answer(engine, start(engine, [task_skill()]).snapshot, "incorrect application")
    second = answer(engine, first.snapshot, "incorrect foundation reasoning")
    state = next(iter(second.snapshot.objectives.values()))
    assert not second.snapshot.turns[-1].judgment.explicit_inability
    assert state.assessment == Assessment.NOT_DEMONSTRATED


def test_rewording_same_problem_is_not_independent_failure_evidence(audit):
    provider, engine, _ = audit
    provider.performance = "BELOW"
    provider.fixed_scope = "one-same-case"
    first = answer(engine, start(engine, [task_skill()], max_questions_per_objective=2).snapshot)
    second = answer(engine, first.snapshot)
    assert second.public.report.objectives[0].assessment == Assessment.INSUFFICIENT


def test_identical_observation_replay_does_not_grow_ledger(audit):
    _, engine, _ = audit
    result = answer(engine, start(engine, [task_skill()]).snapshot)
    state = next(iter(result.snapshot.objectives.values())).model_copy(deep=True)
    turn = result.snapshot.turns[0]
    count = len(state.evidence_history)
    apply_judgment(state, turn)
    assert len(state.evidence_history) == count


@pytest.mark.parametrize("field", ["mode", "depth", "scope"])
def test_invalid_question_contract_retries_once(audit, field):
    provider, engine, _ = audit
    provider.bad_question, provider.bad_attempts = field, 1
    initial = start(engine, [task_skill()])
    assert provider.question_number == 2
    assert initial.snapshot.pending_turn.question_depth == 2


@pytest.mark.parametrize("field", ["mode", "depth", "scope"])
def test_invalid_question_contract_stops_after_bounded_retry(audit, field):
    provider, engine, _ = audit
    provider.bad_question, provider.bad_attempts = field, 10
    with pytest.raises(QuestionUnavailableError, match="AI chưa tạo được"):
        start(engine, [task_skill()])
    assert provider.question_number == 2


def test_budget_prevents_further_generation_even_if_router_would_verify(audit):
    provider, engine, _ = audit
    provider.observation, provider.performance = "NO_EVIDENCE", "UNDETERMINED"
    result = answer(engine, start(engine, [task_skill()], max_questions=1).snapshot)
    assert result.public.is_finished
    assert provider.question_number == 1
    assert result.public.report.objectives[0].assessment == Assessment.INSUFFICIENT


@pytest.mark.parametrize(("task", "expected"), [
    ("Write SQL queries", Mode.CODING),
    ("Diagnose slow SQL queries", Mode.DEBUGGING),
    ("Design relational database schemas", Mode.DESIGN),
    ("Explain database transactions", Mode.TECHNICAL_EXPLANATION),
])
def test_same_skill_selects_mode_from_jd_task(audit, task, expected):
    _, engine, _ = audit
    assert start(engine, [task_skill(task, "sql")]).snapshot.pending_turn.mode == expected


def test_debugging_mode_can_be_l2_without_becoming_coding(audit):
    provider, engine, _ = audit
    provider.proposed_depth = 2
    initial = start(engine, [task_skill("Diagnose a simple query error")])
    assert initial.snapshot.pending_turn.mode == Mode.DEBUGGING
    assert initial.snapshot.pending_turn.question_depth == 2


def test_mixed_uses_task_fit_and_focused_honors_explicit_choice(audit):
    provider, engine, _ = audit
    provider.modes = [SuitableMode(mode=mode, rationale="Valid task aspect") for mode in
                      [Mode.TECHNICAL_EXPLANATION, Mode.DEBUGGING]]
    skills = [task_skill("Diagnose a slow query")]
    mixed = start(engine, skills)
    assert mixed.snapshot.pending_turn.mode == Mode.DEBUGGING
    provider.limit_criteria = True
    focused = start(engine, skills, mode="FOCUSED", focused_question_mode=Mode.TECHNICAL_EXPLANATION)
    assert focused.snapshot.pending_turn.mode == Mode.TECHNICAL_EXPLANATION
    followup = answer(engine, focused.snapshot)
    assert followup.snapshot.pending_turn.mode == Mode.TECHNICAL_EXPLANATION


def test_mixed_prefers_essential_coverage_then_diversity(audit):
    provider, engine, _ = audit
    provider.criterion_count = 2
    provider.modes = [SuitableMode(mode=Mode.DESIGN, rationale="Measures one aspect", criterion_indices=[0]),
                      SuitableMode(mode=Mode.DEBUGGING, rationale="Measures all essential aspects")]
    first = start(engine, [skill("a"), skill("b")])
    assert first.snapshot.pending_turn.mode == Mode.DEBUGGING
    provider.modes[0].criterion_indices = []
    diverse = start(engine, [skill("a"), skill("b")])
    assert {s.selected_mode for s in diverse.snapshot.objectives.values()} == {Mode.DESIGN, Mode.DEBUGGING}


def test_core_gaps_precede_core_match_and_optional_missing(audit):
    _, engine, _ = audit
    skills = [task_skill(name="java", importance_weight=0.95, priority=0.3),
              task_skill(name="spring", importance_weight=0.9, priority=0),
              task_skill(name="sql", importance_weight=0.8, priority=0.2),
              task_skill(name="aws", importance_weight=0.2, priority=0.8)]
    skills[-1].job_tasks[0].requirement_kind = "OPTIONAL"
    result = start(engine, skills, max_questions=3)
    planned = [result.snapshot.objectives[key].objective.skill_id for key in result.snapshot.queue]
    assert planned == ["java", "spring", "sql"]
    aws = next(s for s in result.snapshot.objectives.values() if s.objective.skill_id == "aws")
    assert aws.assessment == Assessment.NOT_ASSESSED
    assert aws.excluded_reason == "PLAN_BUDGET"
    assert not result.public.report.study_recommendations


def test_followup_reserve_and_early_finish_reallocate_to_unasked_objectives(audit):
    _, engine, _ = audit
    skills = [skill(str(i), importance_weight=0.5) for i in range(4)]
    result = start(engine, skills, max_questions=4)
    assert len(result.snapshot.queue) == 2  # ceil(4 * .3) held for follow-ups
    for _ in range(4):
        result = answer(engine, result.snapshot)
    assert result.public.is_finished
    assert all(s.assessment == Assessment.AT for s in result.snapshot.objectives.values())


def test_ambiguous_jd_is_inferred_with_configurable_fallback_and_no_title_mapping(audit):
    _, engine, _ = audit
    engine.policy = InterviewPolicy(fallback_depth=1)
    initial = start(engine, [skill(jd_evidence_spans=["Senior Java developer"])])
    obj = current(initial).objective
    assert obj.inferred and obj.target_depth == 1
    assert obj.depth_basis == "CONFIGURED_FALLBACK"
    engine.policy = InterviewPolicy(seniority_fallback_depths={"senior": 3})
    fallback = start(engine, [skill(jd_evidence_spans=["Senior Java developer"])])
    assert current(fallback).objective.target_depth == 3
    assert current(fallback).objective.depth_basis == "SENIORITY_FALLBACK"
    explicit = start(engine, [task_skill(jd_evidence_spans=["Senior Java developer"])])
    assert current(explicit).objective.target_depth == 2


def test_policy_and_target_survive_recovery_and_cannot_change_mid_session(audit):
    provider, engine, _ = audit
    provider.limit_criteria = True
    original = start(engine, [task_skill()]).snapshot
    restored = Snapshot.model_validate_json(original.model_dump_json())
    engine.policy = InterviewPolicy(fallback_depth=4, min_failure_contexts=5)
    result = answer(engine, restored)
    assert current(result).objective.target_depth == 2
    assert result.snapshot.policy.min_failure_contexts == 2
    judge_context = next(values for kind, values in provider.contexts if kind == "judge")
    assert "candidate_proficiency" not in judge_context
    assert judge_context["objective"]["target_depth"] == 2


def test_snapshot_without_depth_fields_resumes_conservatively(audit):
    _, engine, _ = audit
    payload = start(engine).snapshot.model_dump(mode="json")
    payload.pop("policy")
    for state in payload["objectives"].values():
        for field in ["target_depth", "depth_basis", "depth_rationale", "depth_evidence_spans"]:
            state["objective"].pop(field)
        state.pop("current_question_depth")
        state.pop("evidence_history")
    payload["pending_turn"].pop("question_depth")
    for field in ["depth", "mode", "evidence_scope"]:
        payload["pending_turn"]["question"].pop(field)
    restored = Snapshot.model_validate(payload)
    result = answer(engine, restored)
    assert result.public.report.objectives[0].assessment == Assessment.INSUFFICIENT
    assert result.snapshot.pending_turn.question_depth == 2
    assert result.public.schema_version == 2


def test_policy_rejects_invalid_depth_and_regex():
    with pytest.raises(ValueError):
        InterviewPolicy(seniority_fallback_depths={"intern": 5})
    with pytest.raises(ValueError):
        InterviewPolicy(depth_patterns={"[": 2})


def test_api_carries_action_depth_evidence_and_recovery_through_response(audit):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from adaptive_questioning.evidence.models import StartRequest
    from adaptive_questioning.evidence.routes import router

    provider, engine, _ = audit
    app = FastAPI()
    app.include_router(router)
    app.state.evidence_workflow = engine
    with TestClient(app) as client:
        response = client.post('/api/v2/interview/start', json=StartRequest(
            session_id="api-depth", skills=[task_skill()]).model_dump(mode="json"))
        initial = response.json()
        assert response.status_code == 200
        provider.performance = "BELOW"
        response = client.post('/api/v2/interview/respond', json={
            "snapshot": initial["snapshot"], "turn_id": initial["public"]["pending_turn"]["turn_id"],
            "expected_state_version": 1, "candidate_response": "incorrect application",
        })
        assert response.status_code == 200
        updated = response.json()
        pending = updated["snapshot"]["pending_turn"]
        assert (pending["action"], pending["question_depth"]) == ("ASK_EASIER", 1)
        assert pending["question"]["mode"] == pending["mode"]
        restored = Snapshot.model_validate(updated["snapshot"])
        state = next(iter(restored.objectives.values()))
        assert state.objective.target_depth == 2
        assert state.evidence_history[0].response_excerpt == "incorrect application"
        assert state.evidence_history[0].question_depth == 2
        stopped = client.post('/api/v2/interview/stop', json=updated["snapshot"])
        assert stopped.status_code == 200
        assert stopped.json()["public"]["report"]["objectives"][0]["assessment"] == "INSUFFICIENT_EVIDENCE"


def test_complete_java_backend_intern_session_uses_followup_then_next_objective(audit):
    provider, engine, _ = audit
    provider.limit_criteria = True
    java = task_skill("Implement duplicate ID removal using Java Collections", "java")
    java.job_tasks[0].required_level = 2
    java.jd_evidence_spans = ["Java Backend Intern"]
    sql = task_skill("Write SQL queries for filtered records", "sql", importance_weight=0.8)
    sql.job_tasks[0].required_level = 2
    initial = start(engine, [java, sql])
    assert initial.snapshot.pending_turn.skill_id == "java"
    assert initial.snapshot.pending_turn.question_depth == 2
    result = answer(engine, initial.snapshot, "new HashSet<>(List.of(7, 7, 9))")
    assert result.snapshot.pending_turn.action == Action.FOLLOW_UP
    assert result.snapshot.pending_turn.question_depth == 2
    assert result.snapshot.pending_turn.skill_id == "java"
    provider.limit_criteria = False
    result = answer(engine, result.snapshot, "Set removes duplicate IDs, average membership cost is O(1)")
    assert result.snapshot.pending_turn.action == Action.INITIAL  # NEXT_OBJECTIVE is a transition, not a generated question
    assert result.snapshot.pending_turn.skill_id == "sql"
    assert result.snapshot.pending_turn.mode == Mode.CODING
    result = answer(engine, result.snapshot, "SELECT id FROM events WHERE status = 'active'")
    assert result.snapshot.pending_turn.skill_id == "sql"
    result = answer(engine, result.snapshot, "The WHERE predicate selects only active rows")
    assert result.public.is_finished
    assert all(obj.assessment == Assessment.AT for obj in result.public.report.objectives)
    assert all(turn.question_depth == 2 for turn in result.snapshot.turns)


def test_generator_cannot_substitute_unrelated_mode_for_jd_task(audit):
    provider, engine, _ = audit
    provider.modes = [SuitableMode(mode=Mode.DESIGN, rationale="Incorrectly inferred from skill name")]
    with pytest.raises(ValueError, match="JD task intent"):
        start(engine, [task_skill("Diagnose slow SQL queries", "sql")])


def test_missing_essential_in_chosen_mode_stops_with_explicit_reason(audit):
    provider, engine, _ = audit
    provider.criterion_count = 2
    provider.modes = [SuitableMode(mode=Mode.DEBUGGING, rationale="Only criterion zero is observable", criterion_indices=[0])]
    result = answer(engine, start(engine).snapshot)
    assert result.public.is_finished
    obj = result.public.report.objectives[0]
    assert obj.assessment == Assessment.INSUFFICIENT
    assert obj.stop_reason == "NO_INDEPENDENT_CRITERIA_IN_MODE"
    assert len(obj.missing_criteria) == 1


def test_question_generation_elapsed_time_cannot_publish_expired_pending_turn(audit):
    provider, engine, now = audit
    original = provider.question

    def slow_question(context):
        question = original(context)
        now[0] += timedelta(hours=1)
        return question

    provider.question = slow_question
    result = start(engine)
    assert result.public.is_finished
    assert result.public.pending_turn is None
    assert result.public.report.termination_reason == "TIME_BUDGET"
    assert result.public.report.objectives[0].assessment == Assessment.NOT_ASSESSED


def test_operator_policy_configuration_is_validated_and_frozen_in_snapshot(monkeypatch, audit):
    from adaptive_questioning.evidence.policy_config import configured_policy
    monkeypatch.setenv("EVIDENCE_POLICY_JSON", '{"fallback_depth":1,"reserve_followup_fraction":0.5}')
    policy = configured_policy()
    _, engine, _ = audit
    engine.policy = policy
    initial = start(engine)
    assert initial.snapshot.policy.reserve_followup_fraction == 0.5
    assert initial.snapshot.pending_turn.question_depth == 1
    monkeypatch.setenv("EVIDENCE_POLICY_JSON", '{"fallback_depth":5}')
    with pytest.raises(ValueError):
        configured_policy()


def test_rubric_fingerprint_is_stable_across_questions_but_detects_standard_changes(audit):
    from adaptive_questioning.evidence.planning import rubric_fingerprint
    provider, engine, _ = audit
    provider.limit_criteria = True
    initial = start(engine, [task_skill()])
    fingerprint = rubric_fingerprint(current(initial).objective)
    followup = answer(engine, initial.snapshot)
    assert rubric_fingerprint(current(followup).objective) == fingerprint
    modified = current(followup).objective.model_copy(deep=True)
    modified.criteria[0].at_target = "A materially different standard"
    assert rubric_fingerprint(modified) != fingerprint


def test_multiple_objectives_same_skill_keep_independent_evidence_ledgers(audit):
    _, engine, _ = audit
    tasks = [dict(description=text, required_level=3, evidence_spans=[text])
             for text in ["Write SQL queries", "Diagnose slow SQL queries"]]
    initial = start(engine, [skill(job_tasks=tasks)])
    first_id = initial.snapshot.pending_turn.objective_id
    first = answer(engine, initial.snapshot, "first objective finding")
    second_id = first.snapshot.pending_turn.objective_id
    assert second_id != first_id
    second = answer(engine, first.snapshot, "second objective finding")
    states = second.snapshot.objectives
    assert all(e.response_excerpt == "first objective finding" for e in states[first_id].evidence_history)
    assert all(e.response_excerpt == "second objective finding" for e in states[second_id].evidence_history)
    assert set(e.turn_id for e in states[first_id].evidence_history).isdisjoint(
        e.turn_id for e in states[second_id].evidence_history)


def test_local_cap_prevents_contradiction_probe_generation(audit):
    provider, engine, _ = audit
    provider.limit_criteria = True
    first = answer(engine, start(engine, [task_skill()], max_questions_per_objective=2).snapshot)
    key = first.snapshot.turns[0].question.criterion_ids[0]
    first.snapshot.pending_turn.question.criterion_ids = [key]
    provider.performance = "BELOW"
    second = answer(engine, first.snapshot)
    assert second.public.is_finished
    assert provider.question_number == 2
    state = next(iter(second.snapshot.objectives.values()))
    assert state.contradictions == [key]
    assert state.stop_reason == "LOCAL_BUDGET"
    assert state.assessment == Assessment.INSUFFICIENT


def test_minh_java_backend_intern_full_walkthrough(audit):
    provider, engine, _ = audit
    provider.criterion_counts = {"java": 1, "spring": 2, "sql": 2, "aws": 1}
    java = task_skill("Use Java Collections to store unique user IDs and check membership", "java",
                      importance_weight=0.95, priority=0.38, suggested_strategy="COMPARE_SUBSTITUTE")
    spring = task_skill("Develop Spring Boot REST API request validation and error handling", "spring",
                        importance_weight=0.90, priority=0.0, suggested_strategy="NONE")
    sql = task_skill("Write SQL queries and apply indexing for order history", "sql",
                     importance_weight=0.80, priority=0.32, suggested_strategy="COMPARE_SUBSTITUTE")
    aws = task_skill("Explain basic AWS cloud concepts", "aws",
                     importance_weight=0.20, priority=0.16, suggested_strategy="LEARNING_AGILITY")
    aws.job_tasks[0].requirement_kind = "OPTIONAL"

    # Configure max_questions=8 so the 3 core skills get interviewed and optional AWS stays in reserve
    res = start(engine, [java, spring, sql, aws], max_questions=8, duration_seconds=1080, max_questions_per_objective=3)
    planned_skills = [res.snapshot.objectives[oid].objective.skill_id for oid in res.snapshot.queue]
    assert planned_skills == ["java", "spring", "sql"]

    # --- Skill 1: Java (Turn 1 L2 BELOW -> Turn 2 L1 AT_TARGET -> Turn 3 L2 AT_TARGET) ---
    assert (res.snapshot.pending_turn.skill_id, res.snapshot.pending_turn.action, res.snapshot.pending_turn.question_depth) == ("java", Action.INITIAL, 2)
    provider.performance = "BELOW"
    res = answer(engine, res.snapshot, "Em chọn ArrayList vì nó có thể lưu danh sách user ID và dùng contains để kiểm tra.")
    assert (res.snapshot.pending_turn.skill_id, res.snapshot.pending_turn.action, res.snapshot.pending_turn.question_depth) == ("java", Action.EASIER, 1)

    provider.performance = "AT_TARGET"
    res = answer(engine, res.snapshot, "Set không cho phép phần tử trùng lặp, còn List có thể chứa phần tử trùng. Nên dùng HashSet.")
    assert (res.snapshot.pending_turn.skill_id, res.snapshot.pending_turn.action, res.snapshot.pending_turn.question_depth) == ("java", Action.FOLLOW_UP, 2)

    provider.limit_criteria = True
    res = answer(engine, res.snapshot, "HashSet sử dụng hashing nên tìm kiếm trung bình O(1), còn ArrayList duyệt từng phần tử nên O(n).")

    # --- Skill 2: Spring Boot (Turn 4 L2 INITIAL c1 -> Turn 5 L2 FOLLOW_UP c2) ---
    assert (res.snapshot.pending_turn.skill_id, res.snapshot.pending_turn.action, res.snapshot.pending_turn.question_depth) == ("spring", Action.INITIAL, 2)
    res = answer(engine, res.snapshot, "Em dùng Bean Validation, đặt @Min(1) cho quantity trong DTO và @Valid, trả 400 Bad Request.")
    assert (res.snapshot.pending_turn.skill_id, res.snapshot.pending_turn.action, res.snapshot.pending_turn.question_depth) == ("spring", Action.FOLLOW_UP, 2)

    res = answer(engine, res.snapshot, "Em kiểm tra @ControllerAdvice và @ExceptionHandler cho MethodArgumentNotValidException để trả 400.")

    # --- Skill 3: SQL (Turn 6 L2 INITIAL c1 -> Turn 7 L2 FOLLOW_UP c2 UNCLEAR -> Turn 8 L2 CLARIFY c2 inability) ---
    assert (res.snapshot.pending_turn.skill_id, res.snapshot.pending_turn.action, res.snapshot.pending_turn.question_depth) == ("sql", Action.INITIAL, 2)
    res = answer(engine, res.snapshot, "Em dùng SELECT với WHERE user_id và ORDER BY created_at DESC rồi LIMIT 10.")
    assert (res.snapshot.pending_turn.skill_id, res.snapshot.pending_turn.action, res.snapshot.pending_turn.question_depth) == ("sql", Action.FOLLOW_UP, 2)

    provider.observation, provider.performance = "UNCLEAR", "UNDETERMINED"
    res = answer(engine, res.snapshot, "Em sẽ tạo index cho cột user_id.")
    assert (res.snapshot.pending_turn.skill_id, res.snapshot.pending_turn.action, res.snapshot.pending_turn.question_depth) == ("sql", Action.CLARIFY, 2)

    provider.inability = True
    provider.observation, provider.performance = "NO_EVIDENCE", "UNDETERMINED"
    res = answer(engine, res.snapshot, "Em chưa tìm hiểu kỹ về composite index nên chưa biết khi nào nên dùng.")

    assert res.public.is_finished
    by_skill = {obj.skill_id: obj for obj in res.public.report.objectives}
    assert by_skill["java"].assessment == Assessment.AT
    assert by_skill["java"].study_recommendations
    assert by_skill["spring"].assessment == Assessment.AT
    assert not by_skill["spring"].study_recommendations
    assert by_skill["sql"].strengths and by_skill["sql"].weaknesses and by_skill["sql"].study_recommendations
    assert by_skill["aws"].assessment == Assessment.NOT_ASSESSED
    assert not by_skill["aws"].study_recommendations
    assert len(res.public.report.study_recommendations) >= 2
