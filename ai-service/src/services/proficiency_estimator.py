import datetime
import threading
from typing import List, Dict, Optional, Tuple, Protocol
from pydantic import BaseModel

from src.domain.enums import RichnessLabel, SkillType, SeniorityLevel
from src.domain.models import ExtractedCVSkill, SpanMapping, JobBlock, ProficiencyResult, SpanRichness, UNASSIGNED_JOB_ID
from src.adapters.config import AppConfig
from src.adapters.llm_client import LLMClient
from src.services.structured_logger import global_audit_logger, SkillAuditLog

class ProficiencyEstimating(Protocol):
    """
    Protocol defining the contract for candidate proficiency estimation (P_CV).
    Enables Dependency Inversion (DIP) so alternative estimators can be injected into the pipeline.
    """
    def estimate(
        self,
        skill: ExtractedCVSkill,
        mappings: List[SpanMapping],
        job_blocks: List[JobBlock]
    ) -> ProficiencyResult:
        ...

class SpanAnalysisList(BaseModel):
    analyses: List[SpanRichness]

class ProficiencyEstimator:
    """
    Service responsible for estimating candidate proficiency (P_CV) for a given skill.
    Implements a clean, deterministic mathematical model:
    1. Multi-factor cumulative experience: Duration * Seniority Multiplier * Context Density.
    2. Interval Union: Merges overlapping timelines to strictly prevent double counting.
    3. Non-penalizing Recency: Flags skills not practiced in the past 3 years without reducing cumulative experience.
    4. Continuous Evidence Coverage: Measures factual context density on a continuous [0, 1] scale.
    5. Cross-Skill Span Deduplication & Batch Pre-Analysis: Analyzes unique assigned spans across all CV skills in a single LLM call.
    """
    def __init__(self, llm_client: LLMClient, config: Optional[AppConfig] = None):
        self.llm_client = llm_client
        self.config = config or AppConfig()
        self._span_cache: Dict[str, SpanRichness] = {}
        self._cache_lock = threading.Lock()

    def _get_reference_date(self) -> datetime.date:
        ref_str = self.config.get_reference_date()
        try:
            return datetime.datetime.strptime(ref_str, "%Y-%m-%d").date()
        except ValueError:
            return datetime.date(2024, 6, 1)

    def _parse_date(self, date_str: Optional[str], ref_date: datetime.date, flags: List[str]) -> datetime.date:
        if not date_str:
            return ref_date
        try:
            return datetime.datetime.strptime(date_str, "%Y-%m").date()
        except ValueError:
            flags.append(f"invalid_date_fallback:{date_str}")
            return ref_date

    def _analyze_span_richness(self, skill: ExtractedCVSkill, skill_mappings: List[SpanMapping]) -> List[SpanRichness]:
        """
        Classifies evidence spans into RICH_CONTEXT, LIST_ONLY, or AMBIGUOUS.
        Uses a thread-safe cross-skill span cache (`self._span_cache`) so spans shared
        across multiple skills or pre-analyzed via `estimate_batch` require 0 redundant LLM calls.
        """
        spans_to_analyze = [m.span for m in skill_mappings if m.job_id != UNASSIGNED_JOB_ID]
        unassigned_spans = [m.span for m in skill_mappings if m.job_id == UNASSIGNED_JOB_ID]

        pre_analyzed: List[SpanRichness] = [
            SpanRichness(span=s, richness_label=RichnessLabel.LIST_ONLY, modifier_score=None)
            for s in unassigned_spans
        ]

        if not spans_to_analyze:
            return pre_analyzed

        with self._cache_lock:
            cached_analyses = [self._span_cache[s] for s in spans_to_analyze if s in self._span_cache]
            uncached_spans = [s for s in spans_to_analyze if s not in self._span_cache]

        if not uncached_spans:
            return pre_analyzed + cached_analyses

        spans_text = "\n".join([f"- {s}" for s in uncached_spans])
        prompt = f"""
Analyze the following evidence spans for the skill "{skill.skill_id}".
For each span, determine its richness label:
- RICH_CONTEXT: The span describes actual project context, practical tasks, or system application.
- LIST_ONLY: The span is just a comma-separated or bulleted keyword list of skills without project context.
- AMBIGUOUS: Unclear if it's applied in a real project or just mentioned.

Spans:
{spans_text}
"""
        try:
            llm_result = self.llm_client.complete(prompt, SpanAnalysisList)
            with self._cache_lock:
                for a in llm_result.analyses:
                    self._span_cache[a.span] = a
                matched_for_skill = [self._span_cache[s] for s in uncached_spans if s in self._span_cache]
            if matched_for_skill:
                return pre_analyzed + cached_analyses + matched_for_skill
            return pre_analyzed + cached_analyses + llm_result.analyses
        except Exception:
            # Fallback to LIST_ONLY on LLM failure
            fallback = [
                SpanRichness(span=s, richness_label=RichnessLabel.LIST_ONLY, modifier_score=None)
                for s in uncached_spans
            ]
            return pre_analyzed + cached_analyses + fallback

    def estimate_batch(
        self,
        skills: List[ExtractedCVSkill],
        mappings: List[SpanMapping],
        job_blocks: List[JobBlock],
    ) -> List[ProficiencyResult]:
        """
        Pre-analyzes all unique assigned evidence spans across all CV skills in a SINGLE batched LLM call,
        populates the thread-safe span cache, and then computes P_CV deterministically for every skill in 0ms.
        """
        if not skills:
            return []

        assigned_spans_set = {m.span for m in mappings if m.job_id != UNASSIGNED_JOB_ID}
        unique_uncached_spans: List[str] = []
        seen = set()

        with self._cache_lock:
            for sk in skills:
                for sp in sk.evidence_spans:
                    if sp in assigned_spans_set and sp not in self._span_cache and sp not in seen:
                        seen.add(sp)
                        unique_uncached_spans.append(sp)

        if unique_uncached_spans:
            skill_ids_str = ", ".join(s.skill_id for s in skills)
            spans_text = "\n".join([f"- {s}" for s in unique_uncached_spans])
            prompt = f"""
Analyze the following evidence spans for the skill "{skill_ids_str}".
For each span, determine its richness label:
- RICH_CONTEXT: The span describes actual project context, practical tasks, or system application.
- LIST_ONLY: The span is just a comma-separated or bulleted keyword list of skills without project context.
- AMBIGUOUS: Unclear if it's applied in a real project or just mentioned.

Spans:
{spans_text}
"""
            try:
                llm_result = self.llm_client.complete(prompt, SpanAnalysisList)
                with self._cache_lock:
                    for a in llm_result.analyses:
                        self._span_cache[a.span] = a
                    for sp in unique_uncached_spans:
                        if sp not in self._span_cache:
                            self._span_cache[sp] = SpanRichness(
                                span=sp, richness_label=RichnessLabel.LIST_ONLY, modifier_score=None
                            )
            except Exception:
                with self._cache_lock:
                    for sp in unique_uncached_spans:
                        self._span_cache[sp] = SpanRichness(
                            span=sp, richness_label=RichnessLabel.LIST_ONLY, modifier_score=None
                        )

        return [self.estimate(skill=sk, mappings=mappings, job_blocks=job_blocks) for sk in skills]

    def _calculate_effective_months(
        self,
        skill_mappings: List[SpanMapping],
        jobs_dict: Dict[str, JobBlock],
        span_analyses: List[SpanRichness],
        ref_date: datetime.date,
        flags: List[str]
    ) -> Tuple[float, Optional[datetime.date]]:
        """
        Calculates cumulative effective months with Seniority and Context density multipliers.
        Uses month-interval union to prevent double counting overlapping jobs.
        """
        analysis_map = {a.span: a.richness_label for a in span_analyses}
        job_span_map: Dict[str, List[str]] = {}
        for m in skill_mappings:
            if m.job_id != UNASSIGNED_JOB_ID:
                job_span_map.setdefault(m.job_id, []).append(m.span)

        if not job_span_map:
            # Only unassigned spans (e.g., certificates, courses) -> baseline 6 months (Level 2.0)
            return 6.0, None

        month_weight_map: Dict[Tuple[int, int], float] = {}
        latest_end_date: Optional[datetime.date] = None

        for j_id, spans in job_span_map.items():
            job = jobs_dict.get(j_id)
            if not job or not job.start_date:
                continue

            s_dt = self._parse_date(job.start_date, ref_date, flags)
            e_dt = self._parse_date(job.end_date, ref_date, flags)
            if e_dt < s_dt:
                flags.append(f"job_{j_id}:end_before_start")
                continue

            if latest_end_date is None or e_dt > latest_end_date:
                latest_end_date = e_dt

            # Seniority multiplier
            sen_key = job.seniority_level.value if isinstance(job.seniority_level, SeniorityLevel) else str(job.seniority_level)
            sen_mult = getattr(self.config.seniority_weights, sen_key, 1.0)

            # 3-Tier Context density multiplier (RICH_CONTEXT=1.0, AMBIGUOUS=0.5, LIST_ONLY=0.3)
            has_rich = any(analysis_map.get(s) == RichnessLabel.RICH_CONTEXT for s in spans)
            has_ambiguous = any(analysis_map.get(s) == RichnessLabel.AMBIGUOUS for s in spans)
            if has_rich:
                density_mult = self.config.context_weights.rich_context
            elif has_ambiguous:
                density_mult = self.config.context_weights.ambiguous
            else:
                density_mult = self.config.context_weights.list_only

            combined_weight = sen_mult * density_mult

            # Monthly timeline interval union (taking maximum weight for overlapping months)
            cur_y, cur_m = s_dt.year, s_dt.month
            end_y, end_m = e_dt.year, e_dt.month

            while (cur_y < end_y) or (cur_y == end_y and cur_m <= end_m):
                m_key = (cur_y, cur_m)
                month_weight_map[m_key] = max(month_weight_map.get(m_key, 0.0), combined_weight)
                cur_m += 1
                if cur_m > 12:
                    cur_m = 1
                    cur_y += 1

        total_effective = sum(month_weight_map.values())
        return total_effective, latest_end_date

    def _map_experience_to_proficiency(self, effective_months: float) -> float:
        """Piecewise linear interpolation mapping effective experience months to 1.0 - 5.0 scale."""
        milestones = sorted(self.config.normalization.milestones_months.items())
        for i in range(len(milestones) - 1):
            m1, s1 = milestones[i]
            m2, s2 = milestones[i + 1]
            if m1 <= effective_months <= m2:
                return s1 + (effective_months - m1) * (s2 - s1) / (m2 - m1)
        return milestones[-1][1]

    def estimate(self, skill: ExtractedCVSkill, mappings: List[SpanMapping], job_blocks: List[JobBlock]) -> ProficiencyResult:
        jobs_dict = {jb.job_id: jb for jb in job_blocks}
        flags: List[str] = []
        ref_date = self._get_reference_date()

        skill_mappings = [m for m in mappings if m.span in skill.evidence_spans]
        span_analyses = self._analyze_span_richness(skill, skill_mappings)

        # 1. Calculate effective cumulative experience
        effective_months, latest_end_date = self._calculate_effective_months(
            skill_mappings=skill_mappings,
            jobs_dict=jobs_dict,
            span_analyses=span_analyses,
            ref_date=ref_date,
            flags=flags
        )

        # 2. Map to Candidate Proficiency P_CV in [1.0, 5.0]
        raw_proficiency = self._map_experience_to_proficiency(effective_months)
        final_proficiency = min(5.0, max(1.0, raw_proficiency))

        # 3. Check Recency (without subtracting candidate's actual experience)
        recency_flag = False
        if latest_end_date:
            delta_years = max(0.0, (ref_date - latest_end_date).days / 365.25)
            if delta_years > self.config.recency_years_threshold:
                recency_flag = True

        # 4. Compute Continuous Evidence Coverage Ratio
        total_spans = len(span_analyses)
        rich_spans = sum(1 for a in span_analyses if a.richness_label == RichnessLabel.RICH_CONTEXT)
        c_evidence = (rich_spans / total_spans) if total_spans > 0 else 0.0
        degraded = len(flags) > 0

        # 5. Structured Audit Logging
        raw_dates = [{"job_id": jb.job_id, "start": jb.raw_start_date or jb.start_date, "end": jb.raw_end_date or jb.end_date} for jb in job_blocks]
        parsed_dates = [{"job_id": jb.job_id, "start": jb.start_date, "end": jb.end_date} for jb in job_blocks]
        global_audit_logger.record(SkillAuditLog(
            skill_id=skill.skill_id,
            raw_dates=raw_dates,
            parsed_dates=parsed_dates,
            effective_months=effective_months,
            c_evidence=c_evidence,
            recency_flag=recency_flag,
            degraded=degraded,
            flags=flags,
            active_params={
                "reference_date": str(ref_date),
                "recency_years_threshold": self.config.recency_years_threshold
            }
        ))

        return ProficiencyResult(
            skill_id=skill.skill_id,
            proficiency=final_proficiency,
            c_evidence=c_evidence,
            effective_months=effective_months,
            recency_flag=recency_flag,
            degraded=degraded,
            flags=flags
        )
