"""Pipeline Orchestrator for consolidated end-to-end CV-JD skill inference & graph construction."""
import logging
import time
import uuid
from typing import Any, Dict, List, Optional

from fastapi import UploadFile
from starlette.concurrency import run_in_threadpool

from matching_cv.app.schemas.hetero_graph import (
    GraphConstructionMode,
    Stage4ReasoningRecording,
)
from matching_cv.app.schemas.pipeline import (
    PipelineAnalyzeResponse,
    PipelineDiagnostics,
    PipelineDocumentSummary,
    PipelineExtractionSummary,
    PipelineFailureDetail,
    PipelineGraphSummary,
    PipelineMatchingResult,
    PipelineSemanticReasoning,
    PipelineSemanticRepresentation,
    StageDiagnostic,
)
from matching_cv.app.schemas.semantic_representation import (
    SemanticRepresentationResponse,
)
from matching_cv.app.services.standardized_output_builder import PublicOutputContext
from matching_cv.app.services.pipeline_validation import (
    PipelineInputValidationError,
    PipelineInputValidator,
    SUPPORTED_GRAPH_MODES,
)
from matching_cv.app.services.pipeline_inference import PipelineInferenceService
from matching_cv.app.services.pipeline_extraction import (
    PipelineExtractionError,
    PipelineExtractionService,
)
from matching_cv.app.services.pipeline_response_mapper import PipelineResponseMapper
from matching_cv.app.services.pipeline_graph import (
    GraphBuilder,
    GraphIntegrityError,
    PipelineGraphBuildError,
    PipelineGraphService,
)
from matching_cv.app.services.pipeline_semantic_stage import (
    PipelineSemanticStage,
    SemanticStageError,
)
from matching_cv.app.services.pipeline_reasoning_stage import (
    PipelineReasoningStage,
    ReasoningStageError,
)
from matching_cv.app.services.pipeline_skill_importance import PipelineSkillImportanceStage

logger = logging.getLogger(__name__)

SUPPORTED_PIPELINE_GRAPH_MODES = SUPPORTED_GRAPH_MODES


