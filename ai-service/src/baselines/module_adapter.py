from typing import List, Optional

from src.domain.models import SkillGapResult
from src.pipeline.orchestrator import SkillGapOrchestrator
from src.baselines.base import (
    BaselineInput,
    BaselineMethod,
    BaselineOutputField,
    BaselineSkillResult,
)


class SkillGapModuleAdapter:
    """
    Adapter converting native SkillGapResult objects into BaselineSkillResult objects.
    Ensures the proposed pipeline is evaluated through the exact same evaluation harness.
    Preserves all field values without loss or modification.
    """

    @staticmethod
    def adapt(result: SkillGapResult, baseline_name: str = "proposed_module") -> BaselineSkillResult:
        """Convert a single SkillGapResult into a BaselineSkillResult."""
        return BaselineSkillResult(
            jd_skill_id=result.jd_skill_id,
            semantic_alignment=result.semantic_alignment,
            required_proficiency=result.required_proficiency,
            candidate_proficiency=result.candidate_proficiency,
            gap_magnitude=result.gap_magnitude,
            priority=result.priority,
            metadata={
                "baseline_name": baseline_name,
                "matched_cv_skill_id": result.matched_cv_skill_id,
                "is_substituted": result.is_substituted,
                "severity": result.severity,
                "suggested_strategy": (
                    result.suggested_strategy.value
                    if hasattr(result.suggested_strategy, "value")
                    else str(result.suggested_strategy)
                ),
                "cv_evidence_spans": list(result.cv_evidence_spans),
                "context_job": result.context_job,
                "degraded": result.degraded,
                "flags": list(result.flags),
            },
        )

    @classmethod
    def adapt_all(
        cls, results: List[SkillGapResult], baseline_name: str = "proposed_module"
    ) -> List[BaselineSkillResult]:
        """Convert a list of SkillGapResult objects into BaselineSkillResult objects."""
        return [cls.adapt(res, baseline_name=baseline_name) for res in results]


class ProposedModuleBaseline(BaselineMethod):
    """
    Wrapper encapsulating the complete SkillGapOrchestrator as a BaselineMethod.
    Allows running the full proposed module alongside other baselines under the same interface.
    """

    def __init__(self, orchestrator: SkillGapOrchestrator, name: str = "proposed_module") -> None:
        self._orchestrator = orchestrator
        self._name = name
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
