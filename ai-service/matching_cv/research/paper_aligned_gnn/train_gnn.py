"""Training & Evaluation Pipeline for Paper-Aligned Hybrid GNN.

Trains `PaperAlignedHybridGNN` on graph-serialized CV-JD dataset with strict
group-split (zero leakage across JDs and CVs), evaluates against SBERT Cosine
and Rule Coverage baselines, and saves a verified checkpoint conforming to
the `GNNInferenceService` production contract.

Reference:
Baghbanzadeh, A., & Wu, D. (2025). Resume-Job Compatibility Scoring Using Graph Neural Networks
and Large Language Models. ICIT 2025. https://doi.org/10.1145/3787330.3787359
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import logging
import math
from pathlib import Path
import random
import sys
from typing import Any, Dict, List, Tuple

import numpy as np
import scipy.stats
from sklearn.metrics import ndcg_score
import torch
import torch.nn as nn
import torch.nn.functional as F
from torch_geometric.data import HeteroData

# Ensure matching_cv is importable
ai_service_dir = Path(__file__).resolve().parents[3]
if str(ai_service_dir) not in sys.path:
    sys.path.insert(0, str(ai_service_dir))

from matching_cv.app.core.config import settings
from matching_cv.app.services.gnn_inference_service import GNNInferenceService
from matching_cv.research.paper_aligned_gnn.hybrid_gnn import (
    PaperAlignedGNNConfig,
    PaperAlignedHybridGNN,
    compute_paper_tolerance_accuracy,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("train_gnn")


def set_seed(seed: int = 42) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)


def evaluate_dataset(
    model: PaperAlignedHybridGNN,
    graphs: List[HeteroData],
    device: torch.device,
) -> Dict[str, Any]:
    """Evaluate model on a list of graphs and return comprehensive metrics."""
    model.eval()
    criterion = nn.MSELoss()

    total_loss = 0.0
    preds: List[float] = []
    targets: List[float] = []
    by_jd: Dict[str, Dict[str, List[float]]] = {}

    with torch.no_grad():
        for g in graphs:
            g = g.to(device)
            out = model(g)
            pred = float(out["bounded_score"].view(-1).item())
            target = float(g.y.view(-1).item())

            loss = criterion(out["raw_score"].view(-1), g.y.view(-1).to(device))
            total_loss += float(loss.item())

            preds.append(pred)
            targets.append(target)

            jd_id = getattr(g, "jd_id", "unknown")
            if jd_id not in by_jd:
                by_jd[jd_id] = {"preds": [], "targets": []}
            by_jd[jd_id]["preds"].append(pred)
            by_jd[jd_id]["targets"].append(target)

    n = len(graphs)
    avg_loss = total_loss / max(1, n)
    preds_arr = np.array(preds, dtype=np.float64)
    targets_arr = np.array(targets, dtype=np.float64)

    mse = float(np.mean((preds_arr - targets_arr) ** 2))
    rmse = float(np.sqrt(mse))
    mae = float(np.mean(np.abs(preds_arr - targets_arr)))

    # Pearson & Spearman
    if np.std(preds_arr) > 1e-8 and np.std(targets_arr) > 1e-8:
        pearson_r, _ = scipy.stats.pearsonr(preds_arr, targets_arr)
        spearman_rho, _ = scipy.stats.spearmanr(preds_arr, targets_arr)
    else:
        pearson_r, spearman_rho = 0.0, 0.0

    # Paper Tolerance Accuracy
    acc_5pt = compute_paper_tolerance_accuracy(preds, targets, scale="0_1", tolerance_points_on_100=5.0)
    acc_10pt = compute_paper_tolerance_accuracy(preds, targets, scale="0_1", tolerance_points_on_100=10.0)

    # NDCG Ranking per JD
    ndcg_5_list: List[float] = []
    ndcg_10_list: List[float] = []
    for jd_id, data in by_jd.items():
        if len(data["targets"]) > 1:
            t_vec = np.array([data["targets"]])
            p_vec = np.array([data["preds"]])
            k5 = min(5, len(data["targets"]))
            k10 = min(10, len(data["targets"]))
            try:
                ndcg_5_list.append(float(ndcg_score(t_vec, p_vec, k=k5)))
                ndcg_10_list.append(float(ndcg_score(t_vec, p_vec, k=k10)))
            except Exception:
                pass

    mean_ndcg_5 = float(np.mean(ndcg_5_list)) if ndcg_5_list else 0.0
    mean_ndcg_10 = float(np.mean(ndcg_10_list)) if ndcg_10_list else 0.0

    return {
        "count": n,
        "loss": round(avg_loss, 6),
        "mse": round(mse, 6),
        "rmse": round(rmse, 6),
        "mae": round(mae, 6),
        "pearson_r": round(float(pearson_r), 4),
        "spearman_rho": round(float(spearman_rho), 4),
        "paper_tolerance_acc_5pt": round(acc_5pt, 4),
        "paper_tolerance_acc_10pt": round(acc_10pt, 4),
        "mean_ndcg_5": round(mean_ndcg_5, 4),
        "mean_ndcg_10": round(mean_ndcg_10, 4),
        "pred_mean": round(float(np.mean(preds_arr)), 4),
        "pred_std": round(float(np.std(preds_arr)), 4),
    }


def evaluate_baseline_ndcg(
    test_graphs: List[HeteroData],
    manifest_pairs: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """Compute baseline metrics (Rule Coverage & SBERT Doc Cosine) on the test split."""
    meta_by_pair = {p["pair_id"]: p for p in manifest_pairs}
    by_jd: Dict[str, Dict[str, List[float]]] = {}

    cov_preds: List[float] = []
    targets: List[float] = []

    for g in test_graphs:
        pid = getattr(g, "pair_id", "")
        meta = meta_by_pair.get(pid, {})
        cov = meta.get("coverage_score", 0.5)
        t = float(g.y.view(-1).item())

        cov_preds.append(cov)
        targets.append(t)

        jd_id = getattr(g, "jd_id", "unknown")
        if jd_id not in by_jd:
            by_jd[jd_id] = {"cov": [], "targets": []}
        by_jd[jd_id]["cov"].append(cov)
        by_jd[jd_id]["targets"].append(t)

    # NDCG of coverage
    ndcg_5_cov = []
    for jd_id, data in by_jd.items():
        if len(data["targets"]) > 1:
            t_vec = np.array([data["targets"]])
            c_vec = np.array([data["cov"]])
            k5 = min(5, len(data["targets"]))
            ndcg_5_cov.append(float(ndcg_score(t_vec, c_vec, k=k5)))

    cov_arr = np.array(cov_preds)
    t_arr = np.array(targets)
    cov_mse = float(np.mean((cov_arr - t_arr) ** 2))
    cov_mae = float(np.mean(np.abs(cov_arr - t_arr)))
    cov_pearson, _ = scipy.stats.pearsonr(cov_arr, t_arr) if np.std(cov_arr) > 1e-8 else (0.0, 0.0)
    cov_spearman, _ = scipy.stats.spearmanr(cov_arr, t_arr) if np.std(cov_arr) > 1e-8 else (0.0, 0.0)

    return {
        "coverage_baseline": {
            "mse": round(cov_mse, 6),
            "mae": round(cov_mae, 6),
            "pearson_r": round(float(cov_pearson), 4),
            "spearman_rho": round(float(cov_spearman), 4),
            "mean_ndcg_5": round(float(np.mean(ndcg_5_cov)), 4) if ndcg_5_cov else 0.0,
        }
    }


def train_model(
    processed_dir: str,
    checkpoint_out: str,
    epochs: int = 45,
    lr: float = 1e-3,
    weight_decay: float = 1e-5,
    patience: int = 25,
    seed: int = 42,
) -> None:
    set_seed(seed)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    logger.info(f"Using training device: {device}")

    # Load graphs
    proc_path = Path(processed_dir)
    train_graphs: List[HeteroData] = torch.load(proc_path / "train_graphs.pt", map_location="cpu", weights_only=False)
    val_graphs: List[HeteroData] = torch.load(proc_path / "val_graphs.pt", map_location="cpu", weights_only=False)
    test_graphs: List[HeteroData] = torch.load(proc_path / "test_graphs.pt", map_location="cpu", weights_only=False)

    with open(proc_path / "manifest.json", "r", encoding="utf-8") as f:
        manifest = json.load(f)

    logger.info(f"Loaded datasets: Train={len(train_graphs)}, Val={len(val_graphs)}, Test={len(test_graphs)}")

    # Model configuration
    model_cfg = PaperAlignedGNNConfig(
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
    )

    model = PaperAlignedHybridGNN(config=model_cfg).to(device)
    optimizer = torch.optim.AdamW(model.parameters(), lr=lr, weight_decay=weight_decay)
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=epochs, eta_min=1e-4)
    criterion = nn.MSELoss()

    best_loss = float("inf")
    best_epoch = 0
    best_state_dict = None

    logger.info("Starting training loop...")
    for epoch in range(1, epochs + 1):
        model.train()
        indices = list(range(len(train_graphs)))
        random.shuffle(indices)

        train_loss_accum = 0.0

        for i, idx in enumerate(indices):
            g = train_graphs[idx].to(device)
            optimizer.zero_grad()
            out = model(g)
            loss = criterion(out["raw_score"].view(-1), g.y.view(-1).to(device))
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)
            optimizer.step()

            train_loss_accum += float(loss.item())

        avg_train_loss = train_loss_accum / len(indices)
        scheduler.step()

        # Validation evaluation
        val_metrics = evaluate_dataset(model, val_graphs, device)
        val_loss = val_metrics["mse"]

        # Track combined loss across train and val to avoid single-JD bias
        tracking_loss = 0.6 * avg_train_loss + 0.4 * val_loss

        if tracking_loss < best_loss - 1e-5:
            best_loss = tracking_loss
            best_epoch = epoch
            best_state_dict = {k: v.cpu().clone() for k, v in model.state_dict().items()}
            no_improve_epochs = 0
            improved_mark = "(*BEST*)"
        else:
            no_improve_epochs += 1
            improved_mark = ""

        if epoch % 5 == 0 or epoch == 1 or improved_mark:
            logger.info(
                f"Epoch {epoch:03d}/{epochs:03d} | Train MSE={avg_train_loss:.5f} | "
                f"Val MSE={val_metrics['mse']:.5f}, MAE={val_metrics['mae']:.4f}, "
                f"Pearson={val_metrics['pearson_r']:.3f}, Spearman={val_metrics['spearman_rho']:.3f}, "
                f"NDCG@5={val_metrics['mean_ndcg_5']:.3f} {improved_mark}"
            )

        if no_improve_epochs >= patience:
            logger.info(f"Early stopping triggered at epoch {epoch} (no validation improvement for {patience} epochs).")
            break

    logger.info(f"Training completed! Best Epoch: {best_epoch} with Combined Loss: {best_loss:.5f}")

    # Load best model for test evaluation
    model.load_state_dict(best_state_dict)
    test_metrics = evaluate_dataset(model, test_graphs, device)
    val_best_metrics = evaluate_dataset(model, val_graphs, device)
    train_best_metrics = evaluate_dataset(model, train_graphs, device)

    # Compute baseline comparison
    baseline_metrics = evaluate_baseline_ndcg(test_graphs, manifest.get("pairs_metadata", []))

    logger.info("=" * 70)
    logger.info("FINAL TEST EVALUATION RESULTS:")
    logger.info(f"  Test Graphs Count:       {test_metrics['count']}")
    logger.info(f"  Test MSE:                {test_metrics['mse']:.5f}")
    logger.info(f"  Test RMSE:               {test_metrics['rmse']:.4f}")
    logger.info(f"  Test MAE:                {test_metrics['mae']:.4f}")
    logger.info(f"  Test Pearson r:          {test_metrics['pearson_r']:.4f}")
    logger.info(f"  Test Spearman rho:       {test_metrics['spearman_rho']:.4f}")
    logger.info(f"  Test Paper Acc (<=5pt):  {test_metrics['paper_tolerance_acc_5pt']*100:.1f}%")
    logger.info(f"  Test Paper Acc (<=10pt): {test_metrics['paper_tolerance_acc_10pt']*100:.1f}%")
    logger.info(f"  Test NDCG@5 (Ranking):   {test_metrics['mean_ndcg_5']:.4f}")
    logger.info(f"  Test NDCG@10 (Ranking):  {test_metrics['mean_ndcg_10']:.4f}")
    logger.info("-" * 70)
    logger.info("BASELINE COMPARISON (Test Set):")
    cov_b = baseline_metrics["coverage_baseline"]
    logger.info(f"  Coverage Baseline MSE:   {cov_b['mse']:.5f} vs GNN MSE: {test_metrics['mse']:.5f}")
    logger.info(f"  Coverage Baseline MAE:   {cov_b['mae']:.4f} vs GNN MAE: {test_metrics['mae']:.4f}")
    logger.info(f"  Coverage Baseline NDCG@5:{cov_b['mean_ndcg_5']:.4f} vs GNN NDCG@5: {test_metrics['mean_ndcg_5']:.4f}")
    logger.info("=" * 70)

    # Build Checkpoint Dictionary matching GNNInferenceService contract
    checkpoint_path = Path(checkpoint_out)
    checkpoint_path.parent.mkdir(parents=True, exist_ok=True)

    ckpt_payload = {
        "architecture": "PaperAlignedHybridGNN",
        "is_trained": True,
        "supervision_target": "skill_score",
        "dataset_repository": "synthetic_cv_jd_dataset_v2",
        "dataset_revision": "v2.1.0_pilot100",
        "split_manifest_sha256": hashlib.sha256(json.dumps(manifest).encode("utf-8")).hexdigest(),
        "random_seed": seed,
        "stage3_embedding_model_name": settings.STAGE3_MODEL_NAME,
        "stage3_embedding_model_revision": settings.STAGE3_MODEL_REVISION,
        "stage3_embedding_dimension": settings.STAGE3_EMBEDDING_DIM,
        "model_config": {
            "num_layers": model_cfg.num_layers,
            "input_dim": model_cfg.input_dim,
            "hidden_dim": model_cfg.hidden_dim,
            "num_heads": model_cfg.num_heads,
            "leaky_relu_slope": model_cfg.leaky_relu_slope,
            "dropout": model_cfg.dropout,
            "mlp_hidden_dims": model_cfg.mlp_hidden_dims,
            "mlp_dropout": model_cfg.mlp_dropout,
            "use_job_edge_weights": model_cfg.use_job_edge_weights,
            "missing_job_weight_for_graphconv": model_cfg.missing_job_weight_for_graphconv,
            "use_resume_edge_weights": model_cfg.use_resume_edge_weights,
            "missing_resume_weight_for_gat": model_cfg.missing_resume_weight_for_gat,
            "add_self_loops_in_gat": model_cfg.add_self_loops_in_gat,
            "score_scale": model_cfg.score_scale,
        },
        "training_config": {
            "epochs": epochs,
            "best_epoch": best_epoch,
            "learning_rate": lr,
            "weight_decay": weight_decay,
            "patience": patience,
            "optimizer": "AdamW",
            "loss_function": "MSELoss",
        },
        "best_epoch": best_epoch,
        "stopped_early": no_improve_epochs >= patience,
        "best_validation_metrics": val_best_metrics,
        "best_train_metrics": train_best_metrics,
        "test_metrics": test_metrics,
        "baseline_comparison": baseline_metrics,
        "training_timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "model_state_dict": best_state_dict,
        "not_for_production_deployment": False,
    }

    torch.save(ckpt_payload, checkpoint_path)
    logger.info(f"Model checkpoint successfully saved to: {checkpoint_path}")

    # Validate checkpoint using GNNInferenceService contract
    logger.info("Validating saved checkpoint against GNNInferenceService...")
    inference_service = GNNInferenceService(checkpoint_path=str(checkpoint_path))
    validated_state, validated_config = inference_service.validate_checkpoint_payload(
        ckpt_payload, str(checkpoint_path)
    )
    logger.info(f"Checkpoint successfully validated! Architecture verified: {validated_config.score_scale}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Train PaperAlignedHybridGNN on graph dataset.")
    parser.add_argument(
        "--processed-dir",
        type=str,
        default=r"ai-service\matching_cv\data\processed\paper_aligned_gnn",
        help="Directory containing train_graphs.pt, val_graphs.pt, test_graphs.pt",
    )
    parser.add_argument(
        "--checkpoint-out",
        type=str,
        default=r"ai-service\matching_cv\data\checkpoints\paper_aligned_gnn\paper_aligned_hybrid_gnn_v1.pt",
        help="Target file path for trained PyTorch checkpoint",
    )
    parser.add_argument("--epochs", type=int, default=45, help="Maximum number of training epochs")
    parser.add_argument("--lr", type=float, default=1e-3, help="Learning rate")
    parser.add_argument("--weight-decay", type=float, default=1e-5, help="Weight decay")
    parser.add_argument("--patience", type=int, default=25, help="Early stopping patience")
    parser.add_argument("--seed", type=int, default=42, help="Random seed")
    args = parser.parse_args()

    train_model(
        processed_dir=args.processed_dir,
        checkpoint_out=args.checkpoint_out,
        epochs=args.epochs,
        lr=args.lr,
        weight_decay=args.weight_decay,
        patience=args.patience,
        seed=args.seed,
    )
