"""Offline behavioural tests: coverage, atomic transitions, scope and persistence contract."""
import json
import re
from datetime import datetime, timedelta, timezone

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from adaptive_questioning.evidence.models import (
    Action, Assessment, Blueprint, BlueprintDraft, CriterionDraft, InterviewConfig, InterviewSkill,
    Judgment, Mode, ObjectiveDraft, Observation, Question, Snapshot, StartRequest,
    SuitableMode, TransitionRequest,
)
from adaptive_questioning.evidence.routes import router
from adaptive_questioning.evidence.workflow import EvidenceWorkflow
from adaptive_questioning.evidence.errors import JudgmentUnavailableError
from adaptive_questioning.evidence.planning import MODE_PATTERNS


class ScriptedProvider:
    def __init__(self):
        self.observation = "SUPPORTS"
        self.performance = "AT_TARGET"
        self.limit_criteria = False
        self.invalid_quote = False
        self.fail_question = False
        self.question_number = 0
        self.resolve = False
        self.inability = False
        self.criterion_count = 1
        self.criterion_counts = {}

    def blueprint(self, context):
        requirements = json.loads(context)["requirements"]
        return BlueprintDraft(objectives=[ObjectiveDraft(
            requirement_id=key, skill_id=req["skill_id"],
            criteria=[CriterionDraft(description=f"Criterion {i}", expected_evidence="Observable execution",
                                 below_target="Incorrect execution", at_target="Correct execution",
                                 above_target="Correct with tradeoffs") for i in range(
                                     self.criterion_counts.get(req["skill_id"], 2 if self.limit_criteria else self.criterion_count))],
            suitable_modes=[SuitableMode(mode=mode) for mode in
                            ([mode for mode, pattern in MODE_PATTERNS.items()
                              if not req["description"].startswith("Đánh giá kiến thức thực hành ")
                              and re.search(pattern, req["description"], re.IGNORECASE)] or [Mode.DEBUGGING])],
        ) for key, req in requirements.items()])

    def question(self, context):
        if self.fail_question:
            raise RuntimeError("simulated generator outage")
        values = json.loads(context)
        self.question_number += 1
        contract = values["required_question_contract"]
        ids = contract["criterion_ids"]
        return Question(text=f"How would you diagnose this concrete incident {self.question_number}?",
                        criterion_ids=ids[:1] if self.limit_criteria else ids,
                        mode=contract["mode"], depth=contract["depth"],
                        evidence_scope=contract.get("evidence_scope", f"incident-{self.question_number}"))

    def review_question(self, context):
        return "ALIGNED"

    def judge(self, context):
        values = json.loads(context)
        answer = values["turn"]["answer"]
        return Judgment(
            observations=[Observation(criterion_id=key, response_excerpt="invented evidence" if self.invalid_quote else answer,
                                      observation=self.observation, performance=self.performance,
                                      rationale="Grounded finding", resolves_contradiction=self.resolve)
                          for key in values["turn"]["question"]["criterion_ids"]],
            feedback="Assessment feedback",
            explicit_inability=self.inability, inability_excerpt=answer if self.inability else "",
        )


def skill(name="postgresql", **overrides):
    values = dict(jd_skill_id=name, required_proficiency=4, priority=0, importance_weight=0.9)
    return InterviewSkill(**(values | overrides))


@pytest.fixture
def setup():
    provider = ScriptedProvider()
    now = [datetime(2026, 11, 7, tzinfo=timezone.utc)]
    engine = EvidenceWorkflow(provider, clock=lambda: now[0])
    return provider, engine, now


def start(engine, skills=None, **config):
    return engine.start(StartRequest(session_id="test", skills=skills or [skill()], config=InterviewConfig(**config)))


def answer(engine, snapshot, text="EXPLAIN ANALYZE"):
    return engine.respond(TransitionRequest(snapshot=snapshot, turn_id=snapshot.pending_turn.turn_id,
                                           expected_state_version=snapshot.state_version, candidate_response=text))


