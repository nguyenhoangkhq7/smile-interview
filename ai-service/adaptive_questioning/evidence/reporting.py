"""Pure report projection; internal rubric never leaks through pending turns."""
import re
from typing import Literal

from .models import (
    Assessment, Criterion, CriterionProgress, CriterionReport, Mode, ObjectiveReport,
    ObjectiveState, PendingTurn, PublicEvidence, PublicSession, PublicTurn,
    RecordedEvidence, Report, SessionCoaching, Snapshot, Turn, TurnReview,
)
from .assessment import criterion_resolved
from .policy_config import InterviewPolicy
from .conversation import MAX_FEEDBACK_LENGTH, MAX_PRACTICE_FEEDBACK_LENGTH, brief_feedback, display_skill_name

_STAR_RESULT = re.compile(r"\b(?:kết quả|giảm|tăng|cải thiện|tiết kiệm|đạt|%|giờ|phút|giây|nhờ đó|result|impact|improved|reduced)\b", re.IGNORECASE)
_STAR_ACTION = re.compile(r"\b(?:tôi đã|em đã|mình đã|tự|trực tiếp|đề xuất|triển khai|sửa|xử lý|i led|i built|i fixed|i implemented)\b", re.IGNORECASE)
_STAR_NEGATED = re.compile(r"\b(?:không biết|chưa biết|chưa làm|không xử lý được|không nhớ)\b", re.IGNORECASE)
_DESIGN_TRADEOFF = re.compile(r"\b(?:đánh đổi|trade.?off|độ trễ|latency|nhất quán|consistency|chi phí|cost|scale|mở rộng|bottleneck|nghẽn|ràng buộc)\b", re.IGNORECASE)
_CODING_COMPLEXITY = re.compile(r"(?:\bO\s*\([^)]+\)|độ phức tạp|complexity|time\s+complexity|space\s+complexity|bộ nhớ|ca biên|edge\s*case|rỗng|trùng lặp)", re.IGNORECASE)
_DEBUG_VERIFY = re.compile(r"\b(?:kiểm thử|test|unit\s*test|tái hiện|reproduc\w*|verify|xác minh|log|trace|monitor|regression)\b", re.IGNORECASE)


def _depth_role(item: RecordedEvidence, target_depth: int) -> Literal["TARGET", "DIAGNOSTIC", "EXTENSION"]:
    if item.is_extension or item.question_depth > target_depth:
        return "EXTENSION"
    if item.question_depth < target_depth:
        return "DIAGNOSTIC"
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
        used_hint = cid in state.hinted_criteria
        stagnant_gap = (
            progress.stop_reason in {"NO_PROGRESS", "CRITERION_BUDGET"}
            and bool(progress.unresolved_aspects)
        )
        had_struggle = (
            progress.easier_spent
            or cid in state.assisted_criteria
            or used_hint
            or any(e.criterion_id == cid and (e.performance == "BELOW" or e.explicit_inability) for e in history)
        )
        if res is None and not had_struggle and not stagnant_gap:
            continue  # Unasked/unverified without concrete gaps is not an observed weakness.
        if res is None and stagnant_gap and not had_struggle:
            gap = progress.unresolved_aspects[0].rstrip(".")
            recommendations.append(
                f"{obj.skill_id} ({obj.claim}): Làm rõ và luyện diễn đạt sâu hơn về {c.description} — cần bổ sung: {gap}."
            )
        elif res is None or cid in state.contradictions or res.performance == "BELOW" or cid in state.assisted_criteria:
            recommendations.append(f"{obj.skill_id} ({obj.claim}): Ưu tiên ôn luyện {c.description} — mục tiêu: {c.at_target}.")
        elif used_hint and not progress.transfer_verified:
            recommendations.append(
                f"{obj.skill_id} ({obj.claim}): Đã dùng gợi ý ở {c.description} — hãy luyện lại độc lập để vững phản xạ khi phỏng vấn thật."
            )
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
        hinted=key in state.hinted_criteria,
        transfer_verified=progress.transfer_verified,
    )


def _positive_assessment(state: ObjectiveState, key: str) -> Assessment:
    extension = state.objective.extension_depth
    target = state.objective.target_depth
    evidence = [
        e for e in state.evidence_history
        if e.criterion_id == key and e.independent
        and e.question_depth == extension
        and (e.is_extension or (extension is not None and extension > target))
        and e.observation in {"SUPPORTS", "CONTRADICTS"}
    ]
    if extension is not None and evidence and all(e.performance == "ABOVE" for e in evidence):
        return Assessment.ABOVE
    return Assessment.AT


