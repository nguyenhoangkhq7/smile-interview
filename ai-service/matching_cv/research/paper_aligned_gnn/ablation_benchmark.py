"""5-Fold Group Cross-Validation Ablation Benchmark for Paper-Aligned vs Dependency-Aware Hybrid GNN.

Evaluates ALL 100 CV-JD pairs out-of-fold using strict group splitting by `jd_id` (zero JD/CV leakage):
1. SBERT Mean Max-Cosine Similarity Baseline
2. Bipartite Hybrid GNN (Baghbanzadeh & Wu, ICIT 2025 baseline; `use_skill_dependency_edges=False`)
3. Dependency-Aware Hybrid GNN — Directed Prerequisite DAG (`prerequisite_to` only)
4. Dependency-Aware Hybrid GNN — Bidirectional Prerequisite (`prerequisite_to` + `prerequisite_of`)

Outputs aggregate out-of-fold MSE, RMSE, MAE, Pearson r, Spearman rho, Paper Tolerance Acc (<=5pt, <=10pt),
and per-JD Mean NDCG@5 / NDCG@10 for direct inclusion in academic evaluation tables.
"""
from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path
import random
import sys
from typing import Any, Dict, List
import numpy as np
import scipy.stats
from sklearn.metrics import ndcg_score
import torch
import torch.nn as nn
from torch_geometric.data import HeteroData

ai_service_dir = Path(__file__).resolve().parents[3]
if str(ai_service_dir) not in sys.path:
    sys.path.insert(0, str(ai_service_dir))

from matching_cv.app.core.config import settings
from matching_cv.research.paper_aligned_gnn.hybrid_gnn import (
    PaperAlignedGNNConfig,
    PaperAlignedHybridGNN,
    compute_paper_tolerance_accuracy,
)
from matching_cv.research.paper_aligned_gnn.train_gnn import evaluate_dataset, set_seed

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("ablation_benchmark")


def _aggregate_predictions(
    preds: List[float],
    targets: List[float],
    jd_ids: List[str],
) -> Dict[str, Any]:
    p_arr = np.array(preds, dtype=np.float64)
    t_arr = np.array(targets, dtype=np.float64)
    mse = float(np.mean((p_arr - t_arr) ** 2))
    rmse = float(np.sqrt(mse))
    mae = float(np.mean(np.abs(p_arr - t_arr)))
    pearson_r, _ = scipy.stats.pearsonr(p_arr, t_arr) if np.std(p_arr) > 1e-8 else (0.0, 0.0)
    spearman_rho, _ = scipy.stats.spearmanr(p_arr, t_arr) if np.std(p_arr) > 1e-8 else (0.0, 0.0)
    acc_5 = compute_paper_tolerance_accuracy(preds, targets, scale="0_1", tolerance_points_on_100=5.0)
    acc_10 = compute_paper_tolerance_accuracy(preds, targets, scale="0_1", tolerance_points_on_100=10.0)

    by_jd: Dict[str, Dict[str, List[float]]] = {}
    for p, t, jid in zip(preds, targets, jd_ids):
        by_jd.setdefault(jid, {"preds": [], "targets": []})
        by_jd[jid]["preds"].append(p)
        by_jd[jid]["targets"].append(t)

    ndcg5_list, ndcg10_list = [], []
    for d in by_jd.values():
        if len(d["targets"]) > 1:
            t_v = np.array([d["targets"]])
            p_v = np.array([d["preds"]])
            ndcg5_list.append(float(ndcg_score(t_v, p_v, k=min(5, len(d["targets"])))))
            ndcg10_list.append(float(ndcg_score(t_v, p_v, k=min(10, len(d["targets"])))))

    return {
        "count": len(preds),
        "mse": round(mse, 6),
        "rmse": round(rmse, 4),
        "mae": round(mae, 4),
        "pearson_r": round(float(pearson_r), 4),
        "spearman_rho": round(float(spearman_rho), 4),
        "paper_tolerance_acc_5pt": round(acc_5, 4),
        "paper_tolerance_acc_10pt": round(acc_10, 4),
        "mean_ndcg_5": round(float(np.mean(ndcg5_list)), 4) if ndcg5_list else 0.0,
        "mean_ndcg_10": round(float(np.mean(ndcg10_list)), 4) if ndcg10_list else 0.0,
    }


