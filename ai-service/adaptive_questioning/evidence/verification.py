"""Prepare CV questions from source-backed excerpts without changing the rubric."""
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, wait
from contextvars import copy_context
from dataclasses import dataclass
from time import monotonic

from .assessment import eligible_criteria
from .models import (
    Criterion, InterviewVerification, Objective, ObjectiveState, StartRequest,
    VerificationBatchDraft, VerificationFocus,
)
from .provider import AssessmentProvider, encode_context
from .telemetry import event

PREPARATION_SECONDS = 20
OBJECTIVES_PER_BATCH = 3
PREPARATION_WORKERS = 3


@dataclass(frozen=True)
class VerificationCandidate:
    objective: Objective
    criteria: list[Criterion]
    cv_spans: list[str]
    jd_spans: list[str]


def prepare_verification(
    request: StartRequest, ordered: list[ObjectiveState], provider: AssessmentProvider,
) -> InterviewVerification:
    started = monotonic()
    verification = InterviewVerification()
    candidates = _collect_candidates(request, ordered, verification)
    batches = [candidates[index:index + OBJECTIVES_PER_BATCH]
               for index in range(0, len(candidates), OBJECTIVES_PER_BATCH)]
    for focuses in _prepare_batches(provider, batches, started + PREPARATION_SECONDS):
        verification.focus_by_criterion.update(focuses)
    event("verification.prepared", objectives=len(candidates),
          focuses=len(verification.focus_by_criterion), elapsed_seconds=round(monotonic() - started, 3))
    return verification


def _collect_candidates(
    request: StartRequest, ordered: list[ObjectiveState], verification: InterviewVerification,
) -> list[VerificationCandidate]:
    sources = request.verification_sources
    if sources is None:
        return []
    skills = {skill.jd_skill_id: skill for skill in request.skills}
    candidates = []
    for state in ordered:
        objective = state.objective
        jd_spans = _verified_spans(objective.jd_evidence_spans, sources.jd)
        if jd_spans:
            verification.jd_by_objective[objective.objective_id] = jd_spans[0]
        skill = skills[objective.skill_id]
        if len(candidates) >= request.config.max_questions or skill.semantic_alignment == "MISSING":
            continue
        cv_spans = _verified_spans(skill.cv_evidence_spans, sources.cv)
        if state.selected_mode is None and request.config.focused_question_mode is not None:
            state = state.model_copy(update={"selected_mode": request.config.focused_question_mode})
        eligible = set(eligible_criteria(state))
        criteria = [criterion for criterion in objective.criteria if criterion.criterion_id in eligible]
        if cv_spans and criteria:
            candidates.append(VerificationCandidate(objective, criteria, cv_spans, jd_spans))
    return candidates


def _verified_spans(spans: list[str], sources: dict[str, str]) -> list[str]:
    matched = {}
    for span in spans:
        quote = sources.get(span)
        if quote and quote.strip() and quote.split() == span.split():
            matched[quote] = None
    return list(matched)


def _prepare_batches(
    provider: AssessmentProvider, batches: list[list[VerificationCandidate]], deadline: float,
) -> list[dict[str, VerificationFocus]]:
    if not batches:
        return []
    executor = ThreadPoolExecutor(max_workers=PREPARATION_WORKERS, thread_name_prefix="cv-verification")
    try:
        futures = [executor.submit(copy_context().run, _prepare_batch, provider, batch, deadline)
                   for batch in batches]
        completed, unfinished = wait(futures, timeout=max(0, deadline - monotonic()))
        if unfinished:
            event("verification.timed_out", batches=len(unfinished))
        return [future.result() for future in futures if future in completed]
    finally:
        executor.shutdown(wait=False, cancel_futures=True)


def _prepare_batch(
    provider: AssessmentProvider, candidates: list[VerificationCandidate], deadline: float,
) -> dict[str, VerificationFocus]:
    if monotonic() >= deadline:
        return {}
    try:
        draft = provider.prepare_verification(encode_context(_batch_context(candidates)), deadline=deadline)
        return _ground_drafts(draft, candidates) if monotonic() <= deadline else {}
    except Exception as error:
        event("verification.batch_failed", objectives=len(candidates), error_type=type(error).__name__)
        return {}


def _batch_context(candidates: list[VerificationCandidate]) -> dict:
    return {"objectives": [{
        "skill_id": item.objective.skill_id,
        "task": item.objective.claim,
        "criteria": [{"criterion_id": criterion.criterion_id, "description": criterion.description,
                      "expected_evidence": criterion.expected_evidence} for criterion in item.criteria],
        "cv_spans": item.cv_spans,
        "jd_spans": item.jd_spans,
    } for item in candidates]}


def _ground_drafts(
    draft: VerificationBatchDraft, candidates: list[VerificationCandidate],
) -> dict[str, VerificationFocus]:
    owners = {criterion.criterion_id: candidate for candidate in candidates for criterion in candidate.criteria}
    counts = Counter(item.criterion_id for item in draft.focuses)
    focuses = {}
    for item in draft.focuses:
        candidate = owners.get(item.criterion_id)
        if (candidate is None or counts[item.criterion_id] != 1
                or not 0 <= item.cv_span_index < len(candidate.cv_spans)):
            continue
        if item.jd_span_index is not None and not 0 <= item.jd_span_index < len(candidate.jd_spans):
            continue
        focuses[item.criterion_id] = VerificationFocus(
            cv_excerpt=candidate.cv_spans[item.cv_span_index],
            jd_excerpt=candidate.jd_spans[item.jd_span_index] if item.jd_span_index is not None else None,
            detail_to_verify=item.detail_to_verify,
        )
    return focuses
