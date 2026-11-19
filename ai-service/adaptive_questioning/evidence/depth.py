"""One shared definition of L1–L4 for planning, routing, generation and judging."""
import re

from .models import Action, GroundedRequirement, Objective, ObjectiveState
from .policy_config import InterviewPolicy

DEPTH_DEFINITIONS = {
    1: "Foundation: recognize, define and explain fundamental concepts",
    2: "Application: independently apply a concept to a concrete bounded task",
    3: "Analysis & Problem Solving: investigate causes, debug and reason through alternatives",
    4: "Design & Trade-offs: design a solution, evaluate constraints and technical trade-offs",
}

DEPTH_PATTERNS: dict[str, int] = {
    r"\b(design|architect|trade.?offs?)\b|thiết kế|đánh đổi": 4,
    r"\b(debug|diagnos\w*|analy[sz]\w*|optimi[sz]\w*|troubleshoot\w*)\b|phân tích|chẩn đoán|tối ưu": 3,
    r"\b(write|implement|build|use|apply|develop|execute)\b|viết|triển khai|sử dụng|vận dụng": 2,
    r"\b(explain|define|describe|identify)\b|giải thích|định nghĩa|mô tả": 1,
}


def ground_depth(objective: Objective, requirement: GroundedRequirement, policy: InterviewPolicy) -> None:
    if (
        requirement["has_task"]
        and objective.depth_evidence_spans
        and objective.depth_basis not in {"TASK_HEURISTIC", "CONFIGURED_FALLBACK"}
    ):
        _validate_task_depth(objective, requirement)
        objective.depth_basis = "TASK_INTERPRETATION"
    else:
        _infer_depth(objective, requirement, policy)
    if objective.extension_depth is not None and objective.extension_depth <= objective.target_depth:
        raise ValueError("Extension depth must exceed the frozen target depth")


def _validate_task_depth(objective: Objective, requirement: GroundedRequirement) -> None:
    description = requirement["description"]
    source = requirement["jd_evidence_spans"]
    if any(not span.strip() or not any(span in text for text in [description, *source])
           for span in objective.depth_evidence_spans):
        raise ValueError("Depth provenance must be grounded in the JD task")
    if not objective.depth_rationale.strip() or objective.depth_basis == "UNSPECIFIED":
        raise ValueError("Task-derived depth requires a rationale and basis")


def _infer_depth(objective: Objective, requirement: GroundedRequirement, policy: InterviewPolicy) -> None:
    matches = [depth for pattern, depth in DEPTH_PATTERNS.items()
               if requirement["has_task"] and re.search(pattern, requirement["description"], re.IGNORECASE)]
    objective.target_depth = max(matches) if matches else policy.fallback_depth
    objective.depth_basis = "TASK_HEURISTIC" if matches else "CONFIGURED_FALLBACK"
    objective.depth_rationale = ("Task verbs matched the configured depth policy" if matches
                                 else "No specific task depth; configured general fallback, not a proficiency conversion")
    objective.depth_evidence_spans = requirement["jd_evidence_spans"] if matches else []


def question_depth(state: ObjectiveState, action: Action) -> int:
    if action == Action.EASIER:
        return max(1, state.objective.target_depth - 1)
    if action == Action.DEEPER:
        return state.objective.extension_depth or state.objective.target_depth
    return state.objective.target_depth
