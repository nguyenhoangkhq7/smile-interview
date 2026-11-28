"""Grounded evidence ledger and deterministic sufficiency; CV priors never decide results."""
import re
import unicodedata
from .models import Action, Assessment, Criterion, Judgment, Mode, ObjectiveState, Observation, RecordedEvidence, Turn
from .mode_strategy import supports_easier_drop
from .policy_config import InterviewPolicy
from .criterion_progress import CRITERION_SOFT_LIMIT, progress_for, record_progress
from .conversation import ACKNOWLEDGMENT, INABILITY_ACKNOWLEDGMENT, MAX_FEEDBACK_LENGTH, fit_feedback_length
from .excerpts import source_excerpt, source_lines
from .telemetry import event

VALID_PERFORMANCE = {"BELOW", "AT_TARGET", "ABOVE"}
SUBSTANTIVE = {"SUPPORTS", "CONTRADICTS"}
TERMINAL = {Assessment.AT, Assessment.ABOVE, Assessment.BELOW, Assessment.NOT_DEMONSTRATED}
MAX_SECONDARY_CRITERIA_IN_PROMPT = 3
MAX_SECONDARY_OBSERVATIONS_PER_TURN = 2
_MIN_SECONDARY_EXCERPT_CHARS = 25
_MIN_SECONDARY_EXCERPT_WORDS = 5
_MIN_SECONDARY_RATIONALE_CHARS = 10
_VIETNAMESE_DIACRITICS = re.compile(
    r"[àáạảãâầấậẩẫăằắặẳẵèéẹẻẽêềếệểễìíịỉĩòóọỏõôồốộổỗơờớợởỡùúụủũưừứựửữỳýỵỷỹđ]",
    re.IGNORECASE,
)
_ENGLISH_PROSE_WORDS = frozenset({
    "the", "candidate", "answer", "response", "provides", "correctly", "explains",
    "failed", "however", "without", "because", "therefore", "demonstrates",
    "does", "not", "should", "missing", "instead", "clearly", "mentions",
})


def _looks_like_english_prose(text: str) -> bool:
    """Detect leaked full-English prose rationales while permitting short technical strings."""
    cleaned = text.strip()
    if not cleaned or _VIETNAMESE_DIACRITICS.search(cleaned):
        return False
    words = re.findall(r"[A-Za-z]+", cleaned.lower())
    if len(words) < 8:
        return False
    hits = sum(1 for word in words if word in _ENGLISH_PROSE_WORDS)
    return hits >= 2


def standalone_inability(turn: Turn) -> Judgment | None:
    answer = (turn.answer or "").strip()
    normalized = " ".join(unicodedata.normalize("NFC", answer).casefold().split())
    if not re.fullmatch(
        r"(?:dạ[, ]+)?(?:(?:tôi|em|mình) )?"
        r"(?:(?:không|chưa) (?:biết|làm được|trả lời được|nhớ)(?: câu trả lời| trả lời| cách làm| câu này)?"
        r"|bỏ qua(?: câu này| câu hỏi này)?"
        r"|skip(?: this question)?)"
        r"(?: ạ)?[.!…]*",
        normalized,
    ):
        return None
    return Judgment(
        explicit_inability=True, inability_excerpt=answer, feedback=INABILITY_ACKNOWLEDGMENT,
        observations=[Observation(criterion_id=key, observation="NO_EVIDENCE", performance="UNDETERMINED",
                                  rationale="Ứng viên cho biết chưa trả lời được câu hỏi này.")
                      for key in turn.question.criterion_ids],
    )


