"""Grounded evidence ledger and deterministic sufficiency; CV priors never decide results."""
from .models import Action, Assessment, Judgment, ObjectiveState, Observation, RecordedEvidence, Turn
from .policy_config import InterviewPolicy
from .criterion_progress import progress_for, record_progress
from .conversation import ACKNOWLEDGMENT, MAX_FEEDBACK_LENGTH
from .excerpts import source_excerpt, source_lines

VALID_PERFORMANCE = {"BELOW", "AT_TARGET", "ABOVE"}
SUBSTANTIVE = {"SUPPORTS", "CONTRADICTS"}
TERMINAL = {Assessment.AT, Assessment.ABOVE, Assessment.BELOW, Assessment.NOT_DEMONSTRATED}


def validate_judgment(judgment: Judgment, turn: Turn) -> None:
    if len(judgment.feedback.strip()) > MAX_FEEDBACK_LENGTH:
        # Presentation failure must not discard otherwise valid assessment evidence.
        judgment.feedback = ACKNOWLEDGMENT
    if judgment.explicit_inability:
        grounded = source_excerpt(judgment.inability_excerpt, turn.answer or "")
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
        if item.performance in {"AT_TARGET", "ABOVE"} and item.unresolved_aspects:
            raise ValueError("A passed criterion cannot have unresolved required aspects")
        substantive = item.observation in SUBSTANTIVE
        if substantive:
            grounded = (source_lines(item.response_line_range, turn.answer or "")
                        if item.response_line_range is not None
                        else source_excerpt(item.response_excerpt, turn.answer or ""))
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


def apply_judgment(state: ObjectiveState, turn: Turn, policy: InterviewPolicy | None = None) -> None:
    judgment = turn.judgment
    assert judgment is not None
    validate_judgment(judgment, turn)
    state.turns_spent += 1
    state.clarification_spent |= turn.action == Action.CLARIFY
    state.easier_spent |= turn.action == Action.EASIER
    state.deeper_spent |= turn.action == Action.DEEPER
    if turn.question.assistance == "HINT":
        state.assisted_criteria = sorted(set(state.assisted_criteria) | set(turn.question.criterion_ids))
    for observation in judgment.observations:
        _record_observation(state, turn, observation)
    record_progress(state, turn, policy or InterviewPolicy())
    state.assessment = assess(state, policy)
    if judgment.feedback_contains_hint:
        state.assisted_criteria = sorted(set(state.assisted_criteria) | set(turn.question.criterion_ids))


def _record_observation(state: ObjectiveState, turn: Turn, observation: Observation) -> None:
    evidence = RecordedEvidence(
        **observation.model_dump(), turn_id=turn.turn_id, question_depth=turn.question_depth,
        evidence_scope=turn.question.evidence_scope,
        independent=observation.criterion_id not in state.assisted_criteria,
        explicit_inability=bool(turn.judgment and turn.judgment.explicit_inability),
    )
    if evidence.explicit_inability and evidence.observation not in SUBSTANTIVE:
        evidence.response_excerpt = turn.judgment.inability_excerpt
    if not any(_fingerprint(previous) == _fingerprint(evidence) for previous in state.evidence_history):
        state.evidence_history.append(evidence)
    if not evidence.independent or evidence.question_depth != state.objective.target_depth:
        return  # diagnostics and extensions never overwrite target results
    _update_target_result(state, turn, evidence)


def _update_target_result(state: ObjectiveState, turn: Turn, evidence: RecordedEvidence) -> None:
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
    if incompatible and not recovered_after_easier and key not in state.contradictions:
        state.contradictions.append(key)
    if turn.action == Action.VERIFY and evidence.resolves_contradiction and key in state.contradictions:
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
    target_failed = any(item.question_depth == target and _failure(item) for item in evidence)
    diagnostic = any(
        (item.question_depth is not None and item.question_depth < target
         and (item.observation in SUBSTANTIVE or item.explicit_inability))
        or item.explicit_inability
        for item in evidence
    )
    contexts = {item.evidence_scope.casefold().strip() for item in evidence
                if item.question_depth is not None and item.question_depth <= target
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
            if item.question_depth is not None and item.question_depth <= state.objective.target_depth):
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
    if extension is None or not state.objective.extension_criterion_ids:
        return False
    for key in required:
        evidence = [item for item in _criterion_evidence(state, key)
                    if item.question_depth == extension and item.observation in SUBSTANTIVE]
        if not evidence or any(item.performance != "ABOVE" for item in evidence):
            return False
    return True


