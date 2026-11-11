"""Offline behavioural tests: coverage, atomic transitions, scope and persistence contract."""
import json
import re
from datetime import datetime, timedelta, timezone

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from adaptive_questioning.evidence.models import (
    Action, Assessment, Blueprint, Criterion, InterviewConfig, InterviewSkill,
    Judgment, Mode, Objective, Observation, Question, Snapshot, StartRequest,
    SuitableMode, TransitionRequest,
)
from adaptive_questioning.evidence.routes import router
from adaptive_questioning.evidence.workflow import EvidenceWorkflow
from adaptive_questioning.evidence.errors import JudgmentUnavailableError
from adaptive_questioning.evidence.policy_config import InterviewPolicy


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
        return Blueprint(objectives=[Objective(
            requirement_id=key, skill_id=req["skill_id"], claim=req["description"],
            required_proficiency=req["required_proficiency"],
            criteria=[Criterion(description=f"Criterion {i}", expected_evidence="Observable execution",
                                 below_target="Incorrect execution", at_target="Correct execution",
                                 above_target="Correct with tradeoffs") for i in range(
                                     self.criterion_counts.get(req["skill_id"], 2 if self.limit_criteria else self.criterion_count))],
            suitable_modes=[SuitableMode(mode=mode, rationale="Matches the JD task") for mode in
                            ([mode for mode, pattern in InterviewPolicy().mode_patterns.items()
                              if req["has_task"] and re.search(pattern, req["description"], re.IGNORECASE)] or [Mode.DEBUGGING])],
        ) for key, req in requirements.items()])

    def question(self, context):
        if self.fail_question:
            raise RuntimeError("simulated generator outage")
        values = json.loads(context)
        self.question_number += 1
        ids = values["target_criteria"]
        return Question(surprising_fact_C=f"Observed unverified evidence gap for {ids[0]}",
                        hypothesis_A=f"Candidate needs to demonstrate concrete reasoning at depth {values['question_depth']}",
                        text=f"How would you diagnose this concrete incident {self.question_number}?",
                        criterion_ids=ids[:1] if self.limit_criteria else ids,
                        mode=values["mode"], depth=values["question_depth"],
                        evidence_scope=values.get("required_evidence_scope", f"incident-{self.question_number}"))

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
    values = dict(jd_skill_id=name, required_proficiency=4, candidate_proficiency=4,
                  priority=0, suggested_strategy="NONE", importance_weight=0.9)
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
    second = engine.start(StartRequest(session_id="attempt-2", skills=[skill()], blueprint=frozen,
                                       policy=first.snapshot.policy))
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
    assert result.public.report.evidence_coverage == 1
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
    assert report.evidence_coverage == 0
    assert report.target_attainment is None


def test_passing_one_criterion_does_not_replace_full_coverage(setup):
    provider, engine, _ = setup
    provider.limit_criteria = True
    result = answer(engine, start(engine).snapshot)
    assert not result.public.is_finished
    assert result.public.report.objectives[0].assessment == Assessment.INSUFFICIENT
    assert result.public.report.evidence_coverage == 0.5


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


def test_snapshot_roundtrip_and_stale_turn(setup):
    _, engine, _ = setup
    initial = start(engine).snapshot
    restored = Snapshot.model_validate_json(initial.model_dump_json())
    with pytest.raises(ValueError, match="Stale turn"):
        engine.respond(TransitionRequest(snapshot=restored, turn_id="wrong", expected_state_version=1, candidate_response="answer"))
    assert answer(engine, restored).public.state_version == 2


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
    assert result.public.report.evidence_coverage == 0


def test_reserves_initial_opportunities_for_other_skills(setup):
    provider, engine, _ = setup
    provider.observation, provider.performance = "NO_EVIDENCE", "UNDETERMINED"
    initial = start(engine, [skill(), skill("java")], max_questions=2)
    first = initial.public.pending_turn.skill_id
    result = answer(engine, initial.snapshot)
    assert result.public.pending_turn.skill_id != first


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
    public = response.json()["public"]
    assert "criteria" not in public["pending_turn"]
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
    assert result.public.report.target_attainment == 0


def test_invalid_config_and_duplicate_skills(setup):
    _, engine, _ = setup
    with pytest.raises(ValueError):
        InterviewConfig(mode="FOCUSED")
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
    assert result.public.report.evidence_coverage == 0
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
    assert objective.evidence_turn_ids == [turn_id]
    assert all(e.turn_id == turn_id for e in objective.evidence)


def test_stop_after_deadline_preserves_time_budget_reason(setup):
    _, engine, now = setup
    initial = start(engine)
    now[0] += timedelta(hours=1)
    assert engine.stop(initial.snapshot).public.report.termination_reason == "TIME_BUDGET"


def test_hint_cannot_establish_independent_competence(setup):
    _, engine, _ = setup
    initial = start(engine, max_questions=1).snapshot
    initial.pending_turn.question.assistance = "HINT"
    result = answer(engine, initial)
    assert result.public.report.evidence_coverage == 0
    assert result.public.report.objectives[0].assessment == Assessment.INSUFFICIENT


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