def validate_judgment(
    judgment: Judgment,
    turn: Turn,
    *,
    max_feedback_length: int = MAX_FEEDBACK_LENGTH,
    allow_sentence_trim: bool = False,
    interaction_mode: str = "TEXT",
) -> None:
    if len(judgment.feedback.strip()) > max_feedback_length:
        # Presentation failure must not discard otherwise valid assessment evidence.
        judgment.feedback = fit_feedback_length(
            judgment.feedback,
            max_length=max_feedback_length,
            allow_sentence_trim=allow_sentence_trim,
        )
    voice_punct = interaction_mode == "VOICE" and not turn.submitted_code
    if judgment.explicit_inability:
        grounded = source_excerpt(
            judgment.inability_excerpt, turn.answer or "", allow_punctuation_tolerance=voice_punct,
        )
        if grounded is None:
            raise ValueError("Explicit inability requires a grounded excerpt: copy ONE contiguous passage "
                             "from turn.answer into inability_excerpt, without paraphrasing or added words")
        judgment.inability_excerpt = grounded
    ids = [item.criterion_id for item in judgment.observations]
    if len(ids) != len(set(ids)) or set(ids) != set(turn.question.criterion_ids):
        expected = set(turn.question.criterion_ids)
        duplicates = sorted(key for key in set(ids) if ids.count(key) > 1)
        raise ValueError("Judge must assess exactly the targeted criteria; "
                         f"missing={sorted(expected - set(ids))}, "
                         f"unexpected={sorted(set(ids) - expected)}, duplicates={duplicates}")
    for item in judgment.observations:
        if _looks_like_english_prose(item.rationale):
            raise ValueError(
                f"Observation rationale for criterion_id={item.criterion_id} must be written in Vietnamese, "
                "not English prose"
            )
        if item.performance in {"AT_TARGET", "ABOVE"} and item.unresolved_aspects:
            raise ValueError("A passed criterion cannot have unresolved required aspects")
        substantive = item.observation in SUBSTANTIVE
        if substantive:
            grounded = (source_lines(item.response_line_range, turn.answer or "")
                        if item.response_line_range is not None
                        else source_excerpt(
                            item.response_excerpt, turn.answer or "", allow_punctuation_tolerance=voice_punct,
                        ))
            if grounded is None:
                raise ValueError(f"Evidence excerpt not found in candidate answer for criterion_id={item.criterion_id}. "
                                 "Copy ONE contiguous passage from turn.answer into response_excerpt exactly; "
                                 "do not paraphrase, correct spelling, add quotation marks or combine passages. "
                                 "Put interpretation in rationale, not response_excerpt. Reassess the observation "
                                 "if no passage supports it; never fabricate a quote to keep a score. "
                                 "For code, set response_line_range=[start_line,end_line] using answer_lines "
                                 "(inclusive, 1-based); the server copies those original lines verbatim.")
            item.response_excerpt = grounded
        if substantive and item.performance not in VALID_PERFORMANCE:
            raise ValueError("Substantive evidence requires a performance level")
        if not substantive and item.performance != "UNDETERMINED":
            raise ValueError("Missing evidence cannot be scored")
        if item.observation == "CONTRADICTS" and item.performance != "BELOW":
            raise ValueError("Contradictory performance must be below its criterion anchor")


def eligible_secondary_criteria(
    state: ObjectiveState,
    turn: Turn,
    policy: InterviewPolicy | None = None,
    *,
    coding_compile_error: bool = False,
) -> list[Criterion]:
    """Return unresolved sibling criteria in the same objective eligible for opportunistic positive credit."""
    active_policy = policy or InterviewPolicy()
    if (
        turn.question_depth != state.objective.target_depth
        or turn.action in {Action.EASIER, Action.VERIFY, Action.DEEPER}
        or turn.practice_step == "RETRY"
        or any(item.kind == "HINT" for item in turn.clarifications)
        or coding_compile_error
        or (turn.coding_checks is not None and bool(turn.coding_checks.compile_error))
    ):
        return []
    primary_ids = set(turn.question.criterion_ids)
    excluded = set(state.assisted_criteria) | set(state.hinted_criteria) | set(state.contradictions)
    candidates = [
        criterion for criterion in state.objective.criteria
        if criterion.criterion_id not in primary_ids
        and criterion.criterion_id not in excluded
        and not criterion_resolved(state, criterion.criterion_id, active_policy)
    ]
    candidates.sort(key=lambda c: (not c.essential,))
    return candidates[:MAX_SECONDARY_CRITERIA_IN_PROMPT]


def _is_substantive_secondary_excerpt(grounded: str, *, has_line_range: bool) -> bool:
    stripped = grounded.strip()
    if has_line_range or "\n" in stripped:
        non_empty_lines = [line for line in stripped.splitlines() if line.strip()]
        return len(non_empty_lines) >= 2 or len(stripped) >= _MIN_SECONDARY_EXCERPT_CHARS
    return len(stripped) >= _MIN_SECONDARY_EXCERPT_CHARS and len(stripped.split()) >= _MIN_SECONDARY_EXCERPT_WORDS


