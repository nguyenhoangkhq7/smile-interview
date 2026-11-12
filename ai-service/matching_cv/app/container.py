"""Composition root for the analyze API runtime dependencies."""

from dataclasses import dataclass
from io import BytesIO

from fastapi import UploadFile

from matching_cv.app.core.config import settings
from matching_cv.app.schemas.module1 import Module1Output
from matching_cv.app.services.cached_extraction_service import cached_extraction_service
from matching_cv.app.services.gnn_inference_service import gnn_inference_service
from matching_cv.app.services.pipeline_extraction import PipelineExtractionService
from matching_cv.app.services.pipeline_graph import PipelineGraphService
from matching_cv.app.services.pipeline_inference import PipelineInferenceService
from matching_cv.app.services.pipeline_orchestrator import PipelineOrchestrator
from matching_cv.app.services.pipeline_reasoning_stage import PipelineReasoningStage
from matching_cv.app.services.pipeline_response_mapper import PipelineResponseMapper
from matching_cv.app.services.pipeline_semantic_stage import PipelineSemanticStage
from matching_cv.app.services.pipeline_skill_importance import PipelineSkillImportanceStage
from matching_cv.app.services.pipeline_validation import PipelineInputValidator
from matching_cv.app.services.semantic_representation_service import semantic_representation_service
from matching_cv.app.services.skill_reasoning_service import skill_reasoning_service
from matching_cv.app.services.standardized_output_builder import Module1OutputError, build_module1_output
from matching_cv.app.services.unified_skill_service import unified_skill_service
from matching_cv.research.paper_aligned_gnn.graph_builder import paper_aligned_graph_builder


def _load_skill_importance_evaluator():
    from matching_cv.app.services.production_skill_importance_service import (
        production_skill_importance_service,
    )

    return production_skill_importance_service


def build_pipeline_orchestrator() -> PipelineOrchestrator:
    """Wire production adapters and configuration for the analyze use case."""
    return PipelineOrchestrator(
        graph_builder=paper_aligned_graph_builder,
        input_validator=PipelineInputValidator(settings),
        inference_service=PipelineInferenceService(gnn_inference_service),
        extraction_service=PipelineExtractionService(
            cached_extraction_service,
            unified_skill_service,
        ),
        response_mapper=PipelineResponseMapper(),
        graph_service=PipelineGraphService(
            paper_aligned_graph_builder,
            settings.STAGE3_EMBEDDING_DIM,
        ),
        semantic_stage=PipelineSemanticStage(semantic_representation_service),
        reasoning_stage=PipelineReasoningStage(skill_reasoning_service),
        skill_importance_stage=PipelineSkillImportanceStage(
            _load_skill_importance_evaluator,
            settings.JSI_IMPORTANCE_ENABLED,
        ),
        reasoning_concurrency=settings.PIPELINE_MAX_CONCURRENCY,
        reasoning_timeout_seconds=settings.PIPELINE_LLM_TIMEOUT_SECONDS,
    )


pipeline_orchestrator = build_pipeline_orchestrator()


@dataclass(frozen=True)
class MatchedDocuments:
    cv_text: str
    jd_text: str
    output: Module1Output
    matching_score: float | None = None


async def match_documents(
    cv_text: str, jd_text: str, *, include_compatibility_score: bool = False,
) -> MatchedDocuments:
    """Run the same matching pipeline for text already extracted by Smile Interview."""
    with BytesIO(cv_text.encode("utf-8")) as cv_data, BytesIO(jd_text.encode("utf-8")) as jd_data:
        result = await pipeline_orchestrator.execute_pipeline(
            cv_file=UploadFile(cv_data, filename="candidate.txt"),
            jd_file=UploadFile(jd_data, filename="job-description.txt"),
            enable_skill_importance=True,
            include_compatibility_score=include_compatibility_score,
        )
    context = result._public_context
    if context is None:
        code = result.failure.error_code if result.failure else result.status
        raise Module1OutputError(f"Matching pipeline failed ({code}, run {result.run_id})")
    matching = result.matching_result
    score = None
    if matching is not None:
        score = matching.matching_score / 100 if matching.score_scale == "0_100" else matching.matching_score
    return MatchedDocuments(
        cv_text=context.cv_text,
        jd_text=context.jd_text,
        output=build_module1_output(context),
        matching_score=score,
    )
