"""Ground blueprint identifiers and allocate a bounded, deterministic initial plan."""
from uuid import NAMESPACE_URL, uuid5
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from contextvars import copy_context
from math import ceil
import re
import hashlib
import json
from time import monotonic

from .models import Blueprint, GroundedRequirement, InterviewConfig, InterviewSkill, Mode, Objective, ObjectiveState
from .depth import DEPTH_DEFINITIONS, ground_depth
from .policy_config import InterviewPolicy
from .provider import AssessmentProvider, encode_context
from .preparation_cache import PreparationCache
from .telemetry import event

BLUEPRINT_BATCH_SIZE = 3
BLUEPRINT_WORKERS = 3

MODE_PATTERNS: dict[str, str] = {
    "DEBUGGING": r"\b(debug|diagnos\w*|troubleshoot\w*|optimi[sz]\w*)\b|chẩn đoán|tối ưu|sửa lỗi",
    "DESIGN": r"\b(design|architect|trade.?offs?)\b|thiết kế|đánh đổi",
    "CODING": r"\b(write|implement|code|program)\b|viết|lập trình",
    "TECHNICAL_EXPLANATION": r"\b(explain|define|describe)\b|giải thích|định nghĩa|mô tả",
    "BEHAVIORAL": r"\b(collaborat\w*|mentor\w*|conflict|stakeholders?)\b|phối hợp|hướng dẫn|xung đột",
}


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
                "skill_id": skill.jd_skill_id,
                "description": task.description if task else f"Đánh giá kiến thức thực hành {skill.jd_skill_id}",
                "required_proficiency": task.required_level if task else skill.required_proficiency,
                "inferred": task is None or task.level_basis != "EXPLICIT",
                "has_task": task is not None,
                "requirement_kind": task.requirement_kind if task else "UNSPECIFIED",
                "jd_evidence_spans": task.evidence_spans if task else skill.jd_evidence_spans,
            }
    return requirements