def _train_single_fold(
    train_graphs: List[HeteroData],
    val_graphs: List[HeteroData],
    test_graphs: List[HeteroData],
    *,
    use_skill_dependency_edges: bool,
    use_reverse_skill_dependency_edges: bool,
    dep_gate_init: float,
    dep_mode: str,
    epochs: int,
    lr: float,
    weight_decay: float,
    seed: int,
    device: torch.device,
) -> tuple[List[float], List[float], List[str]]:
    set_seed(seed)
    cfg = PaperAlignedGNNConfig(
        num_layers=2,
        input_dim=settings.STAGE3_EMBEDDING_DIM,
        hidden_dim=128,
        num_heads=1,
        leaky_relu_slope=0.2,
        dropout=0.05,
        mlp_hidden_dims=[128, 64],
        mlp_dropout=0.05,
        use_job_edge_weights=True,
        missing_job_weight_for_graphconv=1.0,
        use_resume_edge_weights=True,
        missing_resume_weight_for_gat=0.0,
        add_self_loops_in_gat=False,
        score_scale="0_1",
        use_skill_dependency_edges=use_skill_dependency_edges,
        use_reverse_skill_dependency_edges=use_reverse_skill_dependency_edges,
        skill_dependency_gate_init=dep_gate_init,
        skill_dependency_mode=dep_mode,
    )
    model = PaperAlignedHybridGNN(config=cfg).to(device)
    optimizer = torch.optim.AdamW(model.parameters(), lr=lr, weight_decay=weight_decay)
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=epochs, eta_min=1e-4)
    criterion = nn.MSELoss()

    best_loss = float("inf")
    best_state = None
    for epoch in range(1, epochs + 1):
        model.train()
        idxs = list(range(len(train_graphs)))
        random.shuffle(idxs)
        train_loss = 0.0
        for idx in idxs:
            g = train_graphs[idx].to(device)
            optimizer.zero_grad()
            out = model(g)
            loss = criterion(out["raw_score"].view(-1), g.y.view(-1).to(device))
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)
            optimizer.step()
            train_loss += float(loss.item())
        train_loss /= max(1, len(idxs))
        scheduler.step()
        val_m = evaluate_dataset(model, val_graphs, device)
        tracking = 0.6 * train_loss + 0.4 * val_m["mse"]
        if tracking < best_loss - 1e-5:
            best_loss = tracking
            best_state = {k: v.cpu().clone() for k, v in model.state_dict().items()}

    if best_state is not None:
        model.load_state_dict(best_state)
    model.eval()
    preds, targets, jds = [], [], []
    with torch.no_grad():
        for g in test_graphs:
            g = g.to(device)
            out = model(g)
            preds.append(float(out["bounded_score"].view(-1).item()))
            targets.append(float(g.y.view(-1).item()))
            jds.append(str(getattr(g, "jd_id", "unknown")))
    return preds, targets, jds


