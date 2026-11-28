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
    Blueprint, Criterion, GroundedRequirement, InterviewConfig, InterviewOpening, InterviewSkill,
    Mode, Objective, ObjectiveState, PriorAttemptContext, SuitableMode,
)
from .depth import DEPTH_DEFINITIONS, ground_depth
from .mode_strategy import default_estimated_seconds
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
    "DESIGN": (
        r"\b(design|architect\w*|trade.?offs?|scalab\w*|high\s+availability|data\s+model\w*|schema\s+design)\b"
        r"|thiết kế|kiến trúc|đánh đổi|phân tán"
    ),
    "CODING": (
        r"\b(?:write(?!\s+(?:docs?|documentation|reports?|emails?|plans?|test\s+cases?|runbooks?)\b)"
        r"|implement(?!\s+(?:ci/?cd|pipelines?|monitoring|workflows?|processes?|policies?|architecture)\b)"
        r"|code|program)\b"
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
                    if objective.estimated_seconds == 120 and objective.suitable_modes:
                        objective.estimated_seconds = default_estimated_seconds(objective.suitable_modes[0].mode)
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
        # Drop ephemeral synthesized behavioral objectives if persisted in a legacy profile blueprint.
        filtered = [
            obj for obj in blueprint.objectives
            if obj.skill_id != BEHAVIORAL_FALLBACK_SKILL_ID or obj.requirement_id in requirements
        ]
        if len(filtered) != len(blueprint.objectives):
            blueprint = Blueprint(objectives=filtered)
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


BEHAVIORAL_FALLBACK_SKILL_ID = "behavioral_competency"


def _is_entry_level_role(role: str) -> bool:
    return bool(re.search(r"\b(?:intern|thực tập|fresher|junior|sinh viên)\b", role, re.IGNORECASE))


def synthesize_behavioral_objectives(
    opening: InterviewOpening | None = None,
    *,
    allow_extension_probes: bool = True,
    limit: int | None = None,
) -> list[Objective]:
    """Synthesize grounded STAR behavioral objectives when a technical JD has no explicit behavioral tasks."""
    role = (opening.role_title.strip() if opening and opening.role_title else "") or "vị trí ứng tuyển"
    entry_level = _is_entry_level_role(role)
    setting = "đồ án, dự án cá nhân hoặc kỳ thực tập" if entry_level else "dự án thực tế"
    templates = [
        (
            "incident_pressure",
            f"Xử lý sự cố kỹ thuật hoặc áp lực tiến độ trong vai trò {role}",
            f"Trình bày một tình huống sự cố hoặc áp lực tiến độ cụ thể từ {setting} và hành động xử lý trực tiếp của bản thân theo khung STAR",
            "Nêu rõ bối cảnh (Situation/Task), hành động cá nhân cụ thể (Action) và kết quả đo được hoặc bài học rút ra (Result).",
            "Chỉ trả lời chung chung không có tình huống thật hoặc chỉ nêu việc nhóm làm mà không rõ vai trò cá nhân.",
            "Nêu đủ tình huống cụ thể, hành động trực tiếp của bản thân và kết quả đạt được.",
            "Đánh giá rõ nguyên nhân gốc, tác động đo lường được và biện pháp phòng ngừa tái diễn.",
        ),
        (
            "team_collaboration",
            f"Phối hợp nhóm và giải quyết bất đồng quan điểm kỹ thuật cho vai trò {role}",
            f"Mô tả một lần bất đồng giải pháp hoặc phối hợp chéo nhóm trong {setting} và cách thống nhất phương án cuối cùng",
            "Nêu rõ mâu thuẫn/ràng buộc, cách lắng nghe và lập luận của bản thân, cùng kết quả thống nhất của nhóm.",
            "Né tránh mâu thuẫn, đổ lỗi cho đồng đội hoặc không nêu cách giải quyết cụ thể.",
            "Trình bày khách quan hai phía, cách trao đổi dựa trên dữ kiện và kết quả tích cực.",
            "Chủ động xây dựng thỏa thuận đánh đổi rõ ràng và cải thiện quy trình làm việc của nhóm.",
        ),
        (
            "ownership_learning",
            f"Chủ động sở hữu đầu việc và học nhanh công nghệ mới cho vai trò {role}",
            f"Kể một ví dụ tự nhận trách nhiệm cho đầu việc khó hoặc công nghệ mới trong {setting} để hoàn thành mục tiêu",
            "Trình bày mục tiêu ban đầu, các bước tự tìm hiểu/triển khai và kết quả thực tế bàn giao.",
            "Chỉ làm theo hướng dẫn từng bước, thiếu dẫn chứng hành động chủ động hoặc kết quả cụ thể.",
            "Thể hiện rõ tính chủ động, kế hoạch xử lý và kết quả bàn giao cụ thể.",
            "Chủ động phát hiện rủi ro sớm, chia sẻ tài liệu hoặc nâng chất lượng cho cả nhóm.",
        ),
    ]
    selected_templates = templates[:limit] if limit is not None else templates
    objectives: list[Objective] = []
    for slug, claim, desc, expected, below, at_target, above in selected_templates:
        req_id = f"{BEHAVIORAL_FALLBACK_SKILL_ID}:{slug}"
        obj_id = str(uuid5(NAMESPACE_URL, req_id))
        objectives.append(Objective(
            requirement_id=req_id,
            objective_id=obj_id,
            skill_id=BEHAVIORAL_FALLBACK_SKILL_ID,
            claim=claim,
            target_depth=2,
            extension_depth=3 if allow_extension_probes else None,
            depth_basis="CONFIGURED_FALLBACK",
            depth_rationale="Mục tiêu hành vi chuẩn STAR bổ sung khi JD không nêu rõ nhiệm vụ ứng xử.",
            requirement_kind="UNSPECIFIED",
            jd_evidence_spans=[claim],
            criteria=[Criterion(
                criterion_id=f"{obj_id}:c1",
                description=desc,
                expected_evidence=expected,
                below_target=below,
                at_target=at_target,
                above_target=above,
                essential=True,
            )],
            suitable_modes=[SuitableMode(mode=Mode.BEHAVIORAL, criterion_indices=[0])],
            estimated_seconds=150,
        ))
    return objectives


def plan(
    blueprint: Blueprint,
    skills: list[InterviewSkill],
    config: InterviewConfig,
    policy: InterviewPolicy | None = None,
    prior_attempts: PriorAttemptContext | None = None,
    opening: InterviewOpening | None = None,
) -> tuple[dict[str, ObjectiveState], list[str]]:
    policy = policy or InterviewPolicy()
    by_skill = {skill.jd_skill_id: skill for skill in skills}
    prior_map = prior_attempts.objective_assessments if prior_attempts else {}
    focus_skills = {sid.strip() for sid in config.focus_skill_ids if sid and sid.strip()}
    mastered = set() if config.include_mastered_skills else (
        set(prior_attempts.mastered_skill_ids) if prior_attempts else set()
    )
    if focus_skills and config.session_purpose == "PRACTICE":
        mastered -= focus_skills
    source_objectives = list(blueprint.objectives)
    has_behavioral = any(any(m.mode == Mode.BEHAVIORAL for m in obj.suitable_modes) for obj in source_objectives)
    needs_focused_behavioral = config.focused_question_mode == Mode.BEHAVIORAL and not has_behavioral
    needs_mixed_behavioral = (
        config.mode == "MIXED"
        and config.include_behavioral_in_mixed
        and config.max_questions >= 4
        and not has_behavioral
        and (not focus_skills or BEHAVIORAL_FALLBACK_SKILL_ID in focus_skills)
    )
    if needs_focused_behavioral or needs_mixed_behavioral:
        synthesized = synthesize_behavioral_objectives(
            opening,
            allow_extension_probes=policy.allow_extension_probes,
            limit=1 if needs_mixed_behavioral else None,
        )
        source_objectives.extend(synthesized)
        by_skill.setdefault(
            BEHAVIORAL_FALLBACK_SKILL_ID,
            InterviewSkill(
                jd_skill_id=BEHAVIORAL_FALLBACK_SKILL_ID,
                jd_skill_name="Kinh nghiệm & Ứng xử (STAR)",
                required_proficiency=2.0,
                priority=0.0 if needs_mixed_behavioral else 0.8,
                importance_weight=max(policy.core_importance, 0.7) if needs_mixed_behavioral else 0.8,
            ),
        )
    ranked = sorted(
        source_objectives,
        key=lambda obj: _rank(obj, by_skill[obj.skill_id], prior_map),
    )
    first, additional, seen = [], [], set()
    for objective in ranked:
        if (focus_skills and objective.skill_id not in focus_skills
                and not (needs_focused_behavioral and objective.skill_id == BEHAVIORAL_FALLBACK_SKILL_ID)):
            additional.append(objective)
            continue
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
    return _allocate(
        ordered, core_skills, config, policy, mastered,
        focus_skills=focus_skills,
        allow_synthesized_behavioral=needs_focused_behavioral,
    )


def plan_recheck(blueprint: Blueprint, objective_id: str, criterion_id: str) -> tuple[dict[str, ObjectiveState], list[str]]:
    objective = next((obj for obj in blueprint.objectives if obj.objective_id == objective_id), None)
    if objective is None:
        raise ValueError("Mục tiêu kiểm chứng không còn thuộc hồ sơ")
    index = next((i for i, c in enumerate(objective.criteria) if c.criterion_id == criterion_id), None)
    modes = [m for m in objective.suitable_modes if not m.criterion_indices or index in m.criterion_indices]
    if index is None or not modes:
        raise ValueError("Tiêu chí không có dạng câu hỏi phù hợp")
    state = ObjectiveState(objective=objective, selected_mode=modes[0].mode, active_criterion_id=criterion_id)
    return {objective_id: state}, [objective_id]


def _fits_session(objective: Objective, config: InterviewConfig) -> bool:
    focused_mode = config.focused_question_mode
    compatible = focused_mode is None or any(item.mode == focused_mode for item in objective.suitable_modes)
    return compatible and objective.estimated_seconds <= config.duration_seconds


def _essential_turn_cost(objective: Objective) -> int:
    return max(1, sum(1 for criterion in objective.criteria if criterion.essential))


def _allocate(
    objectives: list[Objective],
    core_skills: set[str],
    config: InterviewConfig,
    policy: InterviewPolicy,
    mastered: set[str],
    *,
    focus_skills: set[str] | None = None,
    allow_synthesized_behavioral: bool = False,
) -> tuple[dict[str, ObjectiveState], list[str]]:
    states, queue, remaining = {}, [], config.duration_seconds
    mode_usage: Counter[Mode] = Counter()
    initial_limit = min(
        config.max_questions,
        max(len(core_skills), 1, config.max_questions - ceil(config.max_questions * policy.reserve_followup_fraction)),
    )
    planned_slots = 0
    compatible = 0
    skill_matched = 0
    queued_core_objectives = 0
    mastered_in_mode = False
    for obj in objectives:
        modes = [item.mode for item in obj.suitable_modes]
        if (focus_skills and obj.skill_id not in focus_skills
                and not (allow_synthesized_behavioral and obj.skill_id == BEHAVIORAL_FALLBACK_SKILL_ID)):
            states[obj.objective_id] = ObjectiveState(
                objective=obj, lifecycle="EXCLUDED",
                excluded_reason="SKILL_FILTER", stop_reason="SKILL_FILTER",
            )
            continue
        skill_matched += 1
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
        turn_cost = _essential_turn_cost(obj)
        exceeds_slots = bool(queue) and (planned_slots + turn_cost > initial_limit)
        reason = _check_plan_exclusion(
            mode, modes, exceeds_slots, obj.estimated_seconds, remaining, reserve_for_core,
        )
        if reason:
            state.lifecycle, state.excluded_reason = "EXCLUDED", reason
        else:
            state.selected_mode = mode
            queue.append(obj.objective_id)
            planned_slots += turn_cost
            queued_core_objectives += int(is_core)
            mode_usage[mode] += 1
            remaining -= obj.estimated_seconds
        states[obj.objective_id] = state
    if focus_skills and not skill_matched:
        raise ValueError("Không có mục tiêu phù hợp với các kỹ năng đã chọn")
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
    exceeds_slots: bool,
    estimated_seconds: int,
    remaining_seconds: int,
    reserve_for_core: bool,
) -> str | None:
    if mode not in modes:
        return "MODE_FILTER"
    if exceeds_slots or estimated_seconds > remaining_seconds or reserve_for_core:
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