def objective_report(
    state: ObjectiveState,
    policy: InterviewPolicy | None = None,
    skill_weights: dict[str, float] | None = None,
) -> ObjectiveReport:
    active_policy = policy or InterviewPolicy()
    obj = state.objective
    weight = skill_weights.get(obj.skill_id, 0.5) if skill_weights else 0.5
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
    criteria_reports = [criterion_report(state, c, active_policy) for c in obj.criteria]
    return ObjectiveReport(
        objective_id=obj.objective_id, skill_id=obj.skill_id, claim=obj.claim,
        jd_evidence_spans=obj.jd_evidence_spans,
        target_depth=obj.target_depth,
        importance_weight=weight,
        is_core=weight >= active_policy.core_importance,
        hinted=bool(state.hinted_criteria) or any(c.hinted for c in criteria_reports),
        assessment=state.assessment,
        stop_reason=state.stop_reason,
        strengths=[e.rationale for e in target_results if e.performance in {"AT_TARGET", "ABOVE"} and e.criterion_id not in state.contradictions],
        weaknesses=weaknesses,
        study_recommendations=_study_recommendations(state),
        evidence=evidence,
        criteria=criteria_reports,
    )


def _fallback_introduction_feedback(snapshot: Snapshot) -> str:
    intro = (snapshot.conversation.introduction.strip() if snapshot.conversation else "")
    if not intro:
        return ""
    words = len(intro.split())
    lowered = intro.casefold()
    matched_skills = [
        display_skill_name(skill.jd_skill_id, snapshot.skills)
        for skill in snapshot.skills
        if (skill.jd_skill_name and skill.jd_skill_name.casefold() in lowered)
        or (skill.jd_skill_id.replace("_", " ").casefold() in lowered)
    ]
    if words < 25:
        return "Phần tự giới thiệu khá ngắn; khi phỏng vấn thật nên bổ sung 1 dự án tiêu biểu gắn với yêu cầu JD và vai trò cụ thể của bạn."
    if words > 220:
        return "Phần tự giới thiệu hơi dài; nên cô đọng trong 60–90 giây gồm kinh nghiệm chính, 1–2 thành tích nổi bật và lý do phù hợp vị trí."
    if matched_skills:
        joined = ", ".join(dict.fromkeys(matched_skills[:3]))
        return f"Phần tự giới thiệu có nhắc tới kỹ năng liên quan ({joined}). Khi phỏng vấn thật, hãy chốt thêm 1 kết quả đo được từ dự án gần nhất."
    return "Phần tự giới thiệu rõ ràng; bạn nên nhấn mạnh thêm 1–2 kỹ năng cốt lõi trong JD và kết quả dự án thực tế để tạo ấn tượng ngay từ đầu."


def _delivery_notes(turn: Turn, interaction_mode: str) -> list[str]:
    text = (turn.transcript if turn.transcript is not None else (turn.answer or "")).strip()
    has_code = bool((turn.submitted_code or "").strip())
    if not text and not has_code:
        return []
    notes: list[str] = []
    words = len(text.split())
    if turn.mode == Mode.BEHAVIORAL:
        negated = bool(_STAR_NEGATED.search(text)) and words < 30
        has_action = not negated and bool(_STAR_ACTION.search(text))
        has_result = not negated and bool(_STAR_RESULT.search(text))
        if has_action and has_result:
            notes.append("Cấu trúc STAR: đã nêu hành động cá nhân và kết quả/tác động cụ thể.")
        else:
            missing = []
            if not has_action:
                missing.append("Action (hành động trực tiếp của riêng bạn)")
            if not has_result:
                missing.append("Result (kết quả đo được hoặc bài học rút ra)")
            notes.append(f"Gợi ý khung STAR: nên bổ sung rõ phần {' và '.join(missing)}.")
    elif turn.mode == Mode.DESIGN:
        if not _DESIGN_TRADEOFF.search(text):
            notes.append("Gợi ý trình bày Design: nên nêu rõ giả định tải/ràng buộc và đánh đổi (trade-off) giữa các phương án.")
    elif turn.mode == Mode.CODING:
        explanation = (turn.transcript or "").strip() if turn.submitted_code else text
        if turn.submitted_code and not explanation:
            notes.append("Gợi ý phỏng vấn Coding: khi nộp mã, hãy kèm 1–2 câu nêu độ phức tạp Big-O và các ca biên bạn đã kiểm tra.")
        elif explanation and not _CODING_COMPLEXITY.search(explanation):
            notes.append("Gợi ý phỏng vấn Coding: nên nêu rõ độ phức tạp thời gian/bộ nhớ (Big-O) và cách xử lý ca biên.")
    elif turn.mode == Mode.DEBUGGING:
        if words >= 10 and not _DEBUG_VERIFY.search(text):
            notes.append("Gợi ý trình bày Debugging: ngoài nguyên nhân và cách sửa, nên nêu cách tái hiện và kiểm thử để chắc chắn lỗi không tái diễn.")
    if interaction_mode == "VOICE":
        if words < 15 and not turn.submitted_code:
            notes.append("Trình bày giọng nói còn khá ngắn; nên giải thích thêm lý do và ví dụ minh họa để người phỏng vấn nắm chắc tư duy.")
        elif words > 240:
            notes.append("Câu trả lời giọng nói khá dài; nên chia ý theo cấu trúc 1–2–3 để súc tích và dễ theo dõi hơn.")
    return notes


