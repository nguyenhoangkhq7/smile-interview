"""
Phase 1 Initialization, Phase 3 Dual-Anchor Convergence Router (Turn-1 Gate,
1-Line Memory Consolidation & Sub-slot Garbage Collection), and Phase 4 HITL Report Builder.
"""

from typing import List, Optional, Sequence, Tuple
import uuid

from tabulate import tabulate

from adaptive_questioning.config import (
    CONVERGENCE_PROB_THRESHOLD,
    CONVERGENCE_TV_THRESHOLD,
    GLOBAL_COMPLETION_THRESHOLD,
    K_MAX,
    MAX_SUB_SLOTS,
    T_MAX,
)
from adaptive_questioning.core.math_utils import (
    expected_proficiency,
    map_rubric_level,
    temperature_softmax_prior,
    verified_skill_gap,
)
from adaptive_questioning.schemas.api_models import (
    HITLReportResponse,
    SkillAuditReportItem,
)
from adaptive_questioning.schemas.skill_gap_input import QuestionStrategyType, SkillGapInput
from adaptive_questioning.schemas.state import (
    ContextAnchor,
    InterviewSessionState,
    MetamorphicTag,
    SkillBeliefState,
    SubSlot,
)


def initialize_session_state(
    skills_input: Sequence[SkillGapInput],
    session_id: Optional[str] = None,
    t_max: int = T_MAX,
) -> InterviewSessionState:
    """
    Phase 1: Input & Belief Anchoring.
    1. Filter skills where suggested_strategy != "NONE" and priority > 0 into Q_primary,
       sorted by priority descending.
    2. Fix total initial count D = |Q_primary| as a constant denominator.
       Handle D = 0 gracefully (immediately mark session as finished).
    3. Filter skills where suggested_strategy == "NONE" (or priority <= 0) into Context Anchors A_ctx.
    4. Initialize prior belief B_0 via Temperature-Scaled Distance Softmax (tau_prior = 2.0).
    """
    sid = session_id or str(uuid.uuid4())

    primary_candidates: List[SkillGapInput] = []
    context_anchors: List[ContextAnchor] = []

    for item in skills_input:
        strategy_str = (
            item.suggested_strategy.value
            if isinstance(item.suggested_strategy, QuestionStrategyType)
            else str(item.suggested_strategy)
        )
        if strategy_str != QuestionStrategyType.NONE.value and item.priority > 0.0:
            primary_candidates.append(item)
        else:
            context_anchors.append(
                ContextAnchor(
                    jd_skill_id=item.jd_skill_id,
                    candidate_proficiency=item.candidate_proficiency,
                    context_job=item.context_job,
                    consolidated_summary=None,
                    source="INITIAL_NONE",
                )
            )

    # Sort Q_primary by priority descending (stable sort preserves input order on ties)
    primary_candidates.sort(key=lambda x: x.priority, reverse=True)

    primary_queue = [item.jd_skill_id for item in primary_candidates]
    total_d = len(primary_queue)

    skills_map = {}
    for item in primary_candidates:
        b0 = temperature_softmax_prior(item.candidate_proficiency)
        strategy_str = (
            item.suggested_strategy.value
            if isinstance(item.suggested_strategy, QuestionStrategyType)
            else str(item.suggested_strategy)
        )
        alignment_str = (
            item.semantic_alignment.value
            if hasattr(item.semantic_alignment, "value")
            else str(item.semantic_alignment)
        )
        skills_map[item.jd_skill_id] = SkillBeliefState(
            jd_skill_id=item.jd_skill_id,
            matched_cv_skill_id=item.matched_cv_skill_id,
            semantic_alignment=alignment_str,
            is_substituted=item.is_substituted,
            required_proficiency=item.required_proficiency,
            candidate_proficiency=item.candidate_proficiency,
            gap_magnitude=item.gap_magnitude,
            priority=item.priority,
            suggested_strategy=strategy_str,
            cv_evidence_spans=list(item.cv_evidence_spans),
            context_job=item.context_job,
            prior_belief=list(b0),
            current_belief=list(b0),
            belief_trajectory=[list(b0)],
        )

    is_finished = total_d == 0
    termination_reason = "NO_PRIMARY_SKILLS_TO_PROBE" if is_finished else None
    active_skill_id = primary_queue[0] if primary_queue else None

    return InterviewSessionState(
        session_id=sid,
        turn_t=0,
        total_initial_d=total_d,
        d_verified=0,
        t_max=t_max,
        primary_queue=list(primary_queue),
        initial_primary_order=list(primary_queue),
        active_skill_id=active_skill_id,
        skills=skills_map,
        all_input_skills=list(skills_input),
        context_anchors=context_anchors,
        is_finished=is_finished,
        termination_reason=termination_reason,
    )


