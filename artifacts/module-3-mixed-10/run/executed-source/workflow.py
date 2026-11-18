"""Copy-on-write transitions. Backend commits snapshots with compare-and-swap."""
from datetime import datetime, timedelta, timezone
from uuid import uuid4
from collections import Counter
import logging
from pydantic import ValidationError

from .assessment import TERMINAL, apply_judgment, eligible_criteria, next_action, standalone_inability, validate_judgment
from .errors import JudgmentUnavailableError, ProviderUnavailableError, QuestionUnavailableError
from .models import (
    Action, ConversationRequest, InterviewSkillContext, Judgment, ObjectiveState,
    Question, Snapshot, StartRequest, StoredQuestion, TransitionRequest, TransitionResult, Turn,
)
from . import lifecycle
from .planning import BlueprintBuilder, plan, select_mode
from .depth import DEPTH_DEFINITIONS, question_depth
from .policy_config import InterviewPolicy
from .criterion_progress import CRITERION_SOFT_LIMIT, progress_for
from .conversation import turn_introduction
from .question_validation import question_errors
from .provider import AssessmentProvider, encode_context
from .reporting import public_session
from .preparation_cache import PreparationCache
from .telemetry import event

logger = logging.getLogger(__name__)

GENERATION_ATTEMPTS = 2
JUDGMENT_ATTEMPTS = 2

ALIGNMENT_REPAIRS = {
    "WRONG_SKILL": "Ask the candidate to perform the behavior in the selected criterion. Remove the substitute task.",
    "INSUFFICIENT_EVIDENCE": "Ask for the observable evidence specified by the criterion or the current probe. Leave it for the candidate to supply.",
    "WRONG_DEPTH": "Match the requested depth: select a direct prerequisite for a diagnostic or the relevant anchor for a target or extension.",
    "UNANSWERABLE": "Supply the missing inputs and request one deliverable possible in this interaction mode.",
}

_PROMPT_EXCLUDED_OBJECTIVE_FIELDS = {
    "requirement_id", "objective_id", "depth_basis", "depth_rationale",
    "depth_evidence_spans", "requirement_kind", "jd_evidence_spans",
    "suitable_modes", "estimated_seconds",
}


