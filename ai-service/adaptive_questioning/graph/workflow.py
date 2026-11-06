"""
LangGraph StateGraph Orchestrator for Pipeline V2.2 (`langgraph.graph.StateGraph`):
Coordinates Phase 1 Initialization, Step 2B Judge -> Phase 3 Dual-Anchor Convergence Router -> Step 2A Question Generator,
and Phase 4 Auditable HITL Report Generation.
"""

from typing import List, Literal, Optional, Sequence, Tuple, TypedDict

from langgraph.graph import END, START, StateGraph

from adaptive_questioning.config import MAX_SUB_SLOTS, T_MAX
from adaptive_questioning.core.engine import BaseLLMEngine, OpenAILLMEngine
from adaptive_questioning.core.math_utils import (
    normalize_simplex,
    simplex_convex_update_detailed,
)
from adaptive_questioning.core.router import (
    check_global_termination,
    check_local_skill_completion,
    compute_completion_rate,
    consolidate_and_garbage_collect,
    generate_hitl_report,
    initialize_session_state,
)
from adaptive_questioning.schemas.api_models import (
    HITLReportResponse,
    RespondInterviewResponse,
    StartInterviewResponse,
    Step2AQuestionOutput,
)
from adaptive_questioning.schemas.skill_gap_input import SkillGapInput
from adaptive_questioning.schemas.state import (
    AbductiveReasoning,
    InterviewSessionState,
    MetamorphicTag,
    SkillBeliefState,
    SubSlot,
    TurnLog,
)


class GraphTurnState(TypedDict, total=False):
    """TypedDict state schema passed through the compiled LangGraph StateGraph."""

    mode: Literal["START", "RESPOND"]
    session: InterviewSessionState
    candidate_response: Optional[str]

    # Step 2B & Phase 3 intermediate state
    evaluated_turn: int
    evaluated_skill_id: Optional[str]
    previous_belief: List[float]
    updated_belief: List[float]
    tv_delta: float
    metamorphic_tag: Optional[MetamorphicTag]
    reflective_insight: Optional[str]
    consolidated_summary: Optional[str]
    skill_verified: bool
    verification_reason: Optional[str]
    next_question: Optional[str]

    # Final API response payloads
    start_response: Optional[StartInterviewResponse]
    respond_response: Optional[RespondInterviewResponse]