class PipelineOrchestrator:
    """
    Executes the consolidated CV-JD inference pipeline through Stage 5 Paper-Aligned Graph Construction
    and Stage 6 PaperAlignedHybridGNN Inference.
    Orchestrates in-memory service calls without HTTP self-calls.
    """

    def __init__(
        self,
        *,
        graph_builder: GraphBuilder,
        input_validator: PipelineInputValidator,
        inference_service: PipelineInferenceService,
        extraction_service: PipelineExtractionService,
        response_mapper: PipelineResponseMapper,
        graph_service: PipelineGraphService,
        semantic_stage: PipelineSemanticStage,
        reasoning_stage: PipelineReasoningStage,
        skill_importance_stage: PipelineSkillImportanceStage,
        reasoning_concurrency: int,
        reasoning_timeout_seconds: float,
    ) -> None:
        self.graph_builder: GraphBuilder = graph_builder
        self.input_validator = input_validator
        self.inference_service = inference_service
        self.extraction_service = extraction_service
        self.response_mapper = response_mapper
        self.graph_service = graph_service
        self.semantic_stage = semantic_stage
        self.reasoning_stage = reasoning_stage
        self.skill_importance_stage = skill_importance_stage
        self.reasoning_concurrency = reasoning_concurrency
        self.reasoning_timeout_seconds = reasoning_timeout_seconds

    async def execute_pipeline(
        self,
        cv_file: Optional[UploadFile],
        jd_file: Optional[UploadFile],
        graph_mode: str = "similarity_enriched",
        top_k: int = 5,
        include_details: bool = True,
        include_embeddings: bool = False,
        include_graph: bool = False,
        enable_critic: bool = False,
        reasoning_max_pairs: Optional[int] = None,
        reasoning_selection_strategy: Optional[str] = None,
        offline_recording: Optional[Stage4ReasoningRecording] = None,
        allow_partial: bool = False,
        enable_skill_importance: Optional[bool] = None,
        include_compatibility_score: bool = True,
    ) -> PipelineAnalyzeResponse:
        """
        Execute Stages 0 through 6 sequentially:
        - Stage 0: Input Validation
        - Stage 1: Document Parsing & Metadata
        - Stage 2: Unified Skill Extraction & Deduplication (Offline Cached or Live)
        - Stage 3: SBERT Multilingual Representation & Top-K Retrieval
        - Stage 4: LLM Semantic Relationship Reasoning (Mode C)
        - Stage 5: Heterogeneous Graph Construction & Validation
        - Stage 6: Stage 6E GNN Compatibility Inference & Matching Result
        """
        run_id = str(uuid.uuid4())
        pipeline_start_time = time.perf_counter()
        stage_diagnostics: List[StageDiagnostic] = []
        granular_timings: Dict[str, float] = {}
        all_errors: List[Dict[str, Any]] = []

        logger.info(
            f"[{run_id}] Starting unified pipeline execution: "
            f"graph_mode={graph_mode}, top_k={top_k}, enable_critic={enable_critic}"
        )

        # -------------------------------------------------------------
        # STAGE 0: INPUT VALIDATION
        # -------------------------------------------------------------
        try:
            validated_input = await self.input_validator.validate(
                cv_file=cv_file,
                jd_file=jd_file,
                graph_mode=graph_mode,
                top_k=top_k,
                reasoning_max_pairs=reasoning_max_pairs,
                reasoning_selection_strategy=reasoning_selection_strategy,
            )
        except PipelineInputValidationError as validation_error:
            stage_diagnostics.append(
                StageDiagnostic(
                    stage="input_validation",
                    status="failed",
                    duration_ms=round(validation_error.duration_ms, 2),
                    error=validation_error.diagnostic_error,
                )
            )
            return self._build_failure_response(
                run_id=run_id,
                stage="input_validation",
                error_code=validation_error.error_code,
                message=validation_error.message,
                retryable=False,
                graph_mode=graph_mode,
                stages=stage_diagnostics,
                total_duration_ms=validation_error.duration_ms,
            )

        stage_diagnostics.append(
            StageDiagnostic(
                stage="input_validation",
                status="completed",
                duration_ms=validated_input.duration_ms,
            )
        )
        granular_timings["input_validation_ms"] = validated_input.duration_ms
        eff_max_pairs = validated_input.reasoning_max_pairs
        eff_strategy = validated_input.reasoning_selection_strategy
        cv_ext = validated_input.cv_extension
        jd_ext = validated_input.jd_extension

        # -------------------------------------------------------------
        # STAGE 1 & 2: DOCUMENT PARSING & UNIFIED SKILL EXTRACTION
        # -------------------------------------------------------------
        try:
            extraction_outcome = await self.extraction_service.extract(
                cv_file=cv_file,
                jd_file=jd_file,
                run_id=run_id,
            )
        except PipelineExtractionError as extraction_error:
            logger.error(
                f"[{run_id}] Stage 1/2 extraction failure: {extraction_error.cause}",
                exc_info=True,
            )
            stage_diagnostics.append(
                StageDiagnostic(
                    stage="unified_skill_extraction",
                    status="failed",
                    duration_ms=round(extraction_error.duration_ms, 2),
                    error=str(extraction_error.cause),
                )
            )
            return self._build_failure_response(
                run_id=run_id,
                stage="unified_skill_extraction",
                error_code="EXTRACTION_FAILURE",
                message=f"Trích xuất kỹ năng thất bại: {str(extraction_error.cause)}",
                retryable=True,
                graph_mode=graph_mode,
                stages=stage_diagnostics,
                total_duration_ms=(time.perf_counter() - pipeline_start_time) * 1000.0,
            )

        unified_response = extraction_outcome.unified_response
        matched_pid = extraction_outcome.matched_pair_id
        stage1_cv_text = extraction_outcome.cv_text
        stage1_jd_text = extraction_outcome.jd_text
        t_ext_dur = extraction_outcome.duration_ms
        if unified_response.summary and unified_response.summary.timings_ms:
            granular_timings.update(unified_response.summary.timings_ms)
        granular_timings["stage_unified_extraction_total_ms"] = round(t_ext_dur, 2)

        if unified_response.status == "failed":
            stage_diagnostics.append(
                StageDiagnostic(
                    stage="unified_skill_extraction",
                    status="failed",
                    duration_ms=round(t_ext_dur, 2),
                    error="Unified extraction returned failed status",
                )
            )
            err_msg = "; ".join(e.message for e in unified_response.errors) or "Unknown extraction failure"
            return self._build_failure_response(
                run_id=run_id,
                stage="unified_skill_extraction",
                error_code="EXTRACTION_UNSUCCESSFUL",
                message=f"Trích xuất kỹ năng không thành công: {err_msg}",
                retryable=True,
                graph_mode=graph_mode,
                stages=stage_diagnostics,
                total_duration_ms=(time.perf_counter() - pipeline_start_time) * 1000.0,
            )

        stage_diagnostics.append(
            StageDiagnostic(stage="unified_skill_extraction", status="completed", duration_ms=round(t_ext_dur, 2))
        )

        cv_text, jd_text, documents_summary = self.response_mapper.document_summary(
            unified_response,
            cv_filename=cv_file.filename or "",
            jd_filename=jd_file.filename or "",
            cv_extension=cv_ext,
            jd_extension=jd_ext,
        )
        extraction_summary = self.response_mapper.extraction_summary(
            unified_response,
            include_details=include_details,
        )

        # -------------------------------------------------------------
        # STAGE 3: SBERT MULTILINGUAL REPRESENTATION & RETRIEVAL
        # -------------------------------------------------------------
        stage3_response: Optional[SemanticRepresentationResponse] = None
        semantic_rep_summary: Optional[PipelineSemanticRepresentation] = None

        if graph_mode != "evidence_only":
            try:
                # Loading/downloading SBERT and encoding must not block other requests.
                semantic_outcome = await run_in_threadpool(
                    self.semantic_stage.execute,
                    unified_response=unified_response,
                    cv_text=cv_text,
                    jd_text=jd_text,
                    top_k=top_k,
                )
            except SemanticStageError as semantic_error:
                logger.error(
                    f"[{run_id}] Stage 3 SBERT failure: {semantic_error.cause}",
                    exc_info=True,
                )
                stage_diagnostics.append(
                    StageDiagnostic(
                        stage="semantic_representation",
                        status="failed",
                        duration_ms=round(semantic_error.duration_ms, 2),
                        error=str(semantic_error.cause),
                    )
                )
                return self._build_failure_response(
                    run_id=run_id,
                    stage="semantic_representation",
                    error_code="EMBEDDING_FAILURE",
                    message=f"Sinh embedding và truy vấn Top-K thất bại: {str(semantic_error.cause)}",
                    retryable=False,
                    graph_mode=graph_mode,
                    documents=documents_summary,
                    extraction=extraction_summary,
                    stages=stage_diagnostics,
                    total_duration_ms=(time.perf_counter() - pipeline_start_time) * 1000.0,
                )

            stage3_response = semantic_outcome.response
            t_sbert_dur = semantic_outcome.duration_ms
            granular_timings["stage3_sbert_representation_ms"] = round(t_sbert_dur, 2)
            stage_diagnostics.append(
                StageDiagnostic(
                    stage="semantic_representation",
                    status="completed",
                    duration_ms=round(t_sbert_dur, 2),
                )
            )
            semantic_rep_summary = self.response_mapper.semantic_representation_summary(
                stage3_response,
                top_k=top_k,
                include_embeddings=include_embeddings,
            )
        else:
            stage_diagnostics.append(
                StageDiagnostic(
                    stage="semantic_representation",
                    status="skipped",
                    duration_ms=0.0,
                    error="Skipped for evidence_only graph_mode",
                )
            )

        # -------------------------------------------------------------
        # STAGE 4: LLM SEMANTIC REASONING
        # -------------------------------------------------------------
        try:
            reasoning_outcome = await self.reasoning_stage.execute(
                graph_mode=graph_mode,
                offline_recording=offline_recording,
                stage3_response=stage3_response,
                max_pairs=eff_max_pairs,
                selection_strategy=eff_strategy,
                concurrency=self.reasoning_concurrency,
                timeout_seconds=self.reasoning_timeout_seconds,
                enable_critic=enable_critic,
                include_details=include_details,
                run_id=run_id,
            )
        except ReasoningStageError as reasoning_error:
            logger.error(
                f"[{run_id}] Stage 4 reasoning failure: {reasoning_error.cause}",
                exc_info=True,
            )
            stage_diagnostics.append(
                StageDiagnostic(
                    stage="semantic_reasoning",
                    status="failed",
                    duration_ms=round(reasoning_error.duration_ms, 2),
                    error=str(reasoning_error.cause),
                )
            )
            return self._build_failure_response(
                run_id=run_id,
                stage="semantic_reasoning",
                error_code="REASONING_FAILURE",
                message=f"Lập luận quan hệ kỹ năng LLM thất bại: {str(reasoning_error.cause)}",
                retryable=True,
                graph_mode=graph_mode,
                documents=documents_summary,
                extraction=extraction_summary,
                semantic_representation=semantic_rep_summary,
                stages=stage_diagnostics,
                total_duration_ms=(time.perf_counter() - pipeline_start_time) * 1000.0,
            )

        reasoning_summary = reasoning_outcome.summary
        raw_reasoning_results = reasoning_outcome.results
        stage_diagnostics.append(reasoning_outcome.diagnostic)
        if reasoning_outcome.diagnostic.status == "completed":
            granular_timings["stage4_semantic_reasoning_ms"] = reasoning_outcome.duration_ms

        # -------------------------------------------------------------
        # STAGE 5: PAPER-ALIGNED GRAPH CONSTRUCTION & INTEGRITY VALIDATION
        # -------------------------------------------------------------
        try:
            graph_outcome = self.graph_service.build(
                unified_response=unified_response,
                stage3_response=stage3_response,
                reasoning_results=raw_reasoning_results,
                graph_mode=graph_mode,
                pair_id=matched_pid or f"pair_{run_id[:12]}",
                include_graph=include_graph,
            )
        except GraphIntegrityError as graph_error:
            duration = graph_error.duration_ms
            error_message = str(graph_error)
            stage_diagnostics.append(
                StageDiagnostic(
                    stage="graph_construction",
                    status="failed",
                    duration_ms=round(duration, 2),
                    error=error_message,
                )
            )
            return self._build_failure_response(
                run_id=run_id,
                stage="graph_construction",
                error_code="GRAPH_INTEGRITY_VIOLATION",
                message=f"Kiểm tra tính toàn vẹn của đồ thị thất bại: {error_message}",
                retryable=False,
                graph_mode=graph_mode,
                documents=documents_summary,
                extraction=extraction_summary,
                semantic_representation=semantic_rep_summary,
                semantic_reasoning=reasoning_summary,
                stages=stage_diagnostics,
                total_duration_ms=(time.perf_counter() - pipeline_start_time) * 1000.0,
            )
        except PipelineGraphBuildError as graph_error:
            duration = graph_error.duration_ms
            logger.error(f"[{run_id}] Stage 5 graph failure: {graph_error.cause}", exc_info=True)
            stage_diagnostics.append(
                StageDiagnostic(
                    stage="graph_construction",
                    status="failed",
                    duration_ms=round(duration, 2),
                    error=str(graph_error.cause),
                )
            )
            return self._build_failure_response(
                run_id=run_id,
                stage="graph_construction",
                error_code="GRAPH_BUILD_FAILURE",
                message=f"Xây dựng đồ thị thất bại: {str(graph_error.cause)}",
                retryable=False,
                graph_mode=graph_mode,
                documents=documents_summary,
                extraction=extraction_summary,
                semantic_representation=semantic_rep_summary,
                semantic_reasoning=reasoning_summary,
                stages=stage_diagnostics,
                total_duration_ms=(time.perf_counter() - pipeline_start_time) * 1000.0,
            )

        graph_data = graph_outcome.graph_data
        pyg_data = graph_outcome.pyg_data
        graph_summary = graph_outcome.summary
        granular_timings["stage5_graph_construction_ms"] = round(graph_outcome.duration_ms, 2)
        stage_diagnostics.append(
            StageDiagnostic(
                stage="graph_construction",
                status="completed",
                duration_ms=round(graph_outcome.duration_ms, 2),
            )
        )

        # -------------------------------------------------------------        # STAGE 6: PAPER-ALIGNED HYBRID GNN COMPATIBILITY INFERENCE
        # -------------------------------------------------------------
        matching_result = matching_status = pipeline_failure = None
        overall_pipeline_status = "completed"
        if include_compatibility_score:
            inference_outcome = self.inference_service.infer(
                graph=pyg_data,
                graph_mode=graph_mode,
                pair_id=matched_pid or f"pair_{run_id[:12]}",
                run_id=run_id,
            )
            matching_result = inference_outcome.matching_result
            matching_status = inference_outcome.matching_status
            overall_pipeline_status = inference_outcome.pipeline_status
            pipeline_failure = inference_outcome.failure
            stage_diagnostics.append(inference_outcome.diagnostic)
            granular_timings["stage6_gnn_inference_ms"] = inference_outcome.duration_ms
            all_errors.extend(inference_outcome.errors)
        else:
            stage_diagnostics.append(StageDiagnostic(
                stage="gnn_inference", status="skipped", duration_ms=0.0,
            ))

        # -------------------------------------------------------------
        # FINAL SUCCESS ASSEMBLY
        # -------------------------------------------------------------
        total_time_ms = round((time.perf_counter() - pipeline_start_time) * 1000.0, 2)
        granular_timings["pipeline_total_execution_ms"] = total_time_ms

        logger.info(f"[{run_id}] Unified pipeline execution completed with status='{overall_pipeline_status}' in {total_time_ms}ms.")

        response = PipelineAnalyzeResponse(
            run_id=run_id,
            status=overall_pipeline_status,
            pipeline_version="1.0.0",
            graph_mode=graph_mode,
            documents=documents_summary,
            extraction=extraction_summary,
            semantic_representation=semantic_rep_summary,
            semantic_reasoning=reasoning_summary,
            graph=graph_summary,
            matching_result=matching_result,
            matching_status=matching_status,
            diagnostics=PipelineDiagnostics(
                stages=stage_diagnostics,
                total_duration_ms=total_time_ms,
                timings=granular_timings,
                errors=all_errors,
            ),
            failure=pipeline_failure,
        )
        skill_importance_payload = self.skill_importance_stage.evaluate(
            enabled=enable_skill_importance,
            unified_response=unified_response,
            jd_text=jd_text,
            fallback_jd_text=stage1_jd_text,
            run_id=run_id,
        )
        # In-memory hand-off for the standardized public output (not serialized, no recomputation)
        response._public_context = PublicOutputContext(
            cv_text=cv_text or stage1_cv_text or "",
            jd_text=jd_text or stage1_jd_text or "",
            unified_response=unified_response,
            graph_data=graph_data,
            stage3_response=stage3_response,
            matching_score=(matching_result.matching_score if matching_result is not None else None),
            matching_status=matching_status,
            run_id=run_id,
            skill_importance_output=skill_importance_payload,
        )
        return response

    def _build_failure_response(
        self,
        run_id: str,
        stage: str,
        error_code: str,
        message: str,
        retryable: bool,
        graph_mode: GraphConstructionMode,
        stages: List[StageDiagnostic],
        total_duration_ms: float,
        documents: Optional[PipelineDocumentSummary] = None,
        extraction: Optional[PipelineExtractionSummary] = None,
        semantic_representation: Optional[PipelineSemanticRepresentation] = None,
        semantic_reasoning: Optional[PipelineSemanticReasoning] = None,
        graph: Optional[PipelineGraphSummary] = None,
        matching_result: Optional[PipelineMatchingResult] = None,
        matching_status: Optional[str] = None,
    ) -> PipelineAnalyzeResponse:
        """Construct structured failure response payload."""
        logger.warning(f"[{run_id}] Pipeline failure at stage='{stage}', code='{error_code}': {message}")
        return PipelineAnalyzeResponse(
            run_id=run_id,
            status="failed",
            pipeline_version="1.0.0",
            graph_mode=graph_mode,
            documents=documents,
            extraction=extraction,
            semantic_representation=semantic_representation,
            semantic_reasoning=semantic_reasoning,
            graph=graph,
            matching_result=matching_result,
            matching_status=matching_status,
            diagnostics=PipelineDiagnostics(
                stages=stages,
                total_duration_ms=round(total_duration_ms, 2),
                timings={},
                errors=[{"stage": stage, "error_code": error_code, "message": message}],
            ),
            failure=PipelineFailureDetail(
                stage=stage,
                error_code=error_code,
                message=message,
                retryable=retryable,
                run_id=run_id,
            ),
        )
