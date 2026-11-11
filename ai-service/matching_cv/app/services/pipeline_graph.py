"""Graph construction stage for the analyze pipeline."""
from dataclasses import dataclass
import time
from typing import Any, Optional, Protocol

from torch_geometric.data import HeteroData

from matching_cv.app.schemas.pipeline import PipelineGraphSummary
from matching_cv.app.schemas.semantic_reasoning import SkillPairReasoningResult
from matching_cv.app.schemas.semantic_representation import SemanticRepresentationResponse
from matching_cv.app.schemas.unified_skill_extraction import UnifiedExtractFileResponse
from matching_cv.research.paper_aligned_gnn.graph_builder import (
    PaperAlignedGraphBuilder,
    verify_paper_aligned_subgraphs,
)
from matching_cv.research.paper_aligned_gnn.schemas import (
    PaperAlignedGraphConfig,
    PaperAlignedGraphData,
)


class GraphBuilder(Protocol):
    """Graph construction interface consumed by the analyze graph stage."""

    def build_graph(
        self,
        unified_response: UnifiedExtractFileResponse,
        stage3_response: Optional[SemanticRepresentationResponse] = None,
        reasoning_results: Optional[list[SkillPairReasoningResult]] = None,
        pair_id: Optional[str] = None,
    ) -> Any: ...

    def export_to_pyg(self, graph_data: PaperAlignedGraphData) -> Any: ...

    def validate_graph_integrity(self, graph_data: PaperAlignedGraphData) -> Any: ...


@dataclass(frozen=True)
class PipelineGraphOutcome:
    graph_data: PaperAlignedGraphData
    pyg_data: HeteroData
    summary: PipelineGraphSummary
    duration_ms: float


class GraphIntegrityError(ValueError):
    def __init__(self, message: str, duration_ms: float) -> None:
        super().__init__(message)
        self.duration_ms = duration_ms


class PipelineGraphBuildError(RuntimeError):
    def __init__(self, cause: Exception, duration_ms: float) -> None:
        super().__init__(str(cause))
        self.cause = cause
        self.duration_ms = duration_ms


class PipelineGraphService:
    """Builds, validates and exports a paper-aligned heterogeneous graph."""

    def __init__(self, base_builder: GraphBuilder, embedding_dim: int) -> None:
        self._base_builder = base_builder
        self._embedding_dim = embedding_dim

    def build(
        self,
        *,
        unified_response: UnifiedExtractFileResponse,
        stage3_response: Optional[SemanticRepresentationResponse],
        reasoning_results: Optional[list[SkillPairReasoningResult]],
        graph_mode: str,
        pair_id: str,
        include_graph: bool,
    ) -> PipelineGraphOutcome:
        started_at = time.perf_counter()
        try:
            active_builder = self._builder_for_mode(graph_mode)
            graph_data, integrity_report = active_builder.build_graph(
                unified_response=unified_response,
                stage3_response=stage3_response if graph_mode != "evidence_only" else None,
                reasoning_results=reasoning_results if graph_mode == "llm_enriched" else None,
                pair_id=pair_id,
            )
            if not integrity_report.is_valid:
                raise GraphIntegrityError(
                    "; ".join(integrity_report.errors),
                    (time.perf_counter() - started_at) * 1000.0,
                )

            subgraph_checks = verify_paper_aligned_subgraphs(
                graph_data,
                reasoning_results=reasoning_results,
            )
            pyg_data, _, pyg_summary = active_builder.export_to_pyg(graph_data)
            duration_ms = (time.perf_counter() - started_at) * 1000.0

            node_counts = dict(integrity_report.node_counts)
            if "total" not in node_counts:
                node_counts["total"] = sum(node_counts.values())
            edge_counts = dict(integrity_report.edge_counts)
            if "total" not in edge_counts:
                edge_counts["total"] = sum(edge_counts.values())

            summary = PipelineGraphSummary(
                graph_id=graph_data.graph_id,
                graph_mode=graph_mode,
                edge_policy=graph_data.merge_policy,
                node_counts=node_counts,
                edge_counts=edge_counts,
                integrity=integrity_report.model_dump(),
                subgraph_checks=subgraph_checks,
                pyg_summary=pyg_summary if include_graph else None,
                graph_data=graph_data if include_graph else None,
            )
            return PipelineGraphOutcome(
                graph_data=graph_data,
                pyg_data=pyg_data,
                summary=summary,
                duration_ms=duration_ms,
            )
        except GraphIntegrityError:
            raise
        except Exception as error:
            raise PipelineGraphBuildError(
                error,
                (time.perf_counter() - started_at) * 1000.0,
            ) from error

    def _builder_for_mode(self, graph_mode: str) -> GraphBuilder:
        if graph_mode in ("paper_cosine_08", "canonical_only"):
            return PaperAlignedGraphBuilder(
                PaperAlignedGraphConfig(
                    embedding_dim=self._embedding_dim,
                    merge_policy=graph_mode,
                )
            )
        return self._base_builder
