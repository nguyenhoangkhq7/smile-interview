"""Ground blueprint identifiers and allocate a bounded, deterministic initial plan."""
from uuid import NAMESPACE_URL, uuid5
from collections import Counter
from math import ceil
import re
import hashlib
import json

from .models import Blueprint, GroundedRequirement, InterviewConfig, InterviewSkill, Mode, Objective, ObjectiveState
from .depth import DEPTH_DEFINITIONS, ground_depth
from .policy_config import InterviewPolicy
from .provider import AssessmentProvider, encode_context


def requirements_for(skills: list[InterviewSkill]) -> dict[str, GroundedRequirement]:
    requirements: dict[str, GroundedRequirement] = {}
    if len({skill.jd_skill_id for skill in skills}) != len(skills):
        raise ValueError("Duplicate skill identifiers")
    for skill in skills:
        tasks = skill.job_tasks or [None]
        for task in tasks:
            if task and (not task.description.strip() or not task.evidence_spans
                         or any(not span.strip() for span in task.evidence_spans)):
                raise ValueError("Task requires nonempty JD evidence and description")
            task_key = (task.task_id or str(uuid5(NAMESPACE_URL, task.description))) if task else "inferred"
            key = f"{skill.jd_skill_id}:{task_key}"
            if key in requirements:
                raise ValueError("Duplicate task identifiers")
            requirements[key] = {
                "requirement_id": key, "skill_id": skill.jd_skill_id,
                "description": task.description if task else f"Đánh giá kiến thức thực hành {skill.jd_skill_id}",
                "required_proficiency": task.required_level if task else skill.required_proficiency,
                "inferred": task is None or task.level_basis != "EXPLICIT",
                "has_task": task is not None,
                "requirement_kind": task.requirement_kind if task else "UNSPECIFIED",
                "jd_evidence_spans": task.evidence_spans if task else skill.jd_evidence_spans,
            }
    return requirements


class BlueprintBuilder:
    def __init__(self, provider: AssessmentProvider, policy: InterviewPolicy | None = None):
        self.provider = provider
        self.policy = policy or InterviewPolicy()

    def build(self, skills: list[InterviewSkill]) -> Blueprint:
        requirements = requirements_for(skills)
        blueprint = self.provider.blueprint(encode_context({"requirements": requirements, "depth_definitions": DEPTH_DEFINITIONS}))
        return self.validate(blueprint, skills)

    def validate(self, blueprint: Blueprint, skills: list[InterviewSkill]) -> Blueprint:
        requirements = requirements_for(skills)
        ids = [obj.requirement_id for obj in blueprint.objectives]
        if len(ids) != len(set(ids)) or set(ids) != set(requirements):
            raise ValueError("Blueprint must cover every requirement exactly once")
        for objective in blueprint.objectives:
            self._ground(objective, requirements[objective.requirement_id])
        return blueprint

    def _ground(self, objective: Objective, requirement: GroundedRequirement) -> None:
        if objective.skill_id != requirement["skill_id"]:
            raise ValueError("Blueprint changed the requirement skill")
        objective.objective_id = str(uuid5(NAMESPACE_URL, objective.requirement_id))
        objective.required_proficiency = requirement["required_proficiency"]
        objective.claim = requirement["description"]
        objective.inferred = requirement["inferred"]
        objective.jd_evidence_spans = requirement["jd_evidence_spans"]
        objective.requirement_kind = requirement["requirement_kind"]
        ground_depth(objective, requirement, self.policy)
        self._validate_modes(objective, requirement)
        self._ground_criteria(objective)

    def _validate_modes(self, objective: Objective, requirement: GroundedRequirement) -> None:
        task_modes = {Mode(mode) for mode, pattern in self.policy.mode_patterns.items()
                      if requirement["has_task"] and re.search(pattern, objective.claim, re.IGNORECASE)}
        if task_modes and not task_modes.intersection(item.mode for item in objective.suitable_modes):
            raise ValueError("Suitable modes do not cover the JD task intent")
        if len({item.mode for item in objective.suitable_modes}) != len(objective.suitable_modes):
            raise ValueError("Duplicate suitable modes")
        for item in objective.suitable_modes:
            if len(set(item.criterion_indices)) != len(item.criterion_indices) or any(
                    index < 0 or index >= len(objective.criteria) for index in item.criterion_indices):
                raise ValueError("Invalid mode criterion coverage")

    @staticmethod
    def _ground_criteria(objective: Objective) -> None:
        if not any(criterion.essential for criterion in objective.criteria):
            raise ValueError("An objective must have an essential criterion")
        for index, criterion in enumerate(objective.criteria):
            criterion.criterion_id = f"{objective.objective_id}:c{index + 1}"
        if objective.extension_depth is not None:
            # Extension anchors are frozen before interviewing, never invented by Judge.
            if any(c.above_target.strip().casefold() == c.at_target.strip().casefold() for c in objective.criteria if c.essential):
                raise ValueError("Extension must have a distinct higher standard")
            objective.extension_criterion_ids = [c.criterion_id for c in objective.criteria if c.essential]
        else:
            objective.extension_criterion_ids = []