def sanitize_secondary_observations(
    judgment: Judgment,
    state: ObjectiveState,
    turn: Turn,
    policy: InterviewPolicy | None = None,
    *,
    interaction_mode: str = "TEXT",
    coding_compile_error: bool = False,
) -> list[Observation]:
    """Filter opportunistic secondary observations with 5 hard gates; never fails primary grading."""
    raw = list(judgment.secondary_observations)
    if not raw:
        return []
    if judgment.explicit_inability:
        judgment.secondary_observations = []
        return []
    allowed_ids = {
        c.criterion_id
        for c in eligible_secondary_criteria(state, turn, policy, coding_compile_error=coding_compile_error)
    }
    if not allowed_ids:
        event("judge.secondary_dropped", turn_id=turn.turn_id, count=len(raw), reason="turn_ineligible")
        judgment.secondary_observations = []
        return []
    voice_punct = interaction_mode == "VOICE" and not turn.submitted_code
    accepted: list[Observation] = []
    seen_ids: set[str] = set()
    dropped = 0
    for item in raw:
        if len(accepted) >= MAX_SECONDARY_OBSERVATIONS_PER_TURN:
            dropped += 1
            continue
        if (
            item.criterion_id not in allowed_ids
            or item.criterion_id in seen_ids
            or item.observation != "SUPPORTS"
            or item.performance != "AT_TARGET"
            or bool(item.unresolved_aspects)
            or _looks_like_english_prose(item.rationale)
            or len(item.rationale.strip()) < _MIN_SECONDARY_RATIONALE_CHARS
        ):
            dropped += 1
            continue
        grounded = (
            source_lines(item.response_line_range, turn.answer or "")
            if item.response_line_range is not None
            else source_excerpt(item.response_excerpt, turn.answer or "", allow_punctuation_tolerance=voice_punct)
        )
        if grounded is None or not _is_substantive_secondary_excerpt(
            grounded, has_line_range=item.response_line_range is not None,
        ):
            dropped += 1
            continue
        seen_ids.add(item.criterion_id)
        accepted.append(item.model_copy(update={"response_excerpt": grounded, "resolves_contradiction": False}))
    if dropped:
        event("judge.secondary_dropped", turn_id=turn.turn_id, count=dropped, accepted=len(accepted))
    judgment.secondary_observations = accepted
    return accepted


def apply_judgment(
    state: ObjectiveState,
    turn: Turn,
    policy: InterviewPolicy | None = None,
    *,
    max_feedback_length: int = MAX_FEEDBACK_LENGTH,
    allow_sentence_trim: bool = False,
    interaction_mode: str = "TEXT",
) -> None:
    judgment = turn.judgment
    assert judgment is not None
    validate_judgment(
        judgment,
        turn,
        max_feedback_length=max_feedback_length,
        allow_sentence_trim=allow_sentence_trim,
        interaction_mode=interaction_mode,
    )
    secondary = sanitize_secondary_observations(
        judgment, state, turn, policy, interaction_mode=interaction_mode,
    )
    state.turns_spent += 1
    for observation in judgment.observations:
        if observation.performance == "ABOVE" and not (
            policy and policy.allow_extension_probes and turn.action == Action.DEEPER
            and turn.question_depth == state.objective.extension_depth
        ):
            observation.performance = "AT_TARGET"
        _record_observation(state, turn, observation)
    record_progress(state, turn)
    for observation in secondary:
        _record_observation(state, turn, observation, is_secondary=True)
        event("judge.secondary_evidence", turn_id=turn.turn_id, criterion_id=observation.criterion_id)
    state.assessment = assess(state, policy)
    # Candidate-facing feedback suppresses hints. Only delivered assistance taints evidence.