def test_interaction_mode_defaults_for_legacy_and_persists_voice(setup, monkeypatch):
    provider, engine, _ = setup
    assert InterviewConfig().interaction_mode == "TEXT"
    with pytest.raises(ValueError):
        InterviewConfig(interaction_mode="VIDEO")
    seen = []
    judged = []
    original = provider.question
    def capture(context):
        seen.append(json.loads(context)["interaction_mode"])
        return original(context)
    monkeypatch.setattr(provider, "question", capture)
    original_judge = provider.judge
    def capture_judge(context):
        judged.append(json.loads(context))
        return original_judge(context)
    monkeypatch.setattr(provider, "judge", capture_judge)
    first = start(engine, interaction_mode="VOICE")
    assert first.public.config.interaction_mode == "VOICE"
    assert first.snapshot.config.interaction_mode == "VOICE"
    result = answer(engine, first.snapshot)
    assert result.public.config.interaction_mode == "VOICE"
    assert seen and set(seen) == {"VOICE"}
    assert judged[0]["interaction_mode"] == "VOICE"
    assert judged[0]["turn"]["answer"] == "EXPLAIN ANALYZE"
    text_session = start(engine)
    answer(engine, text_session.snapshot)
    assert judged[-1]["interaction_mode"] == "TEXT"
    legacy = first.snapshot.model_dump(mode="json")
    legacy["config"].pop("interaction_mode")
    assert Snapshot.model_validate(legacy).config.interaction_mode == "TEXT"


def test_new_attempt_reuses_profile_rubric_without_previous_evidence(setup, monkeypatch):
    provider, engine, _ = setup
    first = start(engine)
    completed = answer(engine, first.snapshot)
    frozen = Blueprint(objectives=[state.objective for state in completed.snapshot.objectives.values()])
    monkeypatch.setattr(provider, "blueprint", lambda _: pytest.fail("Frozen profile must not generate a new rubric"))
    assert "policy" not in StartRequest.model_fields
    second = engine.start(StartRequest(session_id="attempt-2", skills=[skill()], blueprint=frozen))
    assert second.snapshot.session_id == "attempt-2"
    assert second.snapshot.turns == []
    assert not second.public.is_finished
    assert second.public.pending_turn.turn_id != first.public.pending_turn.turn_id
    for key, state in second.snapshot.objectives.items():
        assert state.objective == first.snapshot.objectives[key].objective
        assert state.evidence_history == []
        assert state.assessment == Assessment.NOT_ASSESSED
    assert completed.public.is_finished


def test_reused_profile_blueprint_rejects_changed_requirements(setup):
    _, engine, _ = setup
    first = start(engine)
    frozen = Blueprint(objectives=[state.objective for state in first.snapshot.objectives.values()])
    with pytest.raises(ValueError, match="every requirement"):
        engine.start(StartRequest(session_id="other", skills=[skill("redis")], blueprint=frozen))


def test_matching_zero_gap_skill_is_verified_with_evidence(setup):
    _, engine, _ = setup
    initial = start(engine)
    assert initial.public.pending_turn is not None
    result = answer(engine, initial.snapshot, "ok")  # short correct answer is not penalized
    assert result.public.is_finished
    assert result.public.report.objectives[0].assessment == Assessment.AT
    assert result.public.report.objectives[0].evidence
    assert initial.snapshot.turns == []  # immutable input


def test_turn_cap_is_not_verification(setup):
    provider, engine, _ = setup
    provider.observation, provider.performance = "NO_EVIDENCE", "UNDETERMINED"
    result = start(engine, max_questions_per_objective=3)
    for _ in range(3):
        result = answer(engine, result.snapshot, "unrelated")
    report = result.public.report
    assert report.objectives[0].assessment == Assessment.INSUFFICIENT
    assert report.objectives[0].stop_reason == "LOCAL_BUDGET"
    assert not report.objectives[0].evidence