class AdaptiveQuestioningWorkflow:
    """
    LangGraph `StateGraph` orchestrating Pipeline V2.2:
      - `step2b_reflective_judge` -> `phase3_convergence_router` -> (conditional) `step2a_question_generator`
    """

    def __init__(self, engine: Optional[BaseLLMEngine] = None) -> None:
        self.engine: BaseLLMEngine = engine or OpenAILLMEngine()
        self.graph = self._build_langgraph()

    def _build_langgraph(self):
        """Construct and compile the LangGraph StateGraph for Pipeline V2.2."""
        builder = StateGraph(GraphTurnState)

        builder.add_node("step2b_reflective_judge", self._node_step2b_judge)
        builder.add_node("phase3_convergence_router", self._node_phase3_router)
        builder.add_node("step2a_question_generator", self._node_step2a_generator)
        builder.add_node("build_start_response", self._node_build_start_response)
        builder.add_node("build_respond_response", self._node_build_respond_response)

        builder.add_conditional_edges(
            START,
            self._route_from_start,
            {
                "step2a_question_generator": "step2a_question_generator",
                "build_start_response": "build_start_response",
                "step2b_reflective_judge": "step2b_reflective_judge",
            },
        )

        # Strictly Step 2B (Judge) -> Phase 3 (Convergence Router)
        builder.add_edge("step2b_reflective_judge", "phase3_convergence_router")

        # Strictly Phase 3 (Router) -> Step 2A (Next Question) OR Finalize if terminated
        builder.add_conditional_edges(
            "phase3_convergence_router",
            self._route_after_phase3,
            {
                "step2a_question_generator": "step2a_question_generator",
                "build_respond_response": "build_respond_response",
            },
        )

        builder.add_conditional_edges(
            "step2a_question_generator",
            self._route_after_step2a,
            {
                "build_start_response": "build_start_response",
                "build_respond_response": "build_respond_response",
            },
        )

        builder.add_edge("build_start_response", END)
        builder.add_edge("build_respond_response", END)

        return builder.compile()

    # -----------------------------------------------------------------------
    # LangGraph Conditional Edge Routers
    # -----------------------------------------------------------------------

    @staticmethod
    def _route_from_start(state: GraphTurnState) -> str:
        session = state["session"]
        if state.get("mode") == "START":
            if session.is_finished or session.active_skill_id is None:
                return "build_start_response"
            return "step2a_question_generator"
        return "step2b_reflective_judge"

    @staticmethod
    def _route_after_phase3(state: GraphTurnState) -> str:
        session = state["session"]
        if session.is_finished or session.active_skill_id is None:
            return "build_respond_response"
        return "step2a_question_generator"

    @staticmethod
    def _route_after_step2a(state: GraphTurnState) -> str:
        if state.get("mode") == "START":
            return "build_start_response"
        return "build_respond_response"

    # -----------------------------------------------------------------------
    # Slot Management Helpers
    # -----------------------------------------------------------------------

    @staticmethod
    def _fill_active_slot(
        skill: SkillBeliefState,
        target_slot_id: str,
        extracted_val: Optional[str],
    ) -> None:
        """Fill the targeted primary slot or active probing sub-slot with extracted evidence."""
        if not extracted_val:
            return
        if target_slot_id == f"{skill.jd_skill_id}:primary" or skill.local_turn_k == 1:
            skill.primary_slot_value = extracted_val
            return

        for sub_slot in skill.active_sub_slots:
            if sub_slot.slot_id == target_slot_id:
                sub_slot.value = extracted_val
                sub_slot.filled = True
                return

        for sub_slot in reversed(skill.active_sub_slots):
            if not sub_slot.filled:
                sub_slot.value = extracted_val
                sub_slot.filled = True
                return

    @staticmethod
    def _register_target_slot(
        skill: SkillBeliefState,
        next_k: int,
        q_out: Step2AQuestionOutput,
    ) -> str:
        """Register dynamic probing sub-slot (capped at MAX_SUB_SLOTS) and return target_slot_id."""
        if next_k == 1:
            return f"{skill.jd_skill_id}:primary"

        if q_out.new_sub_slot is not None and len(skill.active_sub_slots) < MAX_SUB_SLOTS:
            sub_idx = len(skill.active_sub_slots) + 1
            slot_id = f"{skill.jd_skill_id}:sub_{sub_idx}"
            skill.active_sub_slots.append(
                SubSlot(
                    slot_id=slot_id,
                    slot_name=q_out.new_sub_slot.slot_name,
                    description=q_out.new_sub_slot.description,
                    value=None,
                    filled=False,
                )
            )
            return slot_id

        unfilled = [s for s in skill.active_sub_slots if not s.filled]
        if unfilled:
            return unfilled[-1].slot_id
        return q_out.target_slot_id

    # -----------------------------------------------------------------------
    # LangGraph Nodes
    # -----------------------------------------------------------------------

    def _node_step2b_judge(self, state: GraphTurnState) -> GraphTurnState:
        """
        Node Step 2B: Reflective Two-Step Metamorphic PBA Judge & Simplex Convex Interpolation.
        """
        session = state["session"]
        candidate_response = state.get("candidate_response") or ""

        if session.is_finished or session.pending_turn_log is None or session.active_skill_id is None:
            raise ValueError(
                f"Session '{session.session_id}' is already finished or has no pending question."
            )

        pending_log = session.pending_turn_log
        evaluated_turn = pending_log.turn
        evaluated_skill_id = pending_log.skill_id
        skill = session.skills[evaluated_skill_id]
        prev_belief = list(skill.current_belief)

        judge_out = self.engine.evaluate_response(
            skill=skill,
            question=pending_log.question,
            target_slot_id=pending_log.target_slot_id,
            candidate_response=candidate_response,
        )

        # Step 2B.1: Fill active primary slot or probing sub-slot
        extracted_val = judge_out.extracted_slot_value
        self._fill_active_slot(skill, pending_log.target_slot_id, extracted_val)

        # Step 2B.3: Simplex Convex Interpolation (Calibrated PBA Update)
        raw_norm = normalize_simplex(judge_out.raw_posterior_probs)
        p_updated, tv_raw, alpha_t, tv_delta = simplex_convex_update_detailed(
            p_prev=prev_belief,
            p_raw=raw_norm,
            tag=judge_out.metamorphic_tag,
        )

        skill.current_belief = list(p_updated)
        skill.belief_trajectory.append(list(p_updated))

        pending_log.candidate_response = candidate_response
        pending_log.extracted_slot_value = extracted_val
        pending_log.reflective_insight = judge_out.reflective_insight
        pending_log.metamorphic_tag = judge_out.metamorphic_tag
        pending_log.raw_posterior_belief = [round(p, 4) for p in raw_norm]
        pending_log.updated_belief = [round(p, 4) for p in p_updated]
        pending_log.tv_raw = round(tv_raw, 4)
        pending_log.alpha_t = round(alpha_t, 4)
        pending_log.tv_delta = round(tv_delta, 4)

        return {
            "session": session,
            "evaluated_turn": evaluated_turn,
            "evaluated_skill_id": evaluated_skill_id,
            "previous_belief": prev_belief,
            "updated_belief": p_updated,
            "tv_delta": tv_delta,
            "metamorphic_tag": judge_out.metamorphic_tag,
            "reflective_insight": judge_out.reflective_insight,
            "consolidated_summary": judge_out.consolidated_summary,
        }

    def _node_phase3_router(self, state: GraphTurnState) -> GraphTurnState:
        """
        Node Phase 3: Dual-Anchor Convergence Router, 1-Line Memory Consolidation,
        Sub-slot Garbage Collection, and Global Termination Check.
        """
        session = state["session"]
        evaluated_skill_id = state["evaluated_skill_id"]
        assert evaluated_skill_id is not None
        skill = session.skills[evaluated_skill_id]
        tag = state["metamorphic_tag"]
        assert tag is not None
        p_updated = state["updated_belief"]
        tv_delta = state["tv_delta"]

        skill_verified, verification_reason = check_local_skill_completion(
            local_turn_k=skill.local_turn_k,
            tag=tag,
            p_t=p_updated,
            tv_delta=tv_delta,
            active_sub_slots=skill.active_sub_slots,
        )

        if session.pending_turn_log is not None:
            session.pending_turn_log.skill_verified_after_turn = skill_verified
            session.pending_turn_log.verification_reason = verification_reason
            session.turn_history.append(session.pending_turn_log)
            session.pending_turn_log = None

        if skill_verified:
            consolidate_and_garbage_collect(
                session=session,
                skill=skill,
                consolidated_summary=state.get("consolidated_summary"),
                verification_reason=verification_reason,
            )

        check_global_termination(session)

        return {
            "session": session,
            "skill_verified": skill_verified,
            "verification_reason": verification_reason,
            "next_question": None,
        }

    def _node_step2a_generator(self, state: GraphTurnState) -> GraphTurnState:
        """
        Node Step 2A: Abductive CoT (C -> A) & 3-Layer Adaptive Question Generator.
        """
        session = state["session"]
        assert session.active_skill_id is not None
        skill = session.skills[session.active_skill_id]

        next_k = skill.local_turn_k + 1
        q_out = self.engine.generate_question(
            skill=skill,
            context_anchors=session.context_anchors,
            turn_history=session.turn_history,
            next_local_turn_k=next_k,
        )

        target_slot_id = self._register_target_slot(skill, next_k, q_out)
        session.turn_t += 1
        skill.local_turn_k = next_k

        pending_log = TurnLog(
            turn=session.turn_t,
            local_turn=skill.local_turn_k,
            skill_id=skill.jd_skill_id,
            target_slot_id=target_slot_id,
            abductive_reasoning=AbductiveReasoning(
                surprising_fact_C=q_out.surprising_fact_C,
                hypothesis_A=q_out.hypothesis_A,
            ),
            question=q_out.question,
            previous_belief=list(skill.current_belief),
        )
        session.pending_turn_log = pending_log

        return {
            "session": session,
            "next_question": q_out.question,
        }

    @staticmethod
    def _node_build_start_response(state: GraphTurnState) -> GraphTurnState:
        session = state["session"]
        if session.is_finished or session.pending_turn_log is None or session.active_skill_id is None:
            resp = StartInterviewResponse(
                session_id=session.session_id,
                turn=0,
                active_skill_id=None,
                initial_belief=[],
                abductive_reasoning=None,
                question=None,
                is_finished=True,
            )
        else:
            active_skill = session.skills[session.active_skill_id]
            pending = session.pending_turn_log
            resp = StartInterviewResponse(
                session_id=session.session_id,
                turn=pending.turn,
                active_skill_id=active_skill.jd_skill_id,
                initial_belief=[round(p, 4) for p in active_skill.prior_belief],
                abductive_reasoning=pending.abductive_reasoning,
                question=pending.question,
                is_finished=False,
            )
        return {"start_response": resp}

    @staticmethod
    def _node_build_respond_response(state: GraphTurnState) -> GraphTurnState:
        session = state["session"]
        completion_rate = compute_completion_rate(session)
        resp = RespondInterviewResponse(
            session_id=session.session_id,
            turn=state["evaluated_turn"],
            evaluated_skill_id=state["evaluated_skill_id"] or "",
            previous_belief=[round(p, 4) for p in state["previous_belief"]],
            updated_belief=[round(p, 4) for p in state["updated_belief"]],
            tv_delta=round(state["tv_delta"], 4),
            metamorphic_tag=state["metamorphic_tag"] or MetamorphicTag.INVARIANT,
            reflective_insight=state.get("reflective_insight") or "",
            skill_verified=bool(state.get("skill_verified", False)),
            active_skill_id=session.active_skill_id,
            next_question=state.get("next_question"),
            completion_rate=completion_rate,
            is_finished=session.is_finished,
        )
        return {"respond_response": resp}

    # -----------------------------------------------------------------------
    # Public Service Entrypoints
    # -----------------------------------------------------------------------

    def start_session(
        self,
        skills_input: Sequence[SkillGapInput],
        session_id: Optional[str] = None,
        t_max: int = T_MAX,
    ) -> Tuple[InterviewSessionState, StartInterviewResponse]:
        """
        Phase 1 initialization + Cold-start Step 2A via compiled LangGraph StateGraph.
        """
        session = initialize_session_state(
            skills_input=skills_input,
            session_id=session_id,
            t_max=t_max,
        )
        final_state = self.graph.invoke(
            {
                "mode": "START",
                "session": session,
            }
        )
        return final_state["session"], final_state["start_response"]

    def process_candidate_response(
        self,
        session: InterviewSessionState,
        candidate_response: str,
    ) -> RespondInterviewResponse:
        """
        Execute Step 2B -> Phase 3 Router -> Step 2A via compiled LangGraph StateGraph.
        """
        final_state = self.graph.invoke(
            {
                "mode": "RESPOND",
                "session": session,
                "candidate_response": candidate_response,
            }
        )
        return final_state["respond_response"]

    def build_report(self, session: InterviewSessionState) -> HITLReportResponse:
        """Phase 4: Generate Auditable HITL Report."""
        return generate_hitl_report(session)