def _record_observation(
    state: ObjectiveState,
    turn: Turn,
    observation: Observation,
    *,
    is_secondary: bool = False,
) -> None:
    evidence = RecordedEvidence(
        **observation.model_dump(exclude={"response_line_range", "resolves_contradiction", "unresolved_aspects"}),
        turn_id=turn.turn_id,
        question_depth=state.objective.target_depth if is_secondary else turn.question_depth,
        evidence_scope=turn.question.evidence_scope,
        independent=(observation.criterion_id not in state.assisted_criteria
                     and turn.practice_step != "RETRY"
                     and not any(item.kind == "HINT" for item in turn.clarifications)),
        explicit_inability=False if is_secondary else bool(turn.judgment and turn.judgment.explicit_inability),
        is_extension=False if is_secondary else (turn.action == Action.DEEPER),
    )
    if evidence.explicit_inability and evidence.observation not in SUBSTANTIVE:
        evidence.response_excerpt = turn.judgment.inability_excerpt
    if not any(_fingerprint(previous) == _fingerprint(evidence) for previous in state.evidence_history):
        state.evidence_history.append(evidence)
    if not evidence.independent or evidence.is_extension or evidence.question_depth != state.objective.target_depth:
        return  # diagnostics and extensions never overwrite target results
    if not is_secondary and turn.practice_step == "TRANSFER":
        progress_for(state, observation.criterion_id).transfer_verified = (
            evidence.observation == "SUPPORTS" and evidence.performance in {"AT_TARGET", "ABOVE"})
    _update_target_result(state, turn, evidence, resolves_contradiction=observation.resolves_contradiction)


def _update_target_result(
    state: ObjectiveState,
    turn: Turn,
    evidence: RecordedEvidence,
    *,
    resolves_contradiction: bool = False,
) -> None:
    key = evidence.criterion_id
    previous = state.criterion_results.get(key)
    if evidence.explicit_inability and previous and previous.performance in {"AT_TARGET", "ABOVE"}:
        if key not in state.contradictions:
            state.contradictions.append(key)
    if evidence.observation not in SUBSTANTIVE:
        return
    incompatible = previous and (previous.performance == "BELOW") != (evidence.performance == "BELOW")
    recovered_after_easier = (
        previous is not None
        and previous.performance == "BELOW"
        and evidence.performance in {"AT_TARGET", "ABOVE"}
        and progress_for(state, key).easier_spent
        and turn.action == Action.FOLLOW_UP
        and key not in state.contradictions
    )
    recovered_after_clarify = (
        previous is not None
        and previous.performance == "BELOW"
        and evidence.performance in {"AT_TARGET", "ABOVE"}
        and turn.action == Action.CLARIFY
        and key not in state.contradictions
    )
    if incompatible and not (recovered_after_easier or recovered_after_clarify or turn.practice_step == "TRANSFER") and key not in state.contradictions:
        state.contradictions.append(key)
    if turn.action == Action.VERIFY and resolves_contradiction and key in state.contradictions:
        state.contradictions.remove(key)
    state.criterion_results[key] = evidence


def _fingerprint(evidence: RecordedEvidence) -> tuple[object, ...]:
    return (evidence.criterion_id, evidence.question_depth, evidence.evidence_scope.casefold().strip(),
            evidence.performance, evidence.observation, " ".join(evidence.response_excerpt.casefold().split()),
            evidence.independent, evidence.explicit_inability)


def _criterion_evidence(state: ObjectiveState, key: str) -> list[RecordedEvidence]:
    return [item for item in state.evidence_history if item.criterion_id == key and item.independent]


def _failure(item: RecordedEvidence) -> bool:
    return item.performance == "BELOW" or item.explicit_inability


def _diagnosed_failure(state: ObjectiveState, key: str, policy: InterviewPolicy) -> bool:
    current = state.criterion_results.get(key)
    if current and current.performance in {"AT_TARGET", "ABOVE"}:
        return False
    evidence = _criterion_evidence(state, key)
    target = state.objective.target_depth
    if (
        target == 1
        and any(item.question_depth == 1 and item.explicit_inability for item in evidence)
        and progress_for(state, key).stop_reason == "NO_PROGRESS"
    ):
        return True
    target_failed = any(item.question_depth == target and not item.is_extension and _failure(item) for item in evidence)
    no_easier_drop = state.selected_mode is not None and not supports_easier_drop(state.selected_mode)
    diagnostic = any(
        (item.question_depth < target and (item.observation in SUBSTANTIVE or item.explicit_inability))
        or item.explicit_inability
        for item in evidence
    ) or (no_easier_drop and progress_for(state, key).clarification_spent)
    contexts = {item.evidence_scope.casefold().strip() for item in evidence
                if item.question_depth <= target and not item.is_extension
                and (item.observation in SUBSTANTIVE or item.explicit_inability) and item.evidence_scope.strip()}
    return target_failed and (diagnostic or target == 1) and len(contexts) >= policy.min_failure_contexts