def test_passing_one_criterion_does_not_replace_full_coverage(setup):
    provider, engine, _ = setup
    provider.limit_criteria = True
    result = answer(engine, start(engine).snapshot)
    assert not result.public.is_finished
    assert result.public.report.objectives[0].assessment == Assessment.INSUFFICIENT
    assert len(next(iter(result.snapshot.objectives.values())).criterion_results) == 1


def test_invalid_quote_and_generation_failure_leave_input_unchanged(setup):
    provider, engine, _ = setup
    provider.limit_criteria = True
    original = start(engine).snapshot
    saved = original.model_dump_json()
    provider.invalid_quote = True
    with pytest.raises(JudgmentUnavailableError) as failure:
        answer(engine, original)
    assert "excerpt" in str(failure.value.__cause__)
    provider.invalid_quote, provider.fail_question = False, True
    with pytest.raises(RuntimeError, match="outage"):
        answer(engine, original)
    assert original.model_dump_json() == saved


def test_snapshot_roundtrip_and_stale_turn(setup, monkeypatch):
    from pydantic import ValidationError
    provider, engine, _ = setup
    provider.criterion_count = 2
    original_question = provider.question
    seen_cv = []

    def question(context):
        seen_cv.append(json.loads(context)["cv_evidence"])
        return original_question(context)

    monkeypatch.setattr(provider, "question", question)
    task = "Optimize SQL queries"
    spans = ["Tối ưu truy vấn PostgreSQL trên dữ liệu bán hàng."]
    input_skill = skill(cv_evidence_spans=spans, priority=0.4, job_tasks=[
        {"description": task, "required_level": 3, "evidence_spans": [task]},
    ])
    initial = start(engine, [input_skill]).snapshot
    objective = initial.objectives[initial.pending_turn.objective_id].objective
    assert (objective.claim, objective.jd_evidence_spans) == (task, [task])
    expected_skills = [{
        "jd_skill_id": input_skill.jd_skill_id,
        "jd_skill_name": "",
        "matched_cv_skill_name": "",
        "semantic_alignment": "",
        "context_job": "",
        "cv_evidence_spans": spans,
    }]
    dumped_initial = initial.model_dump(mode="json")
    assert dumped_initial["skills"] == expected_skills
    assert {"required_proficiency", "inferred", "extension_criterion_ids", "rubric_version"}.isdisjoint(
        objective.model_dump()
    )
    assert "started_at" not in dumped_initial

    for mutator in (
        lambda p: p.__setitem__("started_at", "2026-11-07T00:00:00Z"),
        lambda p: p.__setitem__("engine_version", "evidence-2.0"),
        lambda p: p["pending_turn"]["question"].__setitem__("assistance", "NONE"),
        lambda p: p["objectives"][initial.pending_turn.objective_id]["objective"].update(inferred=True),
        lambda p: p["objectives"][initial.pending_turn.objective_id]["objective"].update(extension_criterion_ids=[]),
        lambda p: p["objectives"][initial.pending_turn.objective_id]["objective"].update(rubric_version="evidence-2.0"),
        lambda p: p["objectives"][initial.pending_turn.objective_id].update(clarification_spent=True),
    ):
        bad = initial.model_dump(mode="json")
        mutator(bad)
        with pytest.raises(ValidationError):
            Snapshot.model_validate(bad)

    restored = Snapshot.model_validate_json(initial.model_dump_json())
    assert restored == initial
    with pytest.raises(ValueError, match="Stale turn"):
        engine.respond(TransitionRequest(snapshot=restored, turn_id="wrong", expected_state_version=1, candidate_response="answer"))
    result = answer(engine, restored)
    assert result.public.state_version == 2
    assert result.snapshot.model_dump(mode="json")["skills"] == expected_skills
    assert seen_cv == [[], []]  # Only source-verified CV excerpts enter questions in new sessions.


def test_timeout_marks_unasked_objective_not_assessed(setup):
    _, engine, now = setup
    result = start(engine, [skill(), skill("java")])
    now[0] += timedelta(seconds=1000)
    result = answer(engine, result.snapshot)
    assert result.public.report.termination_reason == "TIME_BUDGET"
    assert all(obj.assessment == Assessment.NOT_ASSESSED for obj in result.public.report.objectives)