def check_local_skill_completion(
    local_turn_k: int,
    tag: MetamorphicTag,
    p_t: Sequence[float],
    tv_delta: float,
    active_sub_slots: Sequence[SubSlot],
    k_max: int = K_MAX,
) -> Tuple[bool, Optional[str]]:
    """
    Phase 3 Local Primary Skill Completion Check.
    Mark active primary skill d* as VERIFIED when any 1 of 3 conditions holds:
      - Condition 1 (Valid Belief Convergence):
          * At k = 1: Only triggers if Tag == DECISIVE_SHIFT AND max_l P_t(l) >= 0.75.
          * At k >= 2: Triggers if Tag != INVARIANT AND (max_l P_t(l) >= 0.75 OR TV(P_t, P_{t-1}) <= 0.03).
      - Condition 2 (Sub-slots Saturated):
          * Both 2 probing sub-slots for d* have been created and filled.
      - Condition 3 (Local Turn Cap):
          * Local turns spent on d* reaches k_max = 3.
    """
    max_prob = max(p_t) if p_t else 0.0

    # Condition 1: Valid Belief Convergence
    if local_turn_k == 1:
        if tag == MetamorphicTag.DECISIVE_SHIFT and max_prob >= CONVERGENCE_PROB_THRESHOLD:
            return True, "CONDITION_1_TURN1_DECISIVE_CONVERGENCE"
    elif local_turn_k >= 2:
        if tag != MetamorphicTag.INVARIANT and (
            max_prob >= CONVERGENCE_PROB_THRESHOLD or tv_delta <= CONVERGENCE_TV_THRESHOLD
        ):
            return True, "CONDITION_1_BELIEF_CONVERGENCE"

    # Condition 2: Sub-slots Saturated (both 2 probing sub-slots created and filled)
    if len(active_sub_slots) >= MAX_SUB_SLOTS and all(
        s.filled and bool(s.value) for s in active_sub_slots[:MAX_SUB_SLOTS]
    ):
        return True, "CONDITION_2_SUB_SLOTS_SATURATED"

    # Condition 3: Local Turn Cap (k >= k_max = 3)
    if local_turn_k >= k_max:
        return True, "CONDITION_3_LOCAL_TURN_CAP"

    return False, None


def consolidate_and_garbage_collect(
    session: InterviewSessionState,
    skill: SkillBeliefState,
    consolidated_summary: Optional[str] = None,
    verification_reason: Optional[str] = None,
) -> None:
    """
    Transition & Garbage Collection Action when d* is marked VERIFIED:
      1. 1-Line Memory Consolidation: Append a 1-sentence summary of the verified finding for d* into A_ctx.
      2. Sub-slot Garbage Collection: Archive filled sub-slots for Phase 4 report, then purge all
         temporary sub-slots of d* from active prompt state (active_sub_slots) to prevent context bloating.
      3. Pop d* from Q_primary, increment D_verified <- D_verified + 1, and advance pointer to next skill.
    """
    skill.is_verified = True
    skill.verification_reason = verification_reason or "VERIFIED"

    s_hat = expected_proficiency(skill.current_belief)
    map_lvl = map_rubric_level(skill.current_belief)
    summary_line = (
        consolidated_summary.strip()
        if consolidated_summary and consolidated_summary.strip()
        else (
            f"Đã xác minh kỹ năng '{skill.jd_skill_id}' đạt mức {map_lvl.value} "
            f"({s_hat:.2f}/5.0 so với yêu cầu JD {skill.required_proficiency:.2f}/5.0)."
        )
    )
    skill.consolidated_finding = summary_line

    # 1. Append 1-sentence summary to A_ctx
    session.context_anchors.append(
        ContextAnchor(
            jd_skill_id=skill.jd_skill_id,
            candidate_proficiency=round(s_hat, 3),
            context_job=skill.context_job,
            consolidated_summary=summary_line,
            source="VERIFIED_CONSOLIDATION",
        )
    )

    # 2. Sub-slot Garbage Collection (preserve audit copy in archived_sub_slots, purge active_sub_slots)
    skill.archived_sub_slots = [s.model_copy(deep=True) for s in skill.active_sub_slots]
    skill.active_sub_slots.clear()

    # 3. Pop d* from Q_primary, increment D_verified, advance active_skill_id pointer
    if skill.jd_skill_id in session.primary_queue:
        session.primary_queue.remove(skill.jd_skill_id)
    session.d_verified += 1
    session.active_skill_id = session.primary_queue[0] if session.primary_queue else None


