"""Ground blueprint identifiers and allocate a bounded, deterministic initial plan."""
from uuid import NAMESPACE_URL, uuid5
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from contextvars import copy_context
import logging
from math import ceil
import re
import hashlib
import json
from time import monotonic
from pydantic import ValidationError

from .models import (
    Blueprint, GroundedRequirement, InterviewConfig, InterviewOpening, InterviewSkill,
    Mode, Objective, ObjectiveState, PriorAttemptContext,
)
from .depth import DEPTH_DEFINITIONS, ground_depth
from .policy_config import InterviewPolicy
from .provider import AssessmentProvider, encode_context
from .preparation_cache import PreparationCache
from .telemetry import event

logger = logging.getLogger(__name__)

BLUEPRINT_BATCH_SIZE = 3
BLUEPRINT_WORKERS = 3
BLUEPRINT_BATCH_ATTEMPTS = 2
MAX_JD_DOMAIN_SUMMARY_CHARS = 300
MASTERED_PRIOR_ASSESSMENTS = frozenset({"DEMONSTRATED_AT_TARGET", "DEMONSTRATED_ABOVE_TARGET"})
ALL_COMPATIBLE_SKILLS_MASTERED = "ALL_COMPATIBLE_SKILLS_MASTERED"

MODE_PATTERNS: dict[str, str] = {
    "DEBUGGING": r"\b(debug|diagnos\w*|troubleshoot\w*|optimi[sz]\w*)\b|chẩn đoán|tối ưu|sửa lỗi",
    "DESIGN": r"\b(design|architect|trade.?offs?)\b|thiết kế|đánh đổi",
    "CODING": (
        r"\b(?:write(?!\s+(?:docs?|documentation|reports?|emails?|plans?|test\s+cases?)\b)|implement|code|program)\b"
        r"|viết(?!\s+(?:tài\s+liệu|báo\s+cáo|test\s+case|kế\s+hoạch|email|quy\s+trình)\b)|lập trình"
    ),
    "TECHNICAL_EXPLANATION": r"\b(explain|define|describe)\b|giải thích|định nghĩa|mô tả",
    "BEHAVIORAL": r"\b(collaborat\w*|mentor\w*|conflict|stakeholders?)\b|phối hợp|hướng dẫn|xung đột",
}


def blueprint_domain_context(opening: InterviewOpening | None) -> dict[str, str]:
    """Extract compact, cache-stable JD role/company/domain metadata for blueprint drafting."""
    if opening is None:
        return {}
    context: dict[str, str] = {}
    if opening.role_title and opening.role_title.strip() and opening.role_title.strip() != "vị trí ứng tuyển":
        context["role_title"] = opening.role_title.strip()
    if opening.company and opening.company.strip():
        context["company"] = opening.company.strip()
    if opening.jd_summary and opening.jd_summary.strip():
        summary = " ".join(opening.jd_summary.split())
        context["jd_domain_summary"] = summary[:MAX_JD_DOMAIN_SUMMARY_CHARS]
    return context


