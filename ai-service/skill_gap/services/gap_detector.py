from typing import List, Optional, Tuple
from skill_gap.domain.enums import SemanticAlignment, QuestionStrategy
from skill_gap.domain.models import (
    JDRequirement, ProficiencyResult, MatchResult, SkillGapResult,
    ExtractedCVSkill, JobBlock, SpanMapping, UNASSIGNED_JOB_ID
)
from skill_gap.adapters.config import AppConfig
from skill_gap.adapters.llm_client import LLMClient

class GapDetector:
    """
    Service responsible for quantifying skill gaps between JD requirements and candidate proficiencies.
    Implements a clean, robust, deterministic, and explainable linear framework:
    1. Continuous Substitution Factor: s = clip((soft_match - tau_lo) / (tau_hi - tau_lo), 0, 1).
    2. Linear Scale Normalization: gap = max(0, P_JD - s * P_CV) / 4.0, invariant to scale level.
    3. Deterministic Priority: Priority = Severity = w_j * gap_magnitude.
    4. Adaptive Question Strategy: Deterministic classification based on gap and substitution.
    """
    def __init__(self, llm_client: Optional[LLMClient] = None, config: Optional[AppConfig] = None):
        self.llm_client = llm_client
        self.config = config or AppConfig()

    def compute_semantic_alignment(self, soft_match: float) -> SemanticAlignment:
        """Categorizes alignment into MATCH, PARTIAL, or MISSING based on thresholds."""
        if soft_match >= self.config.thresholds.identity_threshold:
            return SemanticAlignment.MATCH
        elif soft_match >= self.config.thresholds.floor_threshold:
            return SemanticAlignment.PARTIAL
        else:
            return SemanticAlignment.MISSING

    def compute_substitution_factor(self, soft_match: float) -> float:
        """
        Computes continuous substitution transferability factor s in [0.0, 1.0].

        Dùng trực tiếp cosine similarity từ SBERT làm hệ số chuyển giao ngữ nghĩa,
        nhất quán với Skill Match Score formula trong nghiên cứu NLP matching:
            SMS = Σ w_i · sim(S_i, R_j)

        Công thức cũ: s = clip((soft - τ_lo) / (τ_hi - τ_lo), 0, 1)
        → Tạo điểm 0 nhân tạo tại τ_lo: kỹ năng PARTIAL vẫn nhận s=0 khi soft=τ_lo.

        Công thức mới:
        - MATCH  (soft ≥ τ_hi): s = 1.0         → full credit, công nhận kỹ năng đúng
        - PARTIAL (τ_lo ≤ soft < τ_hi): s = soft_match → giữ nguyên cosine similarity thực
        - MISSING (soft < τ_lo): s = 0.0         → không tín dụng (handled by gap formula)
        """
        tau_lo = self.config.thresholds.floor_threshold
        tau_hi = self.config.thresholds.identity_threshold
        if soft_match >= tau_hi:
            return 1.0
        if soft_match < tau_lo:
            return 0.0
        return soft_match

    def compute_gap_magnitude(
        self,
        required_level: float,
        candidate_proficiency: float,
        substitution_factor: float,
        alignment: SemanticAlignment
    ) -> float:
        """
        Calculates normalized gap magnitude in [0.0, 1.0].
        Standardized over the true scale width: Max_Scale (5.0) - Min_Scale (1.0) = 4.0.
        """
        if alignment == SemanticAlignment.MISSING:
            return 1.0

        effective_candidate_level = substitution_factor * candidate_proficiency
        shortfall = max(0.0, required_level - effective_candidate_level)
        return min(1.0, max(0.0, shortfall / 4.0))

    def compute_priorities(
        self,
        w_j: float,
        gap_magnitude: float,
        required_level: float = 5.0
    ) -> Tuple[float, float]:
        """
        Computes Severity and Priority using deterministic algebraic formulation
        incorporating requirement depth P_JD normalized by Max Scale (5.0):
        Severity = Priority = w_j * (required_level / 5.0) * gap_magnitude.
        """
        depth_factor = min(1.0, max(0.0, required_level / 5.0))
        severity = w_j * depth_factor * gap_magnitude
        priority = severity
        return severity, priority

    def classify_question_strategy(
        self,
        alignment: SemanticAlignment,
        substitution_factor: float,
        gap_magnitude: float
    ) -> QuestionStrategy:
        """
        Deterministically selects the recommended adaptive interview question strategy.

        Decision tree:
        - MISSING  → LEARNING_AGILITY  (kỹ năng hoàn toàn không có)
        - PARTIAL  → COMPARE_SUBSTITUTE (kỹ năng thay thế được phát hiện, kể cả khi
                     substitution_factor = 0.0 tại ranh giới floor_threshold — gap lớn
                     chính xác vì s ≈ 0, cần hỏi về khả năng chuyển giao)
        - MATCH + gap > 0 → PROBE_DEPTH  (kỹ năng đúng nhưng chưa đủ chiều sâu)
        - MATCH + gap = 0 → NONE         (đã đáp ứng đầy đủ)
        """
        if alignment == SemanticAlignment.MISSING:
            return QuestionStrategy.LEARNING_AGILITY
        elif alignment == SemanticAlignment.PARTIAL:
            return QuestionStrategy.COMPARE_SUBSTITUTE
        elif gap_magnitude > 0.0:
            return QuestionStrategy.PROBE_DEPTH
        else:
            return QuestionStrategy.NONE

    def detect(
        self,
        requirements: List[JDRequirement],
        proficiencies: List[ProficiencyResult],
        matches: List[MatchResult],
        cv_skills: Optional[List[ExtractedCVSkill]] = None,
        job_blocks: Optional[List[JobBlock]] = None,
        span_mappings: Optional[List[SpanMapping]] = None,
        upstream_degraded: bool = False,
        upstream_flags: Optional[List[str]] = None,
    ) -> List[SkillGapResult]:
        req_dict = {r.jd_skill_id: r for r in requirements}
        prof_dict = {p.skill_id: p for p in proficiencies}
        cv_skill_map = {s.skill_id: s for s in cv_skills} if cv_skills else {}
        job_block_map = {j.job_id: j for j in job_blocks} if job_blocks else {}
        span_to_job = {sm.span: sm.job_id for sm in span_mappings} if span_mappings else {}

        results: List[SkillGapResult] = []

        for match in matches:
            req = req_dict.get(match.jd_skill_id)
            if not req:
                continue

            # 1. Semantic alignment & continuous substitution
            alignment = self.compute_semantic_alignment(match.soft_match)
            substitution_factor = self.compute_substitution_factor(match.soft_match)
            is_substituted = (alignment == SemanticAlignment.PARTIAL)

            # Cleanly isolate MISSING skills so rejected SBERT top-1 noise never leaks into P_CV or spans
            if alignment == SemanticAlignment.MISSING:
                prof = None
                effective_matched_cv_skill_id = None
                candidate_proficiency = 1.0
            else:
                prof = prof_dict.get(match.matched_cv_skill_id)
                effective_matched_cv_skill_id = match.matched_cv_skill_id if prof else None
                candidate_proficiency = prof.proficiency if prof else 1.0

            degraded = bool(upstream_degraded or (prof.degraded if prof else False))
            flags: List[str] = []
            if upstream_flags:
                flags.extend(upstream_flags)
            if prof and prof.flags:
                for fl in prof.flags:
                    if fl not in flags:
                        flags.append(fl)

            # Surface factual diagnostic flags for recency decay and keyword-only evidence
            if prof is not None and alignment != SemanticAlignment.MISSING:
                if prof.recency_flag and "recency_decay_warning" not in flags:
                    flags.append("recency_decay_warning")
                if prof.c_evidence == 0.0 and "low_evidence_density" not in flags:
                    flags.append("low_evidence_density")

            # 2. Normalized Linear Gap
            gap_magnitude = self.compute_gap_magnitude(
                required_level=req.required_level,
                candidate_proficiency=candidate_proficiency,
                substitution_factor=substitution_factor,
                alignment=alignment
            )

            # 3. Deterministic priorities with depth scaling (P_JD / 5.0)
            severity, priority = self.compute_priorities(
                w_j=match.w_j,
                gap_magnitude=gap_magnitude,
                required_level=req.required_level
            )

            # 4. Question Strategy Classification
            strategy = self.classify_question_strategy(
                alignment=alignment,
                substitution_factor=substitution_factor,
                gap_magnitude=gap_magnitude
            )

            # 5. Harvest Rich Context for Module 3 (Adaptive Question Generation)
            if alignment == SemanticAlignment.MISSING:
                cv_evidence_spans: List[str] = []
                context_job_str: Optional[str] = None
            else:
                matched_cv_skill = cv_skill_map.get(match.matched_cv_skill_id)
                cv_evidence_spans = matched_cv_skill.evidence_spans if matched_cv_skill else []

                context_jobs: List[str] = []
                for span in cv_evidence_spans:
                    j_id = span_to_job.get(span)
                    if j_id and j_id != UNASSIGNED_JOB_ID and j_id in job_block_map:
                        jb = job_block_map[j_id]
                        dates = f"{jb.start_date or ''} - {jb.end_date or 'Nay'}"
                        summary = f"{jb.title} ({dates})"
                        if summary not in context_jobs:
                            context_jobs.append(summary)
                    elif j_id == UNASSIGNED_JOB_ID:
                        if "Kỹ năng khác (Không thuộc dự án cụ thể)" not in context_jobs:
                            context_jobs.append("Kỹ năng khác (Không thuộc dự án cụ thể)")

                context_job_str = " | ".join(context_jobs) if context_jobs else None

            results.append(SkillGapResult(
                jd_skill_id=match.jd_skill_id,
                semantic_alignment=alignment,
                matched_cv_skill_id=effective_matched_cv_skill_id,
                is_substituted=is_substituted,
                gap_magnitude=gap_magnitude,
                severity=severity,
                priority=priority,
                required_proficiency=req.required_level,
                candidate_proficiency=candidate_proficiency,
                cv_evidence_spans=cv_evidence_spans,
                context_job=context_job_str,
                suggested_strategy=strategy,
                degraded=degraded,
                flags=flags,
                importance_weight=match.w_j,
                jd_reasoning=req.reasoning,
                job_tasks=req.tasks,
                jd_evidence_spans=list(dict.fromkeys(span for task in req.tasks for span in task.evidence_spans)),
                c_evidence=prof.c_evidence if prof else 0.0,
                recency_flag=prof.recency_flag if prof else False,
            ))

        return results
