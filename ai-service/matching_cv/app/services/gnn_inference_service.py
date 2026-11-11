"""
GNN Inference Service (Default: PaperAlignedHybridGNN).

Replaces the default GNN inference path with the paper-aligned architecture based on:
Baghbanzadeh, A., & Wu, D. (2025). Resume-Job Compatibility Scoring Using Graph Neural Networks
and Large Language Models. ICIT 2025. https://doi.org/10.1145/3787330.3787359

Enforces strict checkpoint safety (Section 7):
- Never loads legacy RelationAwareHybridGNN checkpoints into PaperAlignedHybridGNN.
- Never produces an official matching score using randomly initialized GNN parameters.
- Never fabricates default compatibility scores or silently falls back to the old model.
"""
import hashlib
import logging
import math
import os
from pathlib import Path
import threading
import time
from typing import Any, Dict, Optional, Tuple, Union

import torch
from torch_geometric.data import HeteroData

from matching_cv.app.schemas.gnn_inference import (
    FitCategory,
    GNNInferenceResponse,
)
from matching_cv.research.paper_aligned_gnn.hybrid_gnn import (
    PaperAlignedGNNConfig,
    PaperAlignedHybridGNN,
)

logger = logging.getLogger(__name__)

TH1_NO_FIT_UPPER = 0.25
TH2_GOOD_FIT_LOWER = 0.75

# Pinned Stage 3 SBERT Embedding Metadata
PINNED_SBERT_MODEL_ID = "sentence-transformers/paraphrase-multilingual-mpnet-base-v2"
PINNED_SBERT_REVISION = "4328cf26390c98c5e3c738b4460a05b95f4911f5"
EXPECTED_EMBEDDING_DIM = 768

# Default checkpoint path for trained PaperAlignedHybridGNN
PAPER_ALIGNED_CKPT_PATH = str(
    Path(__file__).resolve().parents[2] / "data/checkpoints/paper_aligned_gnn/paper_aligned_hybrid_gnn_v1.pt"
)

ALLOWED_PAPER_NODE_TYPES = {"resume", "job", "skill"}
LEGACY_FORBIDDEN_NODE_TYPES = {"cv", "jd", "evidence", "requirement"}
ALLOWED_PAPER_EDGE_TYPES = {
    ("resume", "has_skill", "skill"),
    ("skill", "in_resume", "resume"),
    ("job", "requires_skill", "skill"),
    ("skill", "required_by_job", "job"),
}


class GNNInputValidationError(ValueError):
    """Raised when a graph schema violates GNN input contracts or security checks."""
    error_code: str = "GRAPH_FEATURE_CONTRACT_VIOLATION"


class PaperGNNCheckpointUnavailableError(FileNotFoundError):
    """
    Raised when no verified trained checkpoint is available for PaperAlignedHybridGNN.
    Triggers Graph-Only / Diagnostic Mode (Path A) in pipeline orchestrators.
    """
    error_code: str = "MODEL_NOT_TRAINED"
    diagnostic_status: str = "CHECKPOINT_UNAVAILABLE"


class PaperGNNIncompatibleCheckpointError(GNNInputValidationError):
    """
    Raised when an incompatible or legacy checkpoint (e.g., RelationAwareHybridGNN)
    or an unverified/untrained checkpoint is supplied to PaperAlignedHybridGNN.
    """
    error_code: str = "INCOMPATIBLE_CHECKPOINT_ARCHITECTURE"


def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


def classify_score(
    score: float,
    th1: float = TH1_NO_FIT_UPPER,
    th2: float = TH2_GOOD_FIT_LOWER,
    is_calibrated: bool = True,
) -> FitCategory:
    """Classify continuous or bounded score on [0, 1] scale into categorical fit or UNCALIBRATED."""
    if not isinstance(score, (int, float)):
        raise GNNInputValidationError(f"Invalid score type: expected float or int, got {type(score)}")
    if math.isnan(score):
        raise GNNInputValidationError("Score is NaN (numerical instability detected).")
    if math.isinf(score):
        raise GNNInputValidationError("Score is Infinite (overflow/divergence detected).")

    if not is_calibrated:
        return FitCategory.UNCALIBRATED

    val = float(score)
    if val < th1:
        return FitCategory.NO_FIT
    elif val <= th2:
        return FitCategory.POTENTIAL_FIT
    else:
        return FitCategory.GOOD_FIT


