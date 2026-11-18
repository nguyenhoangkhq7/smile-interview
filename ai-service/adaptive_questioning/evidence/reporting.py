"""Pure report projection; internal rubric never leaks through pending turns."""
from .models import (
    Assessment, Criterion, CriterionProgress, CriterionReport, ObjectiveReport,
    ObjectiveState, PendingTurn, PublicEvidence, PublicSession, PublicTurn, Report, Snapshot, Turn,
)
from .assessment import criterion_resolved
from .policy_config import InterviewPolicy
from .conversation import brief_feedback


def _study_recommendations(state: ObjectiveState) -> list[str]:
    if not state.turns_spent or state.assessment == Assessment.NOT_ASSESSED:
        return []
    obj = state.objective
    history = state.evidence_history or []
    recommendations: list[str] = []
    for c in obj.criteria:
        cid = c.criterion_id
        res = state.criterion_results.get(cid)
        progress = state.criterion_progress.get(cid, CriterionProgress())
        had_struggle = (
            progress.easier_spent
            or cid in state.assisted_criteria
            or any(e.criterion_id == cid and (e.performance == "BELOW" or e.explicit_inability) for e in history)
        )
        if res is None and not had_struggle:
            continue  # Unasked/unverified is not an observed weakness.
        if res is None or cid in state.contradictions or res.performance == "BELOW" or cid in state.assisted_criteria:
            recommendations.append(f"{obj.skill_id} ({obj.claim}): Ưu tiên ôn luyện {c.description} — mục tiêu: {c.at_target}.")
        elif had_struggle:
            recommendations.append(f"{obj.skill_id} ({obj.claim}): Tiếp tục luyện các bài toán {c.description} để củng cố phản xạ độc lập.")
    return list(dict.fromkeys(recommendations))


def criterion_report(state: ObjectiveState, criterion: Criterion, policy: InterviewPolicy | None = None) -> CriterionReport:
    active_policy = policy or InterviewPolicy()
    key = criterion.criterion_id
    progress = state.criterion_progress.get(key, CriterionProgress())
    result = state.criterion_results.get(key)
    assessment = Assessment.INSUFFICIENT if progress.turns_spent else Assessment.NOT_ASSESSED
    if criterion_resolved(state, key, active_policy):
        assessment = _positive_assessment(state, key) if result and result.performance in {"AT_TARGET", "ABOVE"} else Assessment.BELOW
    return CriterionReport(
        criterion_id=key,
        description=criterion.description,
        assessment=assessment,
    )


def _positive_assessment(state: ObjectiveState, key: str) -> Assessment:
    extension = state.objective.extension_depth
    evidence = [e for e in state.evidence_history if e.criterion_id == key and e.independent
                and e.question_depth == extension and e.observation in {"SUPPORTS", "CONTRADICTS"}]
    if extension is not None and evidence and all(e.performance == "ABOVE" for e in evidence):
        return Assessment.ABOVE
    return Assessment.AT


def objective_report(state: ObjectiveState, policy: InterviewPolicy | None = None) -> ObjectiveReport:
    active_policy = policy or InterviewPolicy()
    obj = state.objective
    history = state.evidence_history
    evidence = [e for e in history if e.independent and e.question_depth == obj.target_depth
                and (e.observation in {"SUPPORTS", "CONTRADICTS"} or e.explicit_inability)]
    target_results = list(state.criterion_results.values())
    weaknesses = list(dict.fromkeys([
        *[e.rationale for e in target_results if e.performance == "BELOW" and e.criterion_id not in state.contradictions],
        *[e.rationale for e in history if e.independent and e.explicit_inability],
    ]))
    return ObjectiveReport(
        objective_id=obj.objective_id, skill_id=obj.skill_id, claim=obj.claim,
        jd_evidence_spans=obj.jd_evidence_spans,
        assessment=state.assessment,
        stop_reason=state.stop_reason,
        strengths=[e.rationale for e in target_results if e.performance in {"AT_TARGET", "ABOVE"} and e.criterion_id not in state.contradictions],
        weaknesses=weaknesses,
        study_recommendations=_study_recommendations(state),
        evidence=[PublicEvidence.model_validate(item, from_attributes=True) for item in evidence],
        criteria=[criterion_report(state, c, active_policy) for c in obj.criteria],
    )


def report(snapshot: Snapshot) -> Report:
    objectives = [objective_report(s, snapshot.policy) for s in snapshot.objectives.values()]
    return Report(
        termination_reason=snapshot.termination_reason,
        objectives=objectives,
    )


def pending_turn(turn: Turn | None) -> PendingTurn | None:
    if turn is None:
        return None
    return PendingTurn(
        turn_id=turn.turn_id, objective_id=turn.objective_id,
        mode=turn.mode, question=turn.question.text,
        introduction=turn.introduction,
    )


def public_turn(turn: Turn) -> PublicTurn:
    return PublicTurn(
        turn_id=turn.turn_id, objective_id=turn.objective_id,
        mode=turn.mode, question=turn.question.text, answer=turn.answer,
        feedback=brief_feedback(turn) if turn.judgment else None,
    )


def public_session(snapshot: Snapshot) -> PublicSession:
    return PublicSession(
        session_id=snapshot.session_id, state_version=snapshot.state_version,
        is_finished=snapshot.is_finished, deadline_at=snapshot.deadline_at,
        config=snapshot.config, pending_turn=pending_turn(snapshot.pending_turn),
        turns=[public_turn(turn) for turn in snapshot.turns], report=report(snapshot),
        conversation=snapshot.conversation,
    )
