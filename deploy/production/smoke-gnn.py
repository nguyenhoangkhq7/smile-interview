"""Exercise the production checkpoint with a deterministic, offline one-skill graph."""
import math

from matching_cv.app.services.gnn_inference_service import gnn_inference_service
from matching_cv.research.paper_aligned_gnn.graph_builder import paper_aligned_graph_builder
from matching_cv.research.paper_aligned_gnn.schemas import SkillInputItem


def skill(source):
    return SkillInputItem(
        occurrence_id=source.lower(), canonical_skill_id="python", surface_name="Python",
        source_document=source, embedding_vector=[1.0] + [0.0] * 767,
    )


graph, report = paper_aligned_graph_builder.build_graph_from_items(
    [skill("CV")], [skill("JD")], jd_importance_weights={"python": 0.9}
)
if not report.is_valid:
    raise RuntimeError("Smoke fixture produced an invalid graph")
data, _, _ = paper_aligned_graph_builder.export_to_pyg(graph)
result = gnn_inference_service.predict_graph(data)
if result.model_version != "semantic-importance-dependency-gnn-v4" or not math.isfinite(result.matching_score):
    raise RuntimeError("GNN v4 inference failed")
print("GNN v4 inference passed")
