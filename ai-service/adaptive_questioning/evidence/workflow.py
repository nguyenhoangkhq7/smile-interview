"""Copy-on-write transitions. Backend commits snapshots with compare-and-swap."""
from collections import Counter, OrderedDict
from concurrent.futures import Future, ThreadPoolExecutor
from contextvars import copy_context
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import logging
from threading import Lock
from time import monotonic
from uuid import uuid4

from pydantic import ValidationError

from .assessment import (TERMINAL, apply_judgment, criterion_action, criterion_resolved, eligible_criteria,
                         next_action, standalone_inability, validate_judgment)
from .coding_verification import check_coding_answer
from .errors import JudgmentUnavailableError, QuestionUnavailableError
from .models import (
    Action, Blueprint, BlueprintRequest, CodingCheckResult, ConversationRequest, InterviewConfig, InterviewSkillContext,
    InterviewVerification, Judgment, Mode,
    NextQuestionRequest, ObjectiveState, Question, SessionCoaching, Snapshot, StartRequest,
    StoredQuestion, TransitionRequest, TransitionResult, Turn,
)
from . import lifecycle
from .planning import ALL_COMPATIBLE_SKILLS_MASTERED, BlueprintBuilder, plan, plan_recheck, select_mode
from .depth import DEPTH_DEFINITIONS, question_depth
from .policy_config import InterviewPolicy
from .criterion_progress import CRITERION_SOFT_LIMIT, progress_for
from .conversation import turn_introduction
from .question_validation import first_question, question_errors, validate_question
from .provider import AlignmentReview, AssessmentProvider, encode_context
from .reporting import coaching_context, fallback_session_coaching, public_session
from .preparation_cache import PreparationCache
from .telemetry import event
from .verification import prepare_verification

logger = logging.getLogger(__name__)

GENERATION_ATTEMPTS = 3
DIAGNOSTIC_SOFT_REPAIR_LIMIT = 2
JUDGMENT_ATTEMPTS = 2
PREWARM_TTL_SECONDS = 600
PREWARM_MAX_ENTRIES = 64
MAX_CANDIDATE_BACKGROUND_CHARS = 400
MAX_PRIOR_STEM_CHARS = 200
_HARD_ALIGNMENT_VERDICTS = frozenset({"GIVES_SOLUTION", "UNANSWERABLE", "WRONG_SKILL"})
_DIAGNOSTIC_ACTIONS = frozenset({Action.EASIER, Action.CLARIFY})
_PENALTY_DIAGNOSTIC_SOFT_REVIEW = 1
_PENALTY_STANDARD_SOFT_REVIEW = 2
_PENALTY_SOFT_VALIDATION = 3

ALIGNMENT_REPAIRS = {
    "WRONG_SKILL": "Ask the candidate to perform the behavior in the selected criterion. Remove the substitute task.",
    "INSUFFICIENT_EVIDENCE": "Ask for the observable evidence specified by the criterion or the current probe. Leave it for the candidate to supply.",
    "WRONG_DEPTH": "Match the requested depth: select a direct prerequisite for a diagnostic or the relevant anchor for a target or extension.",
    "UNANSWERABLE": (
        "Supply any missing inputs, definitions, or expected behavior that change the answer. "
        "Ask for one answerable deliverable without revealing the solution."
    ),
    "MULTIPLE_TASKS": "Keep one work product for the selected criterion; remove the other deliverables.",
    "GIVES_SOLUTION": "Keep the problem inputs and constraints. Remove the method or answer the candidate must derive.",
}

_PROMPT_EXCLUDED_OBJECTIVE_FIELDS = {
    "requirement_id", "objective_id", "depth_basis", "depth_rationale",
    "depth_evidence_spans", "requirement_kind", "jd_evidence_spans",
    "suitable_modes", "estimated_seconds",
}


@dataclass(frozen=True)
class _PrewarmedQuestion:
    created: float
    config: InterviewConfig
    verification: InterviewVerification | None
    future: Future[Turn | None]