def run_ablation(
    processed_dir: str,
    report_out: str,
    epochs: int = 35,
    lr: float = 1e-3,
    weight_decay: float = 1e-5,
    seed: int = 42,
) -> Dict[str, Any]:
    proc = Path(processed_dir)
    all_graphs: List[HeteroData] = (
        torch.load(proc / "train_graphs.pt", map_location="cpu", weights_only=False)
        + torch.load(proc / "val_graphs.pt", map_location="cpu", weights_only=False)
        + torch.load(proc / "test_graphs.pt", map_location="cpu", weights_only=False)
    )
    manifest = json.loads((proc / "manifest.json").read_text(encoding="utf-8"))
    meta_by_pair = {p["pair_id"]: p for p in manifest.get("pairs_metadata", [])}

    jds = sorted({str(getattr(g, "jd_id", "")) for g in all_graphs})
    assert len(jds) == 10, f"Expected 10 JDs for 5-fold group CV, got {len(jds)}"
    folds = [jds[i : i + 2] for i in range(0, len(jds), 2)]
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    # 1. SBERT Cosine Baseline across all 100 pairs
    sbert_preds, sbert_targets, sbert_jds = [], [], []
    for g in all_graphs:
        pid = getattr(g, "pair_id", "")
        sbert_preds.append(float(meta_by_pair.get(pid, {}).get("sbert_cosine_score", 0.5)))
        sbert_targets.append(float(g.y.view(-1).item()))
        sbert_jds.append(str(getattr(g, "jd_id", "")))
    results: Dict[str, Any] = {
        "protocol": "5-fold Group CV by jd_id (zero JD/CV leakage, all 100 CV-JD pairs evaluated out-of-fold)",
        "epochs": epochs,
        "seed": seed,
        "sbert_cosine_baseline": _aggregate_predictions(sbert_preds, sbert_targets, sbert_jds),
    }

    variants = [
        ("bipartite_gnn_icit2025", False, False, 0.0, "light_sbert_diffusion"),
        ("dep_gnn_light_sbert_directed", True, False, 0.15, "light_sbert_diffusion"),
        ("dep_gnn_light_sbert_bidir", True, True, 0.15, "light_sbert_diffusion"),
        ("dep_gnn_modified_gat_bidir", True, True, 0.25, "modified_gat"),
    ]

    for name, use_dep, use_rev, gate_init, dep_mode in variants:
        logger.info(f"Running 5-fold Group CV for variant: {name}...")
        oof_preds, oof_targets, oof_jds = [], [], []
        for f_idx, test_jd_pair in enumerate(folds):
            test_set = set(test_jd_pair)
            remaining = [j for j in jds if j not in test_set]
            val_jd = {remaining[f_idx % len(remaining)]}
            train_set = set(remaining) - val_jd

            tr = [g for g in all_graphs if getattr(g, "jd_id", "") in train_set]
            va = [g for g in all_graphs if getattr(g, "jd_id", "") in val_jd]
            te = [g for g in all_graphs if getattr(g, "jd_id", "") in test_set]

            fp, ft, fj = _train_single_fold(
                tr, va, te,
                use_skill_dependency_edges=use_dep,
                use_reverse_skill_dependency_edges=use_rev,
                dep_gate_init=gate_init,
                dep_mode=dep_mode,
                epochs=epochs,
                lr=lr,
                weight_decay=weight_decay,
                seed=seed + f_idx,
                device=device,
            )
            oof_preds.extend(fp)
            oof_targets.extend(ft)
            oof_jds.extend(fj)

        results[name] = _aggregate_predictions(oof_preds, oof_targets, oof_jds)
        logger.info(f"  {name} OOF metrics: {results[name]}")

    out_path = Path(report_out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(results, indent=2), encoding="utf-8")
    logger.info(f"5-fold ablation benchmark report saved to {out_path}")
    return results


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="5-fold Group CV Ablation Benchmark for Dependency-Aware GNN.")
    parser.add_argument(
        "--processed-dir",
        type=str,
        default=r"ai-service\matching_cv\data\processed\paper_aligned_gnn_dep",
    )
    parser.add_argument(
        "--report-out",
        type=str,
        default=r"ai-service\matching_cv\data\checkpoints\paper_aligned_gnn\ablation_5fold_report.json",
    )
    parser.add_argument("--epochs", type=int, default=35)
    parser.add_argument("--lr", type=float, default=1e-3)
    parser.add_argument("--weight-decay", type=float, default=1e-5)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    run_ablation(
        processed_dir=args.processed_dir,
        report_out=args.report_out,
        epochs=args.epochs,
        lr=args.lr,
        weight_decay=args.weight_decay,
        seed=args.seed,
    )