def _default_reference_answer(criterion: Criterion, performance: str, turn: Turn | None = None) -> str:
    if performance in {"AT_TARGET", "ABOVE"}:
        return ""
    parts = [f"Ý cốt lõi cần đạt: {criterion.at_target.rstrip('.')}."]
    if criterion.expected_evidence.strip() and criterion.expected_evidence.strip().casefold() != criterion.at_target.strip().casefold():
        parts.append(f"Hướng triển khai: {criterion.expected_evidence.rstrip('.')}.")
    base = " ".join(parts)
    spec = turn.question.coding_spec if turn else None
    if spec and spec.reference_solution.strip():
        code = spec.reference_solution.strip()[:700]
        return f"{base}\n\nMã tham khảo đã kiểm chứng:\n```{spec.language}\n{code}\n```"
    return base


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
        introduction_feedback=_fallback_introduction_feedback(snapshot),
    )


def _default_level_up_tip(criterion: Criterion, performance: str) -> str:
    if performance != "AT_TARGET":
        return ""
    above = criterion.above_target.strip().rstrip(".")
    if not above or above.casefold() == criterion.at_target.strip().rstrip(".").casefold():
        return ""
    return f"Để đạt mức xuất sắc (Senior), hãy mở rộng thêm: {above}."


def coaching_context(snapshot: Snapshot, *, include_turn_maps: bool = True) -> dict[str, object]:
    """Assemble safe, evidence-grounded coaching inputs for end-of-session synthesis."""
    reports = [objective_report(state, snapshot.policy) for state in snapshot.objectives.values() if state.turns_spent > 0]
    opening = snapshot.opening_context
    intro = (snapshot.conversation.introduction.strip() if snapshot.conversation else "")[:800]
    turns_needing_reference = []
    turns_for_level_up = []
    turns_for_delivery_review = []
    if include_turn_maps:
        for turn in snapshot.turns:
            if not turn.judgment:
                continue
            criteria = {c.criterion_id: c for c in snapshot.objectives[turn.objective_id].objective.criteria}
            answer_text = (turn.transcript if turn.transcript is not None else (turn.answer or "")).strip()
            if answer_text and (
                turn.mode in {Mode.BEHAVIORAL, Mode.DESIGN, Mode.CODING, Mode.DEBUGGING}
                or snapshot.config.interaction_mode == "VOICE"
            ):
                turns_for_delivery_review.append({
                    "turn_id": turn.turn_id,
                    "mode": turn.mode.value,
                    "interaction_mode": snapshot.config.interaction_mode,
                    "answer_excerpt": answer_text[:400],
                })
            for obs in turn.judgment.observations:
                crit = criteria.get(obs.criterion_id)
                if crit is None:
                    continue
                if obs.performance == "AT_TARGET":
                    turns_for_level_up.append({
                        "turn_id": turn.turn_id,
                        "mode": turn.mode.value,
                        "question": turn.question.text[:280],
                        "criterion": crit.description,
                        "above_target": crit.above_target,
                    })
                    break
                if obs.performance == "ABOVE":
                    break
                ref_entry: dict[str, object] = {
                    "turn_id": turn.turn_id,
                    "mode": turn.mode.value,
                    "question": turn.question.text[:360],
                    "criterion": crit.description,
                    "at_target": crit.at_target,
                }
                if turn.question.coding_spec and turn.question.coding_spec.reference_solution.strip():
                    ref_entry["verified_reference_code"] = {
                        "language": turn.question.coding_spec.language,
                        "code": turn.question.coding_spec.reference_solution.strip()[:600],
                    }
                turns_needing_reference.append(ref_entry)
                break
    return {
        "role_title": (opening.role_title.strip() if opening else "") or "vị trí ứng tuyển",
        "company": opening.company.strip() if opening else "",
        "termination_reason": snapshot.termination_reason,
        "turns_answered": len(snapshot.turns),
        "candidate_introduction": intro,
        "turns_needing_reference": turns_needing_reference[:12],
        "turns_for_level_up": turns_for_level_up[:8],
        "turns_for_delivery_review": turns_for_delivery_review[:8],
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
    ref_map = snapshot.coaching.turn_reference_answers if snapshot.coaching else {}
    level_up_map = snapshot.coaching.turn_level_up_tips if snapshot.coaching else {}
    delivery_map = snapshot.coaching.turn_delivery_notes if snapshot.coaching else {}
    for turn in snapshot.turns:
        if not turn.judgment or not turn.answer:
            continue
        state = snapshot.objectives[turn.objective_id]
        criteria = {c.criterion_id: c for c in state.objective.criteria}
        llm_delivery = [note.strip() for note in delivery_map.get(turn.turn_id, []) if note and note.strip()]
        base_delivery = llm_delivery or _delivery_notes(turn, snapshot.config.interaction_mode)
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
            reference = (ref_map.get(turn.turn_id, "").strip()
                         or _default_reference_answer(criterion, obs.performance, turn=turn))
            level_up = (level_up_map.get(turn.turn_id, "").strip()
                        or _default_level_up_tip(criterion, obs.performance))
            delivery = list(base_delivery)
            if any(c.kind == "HINT" for c in turn.clarifications):
                delivery.append("Lượt này bạn đã dùng gợi ý — hãy thử giải lại độc lập để vững phản xạ khi phỏng vấn thật.")
            reviews.append(TurnReview(
                turn_id=turn.turn_id,
                excerpt=excerpt if excerpt and excerpt in turn.answer else "",
                reason=reason,
                gaps=gaps,
                next_step=step,
                reference_answer=reference,
                level_up_tip=level_up,
                delivery_notes=delivery,
            ))
    return reviews


def report(snapshot: Snapshot) -> Report:
    skill_weights = {s.jd_skill_id: s.importance_weight for s in snapshot.skills}
    objectives = [objective_report(s, snapshot.policy, skill_weights) for s in snapshot.objectives.values()]
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
    public_spec = turn.question.coding_spec.to_public() if turn.question.coding_spec else None
    return PendingTurn(
        turn_id=turn.turn_id, objective_id=turn.objective_id,
        mode=turn.mode, question=turn.question.text,
        introduction=turn.introduction, requires_code=turn.question.requires_code,
        coding_spec=public_spec,
        clarifications=list(turn.clarifications),
    )


def public_turn(
    turn: Turn,
    *,
    max_feedback_length: int = MAX_FEEDBACK_LENGTH,
    allow_sentence_trim: bool = False,
) -> PublicTurn:
    safe_checks = (
        turn.coding_checks.model_copy(update={"hidden_failed_summaries": []})
        if turn.coding_checks is not None else None
    )
    return PublicTurn(
        practice_step=turn.practice_step,
        turn_id=turn.turn_id, objective_id=turn.objective_id,
        mode=turn.mode, question=turn.question.text, answer=turn.answer,
        feedback=(
            brief_feedback(turn, max_length=max_feedback_length, allow_sentence_trim=allow_sentence_trim)
            if turn.judgment else None
        ),
        submitted_code=turn.submitted_code, transcript=turn.transcript, coding_checks=safe_checks,
        clarifications=list(turn.clarifications),
    )


def public_session(snapshot: Snapshot) -> PublicSession:
    is_practice = snapshot.config.session_purpose == "PRACTICE"
    max_fb_len = MAX_PRACTICE_FEEDBACK_LENGTH if is_practice else MAX_FEEDBACK_LENGTH
    return PublicSession(
        session_id=snapshot.session_id, state_version=snapshot.state_version,
        is_finished=snapshot.is_finished, deadline_at=snapshot.deadline_at,
        paused_remaining_seconds=snapshot.paused_remaining_seconds,
        config=snapshot.config, pending_turn=pending_turn(snapshot.pending_turn),
        awaiting_question=snapshot.next_question_action is not None,
        turns=[
            public_turn(turn, max_feedback_length=max_fb_len, allow_sentence_trim=is_practice)
            for turn in snapshot.turns
        ],
        report=report(snapshot),
        conversation=snapshot.conversation,
    )