def compute_completion_rate(session: InterviewSessionState) -> float:
    """
    Compute global interview completion rate D_verified / D using the constant denominator D.
    """
    if session.total_initial_d <= 0:
        return 1.0
    return round(float(session.d_verified) / float(session.total_initial_d), 4)


def check_global_termination(
    session: InterviewSessionState,
) -> Tuple[bool, Optional[str]]:
    """
    Global Interview Termination Check:
    Terminate the entire interview session when:
      1) Q_primary is empty, OR
      2) D_verified / D >= 0.80, OR
      3) t >= T_max (default T_max = 10)
    """
    if session.is_finished:
        return True, session.termination_reason or "ALREADY_FINISHED"

    if not session.primary_queue:
        session.is_finished = True
        session.termination_reason = "PRIMARY_QUEUE_EMPTY"
        session.active_skill_id = None
        return True, session.termination_reason

    completion_ratio = (
        float(session.d_verified) / float(session.total_initial_d)
        if session.total_initial_d > 0
        else 1.0
    )
    if completion_ratio >= GLOBAL_COMPLETION_THRESHOLD:
        session.is_finished = True
        session.termination_reason = "GLOBAL_COMPLETION_THRESHOLD_80_PERCENT"
        session.active_skill_id = None
        return True, session.termination_reason

    if session.turn_t >= session.t_max:
        session.is_finished = True
        session.termination_reason = "GLOBAL_TURN_CAP_REACHED"
        session.active_skill_id = None
        return True, session.termination_reason

    return False, None