def test_focused_mode_failure_and_budget_exclusions(setup):
    _, engine, _ = setup
    with pytest.raises(ValueError, match="phù hợp"):
        start(engine, mode="FOCUSED", focused_question_mode=Mode.CODING)
    result = start(engine, [skill(), skill("java")], max_questions=1)
    assert sum(s.lifecycle == "EXCLUDED" for s in result.snapshot.objectives.values()) == 1
    assert all(not objective.evidence for objective in result.public.report.objectives)


def test_reserves_initial_opportunities_for_other_skills(setup):
    provider, engine, _ = setup
    provider.observation, provider.performance = "NO_EVIDENCE", "UNDETERMINED"
    initial = start(engine, [skill(), skill("java")], max_questions=2)
    skills_by_objective = {o.objective_id: o.skill_id for o in initial.public.report.objectives}
    first = skills_by_objective[initial.public.pending_turn.objective_id]
    result = answer(engine, initial.snapshot)
    assert skills_by_objective[result.public.pending_turn.objective_id] != first


def test_two_tasks_for_one_skill_keep_distinct_states(setup):
    _, engine, _ = setup
    tasks = [{"description": description, "required_level": 3, "evidence_spans": [description]}
             for description in ("Optimize queries", "Design schema")]
    result = start(engine, [skill(job_tasks=tasks)])
    assert len(result.snapshot.objectives) == 2
    assert len(set(result.snapshot.queue)) == 2


def test_api_projects_no_rubric_in_pending_turn(setup):
    _, engine, _ = setup
    app = FastAPI()
    app.include_router(router)
    app.state.evidence_workflow = engine
    client = TestClient(app)
    response = client.post('/api/v2/interview/start', json=StartRequest(session_id="test", skills=[skill()]).model_dump(mode="json"))
    assert response.status_code == 200
    data = response.json()
    assert set(data) == {"snapshot", "public"}
    public = data["public"]
    assert not {"progress", "evidence_coverage", "target_attainment", "study_recommendations",
                "schema_version", "state_version", "is_finished"}.intersection(public["report"])
    for objective in public["report"]["objectives"]:
        assert not {"covered_criteria", "missing_criteria", "evidence_turn_ids", "inferred",
                    "lifecycle", "excluded_reason"}.intersection(objective)
        assert all("stop_reason" not in c and "turns_spent" not in c for c in objective["criteria"])
    assert not {"criteria", "skill_id", "answer", "feedback"}.intersection(public["pending_turn"])
    assert "belief" not in public


def test_below_target_and_conflicting_evidence(setup):
    provider, engine, _ = setup
    provider.performance = "BELOW"
    result = answer(engine, start(engine).snapshot)
    assert result.public.report.objectives[0].assessment == Assessment.INSUFFICIENT
    assert result.snapshot.pending_turn.action == Action.EASIER
    provider.performance = "AT_TARGET"
    result = answer(engine, result.snapshot)
    assert result.public.report.objectives[0].assessment == Assessment.BELOW


def test_invalid_config_and_duplicate_skills(setup):
    _, engine, _ = setup
    with pytest.raises(ValueError):
        InterviewConfig(mode="FOCUSED")
    with pytest.raises(ValueError):
        InterviewConfig(mode="MIXED", focused_question_mode=Mode.DEBUGGING)
    with pytest.raises(ValueError, match="Duplicate"):
        start(engine, [skill(), skill()])


def test_easier_task_cannot_verify_target_competence(setup):
    provider, engine, _ = setup
    provider.inability = True
    provider.observation, provider.performance = "NO_EVIDENCE", "UNDETERMINED"
    result = start(engine)
    result = answer(engine, result.snapshot, "I cannot solve this task")
    assert result.snapshot.pending_turn.action == Action.EASIER
    provider.inability = False
    provider.observation, provider.performance = "SUPPORTS", "AT_TARGET"
    result = answer(engine, result.snapshot, "I can perform the simpler step")
    assert not next(iter(result.snapshot.objectives.values())).criterion_results
    assert result.public.report.objectives[0].assessment == Assessment.BELOW


