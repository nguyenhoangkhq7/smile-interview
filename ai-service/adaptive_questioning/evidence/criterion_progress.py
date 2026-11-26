"""Per-criterion probe budgets. Exhausting a budget never decides competence."""
from .models import Action, CriterionProgress, ObjectiveState, Turn

CRITERION_SOFT_LIMIT = 3
MAX_TURNS_PER_CRITERION = 6
MAX_STAGNANT_TURNS = 2


def progress_for(state: ObjectiveState, key: str) -> CriterionProgress:
    return state.criterion_progress.setdefault(key, CriterionProgress())


def record_progress(state: ObjectiveState, turn: Turn) -> None:
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
        progress.stop_reason = _stop_reason(progress)
        if (turn.judgment.explicit_inability and item.observation == "NO_EVIDENCE"
                and (turn.question_depth == 1 or turn.action == Action.EASIER)):
            progress.stop_reason = "NO_PROGRESS"


def _new_case(progress: CriterionProgress, turn: Turn, observation: str) -> bool:
    if observation not in {"SUPPORTS", "CONTRADICTS"} or not turn.question.evidence_scope.strip():
        return False
    case = f"{turn.question_depth}:{turn.question.evidence_scope.casefold().strip()}"
    if case in progress.observed_cases:
        return False
    progress.observed_cases.append(case)
    return True


def _stop_reason(progress: CriterionProgress) -> str | None:
    if progress.turns_spent >= MAX_TURNS_PER_CRITERION:
        return "CRITERION_BUDGET"
    if progress.turns_spent >= CRITERION_SOFT_LIMIT and progress.stagnant_turns >= MAX_STAGNANT_TURNS:
        return "NO_PROGRESS"
    return None
