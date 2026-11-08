"""Per-criterion probe budgets. Exhausting a budget never decides competence."""
from .models import Action, CriterionProgress, ObjectiveState, Turn
from .policy_config import InterviewPolicy


def progress_for(state: ObjectiveState, key: str) -> CriterionProgress:
    return state.criterion_progress.setdefault(key, CriterionProgress())


def record_progress(state: ObjectiveState, turn: Turn, policy: InterviewPolicy) -> None:
    if turn.judgment is None:
        return
    for item in turn.judgment.observations:
        progress = progress_for(state, item.criterion_id)
        gaps = sorted({gap.strip().casefold() for gap in item.unresolved_aspects if gap.strip()})
        progressed = _new_case(progress, turn, item.observation) or bool(gaps and gaps != progress.unresolved_aspects)
        progress.stagnant_turns = 0 if progressed else progress.stagnant_turns + 1
        progress.unresolved_aspects = gaps
        progress.turns_spent += 1
        progress.clarification_spent |= turn.action == Action.CLARIFY
        progress.easier_spent |= turn.action == Action.EASIER
        progress.deeper_spent |= turn.action == Action.DEEPER
        progress.stop_reason = _stop_reason(progress, policy)


def _new_case(progress: CriterionProgress, turn: Turn, observation: str) -> bool:
    if observation not in {"SUPPORTS", "CONTRADICTS"} or not turn.question.evidence_scope.strip():
        return False
    case = f"{turn.question_depth}:{turn.question.evidence_scope.casefold().strip()}"
    if case in progress.observed_cases:
        return False
    progress.observed_cases.append(case)
    return True


def _stop_reason(progress: CriterionProgress, policy: InterviewPolicy) -> str | None:
    if progress.turns_spent >= policy.max_turns_per_criterion:
        return "CRITERION_BUDGET"
    if progress.turns_spent >= policy.criterion_soft_limit and progress.stagnant_turns >= policy.max_stagnant_turns:
        return "NO_PROGRESS"
    return None


def restore_progress(state: ObjectiveState, turns: list[Turn], policy: InterviewPolicy) -> None:
    """Old snapshots have a ledger and turns but no per-criterion counters."""
    if state.criterion_progress:
        return
    for turn in turns:
        if turn.objective_id == state.objective.objective_id:
            record_progress(state, turn, policy)