def test_contradiction_requires_explicit_verification(setup):
    provider, engine, _ = setup
    provider.limit_criteria = True
    initial = start(engine).snapshot
    first = answer(engine, initial).snapshot
    previous_id = first.turns[0].question.criterion_ids[0]
    first.pending_turn.question.criterion_ids = [previous_id]
    provider.performance = "BELOW"
    conflict = answer(engine, first).snapshot
    assert conflict.pending_turn.action == Action.VERIFY
    assert conflict.objectives[conflict.queue[0]].assessment == Assessment.INSUFFICIENT
    provider.resolve = True
    provider.performance = "AT_TARGET"
    resolved = answer(engine, conflict)
    state = next(iter(resolved.snapshot.objectives.values()))
    assert state.contradictions == []
    assert state.assessment == Assessment.INSUFFICIENT  # second criterion still missing


def test_report_evidence_points_to_its_actual_turn(setup):
    _, engine, _ = setup
    initial = start(engine)
    turn_id = initial.public.pending_turn.turn_id
    result = answer(engine, initial.snapshot)
    objective = result.public.report.objectives[0]
    assert {e.turn_id for e in objective.evidence} == {turn_id}
    assert set(objective.evidence[0].model_dump()) == {
        "turn_id", "criterion_id", "response_excerpt", "performance", "rationale",
        "depth_role", "observation",
    }


@pytest.mark.parametrize("observation,performance,text", [
    ("SUPPORTS", "AT_TARGET", "EXPLAIN ANALYZE"),
    ("CONTRADICTS", "BELOW", "Je vais supprimer chaque index."),
    ("NO_EVIDENCE", "UNDETERMINED", "Em thích chơi cầu lông."),
    ("NO_EVIDENCE", "UNDETERMINED", "Em chưa biết."),
])
def test_turn_review_is_post_session_and_grounds_each_quote(setup, observation, performance, text):
    from adaptive_questioning.evidence.reporting import report
    provider, engine, _ = setup
    provider.criterion_count = 3
    provider.observation, provider.performance = observation, performance
    current = answer(engine, start(engine).snapshot, text)
    assert not current.public.is_finished
    for live in (current.public.report, report(current.snapshot)):
        assert not live.turn_reviews
        assert not any(o.study_recommendations or o.weaknesses or o.strengths for o in live.objectives)
        assert not any(e.rationale for o in live.objectives for e in o.evidence)
    finished = engine.stop(current.snapshot)
    review, = finished.public.report.turn_reviews
    assert review.turn_id == finished.public.turns[0].turn_id
    assert review.reason and review.next_step
    assert not review.excerpt or review.excerpt in text
    if observation in {"SUPPORTS", "CONTRADICTS"} or text == "Em chưa biết.":
        assert review.excerpt == text
    if text == "Em thích chơi cầu lông.":
        assert "Chưa có bằng chứng" in review.reason
    assert sum(c.assessment == Assessment.NOT_ASSESSED for c in finished.public.report.objectives[0].criteria) == 2


def test_stop_after_deadline_preserves_time_budget_reason(setup):
    _, engine, now = setup
    initial = start(engine)
    now[0] += timedelta(hours=1)
    assert engine.stop(initial.snapshot).public.report.termination_reason == "TIME_BUDGET"


def test_blocked_hint_keeps_next_answer_independent(setup, monkeypatch):
    provider, engine, _ = setup
    provider.observation, provider.performance = "UNCLEAR", "UNDETERMINED"
    original = provider.judge

    def hint_once(context):
        judgment = original(context)
        judgment.feedback_contains_hint = True
        return judgment

    monkeypatch.setattr(provider, "judge", hint_once)
    initial = start(engine, max_questions=2).snapshot
    result = answer(engine, initial)
    assert all(item.observation == "UNCLEAR" and item.performance == "UNDETERMINED"
               for item in result.public.report.objectives[0].evidence)
    assert result.public.report.objectives[0].assessment == Assessment.INSUFFICIENT
    state = next(iter(result.snapshot.objectives.values()))
    assert not state.assisted_criteria
    provider.observation, provider.performance = "SUPPORTS", "AT_TARGET"
    second = answer(engine, result.snapshot)
    assert second.snapshot.objectives[state.objective.objective_id].evidence_history[-1].independent