class EvidenceWorkflow:
    def __init__(
        self,
        provider: AssessmentProvider,
        clock=None,
        policy: InterviewPolicy | None = None,
        preparation_cache: PreparationCache | None = None,
        *,
        prewarm_q1: bool = False,
    ):
        self.provider = provider
        self.clock = clock or (lambda: datetime.now(timezone.utc))
        self.policy = policy or InterviewPolicy()
        self.preparation_cache = preparation_cache
        self.prewarm_q1 = prewarm_q1
        self._prewarm_lock = Lock()
        self._prewarm_executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="q1-prewarm")
        self._prewarmed_q1: OrderedDict[str, _PrewarmedQuestion] = OrderedDict()

    def build_blueprint(self, request: BlueprintRequest) -> Blueprint:
        builder = BlueprintBuilder(self.provider, self.policy, self.preparation_cache)
        return builder.build(request.skills, opening=request.opening)

    def start(self, request: StartRequest) -> TransitionResult:
        policy = self.policy
        event("preparation.started", skills=len(request.skills), reuse_blueprint=request.blueprint is not None)
        builder = BlueprintBuilder(self.provider, policy, self.preparation_cache)

        target = request.recheck_target
        if bool(target) != bool(request.config.recheck) or (target and
                (request.blueprint is None or request.config.max_questions > 3 or request.config.duration_seconds > 300)):
            raise ValueError("Cấu hình kiểm chứng không hợp lệ")
        opening_text: str | None = None
        has_mastered_skills = bool(request.prior_attempts and request.prior_attempts.mastered_skill_ids)
        parallel_opening = request.opening is not None and request.blueprint is None and not has_mastered_skills
        if parallel_opening:
            with ThreadPoolExecutor(max_workers=2) as executor:
                bp_future = executor.submit(copy_context().run, builder.build, request.skills, request.opening)
                open_future = executor.submit(copy_context().run, self._generate_opening, request)
                blueprint = bp_future.result()
                opening_text = open_future.result()
        else:
            blueprint = (
                builder.validate(request.blueprint.model_copy(deep=True), request.skills)
                if request.blueprint is not None
                else builder.build(request.skills, opening=request.opening)
            )

        if target:
            objectives, queue = plan_recheck(blueprint, target.objective_id, target.criterion_id)
        else:
            objectives, queue = plan(blueprint, request.skills, request.config, policy, request.prior_attempts)
        event("preparation.planned", objectives=len(objectives), queued=len(queue))
        if not target and queue and request.opening is not None and not parallel_opening:
            opening_text = self._generate_opening(request)
        ordered = [objectives[key] for key in queue]
        ordered.extend(state for state in objectives.values()
                       if state.excluded_reason == "PLAN_BUDGET"
                       and state.objective.estimated_seconds <= request.config.duration_seconds)
        verification = prepare_verification(request, ordered, self.provider)
        now = self.clock()
        skills = [
            InterviewSkillContext(
                jd_skill_id=skill.jd_skill_id,
                jd_skill_name=skill.jd_skill_name,
                matched_cv_skill_name=skill.matched_cv_skill_name,
                semantic_alignment=skill.semantic_alignment,
                context_job=skill.context_job,
                cv_evidence_spans=skill.cv_evidence_spans,
            )
            for skill in request.skills
        ]
        prior_stems = [
            stem.strip()[:MAX_PRIOR_STEM_CHARS]
            for stem in (request.prior_attempts.prior_question_stems if request.prior_attempts else [])
            if stem and stem.strip()
        ][:20]
        snapshot = Snapshot(
            session_id=request.session_id,
            config=request.config, recheck_target=target,
            skills=skills,
            objectives=objectives,
            queue=queue,
            verification=verification,
            policy=policy.model_copy(deep=True),
            deadline_at=now + timedelta(seconds=request.config.duration_seconds),
            prior_question_stems=prior_stems,
        )
        if not queue:
            return self._result(self._finish(snapshot, ALL_COMPATIBLE_SKILLS_MASTERED))
        if request.opening is not None and not target:
            snapshot.opening_context = request.opening.model_copy(deep=True)
            snapshot.conversation = lifecycle.begin(
                request.opening, now, text=opening_text, interaction_mode=request.config.interaction_mode,
            )
            if self.prewarm_q1:
                self._schedule_q1_prewarm(snapshot)
            event("preparation.ready", phase=snapshot.conversation.phase)
        else:
            self._ask(snapshot, Action.INITIAL)
        return self._result(snapshot)

    def _schedule_q1_prewarm(self, snapshot: Snapshot) -> None:
        if not snapshot.queue:
            return
        copy = snapshot.model_copy(deep=True)
        # Ensure prewarm has a generous deadline while the candidate reads/writes their intro.
        copy.deadline_at = self.clock() + timedelta(seconds=max(copy.config.duration_seconds, 300))

        def _compute() -> Turn | None:
            try:
                self._ask(copy, Action.INITIAL)
                return copy.pending_turn
            except Exception as exc:
                logger.warning("Q1 prewarm failed for session %s (%s): %s",
                               copy.session_id, type(exc).__name__, exc)
                return None

        future = self._prewarm_executor.submit(copy_context().run, _compute)
        now = monotonic()
        with self._prewarm_lock:
            self._prune_prewarm_locked(now)
            self._prewarmed_q1[snapshot.session_id] = _PrewarmedQuestion(now, copy.config, copy.verification, future)
            self._prewarmed_q1.move_to_end(snapshot.session_id)

    def _prune_prewarm_locked(self, now: float) -> None:
        expired = [key for key, entry in self._prewarmed_q1.items() if now - entry.created > PREWARM_TTL_SECONDS]
        for key in expired:
            self._prewarmed_q1.pop(key, None)
        while len(self._prewarmed_q1) >= PREWARM_MAX_ENTRIES:
            self._prewarmed_q1.popitem(last=False)

    def _consume_prewarmed_q1(self, snapshot: Snapshot) -> Turn | None:
        with self._prewarm_lock:
            entry = self._prewarmed_q1.pop(snapshot.session_id, None)
        if (entry is None or monotonic() - entry.created > PREWARM_TTL_SECONDS
                or entry.config != snapshot.config or entry.verification != snapshot.verification):
            return None
        try:
            turn = entry.future.result(timeout=45)
        except Exception:
            return None
        if turn is None or not snapshot.queue:
            return None
        state = snapshot.objectives.get(snapshot.queue[0])
        if (state is None
                or turn.objective_id != state.objective.objective_id
                or turn.mode != state.selected_mode
                or turn.question_depth != question_depth(state, Action.INITIAL)
                or turn.question.criterion_ids != self._targets(state.model_copy(deep=True))):
            return None
        return turn.model_copy(deep=True)

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
        if not request.defer_question and snapshot.next_question_action is not None:
            self._deliver_question(snapshot)
        return self._result(snapshot)

    def _begin_technical(self, snapshot: Snapshot) -> None:
        conversation = snapshot.conversation
        assert conversation is not None
        conversation.phase = "INTERVIEW"
        snapshot.deadline_at = self.clock() + timedelta(seconds=snapshot.config.duration_seconds)
        snapshot.next_question_action = Action.INITIAL

    def respond(self, request: TransitionRequest) -> TransitionResult:
        snapshot = request.snapshot.model_copy(deep=True)
        self._check_request(snapshot, request)
        if self.clock() >= snapshot.deadline_at:
            return self._result(self._finish(snapshot, "TIME_BUDGET"))
        turn = snapshot.pending_turn
        assert turn is not None
        state = snapshot.objectives[turn.objective_id]
        code = request.submitted_code
        if code is not None:
            if not turn.question.requires_code or not code.strip():
                raise ValueError("Lượt này không nhận mã nguồn hoặc mã đang trống")
            turn.submitted_code, turn.transcript = code, request.candidate_response
            turn.answer = code + ("\n\n" + turn.transcript if turn.transcript.strip() else "")
        else:
            turn.answer = request.candidate_response
            needs_code_input = turn.question.requires_code and snapshot.config.interaction_mode == "VOICE"
            if not turn.answer.strip() or (needs_code_input and standalone_inability(turn) is None):
                raise ValueError("Hãy nộp mã hoặc chọn Chưa làm được")
        turn.judgment = self._judge(snapshot, turn)
        apply_judgment(state, turn, snapshot.policy)
        snapshot.turns.append(turn)
        snapshot.pending_turn = None
        self._advance(snapshot, turn)
        if not request.defer_question and snapshot.next_question_action is not None:
            self._deliver_question(snapshot)
        return self._result(snapshot)

    def next_question(self, request: NextQuestionRequest) -> TransitionResult:
        snapshot = request.snapshot.model_copy(deep=True)
        if snapshot.state_version != request.expected_state_version:
            raise ValueError("Stale state version")
        if (snapshot.is_finished or snapshot.pending_turn is not None or snapshot.next_question_action is None
                or (snapshot.conversation and snapshot.conversation.phase != "INTERVIEW")):
            raise ValueError("Interview is not waiting for a question")
        self._deliver_question(snapshot)
        return self._result(snapshot)

    def _deliver_question(self, snapshot: Snapshot) -> None:
        action = snapshot.next_question_action
        assert action is not None
        prewarmed = self._consume_prewarmed_q1(snapshot) if (not snapshot.turns and action == Action.INITIAL) else None
        if prewarmed is not None:
            if self.clock() >= snapshot.deadline_at:
                self._finish(snapshot, "TIME_BUDGET")
                return
            state = snapshot.objectives[snapshot.queue[0]]
            state.lifecycle = "ACTIVE"
            self._targets(state)
            snapshot.pending_turn = prewarmed
            event("question.prewarm_hit", turn_id=prewarmed.turn_id, mode=state.selected_mode.value)
        else:
            self._ask(snapshot, action)
        snapshot.next_question_action = None
        if snapshot.pending_turn and snapshot.conversation and not snapshot.turns:
            snapshot.pending_turn.introduction = lifecycle.introduction_bridge(
                snapshot.conversation.introduction, snapshot.skills,
            )

    def _judge(self, snapshot: Snapshot, turn: Turn) -> Judgment:
        admission = standalone_inability(turn)
        if admission is not None:
            return admission
        coding_turn = turn.model_copy(update={"answer": turn.submitted_code}) if turn.submitted_code else turn
        coding_check = check_coding_answer(coding_turn, "TEXT" if turn.submitted_code else snapshot.config.interaction_mode)
        if coding_check is not None:
            turn.coding_checks = CodingCheckResult(passed=coding_check.passed, total=coding_check.total)
            event("coding.checked", turn_id=turn.turn_id, total=coding_check.total, passed=coding_check.passed)
            if coding_check.passed < coding_check.total:
                judgment = coding_check.failure_judgment(turn)
                validate_judgment(judgment, turn)
                return judgment
        state = snapshot.objectives[turn.objective_id]
        ids = turn.question.criterion_ids
        objective = self._prompt_objective(state, ids)
        context = {
            "interaction_mode": snapshot.config.interaction_mode,
            "objective": objective, "turn": turn,
            "answer_lines": [{"line": index, "text": text} for index, text in
                             enumerate((turn.answer or "").splitlines(), start=1)],
            "depth_definition": DEPTH_DEFINITIONS[turn.question_depth],
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
        if coding_check is not None:
            context["coding_checks"] = {"passed": coding_check.passed, "total": coding_check.total}
        last_error = None
        judge_started = monotonic()
        for attempt in range(JUDGMENT_ATTEMPTS):
            if attempt and self.clock() >= snapshot.deadline_at:
                break
            judgment = None
            try:
                judgment = self.provider.judge(encode_context(context))
                validate_judgment(judgment, turn)
                event("judge.completed", turn_id=turn.turn_id, attempts=attempt + 1,
                      elapsed_seconds=round(monotonic() - judge_started, 3))
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
        if not request.candidate_response.strip() and not (request.submitted_code or "").strip():
            raise ValueError("Answer must not be blank")

    def _advance(self, snapshot: Snapshot, turn: Turn) -> None:
        target = snapshot.recheck_target
        if target:
            state = snapshot.objectives[target.objective_id]
            if criterion_resolved(state, target.criterion_id, snapshot.policy):
                self._finish(snapshot, "SUFFICIENT_EVIDENCE")
                return
        if len(snapshot.turns) >= snapshot.config.max_questions:
            self._finish(snapshot, "QUESTION_BUDGET")
            return
        if self.clock() >= snapshot.deadline_at:
            self._finish(snapshot, "TIME_BUDGET")
            return
        state = snapshot.objectives[turn.objective_id]
        if target:
            progress = progress_for(state, target.criterion_id)
            if progress.stop_reason or state.turns_spent >= snapshot.config.max_questions_per_objective:
                self._finish(snapshot, progress.stop_reason or "LOCAL_BUDGET")
            else:
                snapshot.next_question_action = criterion_action(state, target.criterion_id)
            return
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
            snapshot.next_question_action = action
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
                requires_code=bool(snapshot.recheck_target and question.requires_code),
            ),
        )
        snapshot.pending_turn.introduction = turn_introduction(snapshot, snapshot.pending_turn)
        event("question.ready", turn_id=snapshot.pending_turn.turn_id, mode=state.selected_mode.value)

    @staticmethod
    def _candidate_background(snapshot: Snapshot, skill: InterviewSkillContext | None) -> str | None:
        """Compact, score-free background context for personalized question framing only."""
        parts: list[str] = []
        opening = snapshot.opening_context
        if opening:
            role = (opening.role_title or "").strip()
            company = (opening.company or "").strip()
            if role and role != "vị trí ứng tuyển":
                parts.append(f"Vị trí: {role}" + (f" ({company})" if company else ""))
            elif company:
                parts.append(f"Công ty: {company}")
        if skill is not None and skill.context_job.strip():
            parts.append(f"Bối cảnh CV: {skill.context_job.strip()}")
        if skill is not None and skill.semantic_alignment == "PARTIAL" and skill.matched_cv_skill_name.strip():
            parts.append(f"Kỹ năng tương đương trên CV: {skill.matched_cv_skill_name.strip()}")
        if not parts:
            return None
        return " | ".join(parts)[:MAX_CANDIDATE_BACKGROUND_CHARS]

    @staticmethod
    def _compact_history_turn(turn: Turn) -> dict[str, object]:
        """Strip Turn.judgment from question history; evidence is passed separately in prior_observations."""
        return {
            "turn_id": turn.turn_id,
            "action": turn.action,
            "question_depth": turn.question_depth,
            "question": turn.question,
            "answer": turn.answer,
        }

    def _question_context(self, snapshot: Snapshot, action: Action) -> dict[str, object]:
        state = snapshot.objectives[snapshot.queue[0]]
        skill = next(s for s in snapshot.skills if s.jd_skill_id == state.objective.skill_id)
        targets = self._targets(state)
        if not targets:
            raise ValueError("No independent criteria available for question generation")
        objective = self._prompt_objective(state, targets)
        # Keep the full probing chain without Turn.judgment bloat.
        history_turns = [turn for turn in snapshot.turns
                         if turn.objective_id == state.objective.objective_id
                         and set(turn.question.criterion_ids).intersection(targets)]
        relevant_ids = {turn.turn_id for turn in history_turns}
        other_questions = [
            {"question": turn.question.text[:300], "truncated": len(turn.question.text) > 300}
            for turn in snapshot.turns
            if turn.objective_id == state.objective.objective_id and turn.turn_id not in relevant_ids
        ]
        for stem in snapshot.prior_question_stems:
            other_questions.append({"question": stem[:MAX_PRIOR_STEM_CHARS], "truncated": False})
        contract = {"mode": state.selected_mode, "depth": question_depth(state, action), "criterion_ids": targets}
        if action == Action.CLARIFY and history_turns:
            previous = history_turns[-1]
            contract["evidence_scope"] = previous.question.evidence_scope
            contract["depth"] = previous.question_depth
        context: dict[str, object] = {
            "objective": objective,
            "required_question_contract": contract,
            "interaction_mode": snapshot.config.interaction_mode,
            "action": action,
            "depth_definition": DEPTH_DEFINITIONS[contract["depth"]],
            "probe_reason": state.probe_reason,
            "criterion_progress": progress_for(state, targets[0]),
            "history": [self._compact_history_turn(t) for t in history_turns],
            "other_questions": other_questions,
            "prior_observations": [item for item in state.evidence_history if item.criterion_id in targets],
        }
        if snapshot.verification is None:
            context["cv_evidence"] = skill.cv_evidence_spans
        else:
            self._add_verification_context(context, snapshot.verification, state)
        background = self._candidate_background(snapshot, skill if snapshot.verification is None else None)
        if background:
            context["candidate_background"] = background
        guidance_parts: list[str] = []
        if action == Action.EASIER:
            guidance_parts.append(
                "Simplify one decision from the preceding question. Keep its technical subject and make the "
                "prerequisite observable with a small new case. Do not substitute a generic definition, "
                "an unrelated task, or a question about why the candidate could not answer."
            )
        if action == Action.DEEPER and state.selected_mode == Mode.CODING:
            guidance_parts.append(
                "Build on the prior coding problem/solution in history by changing one harder technical constraint "
                "(e.g. large or streaming input, bounded memory, concurrency, or time/space limit) and ask ONE "
                "focused question about adapting the algorithm/data structure or evaluating trade-offs for above_target. "
                "Do not ask the candidate to rewrite the basic function from scratch or split into separate deliverables."
            )
        criterion_blob = f"{objective.get('claim', '')} {objective['criteria'][0].get('description', '')}".casefold()
        if (not history_turns
                and action in {Action.INITIAL, Action.FOLLOW_UP}
                and snapshot.config.interaction_mode == "TEXT"
                and state.selected_mode == Mode.CODING
                and ("deduplicate" in criterion_blob or "khử trùng" in criterion_blob)
                and "event" in criterion_blob):
            guidance_parts.append(
                "Request a Python function `deduplicate_events(events)` preserving first occurrence by `event_id` and input order."
            )
        if snapshot.recheck_target:
            target = snapshot.recheck_target
            context["recheck_sources"] = target.source_questions
            context["source_scopes"] = target.source_scopes
            guidance_parts.append("Use a genuinely different case from the source questions, preserving the rubric. "
                                  "Set requires_code=true only if the task requires written code. "
                                  "In VOICE the candidate can type code and optionally explain it aloud.")
            context["other_questions"] += [{"question": q, "truncated": False} for q in target.source_questions]
        if guidance_parts:
            context["question_guidance"] = " ".join(guidance_parts)
        return context

    @staticmethod
    def _add_verification_context(
        context: dict[str, object], verification: InterviewVerification, state: ObjectiveState,
    ) -> None:
        focus = verification.focus_by_criterion.get(state.active_criterion_id)
        jd_excerpt = (focus.jd_excerpt if focus else None) or verification.jd_by_objective.get(
            state.objective.objective_id
        )
        sources = {"jd_excerpt": jd_excerpt} if jd_excerpt is not None else {}
        context["verification_context"] = sources
        context["cv_evidence"] = []
        if not context["history"]:
            if focus is None:
                event("verification.jd_context", reason="no_verified_focus")
            else:
                sources["detail_to_verify"] = focus.detail_to_verify
                context["cv_evidence"] = [focus.cv_excerpt]

    @staticmethod
    def _normalize_question_text(text: str) -> str:
        return " ".join(text.casefold().split())

    @staticmethod
    def _prefer_fallback(
        current: tuple[int, Question, str, bool] | None,
        penalty: int,
        question: Question,
        reason: str,
        reviewed: bool,
    ) -> tuple[int, Question, str, bool]:
        if current is None or penalty <= current[0]:
            return (penalty, question, reason, reviewed)
        return current

    def _safe_soft_fallback(
        self,
        context: dict[str, object],
        snapshot: Snapshot,
        candidate: tuple[int, Question, str, bool] | None,
    ) -> Question | None:
        if candidate is None or self.clock() >= snapshot.deadline_at:
            return None
        penalty, question, reason, reviewed = candidate
        if not reviewed:
            try:
                verdict, _ = self._review_question(context, question)
            except (ValidationError, ValueError):
                return None
            if verdict in _HARD_ALIGNMENT_VERDICTS:
                return None
            reason = f"{reason}:{verdict}"
        action = context.get("action")
        action_name = action.value if isinstance(action, Action) else str(action)
        event("question.soft_fallback", action=action_name, penalty=penalty, reason=reason)
        return question

    def _generate_valid_question(self, context: dict[str, object], snapshot: Snapshot) -> Question | None:
        prior_seen = {self._normalize_question_text(turn.question.text) for turn in snapshot.turns}
        prior_seen.update(
            self._normalize_question_text(stem) for stem in snapshot.prior_question_stems if stem.strip()
        )
        rejected_seen: set[str] = set()
        last_review_error: str | None = None
        last_verdict: str | None = None
        best_fallback: tuple[int, Question, str, bool] | None = None
        action = context.get("action")
        is_diagnostic = action in _DIAGNOSTIC_ACTIONS
        gen_seconds = 0.0
        review_seconds = 0.0
        for attempt in range(GENERATION_ATTEMPTS):
            if self.clock() >= snapshot.deadline_at:
                return None
            if attempt == GENERATION_ATTEMPTS - 1 and self._fall_back_to_jd(context):
                last_review_error = None
                # Retain the corrective instruction, without carrying CV text into the JD-only draft.
                if last_verdict in ALIGNMENT_REPAIRS:
                    context["validation_error"] += " " + ALIGNMENT_REPAIRS[last_verdict]
            gen_start = monotonic()
            question, hard_errors, soft_errors, repeated = self._question_attempt(context, prior_seen, rejected_seen)
            gen_seconds += monotonic() - gen_start
            errors = [*hard_errors, *soft_errors]
            failure = None
            if not errors:
                if self.clock() >= snapshot.deadline_at:
                    return None
                review_start = monotonic()
                try:
                    verdict, reason = self._review_question(context, question)
                except (ValidationError, ValueError) as exc:
                    review_seconds += monotonic() - review_start
                    context["validation_error"] = f"Alignment reviewer error: {exc}"
                    logger.warning(
                        "Alignment review failed for session %s (attempt %s/%s): %s",
                        snapshot.session_id, attempt + 1, GENERATION_ATTEMPTS, type(exc).__name__,
                    )
                    continue
                review_seconds += monotonic() - review_start
                if verdict == "ALIGNED":
                    event("question.generated", attempts=attempt + 1,
                          gen_seconds=round(gen_seconds, 3), review_seconds=round(review_seconds, 3))
                    return question
                failure = verdict
                last_verdict = verdict
                if verdict not in _HARD_ALIGNMENT_VERDICTS and question is not None:
                    penalty = _PENALTY_DIAGNOSTIC_SOFT_REVIEW if is_diagnostic else _PENALTY_STANDARD_SOFT_REVIEW
                    best_fallback = self._prefer_fallback(best_fallback, penalty, question, verdict, True)
                    if is_diagnostic and attempt + 1 >= DIAGNOSTIC_SOFT_REPAIR_LIMIT:
                        event("question.generated", attempts=attempt + 1,
                              gen_seconds=round(gen_seconds, 3), review_seconds=round(review_seconds, 3))
                        return self._safe_soft_fallback(context, snapshot, best_fallback)
                context["rejected_draft"] = question.text
                rejected_seen.add(self._normalize_question_text(question.text))
                base_repair = ALIGNMENT_REPAIRS.get(
                    verdict,
                    "Revise the question to match the criterion, depth, mode, and single-task scope.",
                )
                last_review_error = f"{base_repair} Chi tiết lỗi: {reason}" if reason else base_repair
                errors = [last_review_error]
            else:
                if question is not None:
                    if not hard_errors and soft_errors and not repeated:
                        best_fallback = self._prefer_fallback(
                            best_fallback, _PENALTY_SOFT_VALIDATION, question, "soft_validation", False,
                        )
                    rejected_seen.add(self._normalize_question_text(question.text))
                    context["rejected_draft"] = question.text
                if repeated and last_review_error:
                    errors.append(f"Previous rejection to fix: {last_review_error}")
            context["validation_error"] = "; ".join(errors)
            logger.warning("Invalid question for session %s (attempt %s/%s): %s", snapshot.session_id,
                           attempt + 1, GENERATION_ATTEMPTS, failure or context["validation_error"])
        fallback = self._safe_soft_fallback(context, snapshot, best_fallback)
        if fallback is not None:
            event("question.generated", attempts=GENERATION_ATTEMPTS,
                  gen_seconds=round(gen_seconds, 3), review_seconds=round(review_seconds, 3))
            return fallback
        raise QuestionUnavailableError("AI chưa tạo được câu hỏi phù hợp. Dữ liệu đã lưu được giữ nguyên; vui lòng thử lại.")

    @staticmethod
    def _fall_back_to_jd(context: dict[str, object]) -> bool:
        sources = context.get("verification_context")
        if isinstance(sources, dict) and sources.pop("detail_to_verify", None) is not None:
            context["cv_evidence"] = []
            context.pop("rejected_draft", None)
            context["validation_error"] = "Use a hypothetical case from the JD for the same criterion."
            event("verification.jd_context", reason="cv_drafts_rejected")
            return True
        return False

    def _review_question(self, context: dict[str, object], question: Question) -> tuple[str, str]:
        raw = self.provider.review_question(self._review_context(context, question))
        if isinstance(raw, AlignmentReview):
            return raw.verdict, raw.reason.strip()
        if isinstance(raw, dict):
            return str(raw.get("verdict", "ALIGNED")), str(raw.get("reason", "")).strip()
        return str(raw), ""

    @staticmethod
    def _review_context(context, question: Question) -> str:
        objective = context["objective"]
        contract = context["required_question_contract"]
        history = context["history"]
        history_pairs = []
        for item in history:
            if isinstance(item, dict):
                q_field = item.get("question")
                q_text = q_field.text if hasattr(q_field, "text") else (q_field.get("text", "") if isinstance(q_field, dict) else str(q_field))
                history_pairs.append({"question": q_text, "answer": item.get("answer"),
                                      "action": item.get("action"), "depth": item.get("question_depth")})
            else:
                history_pairs.append({"question": item.question.text, "answer": item.answer,
                                      "action": item.action, "depth": item.question_depth})
        payload = {
            "question": question.text,
            "skill_id": objective.get("skill_id", ""),
            "claim": objective.get("claim", ""),
            "criterion": objective["criteria"][0],
            "cv_evidence": context.get("cv_evidence", []),
            "action": context["action"],
            "question_depth": contract["depth"],
            "target_depth": objective["target_depth"],
            "depth_definition": DEPTH_DEFINITIONS[contract["depth"]],
            "mode": contract["mode"],
            "interaction_mode": context["interaction_mode"],
            "probe_reason": context["probe_reason"],
            "unresolved": context["criterion_progress"].unresolved_aspects,
            "history": history_pairs,
        }
        if "recheck_sources" in context:
            payload.update(source_questions=context["recheck_sources"], source_scopes=context["source_scopes"],
                           requires_code=question.requires_code)
        if "verification_context" in context:
            payload["verification_context"] = context["verification_context"]
        return encode_context(payload)

    def _question_attempt(
        self,
        context: dict[str, object],
        prior_seen: set[str],
        rejected_seen: set[str] | None = None,
    ) -> tuple[Question | None, list[str], list[str], bool]:
        try:
            question = self.provider.question(encode_context(context))
        except ValidationError as exc:
            errors = [f"Invalid Question schema at {item['loc']}: {item['type']}"
                      for item in exc.errors(include_input=False, include_url=False)]
            return None, errors, [], False
        except ValueError as exc:
            return None, [str(exc)], [], False
        outcome = validate_question(question, context)
        hard_errors, soft_errors = list(outcome.hard_errors), list(outcome.soft_errors)
        if any(message.startswith("Ask exactly ONE response task") for message in soft_errors):
            first = first_question(question.text)
            if first:
                candidate = question.model_copy(update={"text": first})
                trimmed = validate_question(candidate, context)
                if not trimmed.all_errors:
                    question, hard_errors, soft_errors = candidate, [], []
        normalized = self._normalize_question_text(question.text)
        repeated = False
        if normalized in prior_seen:
            hard_errors.append("The question repeats a prior turn; use a new focused question instead")
            repeated = True
        elif rejected_seen and normalized in rejected_seen:
            hard_errors.append("The draft repeats a previously rejected question; write a substantially revised question instead")
            repeated = True
        return question, hard_errors, soft_errors, repeated

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
        snapshot.next_question_action = None
        with self._prewarm_lock:
            self._prewarmed_q1.pop(snapshot.session_id, None)

        closing_text: str | None = None
        if snapshot.turns:
            if snapshot.conversation is not None:
                with ThreadPoolExecutor(max_workers=2) as executor:
                    closing_future = executor.submit(
                        copy_context().run, self._generate_closing, snapshot, reason, had_pending,
                    )
                    coaching_future = executor.submit(copy_context().run, self._generate_coaching, snapshot)
                    closing_text = closing_future.result()
                    snapshot.coaching = coaching_future.result()
            else:
                snapshot.coaching = self._generate_coaching(snapshot)
        else:
            closing_text = self._generate_closing(snapshot, reason, had_pending)

        lifecycle.close(snapshot, reason, self.clock(), text=closing_text)
        return snapshot

    def _generate_coaching(self, snapshot: Snapshot) -> SessionCoaching | None:
        # The focused report already gives criterion-specific feedback from each saved turn.
        if not snapshot.turns or snapshot.recheck_target:
            return None
        generator = getattr(self.provider, "session_coaching", None)
        if callable(generator):
            try:
                generated = generator(encode_context(coaching_context(snapshot)))
                return SessionCoaching.model_validate(generated)
            except Exception as exc:
                logger.warning("Falling back to deterministic session coaching (%s): %s", type(exc).__name__, exc)
                event("coaching.fallback", error_type=type(exc).__name__)
        return fallback_session_coaching(snapshot)

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