def compute_bounded_matching_score(
    raw_score: float,
    score_scale: str = "0_1",
    is_calibrated: bool = True,
    th1: float = TH1_NO_FIT_UPPER,
    th2: float = TH2_GOOD_FIT_LOWER,
) -> Tuple[float, float, FitCategory]:
    """
    Apply canonical bounding post-processing rule on active score_scale ('0_1' or '0_100').
    Strictly rejects NaN and Infinity explicitly.
    Returns: (matching_score, bounded_display_score, fit_category)
    """
    if not isinstance(raw_score, (int, float)):
        raise GNNInputValidationError(f"Invalid score type: expected float or int, got {type(raw_score)}")
    if math.isnan(raw_score):
        raise GNNInputValidationError("GNN regression score is NaN (numerical instability detected).")
    if math.isinf(raw_score):
        raise GNNInputValidationError("GNN regression score is Infinite (overflow/divergence detected).")

    raw_val = float(raw_score)
    if score_scale == "0_100":
        matching_score = round(min(100.0, max(0.0, raw_val)), 4)
        bounded_display_score = matching_score
        fit_cat = classify_score(matching_score / 100.0, th1=th1, th2=th2, is_calibrated=is_calibrated)
    else:
        matching_score = round(min(1.0, max(0.0, raw_val)), 4)
        bounded_display_score = matching_score
        fit_cat = classify_score(matching_score, th1=th1, th2=th2, is_calibrated=is_calibrated)
    return matching_score, bounded_display_score, fit_cat


