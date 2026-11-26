import datetime
from typing import List, Optional
from skill_gap.domain.models import (
    ExtractedCVSkill,
    JobBlock,
    ProficiencyResult,
    SpanMapping,
    UNASSIGNED_JOB_ID,
)
from skill_gap.adapters.config import AppConfig
from skill_gap.adapters.llm_client import LLMClient
from skill_gap.pipeline.orchestrator import SkillGapOrchestrator
from skill_gap.baselines.base import (
    BaselineInput,
    BaselineMethod,
    BaselineOutputField,
    BaselineSkillResult,
)
from skill_gap.baselines.module_adapter import SkillGapModuleAdapter


class RawDurationEstimator:
    """
    Raw Cumulative Duration Proficiency Estimator (B-RawDuration).

    Mathematical formulation:
        raw_months = sum(job_months(j) for j in jobs_with_evidence)
        P_CV = piecewise_linear_interpolation(raw_months, config.normalization.milestones_months)

    Theoretical foundation & Ablation equivalence:
        This estimator represents the combined ablation of three core components:
        1. Ablation A1 (w/o Seniority Weighting): Role multiplier is fixed at 1.0 (no Supervised 0.8 discount).
        2. Ablation A2 (w/o Context Density): Context multiplier is fixed at 1.0 (no LIST_ONLY 0.3 penalty).
        3. Ablation A3 (w/o Interval Union): Job durations are summed directly, causing double-counting
           when employment dates overlap.

        Reuses the exact interpolation milestones from config.normalization.milestones_months without copying constants.
    """

    def __init__(self, config: Optional[AppConfig] = None) -> None:
        self.config = config or AppConfig()

    def _get_reference_date(self) -> datetime.date:
        ref_str = self.config.get_reference_date()
        try:
            return datetime.datetime.strptime(ref_str, "%Y-%m-%d").date()
        except ValueError:
            return datetime.date(2024, 6, 1)

    def _parse_date(self, date_str: Optional[str], ref_date: datetime.date) -> datetime.date:
        if not date_str:
            return ref_date
        try:
            return datetime.datetime.strptime(date_str, "%Y-%m").date()
        except ValueError:
            return ref_date

    def _map_experience_to_proficiency(self, effective_months: float) -> float:
        """Piecewise linear interpolation mapping using milestones from config."""
        milestones = sorted(self.config.normalization.milestones_months.items())
        for i in range(len(milestones) - 1):
            m1, s1 = milestones[i]
            m2, s2 = milestones[i + 1]
            if m1 <= effective_months <= m2:
                raw_p = s1 + (effective_months - m1) * (s2 - s1) / (m2 - m1)
                return min(5.0, max(1.0, float(raw_p)))
        return float(milestones[-1][1])

    def estimate(
        self,
        skill: ExtractedCVSkill,
        mappings: List[SpanMapping],
        job_blocks: List[JobBlock],
    ) -> ProficiencyResult:
        jobs_dict = {jb.job_id: jb for jb in job_blocks}
        ref_date = self._get_reference_date()

        skill_mappings = [m for m in mappings if m.span in skill.evidence_spans]
        job_ids = {m.job_id for m in skill_mappings if m.job_id != UNASSIGNED_JOB_ID}

        latest_end_date: Optional[datetime.date] = None

        if not job_ids:
            # Only unassigned spans (e.g. certificates, courses) -> baseline 6 months (Level 2.0)
            raw_months = 6.0 if skill_mappings else 0.0
        else:
            raw_months = 0.0
            for j_id in job_ids:
                job = jobs_dict.get(j_id)
                if not job or not job.start_date:
                    continue

                s_dt = self._parse_date(job.start_date, ref_date)
                e_dt = self._parse_date(job.end_date, ref_date)
                if e_dt < s_dt:
                    continue

                if latest_end_date is None or e_dt > latest_end_date:
                    latest_end_date = e_dt

                # Inclusive raw calendar months: (end_y - start_y)*12 + (end_m - start_m) + 1
                job_months = (e_dt.year - s_dt.year) * 12 + (e_dt.month - s_dt.month) + 1
                raw_months += float(job_months)

        final_proficiency = self._map_experience_to_proficiency(raw_months)

        recency_flag = False
        if latest_end_date:
            delta_years = max(0.0, (ref_date - latest_end_date).days / 365.25)
            if delta_years > self.config.recency_years_threshold:
                recency_flag = True

        return ProficiencyResult(
            skill_id=skill.skill_id,
            proficiency=final_proficiency,
            c_evidence=1.0,
            effective_months=raw_months,
            recency_flag=recency_flag,
            degraded=False,
            flags=["raw_duration_estimator"],
        )


class RawDurationBaseline(BaselineMethod):
    """
    B-RawDuration Baseline:
    Encapsulates the complete SkillGap pipeline but injects RawDurationEstimator
    to evaluate the impact of multi-factor modeling vs naive raw tenure accumulation.
    """

    def __init__(
        self,
        llm_client: LLMClient,
        config: Optional[AppConfig] = None,
        name: str = "B-RawDuration",
    ) -> None:
        self._name = name
        self._config = config or AppConfig()
        self._llm_client = llm_client
        self._raw_estimator = RawDurationEstimator(config=self._config)
        self._orchestrator = SkillGapOrchestrator(
            llm_client=self._llm_client,
            config=self._config,
            estimator=self._raw_estimator,
        )
        self._produces = frozenset(
            {
                BaselineOutputField.ALIGNMENT,
                BaselineOutputField.P_JD,
                BaselineOutputField.P_CV,
                BaselineOutputField.GAP_MAGNITUDE,
                BaselineOutputField.PRIORITY,
            }
        )

    @property
    def name(self) -> str:
        return self._name

    @property
    def produces(self) -> frozenset[BaselineOutputField]:
        return self._produces

    @property
    def requires_llm(self) -> bool:
        return True

    @property
    def estimated_llm_calls_per_pair(self) -> int:
        return 2

    def run(self, input_data: BaselineInput) -> List[BaselineSkillResult]:
        raw_results = self._orchestrator.run_pipeline(
            cv_text=input_data.cv_text,
            jd_text=input_data.jd_text,
            cv_skills=input_data.cv_skills,
            jd_skills=input_data.jd_skills,
            match_results=input_data.match_results,
        )
        return SkillGapModuleAdapter.adapt_all(raw_results, baseline_name=self._name)
