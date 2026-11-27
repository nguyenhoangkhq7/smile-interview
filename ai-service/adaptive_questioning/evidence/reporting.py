"""Pure report projection; internal rubric never leaks through pending turns."""
from typing import Literal

from .models import (
    Assessment, Criterion, CriterionProgress, CriterionReport, ObjectiveReport,
    ObjectiveState, PendingTurn, PublicEvidence, PublicSession, PublicTurn,
    RecordedEvidence, Report, SessionCoaching, Snapshot, Turn, TurnReview,
)
from .assessment import criterion_resolved
from .policy_config import InterviewPolicy
from .conversation import brief_feedback, display_skill_name


def _depth_role(item: RecordedEvidence, target_depth: int) -> Literal["TARGET", "DIAGNOSTIC", "EXTENSION"]:
    if item.question_depth < target_depth:
        return "DIAGNOSTIC"
    if item.question_depth > target_depth:
        return "EXTENSION"
    return "TARGET"


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
        criterion_id=key, essential=criterion.essential,
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
    evidence = [
        PublicEvidence(
            turn_id=item.turn_id,
            criterion_id=item.criterion_id,
            response_excerpt=item.response_excerpt,
            performance=item.performance,
            rationale=item.rationale,
            depth_role=_depth_role(item, obj.target_depth),
            observation=item.observation,
        )
        for item in history
        if item.independent and (
            item.observation in {"SUPPORTS", "CONTRADICTS"}
            or item.explicit_inability
            or (item.observation == "UNCLEAR" and item.rationale.strip())
        )
    ]
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
        evidence=evidence,
        criteria=[criterion_report(state, c, active_policy) for c in obj.criteria],
    )


def fallback_session_coaching(snapshot: Snapshot) -> SessionCoaching | None:
    """Deterministic Vietnamese coaching summary grounded in recorded evidence when LLM coaching is unavailable."""
    if not snapshot.turns:
        return None
    reports = [objective_report(state, snapshot.policy) for state in snapshot.objectives.values() if state.turns_spent > 0]
    if not reports:
        return None
    role = (snapshot.opening_context.role_title.strip() if snapshot.opening_context else "") or "vị trí ứng tuyển"
    strong = [r for r in reports if r.assessment in {Assessment.AT, Assessment.ABOVE}]
    weak = [r for r in reports if r.assessment in {Assessment.BELOW, Assessment.NOT_DEMONSTRATED}]
    partial = [r for r in reports if r.assessment == Assessment.INSUFFICIENT]

    summary_parts = [f"Trong buổi phỏng vấn cho vị trí {role}, bạn đã hoàn thành {len(snapshot.turns)} lượt trao đổi."]
    if strong:
        names = ", ".join(dict.fromkeys(display_skill_name(r.skill_id, snapshot.skills) for r in strong))
        summary_parts.append(f"Bạn thể hiện đạt yêu cầu ở các kỹ năng: {names}.")
    if weak:
        names = ", ".join(dict.fromkeys(display_skill_name(r.skill_id, snapshot.skills) for r in weak))
        summary_parts.append(f"Cần ưu tiên củng cố thêm ở: {names}.")
    elif partial:
        summary_parts.append("Một số tiêu chí vẫn cần thêm dữ kiện ở lượt luyện tập sau để kết luận đầy đủ.")

    top_strengths = list(dict.fromkeys(item for r in reports for item in r.strengths))[:3]
    priority_gaps = list(dict.fromkeys(item for r in reports for item in r.weaknesses))[:3]
    actionable = list(dict.fromkeys(item for r in reports for item in r.study_recommendations))[:4]
    if not actionable and strong:
        actionable = ["Tiếp tục luyện các bài toán mở rộng về hiệu năng, biên lỗi và đánh đổi thiết kế ở lượt tiếp theo."]
    elif not actionable:
        actionable = ["Hoàn thành thêm lượt phỏng vấn để có đủ bằng chứng chi tiết cho từng tiêu chí."]

    return SessionCoaching(
        overall_summary=" ".join(summary_parts),
        top_strengths=top_strengths,
        priority_gaps=priority_gaps,
        actionable_study_steps=actionable,
    )