@pytest.mark.parametrize("channel,code", [("TEXT", None), ("TEXT", "SELECT id FROM events"),
                                          ("VOICE", None), ("VOICE", "def answer():\n    return 42")])
def test_checklist_recheck_uses_frozen_optional_criterion_and_records_answer(setup, monkeypatch, channel, code):
    provider, engine, _ = setup
    provider.criterion_count = 3
    first = start(engine)
    objective = next(iter(first.snapshot.objectives.values())).objective.model_copy(deep=True)
    criterion = objective.criteria[1]
    criterion.essential = False
    original_question = provider.question

    def question(context):
        draft = original_question(context)
        if provider.question_number > 2:
            draft.text = "Một tiến trình bị khóa khi cập nhật tồn kho. Bạn xác định giao dịch gây chờ thế nào?"
        draft.requires_code = code is not None
        return draft

    monkeypatch.setattr(provider, "question", question)
    request = StartRequest(session_id="recheck", skills=[skill()], blueprint=Blueprint(objectives=[objective]),
        config={"interaction_mode": channel, "max_questions": 3, "duration_seconds": 300,
                "recheck": {"taskId": 1, "checklistItemId": 2}},
        prior_attempts={"mastered_skill_ids": [objective.skill_id]},
        recheck_target={"objective_id": objective.objective_id, "criterion_id": criterion.criterion_id,
                        "rubric_fingerprint": "same", "source_questions": [first.public.pending_turn.question]})
    current = engine.start(request)
    assert provider.question_number == 3  # Only changing the incident number was rejected.
    assert current.snapshot.pending_turn.question.criterion_ids == [criterion.criterion_id]
    assert current.public.pending_turn.requires_code == bool(code)
    assert current.public.pending_turn.question != first.public.pending_turn.question
    assert not current.public.report.turn_reviews
    if code and channel == "VOICE":
        with pytest.raises(ValueError, match="nộp mã"):
            answer(engine, current.snapshot, "chỉ giải thích")
    submitted_code = code if channel == "VOICE" else None
    result = engine.respond(TransitionRequest(snapshot=current.snapshot, expected_state_version=current.snapshot.state_version,
            turn_id=current.public.pending_turn.turn_id, candidate_response="" if submitted_code else (code or "EXPLAIN ANALYZE"),
            submitted_code=submitted_code))
    assert result.public.is_finished
    assert len(result.public.turns) == 1 and result.public.turns[0].submitted_code == submitted_code
    assert result.public.report.turn_reviews[0].excerpt == (code or "EXPLAIN ANALYZE")
    reports = result.public.report.objectives[0].criteria
    assert [c.assessment for c in reports] == [Assessment.NOT_ASSESSED, Assessment.AT, Assessment.NOT_ASSESSED]
    assert not reports[1].essential
    assert result.public.report.recheck_criterion == reports[1]
    assert result.public.report.coaching is None
    expired = current.snapshot.model_copy(deep=True)
    expired.deadline_at -= timedelta(minutes=6)
    assert engine.stop(expired).public.report.recheck_criterion.assessment == Assessment.INSUFFICIENT


