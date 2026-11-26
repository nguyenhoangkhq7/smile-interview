"""LLM reasoning stage adapter for CV/JD skill pairs."""
from dataclasses import dataclass
import logging
import time
from typing import Any, Dict, List, Optional, Protocol, Tuple

from matching_cv.app.schemas.hetero_graph import Stage4ReasoningRecording
from matching_cv.app.schemas.pipeline import PipelineSemanticReasoning, StageDiagnostic
from matching_cv.app.schemas.semantic_reasoning import SkillPairReasoningResult
from matching_cv.app.schemas.semantic_representation import SemanticRepresentationResponse

logger = logging.getLogger(__name__)


class SkillPairReasoner(Protocol):
    """Interface for reasoning over retrieved CV/JD skill pairs."""

    async def reason_stage3_topk(
        self,
        *,
        stage3_response: Optional[SemanticRepresentationResponse],
        max_pairs: int,
        min_cosine: float,
        selection_strategy: str,
        concurrency: int,
        timeout_seconds: float,
        enable_critic: bool,
        prompt_version: str,
    ) -> Any: ...

    def extract_and_budget_topk_pairs(
        self,
        *,
        stage3_response: SemanticRepresentationResponse,
        max_pairs: int,
        min_cosine: float,
        selection_strategy: str,
    ) -> Tuple[Any, Dict[str, Any]]: ...


@dataclass(frozen=True)
class ReasoningStageOutcome:
    summary: Optional[PipelineSemanticReasoning]
    results: Optional[List[SkillPairReasoningResult]]
    diagnostic: StageDiagnostic
    duration_ms: float


class ReasoningStageError(RuntimeError):
    def __init__(self, cause: Exception, duration_ms: float) -> None:
        super().__init__(str(cause))
        self.cause = cause
        self.duration_ms = duration_ms


class PipelineReasoningStage:
    """Runs live or recorded reasoning and summarizes coverage and outcomes."""

    def __init__(self, reasoner: SkillPairReasoner) -> None:
        self._reasoner = reasoner

    async def execute(
        self,
        *,
        graph_mode: str,
        offline_recording: Optional[Stage4ReasoningRecording],
        stage3_response: Optional[SemanticRepresentationResponse],
        max_pairs: int,
        selection_strategy: str,
        concurrency: int,
        timeout_seconds: float,
        enable_critic: bool,
        include_details: bool,
        run_id: str,
    ) -> ReasoningStageOutcome:
        if graph_mode != "llm_enriched":
            return ReasoningStageOutcome(
                summary=None,
                results=None,
                diagnostic=StageDiagnostic(
                    stage="semantic_reasoning",
                    status="skipped",
                    duration_ms=0.0,
                    error=f"Skipped for {graph_mode} graph_mode",
                ),
                duration_ms=0.0,
            )

        started_at = time.perf_counter()
        if offline_recording is not None:
            logger.info(
                f"[{run_id}] Using offline authentic recording with "
                f"{len(offline_recording.results)} pairs."
            )
            results = offline_recording.results
            duration = (time.perf_counter() - started_at) * 1000.0
            coverage: Dict[str, Any] = {}
            if stage3_response is not None:
                _, coverage = self._reasoner.extract_and_budget_topk_pairs(
                    stage3_response=stage3_response,
                    max_pairs=len(results),
                    min_cosine=0.3,
                    selection_strategy=selection_strategy,
                )
            summary = self._build_summary(
                results=results,
                model_id=offline_recording.model_id,
                prompt_version=offline_recording.prompt_version,
                critic_enabled=offline_recording.critic_enabled,
                evaluated_pairs=len(results),
                failed_pairs=sum(1 for result in results if result.error_status is not None),
                coverage=coverage,
                max_pairs=max_pairs,
                selection_strategy=selection_strategy,
                include_details=include_details,
                offline_fallbacks=True,
            )
        else:
            try:
                batch = await self._reasoner.reason_stage3_topk(
                    stage3_response=stage3_response,
                    max_pairs=max_pairs,
                    min_cosine=0.3,
                    selection_strategy=selection_strategy,
                    concurrency=concurrency,
                    timeout_seconds=timeout_seconds,
                    enable_critic=enable_critic,
                    prompt_version="sprint2-v2",
                )
                duration = (time.perf_counter() - started_at) * 1000.0
                results = batch.results
                coverage = batch.coverage_metrics or {}
                summary = self._build_summary(
                    results=results,
                    model_id=batch.model_id,
                    prompt_version=batch.prompt_version,
                    critic_enabled=enable_critic,
                    evaluated_pairs=batch.evaluated_pairs,
                    failed_pairs=batch.failed_pairs,
                    coverage=coverage,
                    max_pairs=max_pairs,
                    selection_strategy=selection_strategy,
                    include_details=include_details,
                    offline_fallbacks=False,
                )
            except Exception as error:
                duration = (time.perf_counter() - started_at) * 1000.0
                raise ReasoningStageError(error, duration) from error

        return ReasoningStageOutcome(
            summary=summary,
            results=results,
            diagnostic=StageDiagnostic(
                stage="semantic_reasoning",
                status="completed",
                duration_ms=round(duration, 2),
            ),
            duration_ms=round(duration, 2),
        )

    @staticmethod
    def _build_summary(
        *,
        results: List[SkillPairReasoningResult],
        model_id: str,
        prompt_version: str,
        critic_enabled: bool,
        evaluated_pairs: int,
        failed_pairs: int,
        coverage: Dict[str, Any],
        max_pairs: int,
        selection_strategy: str,
        include_details: bool,
        offline_fallbacks: bool,
    ) -> PipelineSemanticReasoning:
        eligible = sum(1 for result in results if result.graph_relation_status == "eligible")
        candidate_only = sum(1 for result in results if result.graph_relation_status == "candidate_only")
        unrelated = sum(1 for result in results if result.relationship == "unrelated")
        uncertain = sum(
            1
            for result in results
            if result.identity == "uncertain" or result.relationship == "uncertain"
        )
        fallback = len(results) if offline_fallbacks else 0

        return PipelineSemanticReasoning(
            model_id=model_id,
            prompt_version=prompt_version,
            critic_enabled=critic_enabled,
            total_pairs_evaluated=evaluated_pairs,
            eligible_relations_count=eligible,
            candidate_only_count=candidate_only,
            unrelated_count=unrelated,
            uncertain_count=uncertain,
            total_retrievable_pairs=coverage.get("total_retrievable_pairs", fallback),
            total_unique_pairs=coverage.get("total_unique_pairs", fallback),
            selected_pairs=coverage.get("selected_pairs", evaluated_pairs if not offline_fallbacks else fallback),
            skipped_by_budget_pairs=coverage.get("skipped_by_budget_pairs", 0),
            failed_pairs=failed_pairs,
            cv_skills_covered=coverage.get("cv_skills_covered", 0),
            cv_skills_total=coverage.get("cv_skills_total", 0),
            cv_skill_coverage_pct=coverage.get("cv_skill_coverage_pct", 0.0),
            jd_skills_covered=coverage.get("jd_skills_covered", 0),
            jd_skills_total=coverage.get("jd_skills_total", 0),
            jd_skill_coverage_pct=coverage.get("jd_skill_coverage_pct", 0.0),
            selection_strategy=coverage.get("selection_strategy", selection_strategy),
            reasoning_budget=max_pairs,
            candidate_coverage_summary=coverage,
            results=[result.model_dump() for result in results] if include_details else None,
        )