def plan(blueprint: Blueprint, skills: list[InterviewSkill], config: InterviewConfig,
         policy: InterviewPolicy | None = None) -> tuple[dict[str, ObjectiveState], list[str]]:
    policy = policy or InterviewPolicy()
    by_skill = {skill.jd_skill_id: skill for skill in skills}
    ranked = sorted(blueprint.objectives, key=lambda obj: _rank(obj, by_skill[obj.skill_id], policy))
    # First pass across skills before additional objectives of the same skill.
    first, additional, seen = [], [], set()
    for objective in ranked:
        (additional if objective.skill_id in seen else first).append(objective)
        seen.add(objective.skill_id)
    return _allocate(first + additional, by_skill, config, policy)


def _allocate(
    objectives: list[Objective],
    by_skill: dict[str, InterviewSkill],
    config: InterviewConfig,
    policy: InterviewPolicy,
) -> tuple[dict[str, ObjectiveState], list[str]]:
    states, queue, remaining = {}, [], config.duration_seconds
    mode_usage: Counter[Mode] = Counter()
    core_skills = {
        obj.skill_id for obj in objectives
        if by_skill[obj.skill_id].importance_weight >= policy.core_importance
        and obj.requirement_kind != "OPTIONAL"
    }
    initial_limit = min(
        config.max_questions,
        max(len(core_skills), 1, config.max_questions - ceil(config.max_questions * policy.reserve_followup_fraction)),
    )
    compatible = 0
    for obj in objectives:
        modes = [item.mode for item in obj.suitable_modes]
        mode, mode_reason = select_mode(obj, config, policy, mode_usage)
        state = ObjectiveState(
            objective=obj,
            current_question_depth=obj.target_depth,
            mode_selection_reason=mode_reason,
        )
        compatible += int(mode in modes)
        optional_reserve = (
            bool(core_skills)
            and obj.requirement_kind == "OPTIONAL"
            and by_skill[obj.skill_id].importance_weight < policy.core_importance
            and len(queue) * config.max_questions_per_objective >= config.max_questions
        )
        reason = _check_plan_exclusion(mode, modes, len(queue), initial_limit, obj.estimated_seconds, remaining, optional_reserve)
        if reason:
            state.lifecycle, state.excluded_reason = "EXCLUDED", reason
        else:
            state.selected_mode = mode
            queue.append(obj.objective_id)
            mode_usage[mode] += 1
            remaining -= obj.estimated_seconds
        states[obj.objective_id] = state
    if not compatible:
        raise ValueError("Không có mục tiêu phù hợp dạng phỏng vấn đã chọn")
    if not queue:
        raise ValueError("Thời lượng không đủ cho một mục tiêu; hãy tăng thời lượng")
    return states, queue


def _check_plan_exclusion(
    mode: Mode,
    modes: list[Mode],
    queue_len: int,
    initial_limit: int,
    estimated_seconds: int,
    remaining_seconds: int,
    optional_reserve: bool,
) -> str | None:
    if mode not in modes:
        return "MODE_FILTER"
    if queue_len >= initial_limit or estimated_seconds > remaining_seconds or optional_reserve:
        return "PLAN_BUDGET"
    return None


def select_mode(objective: Objective, config: InterviewConfig, policy: InterviewPolicy,
                usage: Counter[Mode]) -> tuple[Mode, str]:
    if config.mode == "FOCUSED":
        assert config.focused_question_mode is not None
        return config.focused_question_mode, "User-selected focused mode"
    essential = {i for i, criterion in enumerate(objective.criteria) if criterion.essential}
    task_modes = {Mode(mode) for mode, pattern in policy.mode_patterns.items()
                  if re.search(pattern, objective.claim, re.IGNORECASE)}
    ranked = sorted(enumerate(objective.suitable_modes), key=lambda entry: (
        -int(entry[1].mode in task_modes),
        -len(essential & set(entry[1].criterion_indices or essential)), usage[entry[1].mode], entry[0],
    ))
    chosen = ranked[0][1]
    return chosen.mode, f"JD task fit, essential criterion coverage, then mode coverage: {chosen.rationale}"


def _rank(objective: Objective, skill: InterviewSkill, policy: InterviewPolicy) -> tuple[int, int, float, float, int, str]:
    core = skill.importance_weight >= policy.core_importance
    return (-int(core), int(objective.requirement_kind == "OPTIONAL"),
            -skill.importance_weight,
            -skill.priority,
            objective.estimated_seconds, objective.objective_id)


def rubric_fingerprint(objective: Objective) -> str:
    """Equal IDs alone do not imply equivalent standards across independently built rubrics."""
    standard = objective.model_dump(include={
        "requirement_id", "required_proficiency", "target_depth", "criteria", "suitable_modes",
        "extension_depth", "extension_criterion_ids", "rubric_version",
    }, mode="json")
    return hashlib.sha256(json.dumps(standard, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()