class EvidenceWorkflow:
    def __init__(self, provider: AssessmentProvider, clock=None, policy: InterviewPolicy | None = None,
                 preparation_cache: PreparationCache | None = None):
        self.provider = provider
        self.clock = clock or (lambda: datetime.now(timezone.utc))
        self.policy = policy or InterviewPolicy()
        self.preparation_cache = preparation_cache

    def start(self, request: StartRequest) -> TransitionResult:
        policy = self.policy
        event("preparation.started", skills=len(request.skills), reuse_blueprint=request.blueprint is not None)
        builder = BlueprintBuilder(self.provider, policy, self.preparation_cache)
        blueprint = (builder.validate(request.blueprint.model_copy(deep=True), request.skills)
                     if request.blueprint is not None else builder.build(request.skills))
        objectives, queue = plan(blueprint, request.skills, request.config, policy)
        event("preparation.planned", objectives=len(objectives), queued=len(queue))
        now = self.clock()
        skills = [InterviewSkillContext(jd_skill_id=skill.jd_skill_id, cv_evidence_spans=skill.cv_evidence_spans)
                  for skill in request.skills]
        snapshot = Snapshot(session_id=request.session_id, config=request.config,
                            skills=skills, objectives=objectives, queue=queue, policy=policy.model_copy(deep=True),
                            deadline_at=now + timedelta(seconds=request.config.duration_seconds))
        if request.opening is not None:
            snapshot.opening_context = request.opening.model_copy(deep=True)
            opening_text = self._generate_opening(request)
            snapshot.conversation = lifecycle.begin(request.opening, now, text=opening_text)
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
            conversation.introduction = ""
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
            snapshot.pending_turn.introduction = (lifecycle.INTRODUCTION_BRIDGE if conversation.introduction
                                                   else lifecycle.SKIP_BRIDGE)

    def respond(self, request: TransitionRequest) -> TransitionResult:
        snapshot = request.snapshot.model_copy(deep=True)
        self._check_request(snapshot, request)
        if self.clock() >= snapshot.deadline_at:
            return self._result(self._finish(snapshot, "TIME_BUDGET"))
        turn = snapshot.pending_turn
        assert turn is not None
        state = snapshot.objectives[turn.objective_id]
        turn.answer = request.candidate_response
        turn.judgment = self._judge(snapshot, turn)
        apply_judgment(state, turn, snapshot.policy)
        snapshot.turns.append(turn)
        snapshot.pending_turn = None
        self._advance(snapshot, turn)
        return self._result(snapshot)

    def _judge(self, snapshot: Snapshot, turn: Turn) -> Judgment:
        admission = standalone_inability(turn)
        if admission is not None:
            return admission
        state = snapshot.objectives[turn.objective_id]
        ids = turn.question.criterion_ids
        objective = self._prompt_objective(state, ids)
        context = {
            "interaction_mode": snapshot.config.interaction_mode,
            "objective": objective, "turn": turn,
            "answer_lines": [{"line": index, "text": text} for index, text in
                             enumerate((turn.answer or "").splitlines(), start=1)],
            "depth_definitions": DEPTH_DEFINITIONS,
            "prior_observations": [item for item in state.evidence_history if item.criterion_id in ids],
            "prior_turns": [
                {
                    "action": t.action,
                    "question_depth": t.question_depth,
                    "question": t.question.text,
                    "evidence_scope": t.question.evidence_scope,
                    "answer": t.answer,
                }
                for t in snapshot.turns
                if t.objective_id == turn.objective_id and set(ids).intersection(t.question.criterion_ids)
            ],
        }
        last_error = None
        for attempt in range(JUDGMENT_ATTEMPTS):
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
                               turn.turn_id, attempt + 1, JUDGMENT_ATTEMPTS, feedback)
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
                or state.turns_spent >= CRITERION_SOFT_LIMIT and min(other_turns) < state.turns_spent)

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
        context = self._question_context(snapshot, action)
        question = self._generate_valid_question(context, snapshot)
        if question is None or self.clock() >= snapshot.deadline_at:
            self._finish(snapshot, "TIME_BUDGET")
            return
        assert question.depth is not None
        snapshot.pending_turn = Turn(
            turn_id=str(uuid4()), objective_id=state.objective.objective_id,
            skill_id=state.objective.skill_id, mode=state.selected_mode,
            action=action, question_depth=question.depth,
            question=StoredQuestion(
                text=question.text, criterion_ids=question.criterion_ids, evidence_scope=question.evidence_scope,
            ),
        )
        snapshot.pending_turn.introduction = turn_introduction(snapshot, snapshot.pending_turn)
        event("question.ready", turn_id=snapshot.pending_turn.turn_id, mode=state.selected_mode.value)

    def _question_context(self, snapshot: Snapshot, action: Action) -> dict[str, object]:
        state = snapshot.objectives[snapshot.queue[0]]
        skill = next(s for s in snapshot.skills if s.jd_skill_id == state.objective.skill_id)
        targets = self._targets(state)
        if not targets:
            raise ValueError("No independent criteria available for question generation")
        objective = self._prompt_objective(state, targets)
        # Keep the full probing chain, including older turns after yielding to
        # another objective. Criterion IDs alone are not a cross-objective key.
        history = [turn for turn in snapshot.turns
                   if turn.objective_id == state.objective.objective_id
                   and set(turn.question.criterion_ids).intersection(targets)]
        relevant_ids = {turn.turn_id for turn in history}
        # Other criteria within this objective are only a compact repetition
        # guard. Turns from other objectives never enter the question context.
        other_questions = [
            {"question": turn.question.text[:300], "truncated": len(turn.question.text) > 300}
            for turn in snapshot.turns
            if turn.objective_id == state.objective.objective_id and turn.turn_id not in relevant_ids
        ]
        contract = {"mode": state.selected_mode, "depth": question_depth(state, action), "criterion_ids": targets}
        if action == Action.CLARIFY and history:
            previous = history[-1]
            contract["evidence_scope"] = previous.question.evidence_scope
            contract["depth"] = previous.question_depth
        context = {"objective": objective, "required_question_contract": contract,
                   "question_guidance": "Give all necessary inputs or sample output inline. Ask for one decision "
                                        "or task the candidate can complete here without opening another tool.",
                   "interaction_mode": snapshot.config.interaction_mode,
                   "action": action,
                   "depth_definitions": DEPTH_DEFINITIONS, "probe_reason": state.probe_reason,
                   "criterion_progress": progress_for(state, targets[0]),
                   "cv_evidence": skill.cv_evidence_spans,
                   "history": history, "other_questions": other_questions,
                   "prior_observations": [item for item in state.evidence_history if item.criterion_id in targets]}
        if action == Action.EASIER:
            context["question_guidance"] += (" Ask about one prerequisite using a small concrete example. "
                                             "Do not ask why the candidate could not answer.")
        return context

    def _generate_valid_question(self, context: dict[str, object], snapshot: Snapshot) -> Question | None:
        seen = {" ".join(turn.question.text.casefold().split()) for turn in snapshot.turns}
        for attempt in range(GENERATION_ATTEMPTS):
            if self.clock() >= snapshot.deadline_at:
                return None
            question, errors = self._question_attempt(context, seen)
            if not errors:
                if self.clock() >= snapshot.deadline_at:
                    return None
                verdict = self.provider.review_question(self._review_context(context, question))
                if verdict == "ALIGNED":
                    return question
                context["rejected_draft"] = question.text
                errors = [ALIGNMENT_REPAIRS[verdict]]
            context["validation_error"] = "; ".join(errors)
            logger.warning("Invalid question for session %s (attempt %s/%s): %s", snapshot.session_id,
                           attempt + 1, GENERATION_ATTEMPTS, context["validation_error"])
        raise QuestionUnavailableError("AI chưa tạo được câu hỏi phù hợp. Dữ liệu đã lưu được giữ nguyên; vui lòng thử lại.")

    @staticmethod
    def _review_context(context, question: Question) -> str:
        objective = context["objective"]
        contract = context["required_question_contract"]
        history = context["history"]
        return encode_context({
            "question": question.text, "criterion": objective["criteria"][0],
            "action": context["action"], "question_depth": contract["depth"],
            "target_depth": objective["target_depth"], "depth_definitions": DEPTH_DEFINITIONS,
            "mode": contract["mode"], "interaction_mode": context["interaction_mode"],
            "probe_reason": context["probe_reason"], "unresolved": context["criterion_progress"].unresolved_aspects,
            "history": [{"question": t.question.text, "answer": t.answer} for t in history],
        })

    def _question_attempt(self, context: dict[str, object], seen: set[str]) -> tuple[Question | None, list[str]]:
        try:
            question = self.provider.question(encode_context(context))
        except ValidationError as exc:
            errors = [f"Invalid Question schema at {item['loc']}: {item['type']}"
                      for item in exc.errors(include_input=False, include_url=False)]
            return None, errors
        errors = question_errors(question, context)
        if " ".join(question.text.casefold().split()) in seen:
            errors.append("The question repeats a prior turn; use a new focused question instead")
        return question, errors

    @staticmethod
    def _prompt_objective(state: ObjectiveState, target_ids: list[str]) -> dict[str, object]:
        objective = state.objective.model_dump(mode="json", exclude=_PROMPT_EXCLUDED_OBJECTIVE_FIELDS)
        objective["criteria"] = [c.model_dump(mode="json") for c in state.objective.criteria if c.criterion_id in target_ids]
        return objective

    @staticmethod
    def _targets(state: ObjectiveState) -> list[str]:
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
                mode = select_mode(state.objective, snapshot.config, usage)
                if mode not in modes:
                    continue
                state.selected_mode = mode
                state.excluded_reason, state.lifecycle = None, "PLANNED"
                snapshot.queue.append(state.objective.objective_id)
                break

    def _finish(self, snapshot: Snapshot, reason: str) -> Snapshot:
        snapshot.is_finished, snapshot.termination_reason = True, reason
        for key in snapshot.queue:
            state = snapshot.objectives[key]
            state.lifecycle, state.stop_reason = "CLOSED", reason
        snapshot.queue.clear()
        had_pending = snapshot.pending_turn is not None
        snapshot.pending_turn = None
        closing_text = self._generate_closing(snapshot, reason, had_pending)
        lifecycle.close(snapshot, reason, self.clock(), text=closing_text)
        return snapshot

    def _generate_opening(self, request: StartRequest) -> str | None:
        return self._generate_dialogue(
            "opening_greeting", "opening", lambda: lifecycle.opening_context(request), request.config.interaction_mode
        )

    def _generate_closing(self, snapshot: Snapshot, reason: str, had_pending: bool) -> str | None:
        if snapshot.conversation is None:
            return None
        return self._generate_dialogue(
            "closing_farewell",
            "closing",
            lambda: lifecycle.closing_context(snapshot, reason, had_pending),
            snapshot.config.interaction_mode,
        )

    def _generate_dialogue(self, method_name: str, stage: str, build_context, interaction_mode: str) -> str | None:
        generator = getattr(self.provider, method_name, None)
        if not callable(generator):
            return None
        try:
            generated = generator(encode_context(build_context()))
            raw_text = generated.text if hasattr(generated, "text") else str(generated)
            return lifecycle.clean_dialogue_text(raw_text, interaction_mode)
        except Exception as exc:
            logger.warning("Falling back to template for %s (%s): %s", stage, type(exc).__name__, exc)
            event("dialogue.fallback", stage=stage, error_type=type(exc).__name__)
            return None

    @staticmethod
    def _result(snapshot: Snapshot) -> TransitionResult:
        snapshot.state_version += 1
        return TransitionResult(snapshot=snapshot, public=public_session(snapshot))