class BlueprintBuilder:
    def __init__(self, provider: AssessmentProvider, policy: InterviewPolicy | None = None,
                 cache: PreparationCache | None = None):
        self.provider = provider
        self.policy = policy or InterviewPolicy()
        self.cache = cache

    def build(self, skills: list[InterviewSkill]) -> Blueprint:
        requirements = requirements_for(skills)
        items = list(requirements.items())
        batches = [dict(items[index:index + BLUEPRINT_BATCH_SIZE])
                   for index in range(0, len(items), BLUEPRINT_BATCH_SIZE)]
        event("blueprint.started", requirements=len(items), batches=len(batches), workers=BLUEPRINT_WORKERS)
        if len(batches) <= 1:
            results = [self._prepare_batch(1, 1, requirements)]
        else:
            results = self._parallel_batches(batches)
        blueprint = Blueprint(objectives=[objective for batch in results for objective in batch.objectives])
        try:
            return self.validate(blueprint, skills)
        except ValueError:
            if self.cache:
                self.cache.discard([self._batch_context(batch) for batch in batches])
            raise

    def _parallel_batches(self, batches: list[dict[str, GroundedRequirement]]) -> list[Blueprint]:
        executor = ThreadPoolExecutor(max_workers=BLUEPRINT_WORKERS)
        pending = {executor.submit(copy_context().run, self._prepare_batch, index + 1, len(batches), batch): index
                   for index, batch in enumerate(batches)}
        results = {}
        try:
            for future in as_completed(pending):
                results[pending[future]] = future.result()
                event("blueprint.progress", completed=len(results), total=len(batches))
        except Exception:
            # Running batches may still populate the cache; queued calls must not
            # delay a retryable failure or send another burst to the provider.
            executor.shutdown(wait=False, cancel_futures=True)
            raise
        executor.shutdown()
        return [results[index] for index in range(len(batches))]

    def _prepare_batch(self, index: int, total: int, requirements: dict[str, GroundedRequirement]) -> Blueprint:
        started = monotonic()
        event("blueprint.batch_started", batch=index, total=total, requirements=len(requirements))
        try:
            result = self._build_batch(requirements)
            event("blueprint.batch_completed", batch=index, total=total,
                  elapsed_seconds=round(monotonic() - started, 2))
            return result
        except Exception as error:
            event("blueprint.batch_failed", batch=index, total=total, error_type=type(error).__name__,
                  elapsed_seconds=round(monotonic() - started, 2))
            raise

    def _build_batch(self, requirements: dict[str, GroundedRequirement]) -> Blueprint:
        context = self._batch_context(requirements)
        if self.cache:
            return self.cache.get_or_compute(context, lambda: self._generate_batch(context, requirements))
        return self._generate_batch(context, requirements)

    def _batch_context(self, requirements: dict[str, GroundedRequirement]) -> str:
        prompt_requirements = {
            key: {k: v for k, v in req.items() if k != "has_task"}
            for key, req in requirements.items()
        }
        return encode_context({
            "requirements": prompt_requirements, "depth_definitions": DEPTH_DEFINITIONS,
            "allow_extension_probes": self.policy.allow_extension_probes,
        })

    def _generate_batch(self, context: str, requirements: dict[str, GroundedRequirement]) -> Blueprint:
        draft = self.provider.blueprint(context)
        ids = [objective.requirement_id for objective in draft.objectives]
        if len(ids) != len(set(ids)) or set(ids) != set(requirements):
            raise ValueError("Blueprint must cover every requirement exactly once")
        return Blueprint(objectives=[
            Objective.model_validate(objective.model_dump() | {
                "claim": requirements[objective.requirement_id]["description"],
            })
            for objective in draft.objectives
        ])

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
        objective.claim = requirement["description"]
        objective.jd_evidence_spans = requirement["jd_evidence_spans"]
        objective.requirement_kind = requirement["requirement_kind"]
        if not self.policy.allow_extension_probes:
            objective.extension_depth = None
        ground_depth(objective, requirement, self.policy)
        self._validate_modes(objective, requirement)
        self._ground_criteria(objective)

    def _validate_modes(self, objective: Objective, requirement: GroundedRequirement) -> None:
        task_modes = {Mode(mode) for mode, pattern in MODE_PATTERNS.items()
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
        mode = select_mode(obj, config, mode_usage)
        state = ObjectiveState(objective=obj)
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


def select_mode(objective: Objective, config: InterviewConfig, usage: Counter[Mode]) -> Mode:
    if config.mode == "FOCUSED":
        assert config.focused_question_mode is not None
        return config.focused_question_mode
    essential = {i for i, criterion in enumerate(objective.criteria) if criterion.essential}
    task_modes = {Mode(mode) for mode, pattern in MODE_PATTERNS.items()
                  if re.search(pattern, objective.claim, re.IGNORECASE)}
    ranked = sorted(enumerate(objective.suitable_modes), key=lambda entry: (
        -int(entry[1].mode in task_modes),
        -len(essential & set(entry[1].criterion_indices or essential)), usage[entry[1].mode], entry[0],
    ))
    return ranked[0][1].mode


def _rank(objective: Objective, skill: InterviewSkill, policy: InterviewPolicy) -> tuple[int, int, float, float, int, str]:
    core = skill.importance_weight >= policy.core_importance
    return (-int(core), int(objective.requirement_kind == "OPTIONAL"),
            -skill.importance_weight,
            -skill.priority,
            objective.estimated_seconds, objective.objective_id)


def rubric_fingerprint(objective: Objective) -> str:
    """Equal IDs alone do not imply equivalent standards across independently built rubrics."""
    standard = objective.model_dump(include={
        "requirement_id", "target_depth", "criteria", "suitable_modes",
        "extension_depth",
    }, mode="json")
    return hashlib.sha256(json.dumps(standard, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()