def assess(state: ObjectiveState, policy: InterviewPolicy | None = None) -> Assessment:
    policy = policy or InterviewPolicy()
    if not state.turns_spent:
        return Assessment.NOT_ASSESSED
    required = [criterion.criterion_id for criterion in state.objective.criteria if criterion.essential]
    if state.contradictions:
        return Assessment.INSUFFICIENT
    diagnosed = {key for key in required if _diagnosed_failure(state, key, policy)}
    if len(diagnosed) == len(required) and not any(
            item.performance in {"AT_TARGET", "ABOVE"} and item.observation == "SUPPORTS"
            for key in required for item in _criterion_evidence(state, key)
            if item.question_depth <= state.objective.target_depth and not item.is_extension):
        return Assessment.NOT_DEMONSTRATED
    if any(key not in state.criterion_results and key not in diagnosed for key in required):
        return Assessment.INSUFFICIENT
    failures = [key for key in required if key in diagnosed or state.criterion_results[key].performance == "BELOW"]
    if failures:
        return Assessment.BELOW if all(key in diagnosed for key in failures) else Assessment.INSUFFICIENT
    if _above_target(state, required):
        return Assessment.ABOVE
    return Assessment.AT


def _above_target(state: ObjectiveState, required: list[str]) -> bool:
    extension = state.objective.extension_depth
    if extension is None or not required:
        return False
    target = state.objective.target_depth
    for key in required:
        evidence = [
            item for item in _criterion_evidence(state, key)
            if item.question_depth == extension
            and (item.is_extension or extension > target)
            and item.observation in SUBSTANTIVE
        ]
        if not evidence or any(item.performance != "ABOVE" for item in evidence):
            return False
    return True


def next_action(
    state: ObjectiveState,
    turn: Turn,
    policy: InterviewPolicy | None = None,
    *,
    allow_mode_switch: bool = False,
) -> Action | None:
    policy = policy or InterviewPolicy()
    eligible = [
        key for key in eligible_criteria(state, allow_mode_switch=allow_mode_switch)
        if not progress_for(state, key).stop_reason
    ]
    contradictions = [key for key in state.contradictions if key in eligible]
    if contradictions:
        return _probe(state, contradictions[0], Action.VERIFY, "Resolve conflicting target-level evidence")
    recovery = _diagnostic_recovery(state, turn, eligible)
    if recovery is not None:
        return recovery
    if state.assessment in TERMINAL:
        return _extension_action(state, eligible, policy)
    essential = {c.criterion_id for c in state.objective.criteria if c.essential}
    unresolved = [key for key in eligible if key in essential and not criterion_resolved(state, key, policy)]
    if not unresolved:
        return None
    chosen = _choose_criterion(state, unresolved)
    active_mode = mode_for_criterion(state, chosen, allow_mode_switch=allow_mode_switch)
    return criterion_action(state, chosen, mode=active_mode, last_turn=turn)


def _diagnostic_recovery(state: ObjectiveState, turn: Turn, eligible: list[str]) -> Action | None:
    diagnostic = (turn.action == Action.EASIER
                  or (turn.action == Action.CLARIFY and turn.question_depth < state.objective.target_depth))
    if not diagnostic or not turn.judgment or turn.judgment.explicit_inability:
        return None
    for item in turn.judgment.observations:
        if item.criterion_id in eligible and item.observation == "SUPPORTS" and item.performance in {"AT_TARGET", "ABOVE"}:
            return _probe(state, item.criterion_id, Action.FOLLOW_UP,
                          "Verify independent application at the required depth after diagnosis")
    return None


def _should_offer_code_repair(turn: Turn | None, key: str) -> bool:
    if turn is None or key not in turn.question.criterion_ids or turn.coding_checks is None:
        return False
    if turn.judgment and turn.judgment.explicit_inability:
        return False
    checks = turn.coding_checks
    return checks.total > 0 and checks.passed < checks.total