def requirements_for(skills: list[InterviewSkill]) -> dict[str, GroundedRequirement]:
    requirements: dict[str, GroundedRequirement] = {}
    if len({skill.jd_skill_id for skill in skills}) != len(skills):
        raise ValueError("Duplicate skill identifiers")
    for skill in skills:
        tasks = skill.job_tasks or [None]
        skill_display = skill.jd_skill_name.strip() if skill.jd_skill_name else skill.jd_skill_id
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
                "description": task.description if task else f"Đánh giá kiến thức thực hành {skill_display}",
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

    def build(self, skills: list[InterviewSkill], opening: InterviewOpening | None = None) -> Blueprint:
        requirements = requirements_for(skills)
        domain = blueprint_domain_context(opening)
        items = list(requirements.items())
        batches = [dict(items[index:index + BLUEPRINT_BATCH_SIZE])
                   for index in range(0, len(items), BLUEPRINT_BATCH_SIZE)]
        event("blueprint.started", requirements=len(items), batches=len(batches), workers=BLUEPRINT_WORKERS)
        if len(batches) <= 1:
            results = [self._prepare_batch(1, 1, requirements, domain)]
        else:
            results = self._parallel_batches(batches, domain)
        blueprint = Blueprint(objectives=[objective for batch in results for objective in batch.objectives])
        return self.validate(blueprint, skills)

    def _parallel_batches(
        self,
        batches: list[dict[str, GroundedRequirement]],
        domain: dict[str, str],
    ) -> list[Blueprint]:
        executor = ThreadPoolExecutor(max_workers=BLUEPRINT_WORKERS)
        pending = {
            executor.submit(copy_context().run, self._prepare_batch, index + 1, len(batches), batch, domain): index
            for index, batch in enumerate(batches)
        }
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

    def _prepare_batch(
        self,
        index: int,
        total: int,
        requirements: dict[str, GroundedRequirement],
        domain: dict[str, str],
    ) -> Blueprint:
        started = monotonic()
        event("blueprint.batch_started", batch=index, total=total, requirements=len(requirements))
        try:
            result = self._build_batch(requirements, domain)
            event("blueprint.batch_completed", batch=index, total=total,
                  elapsed_seconds=round(monotonic() - started, 2))
            return result
        except Exception as error:
            event("blueprint.batch_failed", batch=index, total=total, error_type=type(error).__name__,
                  elapsed_seconds=round(monotonic() - started, 2))
            raise

    def _build_batch(self, requirements: dict[str, GroundedRequirement], domain: dict[str, str]) -> Blueprint:
        base_payload = self._batch_payload(requirements, domain)
        cache_key_context = encode_context(base_payload)
        if self.cache:
            return self.cache.get_or_compute(
                cache_key_context,
                lambda: self._generate_batch(base_payload, requirements),
            )
        return self._generate_batch(base_payload, requirements)

    def _batch_payload(
        self,
        requirements: dict[str, GroundedRequirement],
        domain: dict[str, str] | None = None,
    ) -> dict[str, object]:
        prompt_requirements = {
            key: {k: v for k, v in req.items() if k != "has_task"}
            for key, req in requirements.items()
        }
        payload: dict[str, object] = {
            "requirements": prompt_requirements,
            "depth_definitions": DEPTH_DEFINITIONS,
            "allow_extension_probes": self.policy.allow_extension_probes,
        }
        if domain:
            payload.update(domain)
        return payload

    def _batch_context(
        self,
        requirements: dict[str, GroundedRequirement],
        domain: dict[str, str] | None = None,
    ) -> str:
        return encode_context(self._batch_payload(requirements, domain))

    def _generate_batch(self, base_payload: dict[str, object], requirements: dict[str, GroundedRequirement]) -> Blueprint:
        payload = dict(base_payload)
        last_error: Exception | None = None
        for attempt in range(BLUEPRINT_BATCH_ATTEMPTS):
            try:
                draft = self.provider.blueprint(encode_context(payload))
                ids = [objective.requirement_id for objective in draft.objectives]
                if len(ids) != len(set(ids)) or set(ids) != set(requirements):
                    raise ValueError("Blueprint must cover every requirement exactly once")
                batch_blueprint = Blueprint(objectives=[
                    Objective.model_validate(objective.model_dump() | {
                        "claim": requirements[objective.requirement_id]["description"],
                    })
                    for objective in draft.objectives
                ])
                # Validate at batch level before caching so valid sibling batches survive a single failure.
                for objective in batch_blueprint.objectives:
                    self._ground(objective, requirements[objective.requirement_id])
                return batch_blueprint
            except (ValidationError, ValueError) as exc:
                last_error = exc
                detail = (
                    str(exc.errors(include_input=False, include_url=False))
                    if isinstance(exc, ValidationError) else str(exc)
                )
                payload["validation_error"] = detail
                logger.warning(
                    "Invalid blueprint batch (attempt %s/%s): %s",
                    attempt + 1, BLUEPRINT_BATCH_ATTEMPTS, detail,
                )
        assert last_error is not None
        if isinstance(last_error, ValidationError):
            raise ValueError(str(last_error)) from last_error
        raise last_error

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


