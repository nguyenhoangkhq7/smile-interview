"""Check the semantic-importance graph and its exported GNN inputs."""

from collections import defaultdict
from math import isclose
from typing import Any

from torch_geometric.data import HeteroData

from matching_cv.research.paper_aligned_gnn.graph_builder import _extract_jd_importance_map
from matching_cv.research.paper_aligned_gnn.schemas import PaperAlignedGraphData
from matching_cv.research.paper_aligned_gnn.shared_skill_matcher import compute_vector_cosine


def _range(values: list[float]) -> dict[str, float | int | None]:
    return {"count": len(values), "min": min(values) if values else None, "max": max(values) if values else None}


def _export_agrees(pyg: HeteroData, relation: tuple[str, str, str], edges: list) -> bool:
    if relation not in pyg.edge_types:
        return False
    store = pyg[relation]
    source_ids = pyg[relation[0]].node_ids
    target_ids = pyg[relation[2]].node_ids
    pairs = [
        (source_ids[src], target_ids[dst])
        for src, dst in store.edge_index.T.tolist()
    ]
    if pairs != [(edge.source_id, edge.target_id) for edge in edges]:
        return False
    for field in ("edge_attr", "edge_effective_weight"):
        weights = getattr(store, field, None)
        if weights is None or weights.numel() != len(edges):
            return False
        if any(
            not isclose(value, edge.tensor_weight, abs_tol=1e-6)
            for value, edge in zip(weights.flatten().tolist(), edges)
        ):
            return False
    return True


def audit_semantic_edge_weights(
    graph: PaperAlignedGraphData, pyg: HeteroData, importance: Any
) -> dict[str, Any]:
    """Check each edge against its source rule and each tensor against the same endpoints."""
    weights = _extract_jd_importance_map(skill_importance_output=importance)
    groups: dict[tuple[str, str, str], list] = defaultdict(list)
    values: dict[str, list[float]] = defaultdict(list)
    formula_errors = 0
    jd_fallback_edges = 0
    dependency_fallback_edges = 0
    for edge in graph.edges:
        relation = edge.edge_type
        groups[(edge.source_type, relation, edge.target_type)].append(edge)
        if relation in ("has_skill", "in_resume"):
            group = "cv"
            expected = 1.0
        elif relation in ("requires_skill", "required_by_job"):
            group = "jd"
            skill_id = edge.target_id if relation == "requires_skill" else edge.source_id
            node = graph.skill_nodes[skill_id]
            jsi_weight = weights.get(node.jd_canonical_id or node.canonical_skill_id)
            jd_fallback_edges += jsi_weight is None
            expected = 1.0 if jsi_weight is None else round(jsi_weight, 4)
        else:
            group = "prerequisite"
            cosine = compute_vector_cosine(
                graph.skill_nodes[edge.source_id].embedding_vector,
                graph.skill_nodes[edge.target_id].embedding_vector,
            )
            dependency_fallback_edges += cosine is None
            expected = 0.75 if cosine is None else round(max(0.1, min(1.0, cosine)), 6)
        values[group].append(edge.tensor_weight)
        formula_errors += not isclose(edge.tensor_weight, expected, abs_tol=1e-6)

    return {
        "weights": {group: _range(values[group]) for group in ("cv", "jd", "prerequisite")},
        "relation_counts": {relation[1]: len(edges) for relation, edges in groups.items()},
        "formula_mismatches": formula_errors,
        "pyg_mismatch_relations": [
            relation[1] for relation, edges in groups.items() if not _export_agrees(pyg, relation, edges)
        ],
        "jd_unverified_by_jsi_edges": jd_fallback_edges,
        "prerequisite_cosine_fallback_edges": dependency_fallback_edges,
    }