def generate_hitl_report(session: InterviewSessionState) -> HITLReportResponse:
    """
    Phase 4: Auditable HITL Report Generator.
    Computes Verified Proficiency Score, MAP Rubric Level, Verified Skill Gap,
    and builds both structured JSON and a formatted Markdown summary table.
    """
    evaluated_items: List[SkillAuditReportItem] = []

    for skill_id in session.initial_primary_order:
        skill = session.skills[skill_id]
        s_hat = expected_proficiency(skill.current_belief)
        map_lvl = map_rubric_level(skill.current_belief)
        v_gap = verified_skill_gap(skill.required_proficiency, s_hat)

        skill_logs = [log for log in session.turn_history if log.skill_id == skill_id]
        tags = [log.metamorphic_tag for log in skill_logs if log.metamorphic_tag is not None]
        justifications = [
            log.reflective_insight for log in skill_logs if log.reflective_insight is not None
        ]
        sub_slots_record = (
            skill.archived_sub_slots if skill.is_verified else skill.active_sub_slots
        )

        evaluated_items.append(
            SkillAuditReportItem(
                jd_skill_id=skill.jd_skill_id,
                matched_cv_skill_id=skill.matched_cv_skill_id,
                suggested_strategy=skill.suggested_strategy,
                initial_cv_proficiency=round(skill.candidate_proficiency, 2),
                verified_proficiency=round(s_hat, 2),
                required_jd_proficiency=round(skill.required_proficiency, 2),
                verified_skill_gap=round(v_gap, 2),
                map_rubric_level=map_lvl,
                is_verified=skill.is_verified,
                verification_reason=skill.verification_reason,
                local_turns_spent=skill.local_turn_k,
                prior_belief=[round(p, 4) for p in skill.prior_belief],
                final_belief=[round(p, 4) for p in skill.current_belief],
                belief_trajectory=[
                    [round(p, 4) for p in vec] for vec in skill.belief_trajectory
                ],
                metamorphic_tags=tags,
                judge_justifications=justifications,
                primary_slot_value=skill.primary_slot_value,
                filled_sub_slots=sub_slots_record,
                consolidated_finding=skill.consolidated_finding,
            )
        )

    completion_rate = compute_completion_rate(session)

    # Build Markdown summary table using `tabulate` (GitHub Flavored Markdown format)
    table_headers = [
        "Kỹ năng (`jd_skill_id`)",
        "Chiến lược",
        "$s_{cv}$ (CV Ban đầu)",
        "$\\hat{s}_{\\text{final}}$ (Sau Phỏng vấn)",
        "$s_{jd}$ (Yêu cầu JD)",
        "Verified Gap",
        "MAP Rubric",
        "Trạng thái",
    ]
    table_rows = []
    for item in evaluated_items:
        status_label = f"VERIFIED ({item.verification_reason})" if item.is_verified else "UNVERIFIED"
        table_rows.append(
            [
                f"`{item.jd_skill_id}`",
                f"`{item.suggested_strategy}`",
                f"{item.initial_cv_proficiency:.2f}",
                f"**{item.verified_proficiency:.2f}**",
                f"{item.required_jd_proficiency:.2f}",
                f"{item.verified_skill_gap:.2f}",
                f"**{item.map_rubric_level.value}**",
                status_label,
            ]
        )

    github_table = tabulate(table_rows, headers=table_headers, tablefmt="github")

    md_lines = [
        f"# Báo cáo Kiểm toán Phỏng vấn Thích ứng (Auditable HITL Report - Session `{session.session_id}`)",
        "",
        f"- **Trạng thái phiên**: `{'FINISHED' if session.is_finished else 'IN_PROGRESS'}` "
        f"({session.termination_reason or 'ACTIVE'})",
        f"- **Tổng số lượt hỏi ($t$)**: {session.turn_t} / {session.t_max}",
        f"- **Tiến độ xác minh kỹ năng ($D_{{\\text{{verified}}}} / D$)**: "
        f"{session.d_verified} / {session.total_initial_d} ({completion_rate * 100:.1f}%)",
        "",
        "## 1. Bảng Đối chiếu Năng lực Trước & Sau Phỏng vấn",
        "",
        github_table,
    ]

    md_lines.extend(["", "## 2. Quỹ đạo Niềm tin ($B_{0:T}$), Metamorphic Tags & Bằng chứng Sub-slots", ""])
    for item in evaluated_items:
        traj_str = " -> ".join(str(vec) for vec in item.belief_trajectory)
        tags_str = ", ".join(t.value for t in item.metamorphic_tags) if item.metamorphic_tags else "None"
        md_lines.append(f"### Kỹ năng: `{item.jd_skill_id}`")
        md_lines.append(f"- **Quỹ đạo niềm tin ($B_{{0:T}}$)**: `{traj_str}`")
        md_lines.append(f"- **Metamorphic Tags**: `{tags_str}`")
        if item.primary_slot_value:
            md_lines.append(f"- **Primary Slot Evidence**: {item.primary_slot_value}")
        if item.filled_sub_slots:
            for sub in item.filled_sub_slots:
                md_lines.append(
                    f"- **Sub-slot `{sub.slot_id}` ({sub.slot_name})**: {sub.value or 'Unfilled'}"
                )
        if item.judge_justifications:
            for idx, just in enumerate(item.judge_justifications, start=1):
                md_lines.append(f"- **Judge Insight (k={idx})**: {just}")
        if item.consolidated_finding:
            md_lines.append(f"- **1-Line Consolidated Memory**: *{item.consolidated_finding}*")
        md_lines.append("")

    markdown_summary = "\n".join(md_lines)

    return HITLReportResponse(
        session_id=session.session_id,
        is_finished=session.is_finished,
        termination_reason=session.termination_reason,
        total_turns=session.turn_t,
        total_initial_primary_skills=session.total_initial_d,
        verified_primary_skills=session.d_verified,
        completion_rate=completion_rate,
        evaluated_skills=evaluated_items,
        consolidated_context_anchors=list(session.context_anchors),
        turn_audit_trail=list(session.turn_history),
        markdown_summary=markdown_summary,
    )