def plan(
    blueprint: Blueprint,
    skills: list[InterviewSkill],
    config: InterviewConfig,
    policy: InterviewPolicy | None = None,
    prior_attempts: PriorAttemptContext | None = None,
) -> tuple[dict[str, ObjectiveState], list[str]]:
    policy = policy or InterviewPolicy()
    by_skill = {skill.jd_skill_id: skill for skill in skills}
    prior_map = prior_attempts.objective_assessments if prior_attempts else {}
    mastered = prior_attempts.mastered_skill_ids if prior_attempts else set()
    ranked = sorted(
        blueprint.objectives,
        key=lambda obj: _rank(obj, by_skill[obj.skill_id], prior_map),
    )
    first, additional, seen = [], [], set()
    for objective in ranked:
        if objective.skill_id in seen or not _fits_session(objective, config):
            additional.append(objective)
        else:
            first.append(objective)
            seen.add(objective.skill_id)
    core_skills = {
        skill_id for skill_id in seen - mastered
        if by_skill[skill_id].importance_weight >= policy.core_importance
    }
    # Stable grouping preserves the first pass across skills within each group.
    ordered = sorted(first + additional, key=lambda obj: obj.skill_id not in core_skills)
    return _allocate(ordered, core_skills, config, policy, mastered)


def _fits_session(objective: Objective, config: InterviewConfig) -> bool:
    focused_mode = config.focused_question_mode
    compatible = focused_mode is None or any(item.mode == focused_mode for item in objective.suitable_modes)
    return compatible and objective.estimated_seconds <= config.duration_seconds


def _allocate(
    objectives: list[Objective],
    core_skills: set[str],
    config: InterviewConfig,
    policy: InterviewPolicy,
    mastered: set[str],
) -> tuple[dict[str, ObjectiveState], list[str]]:
    states, queue, remaining = {}, [], config.duration_seconds
    mode_usage: Counter[Mode] = Counter()
    initial_limit = min(
        config.max_questions,
        max(len(core_skills), 1, config.max_questions - ceil(config.max_questions * policy.reserve_followup_fraction)),
    )
    compatible = 0
    queued_core_objectives = 0
    mastered_in_mode = False
    for obj in objectives:
        modes = [item.mode for item in obj.suitable_modes]
        if obj.skill_id in mastered:
            mastered_in_mode |= config.focused_question_mode is None or config.focused_question_mode in modes
            states[obj.objective_id] = ObjectiveState(
                objective=obj, lifecycle="EXCLUDED",
                excluded_reason="SKILL_ALREADY_MASTERED", stop_reason="SKILL_ALREADY_MASTERED",
            )
            continue
        mode = select_mode(obj, config, mode_usage)
        state = ObjectiveState(objective=obj)
        compatible += int(mode in modes)
        is_core = obj.skill_id in core_skills
        reserve_for_core = (
            not is_core
            and queued_core_objectives * config.max_questions_per_objective >= config.max_questions
        )
        reason = _check_plan_exclusion(
            mode, modes, len(queue), initial_limit, obj.estimated_seconds, remaining, reserve_for_core,
        )
        if reason:
            state.lifecycle, state.excluded_reason = "EXCLUDED", reason
        else:
            state.selected_mode = mode
            queue.append(obj.objective_id)
            queued_core_objectives += int(is_core)
            mode_usage[mode] += 1
            remaining -= obj.estimated_seconds
        states[obj.objective_id] = state
    if not compatible:
        if mastered_in_mode:
            return states, queue
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
    reserve_for_core: bool,
) -> str | None:
    if mode not in modes:
        return "MODE_FILTER"
    if queue_len >= initial_limit or estimated_seconds > remaining_seconds or reserve_for_core:
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


def _rank(
    objective: Objective,
    skill: InterviewSkill,
    prior_assessments: dict[str, str],
) -> tuple[float, float, int, int, str]:
    prior_status = prior_assessments.get(objective.objective_id)
    return (
        -skill.priority,
        -skill.importance_weight,
        int(prior_status in MASTERED_PRIOR_ASSESSMENTS),
        objective.estimated_seconds,
        objective.objective_id,
    )


def rubric_fingerprint(objective: Objective) -> str:
    """Equal IDs alone do not imply equivalent standards across independently built rubrics."""
    standard = objective.model_dump(include={
        "requirement_id", "target_depth", "criteria", "suitable_modes",
        "extension_depth",
    }, mode="json")
    return hashlib.sha256(json.dumps(standard, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()