class GNNInferenceService:
    """
    Default Paper-Aligned Hybrid GNN Inference Service (Baghbanzadeh & Wu, ICIT 2025).

    Uses `PaperAlignedHybridGNN` exclusively by default:
    1. GraphConv on Job-Skill connections.
    2. Modified GAT implementing Equation (2) on Resume-Skill connections.
    3. Final Resume and Job node embeddings.
    4. Concatenated document readout [h_resume || h_job].
    5. MLP regression head.

    Enforces strict checkpoint safety:
    - Rejects legacy `RelationAwareHybridGNN` checkpoints with `PaperGNNIncompatibleCheckpointError`.
    - Raises `PaperGNNCheckpointUnavailableError` (`MODEL_NOT_TRAINED` / `CHECKPOINT_UNAVAILABLE`)
      when no verified trained `PaperAlignedHybridGNN` checkpoint is present, preventing any
      untrained forward pass from producing a compatibility score.
    """

    def __init__(self, checkpoint_path: Optional[str] = None):
        self.checkpoint_path: str = checkpoint_path or PAPER_ALIGNED_CKPT_PATH
        self._models: Dict[str, PaperAlignedHybridGNN] = {}
        self._checkpoint_metadata: Dict[str, Dict[str, Any]] = {}
        self._lock = threading.Lock()

    def validate_checkpoint_payload(
        self,
        ckpt_obj: Any,
        ckpt_path: str,
    ) -> Tuple[Dict[str, Any], PaperAlignedGNNConfig]:
        """
        Validate that a loaded checkpoint dictionary is a verified trained
        PaperAlignedHybridGNN checkpoint and NOT a legacy RelationAwareHybridGNN
        or untrained state dict.
        """
        if not isinstance(ckpt_obj, dict):
            raise PaperGNNIncompatibleCheckpointError(
                f"INCOMPATIBLE_CHECKPOINT_ARCHITECTURE: Checkpoint at '{ckpt_path}' is not a valid metadata dictionary."
            )

        state_dict = ckpt_obj.get("model_state_dict")
        if not isinstance(state_dict, dict) or len(state_dict) == 0:
            raise PaperGNNIncompatibleCheckpointError(
                f"INCOMPATIBLE_CHECKPOINT_ARCHITECTURE: Checkpoint at '{ckpt_path}' is missing a non-empty 'model_state_dict'."
            )

        # Detect legacy RelationAwareHybridGNN state dict keys explicitly
        legacy_markers = ("struct_conv", "sem_conv", "cand_conv", "projector.")
        if any(any(m in k for m in legacy_markers) for k in state_dict.keys()):
            raise PaperGNNIncompatibleCheckpointError(
                f"INCOMPATIBLE_CHECKPOINT_ARCHITECTURE: Refusing to load legacy RelationAwareHybridGNN checkpoint "
                f"from '{ckpt_path}' into PaperAlignedHybridGNN."
            )

        arch = ckpt_obj.get("architecture")
        if arch != "PaperAlignedHybridGNN":
            raise PaperGNNIncompatibleCheckpointError(
                f"INCOMPATIBLE_CHECKPOINT_ARCHITECTURE: Expected checkpoint architecture 'PaperAlignedHybridGNN', "
                f"got {arch!r} at '{ckpt_path}'."
            )

        is_trained = ckpt_obj.get("is_trained")
        if is_trained is not True:
            raise PaperGNNIncompatibleCheckpointError(
                f"INCOMPATIBLE_CHECKPOINT_ARCHITECTURE: Checkpoint at '{ckpt_path}' is not marked as a verified "
                f"trained checkpoint (is_trained={is_trained!r}). Untrained weights cannot produce official scores."
            )

        # Enforce supervision target alignment
        sup_target = ckpt_obj.get("supervision_target")
        if sup_target is not None and sup_target != "skill_score":
            raise PaperGNNIncompatibleCheckpointError(
                f"INCOMPATIBLE_CHECKPOINT_ARCHITECTURE: Expected checkpoint supervision_target 'skill_score', "
                f"got {sup_target!r} at '{ckpt_path}'."
            )

        # Enforce SBERT feature provenance and dimensionality
        emb_model = ckpt_obj.get("stage3_embedding_model_name")
        if emb_model is not None and emb_model != PINNED_SBERT_MODEL_ID:
            raise PaperGNNIncompatibleCheckpointError(
                f"INCOMPATIBLE_CHECKPOINT_ARCHITECTURE: Expected embedding model '{PINNED_SBERT_MODEL_ID}', "
                f"got {emb_model!r} at '{ckpt_path}'."
            )

        emb_rev = ckpt_obj.get("stage3_embedding_model_revision")
        if emb_rev is not None and emb_rev != PINNED_SBERT_REVISION:
            raise PaperGNNIncompatibleCheckpointError(
                f"INCOMPATIBLE_CHECKPOINT_ARCHITECTURE: Expected embedding revision '{PINNED_SBERT_REVISION}', "
                f"got {emb_rev!r} at '{ckpt_path}'."
            )

        emb_dim = ckpt_obj.get("stage3_embedding_dimension")
        if emb_dim is not None and int(emb_dim) != EXPECTED_EMBEDDING_DIM:
            raise PaperGNNIncompatibleCheckpointError(
                f"INCOMPATIBLE_CHECKPOINT_ARCHITECTURE: Expected embedding dimension {EXPECTED_EMBEDDING_DIM}, "
                f"got {emb_dim!r} at '{ckpt_path}'."
            )

        raw_cfg = ckpt_obj.get("model_config") or {}
        valid_cfg_keys = {
            "num_layers",
            "input_dim",
            "hidden_dim",
            "num_heads",
            "leaky_relu_slope",
            "dropout",
            "mlp_hidden_dims",
            "mlp_dropout",
            "use_job_edge_weights",
            "missing_job_weight_for_graphconv",
            "use_resume_edge_weights",
            "missing_resume_weight_for_gat",
            "add_self_loops_in_gat",
            "score_scale",
        }
        filtered_cfg = {k: v for k, v in raw_cfg.items() if k in valid_cfg_keys}
        cfg = PaperAlignedGNNConfig(**filtered_cfg)
        return state_dict, cfg

    def get_model(
        self,
        mode: Optional[Union[str, Any]] = None,
        checkpoint_path: Optional[str] = None,
    ) -> Tuple[PaperAlignedHybridGNN, Dict[str, Any]]:
        """
        Load and cache a verified trained PaperAlignedHybridGNN checkpoint.
        Thread-safe singleton caching with device auto-detection (CPU or CUDA).
        Raises:
        - `PaperGNNCheckpointUnavailableError` if the checkpoint file does not exist.
        - `PaperGNNIncompatibleCheckpointError` if the checkpoint belongs to the legacy
          `RelationAwareHybridGNN` or fails `PaperAlignedHybridGNN` verification.
        """
        resolved_ckpt = os.path.abspath(checkpoint_path or self.checkpoint_path)
        if not os.path.exists(resolved_ckpt) or not os.path.isfile(resolved_ckpt):
            raise PaperGNNCheckpointUnavailableError(
                f"MODEL_NOT_TRAINED: CHECKPOINT_UNAVAILABLE - No verified trained checkpoint for "
                f"PaperAlignedHybridGNN found at '{checkpoint_path or self.checkpoint_path}'."
            )

        ckpt_sha = sha256_file(resolved_ckpt)
        cache_key = f"{resolved_ckpt}:{ckpt_sha}"

        with self._lock:
            if cache_key in self._models:
                return self._models[cache_key], self._checkpoint_metadata[cache_key]

            ckpt_obj = torch.load(resolved_ckpt, map_location="cpu", weights_only=True)
            state_dict, cfg = self.validate_checkpoint_payload(ckpt_obj, checkpoint_path or self.checkpoint_path)

            device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
            model = PaperAlignedHybridGNN(cfg)
            try:
                model.load_state_dict(state_dict, strict=True)
            except Exception as load_err:
                raise PaperGNNIncompatibleCheckpointError(
                    f"INCOMPATIBLE_CHECKPOINT_ARCHITECTURE: State dict mismatch loading '{checkpoint_path or self.checkpoint_path}' "
                    f"into PaperAlignedHybridGNN: {load_err}"
                ) from load_err

            model.to(device)
            model.eval()

            meta = {
                "architecture": "PaperAlignedHybridGNN",
                "model_version": ckpt_obj.get("model_version", "paper-aligned-2025-v1"),
                "checkpoint_name": os.path.basename(resolved_ckpt),
                "checkpoint_path": checkpoint_path or self.checkpoint_path,
                "checkpoint_sha256": ckpt_sha,
                "score_scale": cfg.score_scale,
                "supervision_target": ckpt_obj.get("supervision_target", "skill_score"),
                "score_version": ckpt_obj.get("score_version", "skill-target-regression-v1"),
                "calibrated_thresholds": ckpt_obj.get("calibrated_thresholds"),
                "stage3_embedding_model_name": ckpt_obj.get("stage3_embedding_model_name", PINNED_SBERT_MODEL_ID),
                "stage3_embedding_model_revision": ckpt_obj.get("stage3_embedding_model_revision", PINNED_SBERT_REVISION),
                "stage3_embedding_dimension": ckpt_obj.get("stage3_embedding_dimension", EXPECTED_EMBEDDING_DIM),
                "model_config": ckpt_obj.get("model_config", {}),
                "training_metadata": ckpt_obj.get("training_metadata", {}),
                "device": str(device),
            }

            self._models[cache_key] = model
            self._checkpoint_metadata[cache_key] = meta
            logger.info(
                f"Loaded verified PaperAlignedHybridGNN checkpoint from {resolved_ckpt} (SHA256: {ckpt_sha}) on {device}"
            )
            return model, meta

    def validate_graph(
        self,
        graph: HeteroData,
        mode: Optional[Union[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Validate a PyG HeteroData graph against the Paper-Aligned Bipartite Graph Contract:
        - Must contain 'resume' (1 node, 768D) and 'job' (1 node, 768D) document nodes.
        - Must contain 'skill' entity nodes (N >= 0, 768D) with finite features.
        - Must NOT contain legacy 4-node types ('cv', 'jd', 'evidence', 'requirement')
          or skill-to-skill edges.
        - All edges must be valid document <-> skill bipartite edges with aligned proficiency tensors.
        """
        if not isinstance(graph, HeteroData):
            raise GNNInputValidationError(f"Expected torch_geometric.data.HeteroData, got {type(graph)}")

        node_types_set = set(graph.node_types)

        # Reject legacy 4-node graph structures explicitly
        legacy_found = node_types_set.intersection(LEGACY_FORBIDDEN_NODE_TYPES)
        if legacy_found:
            raise GNNInputValidationError(
                f"GRAPH_INTEGRITY_VIOLATION: Legacy node types {sorted(legacy_found)} detected. "
                "PaperAlignedHybridGNN requires a paper-aligned bipartite graph with ('resume', 'job', 'skill') nodes."
            )

        unexpected_nodes = node_types_set - ALLOWED_PAPER_NODE_TYPES
        if unexpected_nodes:
            raise GNNInputValidationError(
                f"GRAPH_INTEGRITY_VIOLATION: Unsupported node types {sorted(unexpected_nodes)} in paper-aligned graph."
            )

        for doc_nt in ("resume", "job"):
            if doc_nt not in node_types_set:
                raise GNNInputValidationError(
                    f"GRAPH_INTEGRITY_VIOLATION: Missing mandatory '{doc_nt}' document node in paper-aligned graph."
                )
            store = graph[doc_nt]
            if not hasattr(store, "x") or store.x is None or store.x.ndim != 2:
                raise GNNInputValidationError(
                    f"GRAPH_INTEGRITY_VIOLATION: Document node '{doc_nt}' is missing a 2D feature tensor 'x'."
                )
            if int(store.x.size(0)) != 1:
                raise GNNInputValidationError(
                    f"GRAPH_INTEGRITY_VIOLATION: Document node '{doc_nt}' must have exactly 1 node, got {int(store.x.size(0))}."
                )
            if int(store.x.size(1)) != 768:
                raise GNNInputValidationError(
                    f"GRAPH_INTEGRITY_VIOLATION: Document node '{doc_nt}' feature dimension mismatch: expected 768, got {int(store.x.size(1))}."
                )
            if torch.isnan(store.x).any() or torch.isinf(store.x).any():
                raise GNNInputValidationError(
                    f"GRAPH_INTEGRITY_VIOLATION: Document node '{doc_nt}' contains NaN or Inf values."
                )

        if "skill" not in node_types_set:
            raise GNNInputValidationError(
                "GRAPH_INTEGRITY_VIOLATION: Graph is missing mandatory 'skill' node store."
            )

        skill_store = graph["skill"]
        if not hasattr(skill_store, "x") or skill_store.x is None or skill_store.x.ndim != 2:
            raise GNNInputValidationError(
                "GRAPH_INTEGRITY_VIOLATION: 'skill' node store is missing a 2D feature tensor 'x'."
            )
        num_skills = int(skill_store.x.size(0))
        if int(skill_store.x.size(1)) != 768:
            raise GNNInputValidationError(
                f"GRAPH_INTEGRITY_VIOLATION: 'skill' node feature dimension mismatch: expected 768, got {int(skill_store.x.size(1))}."
            )
        if num_skills > 0 and (torch.isnan(skill_store.x).any() or torch.isinf(skill_store.x).any()):
            raise GNNInputValidationError(
                "GRAPH_INTEGRITY_VIOLATION: 'skill' node features contain NaN or Inf values."
            )

        # Validate edge types (strictly bipartite document <-> skill; no skill <-> skill edges)
        for et in graph.edge_types:
            if et not in ALLOWED_PAPER_EDGE_TYPES:
                raise GNNInputValidationError(
                    f"GRAPH_INTEGRITY_VIOLATION: Forbidden or non-bipartite edge type {et} detected. "
                    "PaperAlignedHybridGNN only permits document-skill bipartite edges."
                )
            e_store = graph[et]
            ei = getattr(e_store, "edge_index", None)
            if ei is None or ei.ndim != 2 or int(ei.size(0)) != 2:
                raise GNNInputValidationError(
                    f"GRAPH_INTEGRITY_VIOLATION: Edge type {et} has malformed edge_index shape."
                )
            num_e = int(ei.size(1))
            if num_e > 0:
                src_type, _, dst_type = et
                max_src = 1 if src_type in ("resume", "job") else num_skills
                max_dst = 1 if dst_type in ("resume", "job") else num_skills
                if int(ei[0].min().item()) < 0 or int(ei[0].max().item()) >= max_src:
                    raise GNNInputValidationError(
                        f"GRAPH_INTEGRITY_VIOLATION: Source index out of bounds in edge type {et}."
                    )
                if int(ei[1].min().item()) < 0 or int(ei[1].max().item()) >= max_dst:
                    raise GNNInputValidationError(
                        f"GRAPH_INTEGRITY_VIOLATION: Target index out of bounds in edge type {et}."
                    )

            ea = getattr(e_store, "edge_attr", None)
            if ea is not None and ea.numel() > 0:
                if int(ea.size(0)) != num_e:
                    raise GNNInputValidationError(
                        f"GRAPH_INTEGRITY_VIOLATION: edge_attr count ({int(ea.size(0))}) != num_edges ({num_e}) for {et}."
                    )
                if torch.isnan(ea).any() or torch.isinf(ea).any():
                    raise GNNInputValidationError(
                        f"GRAPH_INTEGRITY_VIOLATION: edge_attr contains NaN or Inf values for {et}."
                    )

        node_counts = {nt: int(graph[nt].num_nodes) for nt in graph.node_types}
        edge_counts = {
            f"{s}__{r}__{d}": int(graph[(s, r, d)].edge_index.shape[-1]) for s, r, d in graph.edge_types
        }

        # Validate forward vs. reverse edge consistency
        direction_pairs = [
            (("resume", "has_skill", "skill"), ("skill", "in_resume", "resume")),
            (("job", "requires_skill", "skill"), ("skill", "required_by_job", "job")),
        ]
        for fwd_et, rev_et in direction_pairs:
            if fwd_et in graph.edge_types and rev_et in graph.edge_types:
                fwd_ei = graph[fwd_et].edge_index
                rev_ei = graph[rev_et].edge_index
                if int(fwd_ei.size(1)) != int(rev_ei.size(1)):
                    raise GNNInputValidationError(
                        f"GRAPH_INTEGRITY_VIOLATION: Forward edge count ({int(fwd_ei.size(1))}) != "
                        f"reverse edge count ({int(rev_ei.size(1))}) for {fwd_et} vs {rev_et}."
                    )
                if int(fwd_ei.size(1)) > 0:
                    if not (torch.equal(fwd_ei[0], rev_ei[1]) and torch.equal(fwd_ei[1], rev_ei[0])):
                        raise GNNInputValidationError(
                            f"GRAPH_INTEGRITY_VIOLATION: Forward edge_index is not the transpose of reverse edge_index for {fwd_et} vs {rev_et}."
                        )
                    fwd_ea = getattr(graph[fwd_et], "edge_attr", None)
                    rev_ea = getattr(graph[rev_et], "edge_attr", None)
                    if fwd_ea is not None and rev_ea is not None and fwd_ea.numel() > 0 and rev_ea.numel() > 0:
                        if not torch.allclose(fwd_ea, rev_ea, atol=1e-6):
                            raise GNNInputValidationError(
                                f"GRAPH_INTEGRITY_VIOLATION: Forward edge_attr != reverse edge_attr for {fwd_et} vs {rev_et}."
                            )
                    fwd_hp = getattr(graph[fwd_et], "edge_has_proficiency", None)
                    rev_hp = getattr(graph[rev_et], "edge_has_proficiency", None)
                    if fwd_hp is not None and rev_hp is not None and fwd_hp.numel() > 0 and rev_hp.numel() > 0:
                        if not torch.equal(fwd_hp, rev_hp):
                            raise GNNInputValidationError(
                                f"GRAPH_INTEGRITY_VIOLATION: Forward edge_has_proficiency != reverse edge_has_proficiency for {fwd_et} vs {rev_et}."
                            )

        # Summarize proficiency edge coverage with stored vs. effective weight audit
        prof_summary: Dict[str, Any] = {}
        norm_mode = getattr(graph, "edge_weight_normalization", "scaled_0_1")
        job_eff_fallback = 1.0 if norm_mode == "scaled_0_1" else 10.0
        resume_eff_fallback = 0.0

        for et in [
            ("resume", "has_skill", "skill"),
            ("job", "requires_skill", "skill"),
            ("skill", "in_resume", "resume"),
            ("skill", "required_by_job", "job"),
        ]:
            if et in graph.edge_types:
                hp = getattr(graph[et], "edge_has_proficiency", None)
                ea = getattr(graph[et], "edge_attr", None)
                eff_attr = getattr(graph[et], "edge_effective_weight", None)
                total_e = int(graph[et].edge_index.size(1))
                with_prof = int(hp.sum().item()) if hp is not None and hp.numel() == total_e else 0
                missing_prof = total_e - with_prof
                is_job_edge = et[1] in ("requires_skill", "required_by_job")
                eff_fallback = job_eff_fallback if is_job_edge else resume_eff_fallback

                stored_mean = 0.0
                eff_mean = 0.0
                consistency_ok = True
                if total_e > 0 and ea is not None and ea.numel() == total_e:
                    ea_flat = ea.view(-1).float()
                    stored_mean = float(ea_flat.mean().item())
                    if hp is not None and hp.numel() == total_e:
                        missing_mask = ~hp.view(-1).bool()
                        if missing_mask.any():
                            max_missing_stored = float(ea_flat[missing_mask].abs().max().item())
                            if max_missing_stored > 1e-6:
                                raise GNNInputValidationError(
                                    f"GRAPH_INTEGRITY_VIOLATION: Missing proficiency edges in {et} must have stored "
                                    f"edge_attr == 0.0, found max abs value {max_missing_stored}."
                                )
                        if eff_attr is not None and eff_attr.numel() == total_e:
                            eff_flat = eff_attr.view(-1).float()
                        else:
                            eff_flat = ea_flat.clone()
                            eff_flat[missing_mask] = eff_fallback
                        eff_mean = float(eff_flat.mean().item())
                        expected_eff_mean = (float(ea_flat.sum().item()) + missing_prof * eff_fallback) / total_e
                        consistency_ok = abs(eff_mean - expected_eff_mean) < 1e-5
                        if not consistency_ok:
                            raise GNNInputValidationError(
                                f"GRAPH_INTEGRITY_VIOLATION: Proficiency tensor numerical contradiction in {et}: "
                                f"effective_mean={eff_mean:.6f} != expected={expected_eff_mean:.6f}."
                            )
                    else:
                        eff_mean = stored_mean

                prof_summary[f"{et[0]}__{et[1]}__{et[2]}"] = {
                    "total_edges": total_e,
                    "with_proficiency": with_prof,
                    "missing_proficiency": missing_prof,
                    "stored_tensor_missing_fallback": 0.0,
                    "effective_layer_missing_fallback": float(eff_fallback),
                    "stored_edge_attr_mean": round(stored_mean, 8),
                    "effective_edge_weight_mean": round(eff_mean, 8),
                    "numerical_consistency_verified": consistency_ok,
                }

        mode_str = mode.value if hasattr(mode, "value") else str(mode or "verified_equivalence")
        return {
            "validation_status": "VALID",
            "architecture": "PaperAlignedHybridGNN",
            "node_counts": node_counts,
            "edge_counts": edge_counts,
            "proficiency_summary": prof_summary,
            "forward_reverse_edge_consistency": True,
            "mode_evaluated": mode_str,
            "feature_dim": 768,
        }

    def predict_graph(
        self,
        graph: HeteroData,
        mode: Union[str, Any] = "verified_equivalence",
        pair_id: Optional[str] = None,
        checkpoint_path: Optional[str] = None,
    ) -> GNNInferenceResponse:
        """
        Execute deterministic forward inference on a validated Paper-Aligned HeteroData graph.
        - Validates graph schema first (`validate_graph`).
        - Verifies and loads a trained `PaperAlignedHybridGNN` checkpoint (`get_model`).
        - Raises `PaperGNNCheckpointUnavailableError` when no trained checkpoint is available.
        - Raises `PaperGNNIncompatibleCheckpointError` if an incompatible/legacy checkpoint is supplied.
        """
        mode_str = mode.value if hasattr(mode, "value") else str(mode or "verified_equivalence")
        val_summary = self.validate_graph(graph, mode=mode_str)

        model, meta = self.get_model(mode=mode_str, checkpoint_path=checkpoint_path)
        device = next(model.parameters()).device
        graph = graph.to(device)

        t0 = time.perf_counter()
        with torch.inference_mode():
            out = model(graph)
            raw_score = float(out["raw_score"].view(-1)[0].item())
        latency_ms = round((time.perf_counter() - t0) * 1000.0, 3)

        score_scale = str(out.get("score_scale", meta.get("score_scale", "0_1")))
        calibrated_thresholds = meta.get("calibrated_thresholds")
        has_calibrated_thresholds = (
            isinstance(calibrated_thresholds, dict)
            and "no_fit_upper" in calibrated_thresholds
            and "good_fit_lower" in calibrated_thresholds
        )
        th1_val = float(calibrated_thresholds["no_fit_upper"]) if has_calibrated_thresholds else TH1_NO_FIT_UPPER
        th2_val = float(calibrated_thresholds["good_fit_lower"]) if has_calibrated_thresholds else TH2_GOOD_FIT_LOWER

        matching_score, bounded_score, fit_cat = compute_bounded_matching_score(
            raw_score=raw_score,
            score_scale=score_scale,
            is_calibrated=has_calibrated_thresholds,
            th1=th1_val,
            th2=th2_val,
        )
        scale_bounds = out.get("scale_bounds") or (
            {"min": 0.0, "max": 100.0} if score_scale == "0_100" else {"min": 0.0, "max": 1.0}
        )
        attn_map = out.get("resume_skill_canonical_attention_map") or out.get("resume_skill_attention_map") or {}
        rounded_raw = round(raw_score, 4)
        pred_target = str(meta.get("supervision_target", "skill_score"))
        score_ver = str(meta.get("score_version", "skill-target-regression-v1"))

        return GNNInferenceResponse(
            pair_id=pair_id or getattr(graph, "pair_id", None),
            model_name="PaperAlignedHybridGNN",
            matching_score=matching_score,
            raw_score=rounded_raw,
            raw_model_score=rounded_raw,
            predicted_target_name=pred_target,
            score_version=score_ver,
            calibrated_score=None,
            calibration_status="CALIBRATED" if has_calibrated_thresholds else "UNCALIBRATED",
            bounded_display_score=bounded_score,
            fit_category=fit_cat,
            score_scale=score_scale,
            score_range={"min": float(scale_bounds["min"]), "max": float(scale_bounds["max"])},
            score_type="bounded_uncalibrated_regression",
            classification_thresholds=(
                {"no_fit_upper": th1_val, "good_fit_lower": th2_val} if has_calibrated_thresholds else None
            ),
            graph_mode=mode_str,
            model_version=meta.get("model_version", "paper-aligned-2025-v1"),
            checkpoint_name=meta["checkpoint_name"],
            checkpoint_sha256=meta["checkpoint_sha256"],
            input_validation=val_summary,
            resume_skill_attention=attn_map,
            inference_latency_ms=latency_ms,
            probability_calibration_disclaimer=(
                "Score represents GNN-predicted skill compatibility based on Baghbanzadeh & Wu (ICIT 2025) "
                "trained on skill_score (empirical View B dataset range [0.0, 0.5641], test 90th percentile = 0.2041). "
                "It is an uncalibrated regression output (calibration_status='UNCALIBRATED'), NOT a posterior probability "
                "of suitability. It does NOT evaluate holistic candidate suitability (e.g. experience, education, seniority, culture fit)."
            ),
        )

# Default singleton service instance.
gnn_inference_service = GNNInferenceService()
