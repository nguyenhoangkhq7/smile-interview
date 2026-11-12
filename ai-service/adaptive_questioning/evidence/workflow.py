"""Copy-on-write transitions. Backend commits snapshots with compare-and-swap."""
from datetime import datetime, timedelta, timezone
from uuid import uuid4
from collections import Counter
import logging
from pydantic import ValidationError

from .assessment import TERMINAL, apply_judgment, eligible_criteria, next_action, validate_judgment
from .errors import JudgmentUnavailableError, QuestionUnavailableError
from .models import Action, ConversationRequest, Judgment, ObjectiveState, Question, Snapshot, StartRequest, TransitionRequest, TransitionResult, Turn
from . import lifecycle
from .planning import BlueprintBuilder, plan, select_mode
from .depth import DEPTH_DEFINITIONS, question_depth
from .policy_config import InterviewPolicy
from .criterion_progress import progress_for, restore_progress
from .conversation import turn_introduction
from .question_validation import question_errors
from .provider import AssessmentProvider, encode_context
from .reporting import public_session
from .preparation_cache import PreparationCache
from .telemetry import event

logger = logging.getLogger(__name__)


class EvidenceWorkflow:
    def __init__(self, provider: AssessmentProvider, clock=None, policy: InterviewPolicy | None = None,
                 preparation_cache: PreparationCache | None = None):
        self.provider = provider
        self.clock = clock or (lambda: datetime.now(timezone.utc))
        self.policy = policy or InterviewPolicy()
        self.preparation_cache = preparation_cache

    def start(self, request: StartRequest) -> TransitionResult:
        policy = request.policy or self.policy
        event("preparation.started", skills=len(request.skills), reuse_blueprint=request.blueprint is not None)
        builder = BlueprintBuilder(self.provider, policy, self.preparation_cache)
        blueprint = (builder.validate(request.blueprint.model_copy(deep=True), request.skills)
                     if request.blueprint is not None else builder.build(request.skills))
        objectives, queue = plan(blueprint, request.skills, request.config, policy)
        event("preparation.planned", objectives=len(objectives), queued=len(queue))
        now = self.clock()
        snapshot = Snapshot(session_id=request.session_id, config=request.config,
                            skills=request.skills, objectives=objectives, queue=queue, policy=policy.model_copy(deep=True),
                            started_at=now, deadline_at=now + timedelta(seconds=request.config.duration_seconds))
        if request.opening is not None:
            snapshot.conversation = lifecycle.begin(request.opening, now)
            event("preparation.ready", phase="OPENING")
        else:
            self._ask(snapshot, Action.INITIAL)
        return self._result(snapshot)

    def converse(self, request: ConversationRequest) -> TransitionResult:
        snapshot = request.snapshot.model_copy(deep=True)
        conversation = snapshot.conversation
        if (conversation is None or snapshot.state_version != request.expected_state_version
                or conversation.message.message_id != request.message_id):
            raise ValueError("Stale conversation identifier or version")
        if conversation.phase == "CLOSING" and request.action == "NEXT":
            conversation.phase = "FINISHED"
        elif conversation.phase == "OPENING" and request.action == "NEXT":
            conversation.phase = "SELF_INTRODUCTION"
            conversation.expires_at = self.clock() + timedelta(seconds=lifecycle.INTRODUCTION_SECONDS)
        elif conversation.phase in {"OPENING", "SELF_INTRODUCTION"} and request.action == "SKIP_INTRODUCTION":
            conversation.introduction_skipped = True
            self._begin_technical(snapshot)
        elif conversation.phase == "SELF_INTRODUCTION" and request.action == "SUBMIT_INTRODUCTION":
            if not request.introduction.strip():
                raise ValueError("Introduction must not be blank")
            conversation.introduction = request.introduction.strip()
            self._begin_technical(snapshot)
        else:
            raise ValueError("Action is not allowed in this conversation phase")
        return self._result(snapshot)

    def _begin_technical(self, snapshot: Snapshot) -> None:
        conversation = snapshot.conversation
        assert conversation is not None
        conversation.phase = "INTERVIEW"
        snapshot.deadline_at = self.clock() + timedelta(seconds=snapshot.config.duration_seconds)
        self._ask(snapshot, Action.INITIAL)
        if snapshot.pending_turn:
            snapshot.pending_turn.introduction = (lifecycle.SKIP_BRIDGE if conversation.introduction_skipped
                                                   else lifecycle.INTRODUCTION_BRIDGE)

    def respond(self, request: TransitionRequest) -> TransitionResult:
        snapshot = request.snapshot.model_copy(deep=True)
        self._check_request(snapshot, request)
        if self.clock() >= snapshot.deadline_at:
            return self._result(self._finish(snapshot, "TIME_BUDGET"))
        turn = snapshot.pending_turn
        assert turn is not None
        state = snapshot.objectives[turn.objective_id]
        self._retain_legacy_evidence(state)
        restore_progress(state, snapshot.turns, snapshot.policy)
        turn.answer = request.candidate_response
        turn.judgment = self._judge(snapshot, turn)
        apply_judgment(state, turn, snapshot.policy)
        snapshot.turns.append(turn)
        snapshot.pending_turn = None
        self._advance(snapshot, turn)
        return self._result(snapshot)

    def _judge(self, snapshot: Snapshot, turn: Turn) -> Judgment:
        state = snapshot.objectives[turn.objective_id]
        ids = turn.question.criterion_ids
        targets = [criterion for criterion in state.objective.criteria if criterion.criterion_id in ids]
        objective = state.objective.model_dump(
            mode="json",
            exclude={"suitable_modes", "estimated_seconds", "rubric_version", "depth_evidence_spans", "jd_evidence_spans"}
        )
        objective["criteria"] = [criterion.model_dump(mode="json") for criterion in targets]
        context = {
            "interaction_mode": snapshot.config.interaction_mode,
            "objective": objective, "turn": turn,
            "answer_lines": [{"line": index, "text": text} for index, text in
                             enumerate((turn.answer or "").splitlines(), start=1)],
            "required_criterion_ids": ids, "target_criteria": targets,
            "depth_definitions": DEPTH_DEFINITIONS,
            "prior_observations": [item for item in state.evidence_history if item.criterion_id in ids],
            "prior_turns": [t for t in snapshot.turns if t.objective_id == turn.objective_id],
        }
        last_error = None
        for attempt in range(snapshot.policy.judgment_attempts):
            if attempt and self.clock() >= snapshot.deadline_at:
                break
            judgment = None
            try:
                judgment = self.provider.judge(encode_context(context))
                validate_judgment(judgment, turn)
                return judgment
            except (ValidationError, ValueError) as exc:
                last_error = exc
                feedback = str(exc.errors(include_input=False, include_url=False)) if isinstance(exc, ValidationError) else str(exc)
                context["validation_error"] = feedback
                if judgment is not None:
                    context["previous_invalid_judgment"] = judgment.model_dump(mode="json")
                logger.warning("Invalid judge output for turn %s (attempt %s/%s): %s",
                               turn.turn_id, attempt + 1, snapshot.policy.judgment_attempts, feedback)
        raise JudgmentUnavailableError(
            "AI chưa thể chấm câu trả lời một cách hợp lệ. Câu trả lời chưa bị chấm điểm; vui lòng thử gửi lại."
        ) from last_error

    def stop(self, snapshot: Snapshot) -> TransitionResult:
        updated = snapshot.model_copy(deep=True)
        if not updated.is_finished:
            technical = updated.conversation is None or updated.conversation.phase == "INTERVIEW"
            self._finish(updated, "TIME_BUDGET" if technical and self.clock() >= updated.deadline_at else "USER_STOP")
        return self._result(updated)

    @staticmethod
    def _check_request(snapshot: Snapshot, request: TransitionRequest) -> None:
        if snapshot.conversation and snapshot.conversation.phase != "INTERVIEW":
            raise ValueError("Interview is not accepting technical answers")
        if snapshot.is_finished or snapshot.pending_turn is None:
            raise ValueError("Interview has no pending question")
        if snapshot.state_version != request.expected_state_version:
            raise ValueError("Stale state version")
        if snapshot.pending_turn.turn_id != request.turn_id:
            raise ValueError("Stale turn identifier")
        if not request.candidate_response.strip():
            raise ValueError("Answer must not be blank")

    def _advance(self, snapshot: Snapshot, turn: Turn) -> None:
        if len(snapshot.turns) >= snapshot.config.max_questions:
            self._finish(snapshot, "QUESTION_BUDGET")
            return
        if self.clock() >= snapshot.deadline_at:
            self._finish(snapshot, "TIME_BUDGET")
            return
        state = snapshot.objectives[turn.objective_id]
        capped = state.turns_spent >= snapshot.config.max_questions_per_objective
        # Budgets are checked before routing can request another model generation.
        action = None if capped else next_action(state, turn, snapshot.policy)
        sufficient = state.assessment in TERMINAL
        if action is None:
            reason = "LOCAL_BUDGET" if capped else self._criterion_stop_reason(state)
            state.lifecycle, state.stop_reason = "CLOSED", "SUFFICIENT_EVIDENCE" if sufficient else reason
            snapshot.queue.pop(0)
            action = Action.INITIAL
        elif self._should_yield(snapshot, state):
            state.lifecycle = "PLANNED"
            snapshot.queue.append(snapshot.queue.pop(0))
            snapshot.queue.sort(key=lambda key: snapshot.objectives[key].turns_spent)
            action = Action.INITIAL
        if not snapshot.queue:
            self._reallocate(snapshot)
        if snapshot.queue:
            selected = snapshot.objectives[snapshot.queue[0]]
            if action == Action.INITIAL and selected.turns_spent:
                previous = next(t for t in reversed(snapshot.turns) if t.objective_id == selected.objective.objective_id)
                action = next_action(selected, previous, snapshot.policy)
                if action is None:
                    raise ValueError("Paused objective has no remaining probe")
            self._ask(snapshot, action)
        else:
            self._finish(snapshot, "PLAN_COMPLETE")

    def _should_yield(self, snapshot: Snapshot, state: ObjectiveState) -> bool:
        if len(snapshot.queue) < 2:
            return False
        reserve = len(snapshot.queue) - 1
        available = snapshot.config.max_questions - len(snapshot.turns)
        reserved_seconds = sum(snapshot.objectives[key].objective.estimated_seconds for key in snapshot.queue[1:])
        time_remaining = (snapshot.deadline_at - self.clock()).total_seconds()
        other_turns = [snapshot.objectives[key].turns_spent for key in snapshot.queue[1:]]
        return (min(other_turns) == 0 and (available <= reserve or time_remaining <= reserved_seconds)
                or state.turns_spent >= snapshot.policy.criterion_soft_limit and min(other_turns) < state.turns_spent)

    @staticmethod
    def _criterion_stop_reason(state: ObjectiveState) -> str:
        reasons = {item.stop_reason for item in state.criterion_progress.values()}
        if "NO_PROGRESS" in reasons:
            return "NO_PROGRESS"
        if "CRITERION_BUDGET" in reasons:
            return "CRITERION_BUDGET"
        return "NO_INDEPENDENT_CRITERIA_IN_MODE"

    def _ask(self, snapshot: Snapshot, action: Action) -> None:
        event("question.started", action=action.value, answered=len(snapshot.turns))
        if self.clock() >= snapshot.deadline_at:
            self._finish(snapshot, "TIME_BUDGET")
            return
        if len(snapshot.turns) >= snapshot.config.max_questions:
            self._finish(snapshot, "QUESTION_BUDGET")
            return
        state = snapshot.objectives[snapshot.queue[0]]
        if state.turns_spent >= snapshot.config.max_questions_per_objective:
            raise ValueError("Cannot generate beyond the objective budget")
        state.lifecycle = "ACTIVE"
        state.current_question_depth = question_depth(state, action)
        criteria = self._targets(state, action, snapshot)
        if not criteria:
            raise ValueError("No independent criteria available for question generation")
        context = self._question_context(snapshot, action)
        question = self._generate_valid_question(context, snapshot, criteria)
        if question is None or self.clock() >= snapshot.deadline_at:
            self._finish(snapshot, "TIME_BUDGET")
            return
        snapshot.pending_turn = Turn(turn_id=str(uuid4()), objective_id=state.objective.objective_id,
                                     skill_id=state.objective.skill_id, mode=state.selected_mode,
                                     action=action,
                                     question_depth=state.current_question_depth, question=question)
        snapshot.pending_turn.introduction = turn_introduction(snapshot, snapshot.pending_turn)
        event("question.ready", turn_id=snapshot.pending_turn.turn_id, mode=state.selected_mode.value)

    def _question_context(self, snapshot: Snapshot, action: Action) -> dict[str, object]:
        state = snapshot.objectives[snapshot.queue[0]]
        skill = next(s for s in snapshot.skills if s.jd_skill_id == state.objective.skill_id)
        targets = self._targets(state, action, snapshot)
        objective = state.objective.model_dump(
            mode="json",
            exclude={"suitable_modes", "estimated_seconds", "rubric_version", "depth_evidence_spans", "jd_evidence_spans"}
        )
        objective["criteria"] = [c.model_dump(mode="json") for c in state.objective.criteria if c.criterion_id in targets]
        objective["extension_criterion_ids"] = [key for key in objective["extension_criterion_ids"] if key in targets]
        context = {"objective": objective, "mode": state.selected_mode,
                   "interaction_mode": snapshot.config.interaction_mode,
                   "action": action,
                   "question_depth": state.current_question_depth, "depth_definitions": DEPTH_DEFINITIONS,
                   "target_criteria": targets, "probe_reason": state.probe_reason,
                   "criterion_progress": progress_for(state, targets[0]),
                   "cv_evidence": skill.cv_evidence_spans, "strategy": skill.suggested_strategy,
                   "history": snapshot.turns, "remaining_questions": snapshot.config.max_questions - len(snapshot.turns)}
        if action == Action.CLARIFY and snapshot.turns:
            previous = next(t for t in reversed(snapshot.turns) if t.objective_id == state.objective.objective_id
                            and targets[0] in t.question.criterion_ids)
            context["required_evidence_scope"] = previous.question.evidence_scope
        return context

    def _generate_valid_question(self, context: dict[str, object], snapshot: Snapshot,
                                 criteria: list[str]) -> Question | None:
        seen = {" ".join(turn.question.text.casefold().split()) for turn in snapshot.turns}
        contract = {"mode": context["mode"], "depth": context["question_depth"], "criterion_ids": criteria}
        if "required_evidence_scope" in context:
            contract["evidence_scope"] = context["required_evidence_scope"]
        context["required_question_contract"] = contract
        for attempt in range(snapshot.policy.generation_attempts):
            if self.clock() >= snapshot.deadline_at:
                return None
            question, errors = self._question_attempt(context, criteria, seen)
            if not errors:
                return question
            context["validation_error"] = "; ".join(errors)
            logger.warning("Invalid question for session %s (attempt %s/%s): %s", snapshot.session_id,
                           attempt + 1, snapshot.policy.generation_attempts, context["validation_error"])
        raise QuestionUnavailableError("AI chưa tạo được câu hỏi phù hợp. Dữ liệu đã lưu được giữ nguyên; vui lòng thử lại.")

    def _question_attempt(self, context: dict[str, object], criteria: list[str], seen: set[str]) -> tuple[Question | None, list[str]]:
        try:
            question = self.provider.question(encode_context(context))
        except ValidationError as exc:
            errors = [f"Invalid Question schema at {item['loc']}: {item['type']}"
                      for item in exc.errors(include_input=False, include_url=False)]
            return None, errors
        errors = question_errors(question, context, criteria)
        if " ".join(question.text.casefold().split()) in seen:
            errors.append("The question repeats a prior turn; use a new focused question instead")
        return question, errors

    @staticmethod
    def _targets(state: ObjectiveState, action: Action, snapshot: Snapshot) -> list[str]:
        eligible = eligible_criteria(state)
        if state.active_criterion_id in eligible:
            return [state.active_criterion_id]
        essential = [c.criterion_id for c in state.objective.criteria if c.essential and c.criterion_id in eligible]
        candidates = essential or eligible
        if not candidates:
            return []
        state.active_criterion_id = candidates[0]
        return [candidates[0]]

    def _reallocate(self, snapshot: Snapshot) -> None:
        remaining = (snapshot.deadline_at - self.clock()).total_seconds()
        for state in snapshot.objectives.values():
            if state.excluded_reason == "PLAN_BUDGET" and state.objective.estimated_seconds <= remaining:
                modes = [item.mode for item in state.objective.suitable_modes]
                usage = Counter(t.mode for t in snapshot.turns)
                mode, reason = select_mode(state.objective, snapshot.config, snapshot.policy, usage)
                if mode not in modes:
                    continue
                state.selected_mode, state.mode_selection_reason = mode, reason
                state.excluded_reason, state.lifecycle = None, "PLANNED"
                snapshot.queue.append(state.objective.objective_id)
                break

    @staticmethod
    def _retain_legacy_evidence(state: ObjectiveState) -> None:
        legacy = [e for e in state.criterion_results.values() if e.question_depth is None]
        for evidence in legacy:
            if evidence not in state.evidence_history:
                state.evidence_history.append(evidence)
        for evidence in legacy:
            state.criterion_results.pop(evidence.criterion_id, None)

    def _finish(self, snapshot: Snapshot, reason: str) -> Snapshot:
        snapshot.is_finished, snapshot.termination_reason = True, reason
        for key in snapshot.queue:
            state = snapshot.objectives[key]
            state.lifecycle, state.stop_reason = "CLOSED", reason
        snapshot.queue.clear()
        snapshot.pending_turn = None
        lifecycle.close(snapshot, reason, self.clock())
        return snapshot

    @staticmethod
    def _result(snapshot: Snapshot) -> TransitionResult:
        snapshot.state_version += 1
        return TransitionResult(snapshot=snapshot, public=public_session(snapshot))