def coaching_context(snapshot: Snapshot) -> dict[str, object]:
    """Assemble safe, evidence-grounded coaching inputs for end-of-session synthesis."""
    reports = [objective_report(state, snapshot.policy) for state in snapshot.objectives.values() if state.turns_spent > 0]
    opening = snapshot.opening_context
    return {
        "role_title": (opening.role_title.strip() if opening else "") or "vị trí ứng tuyển",
        "company": opening.company.strip() if opening else "",
        "termination_reason": snapshot.termination_reason,
        "turns_answered": len(snapshot.turns),
        "objectives": [
            {
                "skill": display_skill_name(item.skill_id, snapshot.skills),
                "claim": item.claim,
                "assessment": item.assessment.value,
                "strengths": item.strengths[:3],
                "weaknesses": item.weaknesses[:3],
                "study_recommendations": item.study_recommendations[:3],
                "evidence": [
                    {
                        "depth_role": ev.depth_role,
                        "observation": ev.observation,
                        "performance": ev.performance,
                        "rationale": ev.rationale,
                    }
                    for ev in item.evidence[:4]
                ],
            }
            for item in reports
        ],
    }


def _turn_reviews(snapshot: Snapshot) -> list[TurnReview]:
    reviews = []
    for turn in snapshot.turns:
        if not turn.judgment or not turn.answer:
            continue
        criteria = {c.criterion_id: c for c in snapshot.objectives[turn.objective_id].objective.criteria}
        for obs in turn.judgment.observations:
            criterion = criteria.get(obs.criterion_id)
            if criterion is None:
                continue
            excerpt = obs.response_excerpt or turn.judgment.inability_excerpt
            gaps = [part.strip() for part in obs.unresolved_aspects if part.strip()]
            if gaps:
                step = f"Làm lại một bài về {criterion.description}. Tập trung vào {gaps[0].rstrip('.')}."
            elif obs.performance in {"AT_TARGET", "ABOVE"}:
                step = f"Thử áp dụng trong tình huống mới: {criterion.description}"
            else:
                step = f"Khi trả lời lại, hãy thể hiện: {criterion.at_target}"
            reason = obs.rationale
            if obs.observation == "NO_EVIDENCE" and not turn.judgment.explicit_inability:
                reason = f"Chưa có bằng chứng cho tiêu chí {criterion.description}. {reason}"
            reviews.append(TurnReview(turn_id=turn.turn_id, excerpt=excerpt if excerpt and excerpt in turn.answer else "",
                                      reason=reason, gaps=gaps, next_step=step))
    return reviews


def report(snapshot: Snapshot) -> Report:
    objectives = [objective_report(s, snapshot.policy) for s in snapshot.objectives.values()]
    target = snapshot.recheck_target
    selected = next((c for o in objectives if target and o.objective_id == target.objective_id
                     for c in o.criteria if c.criterion_id == target.criterion_id), None)
    if selected and selected.assessment == Assessment.NOT_ASSESSED and snapshot.termination_reason == "TIME_BUDGET":
        selected = selected.model_copy(update={"assessment": Assessment.INSUFFICIENT})
    if not snapshot.is_finished:
        for objective in objectives:
            objective.strengths = []
            objective.weaknesses = []
            objective.study_recommendations = []
            for evidence in objective.evidence:
                evidence.rationale = ""
    return Report(
        termination_reason=snapshot.termination_reason,
        recheck_criterion=selected,
        turn_reviews=_turn_reviews(snapshot) if snapshot.is_finished else [],
        objectives=objectives,
        coaching=snapshot.coaching,
    )


def pending_turn(turn: Turn | None) -> PendingTurn | None:
    if turn is None:
        return None
    return PendingTurn(
        turn_id=turn.turn_id, objective_id=turn.objective_id,
        mode=turn.mode, question=turn.question.text,
        introduction=turn.introduction, requires_code=turn.question.requires_code,
    )


def public_turn(turn: Turn) -> PublicTurn:
    return PublicTurn(
        turn_id=turn.turn_id, objective_id=turn.objective_id,
        mode=turn.mode, question=turn.question.text, answer=turn.answer,
        feedback=brief_feedback(turn) if turn.judgment else None,
        submitted_code=turn.submitted_code, transcript=turn.transcript, coding_checks=turn.coding_checks,
    )


def public_session(snapshot: Snapshot) -> PublicSession:
    return PublicSession(
        session_id=snapshot.session_id, state_version=snapshot.state_version,
        is_finished=snapshot.is_finished, deadline_at=snapshot.deadline_at,
        config=snapshot.config, pending_turn=pending_turn(snapshot.pending_turn),
        awaiting_question=snapshot.next_question_action is not None,
        turns=[public_turn(turn) for turn in snapshot.turns], report=report(snapshot),
        conversation=snapshot.conversation,
    )