def criterion_action(
    state: ObjectiveState,
    key: str,
    *,
    mode: Mode | None = None,
    last_turn: Turn | None = None,
) -> Action:
    progress = progress_for(state, key)
    if key in state.contradictions:
        return _probe(state, key, Action.VERIFY, "Resolve conflicting target-level evidence")
    if not progress.turns_spent:
        return _probe(state, key, Action.FOLLOW_UP, "Collect initial evidence for an untested essential criterion")
    evidence = [e for e in state.evidence_history if e.criterion_id == key]
    last = evidence[-1] if evidence else None
    active_mode = mode or state.selected_mode
    if _should_offer_code_repair(last_turn, key) and not progress.clarification_spent:
        return _probe(
            state, key, Action.CLARIFY,
            "Ask the candidate to inspect and fix the remaining failing edge or logic case in their submitted code",
        )
    if last and (last.performance == "BELOW" or last.explicit_inability):
        if active_mode is not None and not supports_easier_drop(active_mode):
            if last.explicit_inability:
                return _probe(
                    state, key, Action.FOLLOW_UP,
                    "Ask for a simpler concrete example from coursework, internship, or personal project",
                )
            if not progress.clarification_spent:
                return _probe(
                    state, key, Action.CLARIFY,
                    "Probe the missing STAR detail (personal Action or measurable Result) in the candidate's own story",
                )
        elif not progress.easier_spent and state.objective.target_depth > 1:
            return _probe(state, key, Action.EASIER, "Ask for one simpler prerequisite decision using a small concrete case")
    if last and last.observation in {"UNCLEAR", "NO_EVIDENCE"} and not progress.clarification_spent:
        return _probe(state, key, Action.CLARIFY, "Clarify the missing or ambiguous evidence without hints")
    gaps = "; ".join(progress.unresolved_aspects)
    return _probe(state, key, Action.FOLLOW_UP, f"Verify unresolved evidence: {gaps}" if gaps else "Obtain independent evidence for the unresolved criterion")


def criterion_resolved(state: ObjectiveState, key: str, policy: InterviewPolicy) -> bool:
    if key in state.contradictions:
        return False
    result = state.criterion_results.get(key)
    return bool(result and result.performance in {"AT_TARGET", "ABOVE"}) or _diagnosed_failure(state, key, policy)


def _choose_criterion(state: ObjectiveState, candidates: list[str]) -> str:
    active = state.active_criterion_id
    unasked = [key for key in candidates if not progress_for(state, key).turns_spent]
    if active in candidates and (progress_for(state, active).turns_spent < CRITERION_SOFT_LIMIT or not unasked):
        return active
    return min(candidates, key=lambda key: progress_for(state, key).turns_spent)


def _probe(state: ObjectiveState, key: str, action: Action, reason: str) -> Action:
    state.active_criterion_id, state.probe_reason = key, reason
    return action


def _extension_action(state: ObjectiveState, eligible: list[str], policy: InterviewPolicy) -> Action | None:
    if state.assessment != Assessment.AT or not policy.allow_extension_probes or state.objective.extension_depth is None:
        return None
    for criterion in state.objective.criteria:
        key = criterion.criterion_id
        if criterion.essential and key in eligible and not progress_for(state, key).deeper_spent:
            return _probe(state, key, Action.DEEPER, "Measure the predefined higher standard after target attainment")
    return None


def _indices_for_mode(state: ObjectiveState, mode_item) -> list[int]:
    if mode_item is None:
        return []
    return list(mode_item.criterion_indices) if mode_item.criterion_indices else list(range(len(state.objective.criteria)))


def mode_for_criterion(state: ObjectiveState, criterion_id: str, *, allow_mode_switch: bool = False) -> Mode:
    assert state.selected_mode is not None
    index = next((i for i, c in enumerate(state.objective.criteria) if c.criterion_id == criterion_id), None)
    if index is None:
        return state.selected_mode
    primary = next((item for item in state.objective.suitable_modes if item.mode == state.selected_mode), None)
    if index in _indices_for_mode(state, primary) or not allow_mode_switch:
        return state.selected_mode
    for item in state.objective.suitable_modes:
        if index in _indices_for_mode(state, item):
            return item.mode
    return state.selected_mode


def eligible_criteria(state: ObjectiveState, *, allow_mode_switch: bool = False) -> list[str]:
    primary = next((item for item in state.objective.suitable_modes if item.mode == state.selected_mode), None)
    if primary is None:
        indices = list(range(len(state.objective.criteria)))
    else:
        indices = _indices_for_mode(state, primary)
        if allow_mode_switch:
            seen = set(indices)
            for item in state.objective.suitable_modes:
                for idx in _indices_for_mode(state, item):
                    if idx not in seen:
                        indices.append(idx)
                        seen.add(idx)
    return [state.objective.criteria[index].criterion_id for index in indices
            if state.objective.criteria[index].criterion_id not in state.assisted_criteria]