def next_action(state: ObjectiveState, turn: Turn, policy: InterviewPolicy | None = None) -> Action | None:
    policy = policy or InterviewPolicy()
    eligible = [key for key in eligible_criteria(state) if not progress_for(state, key).stop_reason]
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
    return _criterion_action(state, _choose_criterion(state, unresolved, policy))


def _diagnostic_recovery(state: ObjectiveState, turn: Turn, eligible: list[str]) -> Action | None:
    if turn.action != Action.EASIER or not turn.judgment or turn.judgment.explicit_inability:
        return None
    for item in turn.judgment.observations:
        if item.criterion_id in eligible and item.observation == "SUPPORTS" and item.performance in {"AT_TARGET", "ABOVE"}:
            return _probe(state, item.criterion_id, Action.FOLLOW_UP,
                          "Verify independent application at the required depth after diagnosis")
    return None


def _criterion_action(state: ObjectiveState, key: str) -> Action:
    progress = progress_for(state, key)
    if not progress.turns_spent:
        return _probe(state, key, Action.FOLLOW_UP, "Collect initial evidence for an untested essential criterion")
    evidence = [e for e in state.evidence_history if e.criterion_id == key]
    last = evidence[-1] if evidence else None
    if last and (last.performance == "BELOW" or last.explicit_inability) and not progress.easier_spent and state.objective.target_depth > 1:
        return _probe(state, key, Action.EASIER, "Diagnose the foundation behind the observed error")
    if last and last.observation in {"UNCLEAR", "NO_EVIDENCE"} and not progress.clarification_spent:
        return _probe(state, key, Action.CLARIFY, "Clarify the missing or ambiguous evidence without hints")
    gaps = "; ".join(progress.unresolved_aspects)
    return _probe(state, key, Action.FOLLOW_UP, f"Verify unresolved evidence: {gaps}" if gaps else "Obtain independent evidence for the unresolved criterion")


def criterion_resolved(state: ObjectiveState, key: str, policy: InterviewPolicy) -> bool:
    if key in state.contradictions:
        return False
    result = state.criterion_results.get(key)
    return bool(result and result.performance in {"AT_TARGET", "ABOVE"}) or _diagnosed_failure(state, key, policy)


def _choose_criterion(state: ObjectiveState, candidates: list[str], policy: InterviewPolicy) -> str:
    active = state.active_criterion_id
    unasked = [key for key in candidates if not progress_for(state, key).turns_spent]
    if active in candidates and (progress_for(state, active).turns_spent < policy.criterion_soft_limit or not unasked):
        return active
    return min(candidates, key=lambda key: progress_for(state, key).turns_spent)


def _probe(state: ObjectiveState, key: str, action: Action, reason: str) -> Action:
    state.active_criterion_id, state.probe_reason = key, reason
    return action


def _extension_action(state: ObjectiveState, eligible: list[str], policy: InterviewPolicy) -> Action | None:
    if state.assessment != Assessment.AT or not policy.allow_extension_probes or state.objective.extension_depth is None:
        return None
    for key in state.objective.extension_criterion_ids:
        if key in eligible and not progress_for(state, key).deeper_spent:
            return _probe(state, key, Action.DEEPER, "Measure the predefined higher standard after target attainment")
    return None


def eligible_criteria(state: ObjectiveState) -> list[str]:
    mode = next((item for item in state.objective.suitable_modes if item.mode == state.selected_mode), None)
    indices = mode.criterion_indices if mode and mode.criterion_indices else range(len(state.objective.criteria))
    return [state.objective.criteria[index].criterion_id for index in indices
            if state.objective.criteria[index].criterion_id not in state.assisted_criteria]