@pytest.mark.parametrize("expires", [True, False])
def test_recheck_clarification_keeps_scope_until_time_or_question_budget(setup, expires):
    provider, engine, clock = setup
    provider.criterion_count = 3
    obj = next(iter(start(engine).snapshot.objectives.values())).objective
    selected = obj.criteria[1].criterion_id
    request = StartRequest(session_id="practice", skills=[skill()], blueprint=Blueprint(objectives=[obj]),
        config={"max_questions": 3, "duration_seconds": 300, "recheck": {"taskId": 1, "checklistItemId": 2}},
        recheck_target={"objective_id": obj.objective_id, "criterion_id": selected, "rubric_fingerprint": "frozen"})
    result = engine.start(request)
    provider.observation, provider.performance = "NO_EVIDENCE", "UNDETERMINED"
    first_scope = result.snapshot.pending_turn.question.evidence_scope
    for n in range(3):
        turn = result.snapshot.pending_turn
        assert turn.question.criterion_ids == [selected]
        if n == 1:
            assert turn.action == Action.CLARIFY and turn.question.evidence_scope == first_scope
            if expires:
                clock[0] += timedelta(minutes=5)
        result = answer(engine, result.snapshot, "Lạc đề")
        if result.public.is_finished:
            break
    assert len(result.public.turns) == (1 if expires else 3)
    assert result.public.report.termination_reason == ("TIME_BUDGET" if expires else "QUESTION_BUDGET")
    assert result.public.report.recheck_criterion.assessment == Assessment.INSUFFICIENT


def test_two_question_draft_keeps_only_a_reviewed_complete_task(setup, monkeypatch):
    provider, engine, _ = setup
    original = provider.question
    reviewed = []
    def draft(context):
        q = original(context)
        q.text = "Bạn sẽ phân tích sự cố này thế nào? Bạn sẽ viết thêm công cụ nào?"
        return q
    monkeypatch.setattr(provider, "question", draft)
    monkeypatch.setattr(provider, "review_question", lambda ctx: reviewed.append(json.loads(ctx)["question"]) or "ALIGNED")
    result = start(engine)
    assert reviewed == [result.public.pending_turn.question]
    assert result.public.pending_turn.question == "Bạn sẽ phân tích sự cố này thế nào?"


def test_api_rejects_incompatible_schema_and_bad_config(setup):
    _, engine, _ = setup
    app = FastAPI()
    app.include_router(router)
    app.state.evidence_workflow = engine
    with TestClient(app) as client:
        payload = StartRequest(session_id="test", skills=[skill()]).model_dump(mode="json")
        payload["config"]["mode"] = "FOCUSED"
        assert client.post('/api/v2/interview/start', json=payload).status_code == 422
        snapshot = start(engine).snapshot.model_dump(mode="json")
        snapshot["schema_version"] = 99
        assert client.post('/api/v2/interview/stop', json=snapshot).status_code == 422


def test_api_start_accepts_legacy_persisted_blueprint_fields_and_rejects_unknown_fields(setup, monkeypatch):
    provider, engine, _ = setup
    initial = start(engine)
    legacy_blueprint = Blueprint(
        objectives=[state.objective for state in initial.snapshot.objectives.values()]
    ).model_dump(mode="json")
    for objective in legacy_blueprint["objectives"]:
        objective.update(
            required_proficiency=4.0,
            extension_criterion_ids=[],
            inferred=True,
            rubric_version="evidence-2.0",
            rubric_fingerprint="legacy-fingerprint",
        )
        for mode in objective["suitable_modes"]:
            mode["rationale"] = "Legacy rationale"

    monkeypatch.setattr(provider, "blueprint", lambda _: pytest.fail("Reused blueprint must not regenerate"))
    app = FastAPI()
    app.include_router(router)
    app.state.evidence_workflow = engine
    with TestClient(app) as client:
        payload = StartRequest(session_id="attempt-legacy", skills=[skill()]).model_dump(mode="json")
        payload["blueprint"] = legacy_blueprint
        ok = client.post('/api/v2/interview/start', json=payload)
        assert ok.status_code == 200
        assert ok.json()["snapshot"]["session_id"] == "attempt-legacy"

        bad_payload = StartRequest(session_id="attempt-bad", skills=[skill()]).model_dump(mode="json")
        bad_payload["blueprint"] = {
            "objectives": [{**legacy_blueprint["objectives"][0], "unexpected_field": "invalid"}]
        }
        assert client.post('/api/v2/interview/start', json=bad_payload).status_code == 422
