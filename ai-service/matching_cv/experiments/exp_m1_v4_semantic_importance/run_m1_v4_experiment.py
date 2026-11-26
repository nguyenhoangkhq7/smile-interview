"""Local 5-seed Re-evaluation of Module 1 (v4 Semantic-Importance Architecture).

Re-runs the exact Module 1 benchmark protocol (80 train / 20 val / 112 locked independent test,
5 fixed seeds: 42, 102, 202, 302, 402; metrics: Macro-MAE, Macro-NDCG@5, Macro-Spearman)
100% locally with ZERO external LLM / OpenRouter calls:
  1. Preserves exact option1_locked graph topology, extracted skills, 768D SBERT embeddings,
     skill-skill dependency edges, and locked rubric ground-truth scores `y`.
  2. Re-weights JD <-> Skill edges using local JSI-v1 (`ProductionSkillImportanceService`)
     on the original JD texts (10 synthetic JDs + 14 matched public JDs from resume-ats-score-v1-en).
  3. Sets CV <-> Skill edges to uniform 1.0 (zero CV proficiency weights).
  4. Trains & evaluates:
       - Baselines: SBERT cosine, SBERT + Ridge (pooled SBERT embeddings, alpha tuned on val)
       - New v4 GNN variants (5 seeds each):
           * gnn_v4_bipartite
           * gnn_v4_dependency
           * gnn_v4_full (Semantic-Importance + Asymmetric SBERT DAG Diffusion)
           * gnn_v4_full_no_wj (Ablation: uniform JD edges = 1.0)
       - Historical reference (evaluated identically from existing exp_m1_reval_20261121 checkpoints):
           * old_gnn_v1_bipartite, old_gnn_v2_dependency, old_gnn_v3_full, old_gnn_v3_no_prof
"""
from __future__ import annotations

import csv
from dataclasses import asdict
import glob
import json
import logging
import os
import random
import re
import sys
import time
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import scipy.stats
import torch
import torch.nn as nn
import torch.nn.functional as F
from sklearn.linear_model import Ridge
from sklearn.metrics import ndcg_score
from torch_geometric.data import HeteroData

# Ensure `matching_cv` is importable
THIS_FILE = Path(__file__).resolve()
MATCHING_CV_DIR = THIS_FILE.parents[2]
AI_SERVICE_DIR = THIS_FILE.parents[3]
if str(AI_SERVICE_DIR) not in sys.path:
    sys.path.insert(0, str(AI_SERVICE_DIR))

from matching_cv.app.services.production_skill_importance_service import (
    production_skill_importance_service,
)
from matching_cv.research.data.canonical_skill_normalizer import normalize_canonical_skill
from matching_cv.research.paper_aligned_gnn.hybrid_gnn import (
    PaperAlignedGNNConfig,
    PaperAlignedHybridGNN,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("exp_m1_v4")

SEEDS = [42, 102, 202, 302, 402]
JOB_FWD = ("job", "requires_skill", "skill")
JOB_REV = ("skill", "required_by_job", "job")
CV_FWD = ("resume", "has_skill", "skill")
CV_REV = ("skill", "in_resume", "resume")

OLD_EXP_DIR = MATCHING_CV_DIR / "experiments" / "exp_m1_reval_20261121"
OUT_DIR = THIS_FILE.parent
SYNTH_JOBS_PATH = (
    MATCHING_CV_DIR
    / "dataset"
    / "synthetic_cv_jd_dataset_v2"
    / "synthetic_cv_jd_dataset_v2"
    / "raw"
    / "jobs.jsonl"
)
PUBLIC_ATS_DIR = MATCHING_CV_DIR / "dataset" / "resume-ats-score-v1-en"


def set_seed(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)


# ---------------------------------------------------------------------------
# Step 1: Recover original JD texts & compute JSI-v1 importance weights w_j
# ---------------------------------------------------------------------------
def load_synthetic_jd_texts() -> Dict[str, Dict[str, Any]]:
    """Load the 10 synthetic JDs (jd_001..jd_010) from jobs.jsonl."""
    jobs: Dict[str, Dict[str, Any]] = {}
    with SYNTH_JOBS_PATH.open("r", encoding="utf-8") as fh:
        for line in fh:
            if not line.strip():
                continue
            obj = json.loads(line)
            jobs[str(obj["jd_id"])] = obj
    return jobs


def recover_real_test_jd_texts(test_graphs: List[HeteroData]) -> Tuple[Dict[str, str], Dict[str, Any]]:
    """Match all 14 real_jd_XXX graphs back to their verbatim JD text in resume-ats-score-v1-en."""
    all_jds: Dict[str, int] = {}
    for split in ("train.csv", "validation.csv"):
        csv_path = PUBLIC_ATS_DIR / split
        with csv_path.open("r", encoding="utf-8", errors="replace") as fh:
            for row in csv.DictReader(fh):
                parts = re.split(r"\s+SEP\s+", row["text"], maxsplit=1)
                if len(parts) == 2:
                    jd_txt = parts[1].strip()
                    all_jds[jd_txt] = all_jds.get(jd_txt, 0) + 1

    jd_skills: Dict[str, List[str]] = {}
    for g in test_graphs:
        jid = str(g.jd_id)
        if jid not in jd_skills:
            j_idx = g[JOB_FWD].edge_index[1].tolist()
            cids = list(g["skill"].canonical_ids)
            jd_skills[jid] = [cids[i] for i in j_idx]

    matched_texts: Dict[str, str] = {}
    match_audit: Dict[str, Any] = {}
    for jid, sks in sorted(jd_skills.items()):
        scored: List[Tuple[float, int, int, str]] = []
        for jd_txt, count in all_jds.items():
            low = jd_txt.lower()
            hits = 0
            for sk in sks:
                term = sk.replace("-", " ")
                if term in low or sk in low:
                    hits += 1
                else:
                    tokens = [tok for tok in term.split() if len(tok) >= 3]
                    if tokens and all(tok in low for tok in tokens):
                        hits += 1
            scored.append((hits / max(len(sks), 1), hits, count, jd_txt))
        scored.sort(key=lambda item: (item[0], item[2]), reverse=True)
        best_ratio, best_hits, best_cnt, best_text = scored[0]
        matched_texts[jid] = best_text
        match_audit[jid] = {
            "skill_match_hits": best_hits,
            "total_skills": len(sks),
            "skill_match_ratio": round(best_ratio, 4),
            "csv_occurrences": best_cnt,
            "jd_char_len": len(best_text),
            "jd_preview": best_text[:120],
        }
    return matched_texts, match_audit


def compute_jsi_weights_for_jd(
    jd_id: str,
    jd_text: str,
    canonical_skills: List[str],
    job_title: Optional[str] = None,
) -> Tuple[Dict[str, float], Dict[str, Any]]:
    """Compute local JSI-v1 importance weights w_j for a JD's extracted skill list."""
    explicit_skills = [
        {
            "skill_id": sk,
            "canonical_id": sk,
            "name": sk.replace("-", " "),
            "surface_forms": [sk.replace("-", " ")],
        }
        for sk in canonical_skills
    ]
    out = production_skill_importance_service.evaluate_jd_importance(
        jd_text=jd_text,
        explicit_skills=explicit_skills,
        implicit_skills=[],
        job_title=job_title,
        jd_id=jd_id,
        force_enable=True,
    )
    raw_map: Dict[str, float] = {}
    for rec in out.records:
        cid = normalize_canonical_skill(rec.skill_id) or rec.skill_id
        raw_map[rec.skill_id] = float(rec.weight)
        if cid:
            raw_map[cid] = float(rec.weight)

    weights: Dict[str, float] = {}
    mapped_count = 0
    for sk in canonical_skills:
        norm_sk = normalize_canonical_skill(sk) or sk
        if sk in raw_map:
            weights[sk] = float(np.clip(raw_map[sk], 0.05, 1.0))
            mapped_count += 1
        elif norm_sk in raw_map:
            weights[sk] = float(np.clip(raw_map[norm_sk], 0.05, 1.0))
            mapped_count += 1
        else:
            # Strict v4 fallback = 1.0 when JSI excludes or misses a skill
            weights[sk] = 1.0

    vals = list(weights.values())
    audit = {
        "status": out.status.value,
        "mapped_count": mapped_count,
        "total_skills": len(canonical_skills),
        "fallback_count": len(canonical_skills) - mapped_count,
        "min_w": round(float(min(vals)), 4) if vals else 0.0,
        "max_w": round(float(max(vals)), 4) if vals else 0.0,
        "mean_w": round(float(np.mean(vals)), 4) if vals else 0.0,
        "std_w": round(float(np.std(vals)), 4) if vals else 0.0,
    }
    return weights, audit


def reweight_graph_to_v4(g: HeteroData, jd_weight_map: Optional[Dict[str, float]]) -> HeteroData:
    """Clone a HeteroData graph and re-weight edges for v4 semantic-importance mode.

    - Job <-> Skill edges receive JSI-v1 importance weight w_j (fallback 1.0).
    - Resume <-> Skill edges receive uniform 1.0 (zero proficiency).
    - Skill <-> Skill edges, node embeddings, topology, and target y remain untouched.
    """
    ng = g.clone()
    cids = list(ng["skill"].canonical_ids)

    # 1. Job <-> Skill: JSI-v1 importance w_j
    if JOB_FWD in ng.edge_types and "edge_index" in ng[JOB_FWD]:
        j_skill_idxs = ng[JOB_FWD].edge_index[1].tolist()
        if j_skill_idxs:
            if jd_weight_map is not None:
                jw = torch.tensor(
                    [[float(jd_weight_map.get(cids[idx], 1.0))] for idx in j_skill_idxs],
                    dtype=torch.float32,
                )
            else:
                jw = torch.ones((len(j_skill_idxs), 1), dtype=torch.float32)
            ng[JOB_FWD].edge_attr = jw
            ng[JOB_FWD].edge_effective_weight = jw.squeeze(-1).clone()
            ng[JOB_FWD].edge_has_proficiency = torch.ones((len(j_skill_idxs),), dtype=torch.bool)
            if JOB_REV in ng.edge_types and "edge_index" in ng[JOB_REV]:
                ng[JOB_REV].edge_attr = jw.clone()
                ng[JOB_REV].edge_effective_weight = jw.squeeze(-1).clone()
                ng[JOB_REV].edge_has_proficiency = torch.ones((len(j_skill_idxs),), dtype=torch.bool)

    # 2. Resume <-> Skill: uniform 1.0 (pure semantic topology, zero CV proficiency)
    if CV_FWD in ng.edge_types and "edge_index" in ng[CV_FWD]:
        n_cv = int(ng[CV_FWD].edge_index.shape[1])
        if n_cv > 0:
            cw = torch.ones((n_cv, 1), dtype=torch.float32)
            ng[CV_FWD].edge_attr = cw
            ng[CV_FWD].edge_effective_weight = cw.squeeze(-1).clone()
            ng[CV_FWD].edge_has_proficiency = torch.zeros((n_cv,), dtype=torch.bool)
            if CV_REV in ng.edge_types and "edge_index" in ng[CV_REV]:
                ng[CV_REV].edge_attr = cw.clone()
                ng[CV_REV].edge_effective_weight = cw.squeeze(-1).clone()
                ng[CV_REV].edge_has_proficiency = torch.zeros((n_cv,), dtype=torch.bool)

    ng.edge_weight_mode = "semantic_importance"
    return ng


def reweight_asym_pairs_to_v4(pairs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Re-weight counterfactual asymmetry pairs to uniform 1.0 (no proficiency)."""
    out: List[Dict[str, Any]] = []
    for rec in pairs:
        new_rec = dict(rec)
        new_rec["g_higher"] = reweight_graph_to_v4(rec["g_higher"], jd_weight_map=None)
        new_rec["g_lower"] = reweight_graph_to_v4(rec["g_lower"], jd_weight_map=None)
        out.append(new_rec)
    return out


# ---------------------------------------------------------------------------
# Step 2: Metrics (identical per-JD macro protocol to original experiment)
# ---------------------------------------------------------------------------
def evaluate_predictions(
    graphs: List[HeteroData],
    preds: List[float],
) -> Dict[str, Any]:
    """Compute per-JD macro metrics (Macro-MAE, Macro-NDCG@5, Macro-Spearman) + pooled stats."""
    by_jd: Dict[str, Dict[str, List[float]]] = defaultdict(lambda: {"p": [], "t": []})
    targets = [float(g.y.view(-1).item()) for g in graphs]

    for g, p, t in zip(graphs, preds, targets):
        jid = str(g.jd_id)
        by_jd[jid]["p"].append(float(p))
        by_jd[jid]["t"].append(float(t))

    per_jd: Dict[str, Dict[str, float]] = {}
    maes, mses, ndcg5s, spearmans, pearsons = [], [], [], [], []
    for jid, d in sorted(by_jd.items()):
        yp = np.array(d["p"], dtype=np.float64)
        yt = np.array(d["t"], dtype=np.float64)
        mae = float(np.mean(np.abs(yp - yt)))
        mse = float(np.mean((yp - yt) ** 2))
        if len(yt) > 1 and float(np.sum(yt)) > 0.0:
            n5 = float(ndcg_score(yt.reshape(1, -1), yp.reshape(1, -1), k=min(5, len(yt))))
        else:
            n5 = 1.0
        if np.std(yp) > 1e-8 and np.std(yt) > 1e-8:
            rho = float(scipy.stats.spearmanr(yp, yt).statistic)
            pr = float(scipy.stats.pearsonr(yp, yt).statistic)
        else:
            rho, pr = 0.0, 0.0
        maes.append(mae)
        mses.append(mse)
        ndcg5s.append(n5)
        spearmans.append(rho)
        pearsons.append(pr)
        per_jd[jid] = {
            "n": len(yt),
            "mae_0_1": round(mae, 6),
            "mae_100": round(mae * 100.0, 3),
            "ndcg5": round(n5, 4),
            "spearman": round(rho, 4),
            "pearson": round(pr, 4),
        }

    p_all = np.array(preds, dtype=np.float64)
    t_all = np.array(targets, dtype=np.float64)
    pooled_mae = float(np.mean(np.abs(p_all - t_all)))
    pooled_rmse = float(np.sqrt(np.mean((p_all - t_all) ** 2)))
    if np.std(p_all) > 1e-8 and np.std(t_all) > 1e-8:
        pooled_pr = float(scipy.stats.pearsonr(p_all, t_all).statistic)
        pooled_rho = float(scipy.stats.spearmanr(p_all, t_all).statistic)
    else:
        pooled_pr, pooled_rho = 0.0, 0.0

    return {
        "n_pairs": len(graphs),
        "n_jds": len(by_jd),
        "macro_mae_0_1": round(float(np.mean(maes)), 6),
        "macro_mae_100": round(float(np.mean(maes) * 100.0), 3),
        "macro_mse_0_1": round(float(np.mean(mses)), 6),
        "macro_ndcg5": round(float(np.mean(ndcg5s)), 4),
        "macro_spearman": round(float(np.mean(spearmans)), 4),
        "macro_pearson": round(float(np.mean(pearsons)), 4),
        "pooled_mae_100": round(pooled_mae * 100.0, 3),
        "pooled_rmse_100": round(pooled_rmse * 100.0, 3),
        "pooled_pearson": round(pooled_pr, 4),
        "pooled_spearman": round(pooled_rho, 4),
        "per_jd": per_jd,
    }


def evaluate_asymmetry_pairs(
    model: PaperAlignedHybridGNN,
    pairs: List[Dict[str, Any]],
    device: torch.device,
) -> Dict[str, float]:
    """Evaluate pairwise directional accuracy (score(g_higher) > score(g_lower))."""
    if not pairs:
        return {"count": 0, "accuracy": 0.0, "mean_gap": 0.0}
    model.eval()
    correct = 0
    gaps: List[float] = []
    with torch.no_grad():
        for rec in pairs:
            s_hi = float(model(rec["g_higher"].to(device))["bounded_score"].view(-1).item())
            s_lo = float(model(rec["g_lower"].to(device))["bounded_score"].view(-1).item())
            gap = s_hi - s_lo
            if gap > 0.0:
                correct += 1
            gaps.append(gap)
    return {
        "count": len(pairs),
        "accuracy": round(correct / len(pairs), 4),
        "mean_gap": round(float(np.mean(gaps)), 4),
    }


# ---------------------------------------------------------------------------
# Step 3: Non-graph SBERT Baselines (SBERT cosine & SBERT + Ridge)
# ---------------------------------------------------------------------------
def extract_sbert_similarity_features(g: HeteroData) -> np.ndarray:
    """Build compact, domain-transferable SBERT cosine distribution features (11D)."""
    skill_x = g["skill"].x.detach().cpu().numpy()
    j_idx = (
        g[JOB_FWD].edge_index[1].detach().cpu().numpy()
        if JOB_FWD in g.edge_types and "edge_index" in g[JOB_FWD]
        else np.array([], dtype=int)
    )
    c_idx = (
        g[CV_FWD].edge_index[1].detach().cpu().numpy()
        if CV_FWD in g.edge_types and "edge_index" in g[CV_FWD]
        else np.array([], dtype=int)
    )
    if len(j_idx) == 0 or len(c_idx) == 0:
        return np.zeros(11, dtype=np.float32)

    jm = skill_x[j_idx]
    cm = skill_x[c_idx]
    jm_n = jm / np.maximum(np.linalg.norm(jm, axis=1, keepdims=True), 1e-8)
    cm_n = cm / np.maximum(np.linalg.norm(cm, axis=1, keepdims=True), 1e-8)
    sim = np.clip(jm_n @ cm_n.T, 0.0, 1.0)

    max_j2c = sim.max(axis=1)
    max_c2j = sim.max(axis=0)

    # w_j weighted max-cosine
    if "edge_attr" in g[JOB_FWD] and g[JOB_FWD].edge_attr is not None:
        w = g[JOB_FWD].edge_attr.detach().cpu().numpy().reshape(-1)
        w_max_j2c = float(np.sum(max_j2c * w) / max(float(w.sum()), 1e-8))
    else:
        w_max_j2c = float(np.mean(max_j2c))

    u_jd = jm.mean(axis=0)
    u_cv = cm.mean(axis=0)
    n_jd, n_cv = np.linalg.norm(u_jd), np.linalg.norm(u_cv)
    pooled_cos = float(np.dot(u_jd, u_cv) / (n_jd * n_cv)) if (n_jd > 1e-8 and n_cv > 1e-8) else 0.0

    shared_ratio = float(len(set(j_idx.tolist()) & set(c_idx.tolist())) / max(len(set(j_idx.tolist())), 1))
    q25, q50, q75 = np.percentile(max_j2c, [25, 50, 75])

    return np.array(
        [
            float(np.mean(max_j2c)),
            float(np.mean(max_c2j)),
            w_max_j2c,
            pooled_cos,
            float(q25),
            float(q50),
            float(q75),
            float(np.mean(max_j2c >= 0.50)),
            float(np.mean(max_j2c >= 0.70)),
            float(np.mean(max_j2c >= 0.85)),
            shared_ratio,
        ],
        dtype=np.float32,
    )


def _fit_best_ridge(
    X_tr: np.ndarray,
    y_tr: np.ndarray,
    X_va: np.ndarray,
    val_graphs: List[HeteroData],
    X_te: np.ndarray,
) -> Tuple[float, List[float], List[float]]:
    mu = X_tr.mean(axis=0, keepdims=True)
    sd = np.maximum(X_tr.std(axis=0, keepdims=True), 1e-6)
    X_tr_s = (X_tr - mu) / sd
    X_va_s = (X_va - mu) / sd
    X_te_s = (X_te - mu) / sd

    best_alpha = 10.0
    best_val_mae = float("inf")
    best_model: Optional[Ridge] = None
    for alpha in (0.1, 1.0, 3.0, 10.0, 30.0, 100.0, 300.0, 1000.0):
        reg = Ridge(alpha=alpha)
        reg.fit(X_tr_s, y_tr)
        p_va = np.clip(reg.predict(X_va_s), 0.0, 1.0).tolist()
        m_va = evaluate_predictions(val_graphs, p_va)
        if m_va["macro_mae_0_1"] < best_val_mae:
            best_val_mae = m_va["macro_mae_0_1"]
            best_alpha = alpha
            best_model = reg

    assert best_model is not None
    return (
        best_alpha,
        np.clip(best_model.predict(X_va_s), 0.0, 1.0).tolist(),
        np.clip(best_model.predict(X_te_s), 0.0, 1.0).tolist(),
    )


def run_sbert_baselines(
    train_graphs: List[HeteroData],
    val_graphs: List[HeteroData],
    test_graphs: List[HeteroData],
) -> Dict[str, Any]:
    """Evaluate SBERT cosine and SBERT + Ridge (alpha selected strictly on validation Macro-MAE)."""
    val_cos = [float(getattr(g, "sbert_cosine_score", 0.0)) for g in val_graphs]
    test_cos = [float(getattr(g, "sbert_cosine_score", 0.0)) for g in test_graphs]
    y_tr = np.array([float(g.y.view(-1).item()) for g in train_graphs], dtype=np.float64)

    # SBERT + Ridge (11D SBERT similarity distribution + w_j max-cos + overlap)
    X_tr = np.stack([extract_sbert_similarity_features(g) for g in train_graphs])
    X_va = np.stack([extract_sbert_similarity_features(g) for g in val_graphs])
    X_te = np.stack([extract_sbert_similarity_features(g) for g in test_graphs])
    best_alpha, ridge_val_preds, ridge_test_preds = _fit_best_ridge(X_tr, y_tr, X_va, val_graphs, X_te)

    # SBERT + Ridge (1D calibrated cosine only)
    X1_tr = np.array([[float(getattr(g, "sbert_cosine_score", 0.0))] for g in train_graphs], dtype=np.float64)
    X1_va = np.array([[float(getattr(g, "sbert_cosine_score", 0.0))] for g in val_graphs], dtype=np.float64)
    X1_te = np.array([[float(getattr(g, "sbert_cosine_score", 0.0))] for g in test_graphs], dtype=np.float64)
    best_alpha_1d, r1_val, r1_test = _fit_best_ridge(X1_tr, y_tr, X1_va, val_graphs, X1_te)

    non_empty_idx = [i for i, g in enumerate(test_graphs) if int(g[CV_FWD].edge_index.shape[1]) > 0]
    te_ne = [test_graphs[i] for i in non_empty_idx]

    return {
        "sbert_cosine": {
            "val": evaluate_predictions(val_graphs, val_cos),
            "test": evaluate_predictions(test_graphs, test_cos),
            "test_non_empty_cv82": evaluate_predictions(te_ne, [test_cos[i] for i in non_empty_idx]),
            "test_preds": test_cos,
        },
        "sbert_ridge": {
            "selected_alpha": best_alpha,
            "val": evaluate_predictions(val_graphs, ridge_val_preds),
            "test": evaluate_predictions(test_graphs, ridge_test_preds),
            "test_non_empty_cv82": evaluate_predictions(te_ne, [ridge_test_preds[i] for i in non_empty_idx]),
            "test_preds": ridge_test_preds,
        },
        "sbert_ridge_1d": {
            "selected_alpha": best_alpha_1d,
            "val": evaluate_predictions(val_graphs, r1_val),
            "test": evaluate_predictions(test_graphs, r1_test),
            "test_non_empty_cv82": evaluate_predictions(te_ne, [r1_test[i] for i in non_empty_idx]),
            "test_preds": r1_test,
        },
    }


# ---------------------------------------------------------------------------
# Step 4: GNN Training Loop (pure Validation Macro-MAE checkpoint selection)
# ---------------------------------------------------------------------------
def train_single_seed(
    variant_name: str,
    model_cfg: PaperAlignedGNNConfig,
    train_graphs: List[HeteroData],
    val_graphs: List[HeteroData],
    test_graphs: List[HeteroData],
    asym_train_pairs: List[Dict[str, Any]],
    asym_eval_zero_shot: List[Dict[str, Any]],
    asym_eval_with_rel: List[Dict[str, Any]],
    *,
    lr: float,
    asym_loss_weight: float,
    seed: int,
    epochs: int = 55,
    patience: int = 18,
    ckpt_out: Optional[Path] = None,
) -> Dict[str, Any]:
    """Train one GNN seed selecting strictly on pure Validation Macro-per-JD MAE."""
    set_seed(seed)
    device = torch.device("cpu")
    model = PaperAlignedHybridGNN(config=model_cfg).to(device)
    optimizer = torch.optim.AdamW(model.parameters(), lr=lr, weight_decay=1e-5)
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=epochs, eta_min=1e-4)
    criterion = nn.MSELoss()

    best_val_mae = float("inf")
    best_epoch = 0
    best_state = None
    best_val_metrics: Dict[str, Any] = {}
    no_improve = 0
    batch_size = 2

    for epoch in range(1, epochs + 1):
        model.train()
        idxs = list(range(len(train_graphs)))
        random.shuffle(idxs)
        asym_pool = list(range(len(asym_train_pairs)))
        random.shuffle(asym_pool)
        asym_ptr = 0

        for start in range(0, len(idxs), batch_size):
            batch = idxs[start : start + batch_size]
            optimizer.zero_grad()

            losses = []
            for idx in batch:
                g = train_graphs[idx].to(device)
                out = model(g)
                losses.append(criterion(out["raw_score"].view(-1), g.y.view(-1).to(device)))
            total_loss = torch.stack(losses).mean()

            if asym_train_pairs and asym_loss_weight > 0.0:
                rec = asym_train_pairs[asym_pool[asym_ptr % len(asym_pool)]]
                asym_ptr += 1
                g_hi = rec["g_higher"].to(device)
                g_lo = rec["g_lower"].to(device)
                margin = 0.26 if rec.get("kind") == "solo" else 0.08
                s_hi = model(g_hi)["raw_score"].view(-1)
                s_lo = model(g_lo)["raw_score"].view(-1)
                rank_a = F.relu(margin - (s_hi - s_lo)).mean()
                if rec.get("kind") == "solo":
                    rank_a = (
                        rank_a
                        + 0.25 * F.relu(s_hi - 0.78).pow(2).mean()
                        + 0.25 * F.relu(0.58 - s_hi).pow(2).mean()
                        + 0.35 * F.relu(0.20 - s_lo).pow(2).mean()
                        + 0.25 * F.relu(s_lo - 0.38).pow(2).mean()
                    )
                total_loss = total_loss + asym_loss_weight * rank_a

            total_loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)
            optimizer.step()

        scheduler.step()

        # Pure validation Macro-per-JD MAE selection
        model.eval()
        val_preds: List[float] = []
        with torch.no_grad():
            for g in val_graphs:
                val_preds.append(float(model(g.to(device))["bounded_score"].view(-1).item()))
        val_m = evaluate_predictions(val_graphs, val_preds)

        if val_m["macro_mae_0_1"] < best_val_mae - 1e-6:
            best_val_mae = val_m["macro_mae_0_1"]
            best_epoch = epoch
            best_val_metrics = val_m
            best_state = {k: v.cpu().clone() for k, v in model.state_dict().items()}
            no_improve = 0
        else:
            no_improve += 1
            if no_improve >= patience:
                break

    assert best_state is not None
    model.load_state_dict(best_state)
    model.eval()

    if ckpt_out is not None:
        ckpt_out.parent.mkdir(parents=True, exist_ok=True)
        torch.save(
            {
                "experiment_id": "exp_m1_v4_semantic_importance",
                "architecture": "PaperAlignedHybridGNN",
                "model_version": variant_name,
                "is_trained": True,
                "edge_weight_mode": "semantic_importance",
                "random_seed": seed,
                "model_config": asdict(model_cfg),
                "training_config": {
                    "training_pool": "development_train_jd001_jd008",
                    "lr": lr,
                    "epochs": epochs,
                    "best_epoch": best_epoch,
                    "patience": patience,
                    "asym_loss_weight": asym_loss_weight,
                    "depth_loss_weight": 0.0,
                    "checkpoint_selection": "pure_validation_macro_per_jd_mae",
                },
                "best_val_metrics": best_val_metrics,
                "model_state_dict": best_state,
            },
            ckpt_out,
        )

    test_preds: List[float] = []
    with torch.no_grad():
        for g in test_graphs:
            test_preds.append(float(model(g.to(device))["bounded_score"].view(-1).item()))

    non_empty_idx = [i for i, g in enumerate(test_graphs) if int(g[CV_FWD].edge_index.shape[1]) > 0]
    te_ne = [test_graphs[i] for i in non_empty_idx]

    return {
        "seed": seed,
        "best_epoch": best_epoch,
        "val": best_val_metrics,
        "test": evaluate_predictions(test_graphs, test_preds),
        "test_non_empty_cv82": evaluate_predictions(te_ne, [test_preds[i] for i in non_empty_idx]),
        "asym_zero_shot": evaluate_asymmetry_pairs(model, asym_eval_zero_shot, device),
        "asym_with_rel": evaluate_asymmetry_pairs(model, asym_eval_with_rel, device),
        "test_preds": test_preds,
    }


def aggregate_seed_runs(runs: List[Dict[str, Any]], split_key: str = "test") -> Dict[str, Any]:
    """Compute mean +- std across seeds + average per-JD metrics."""
    def _stats(vals: List[float], digits: int = 4) -> Dict[str, float]:
        arr = np.array(vals, dtype=np.float64)
        return {
            "mean": round(float(np.mean(arr)), digits),
            "std": round(float(np.std(arr, ddof=0)), digits),
            "min": round(float(np.min(arr)), digits),
            "max": round(float(np.max(arr)), digits),
        }

    # Aggregate per-JD averages across seeds for cluster bootstrap comparisons
    jd_ids = sorted(runs[0][split_key]["per_jd"].keys())
    per_jd_mean: Dict[str, Dict[str, float]] = {}
    for jid in jd_ids:
        per_jd_mean[jid] = {
            "mae_100": round(float(np.mean([r[split_key]["per_jd"][jid]["mae_100"] for r in runs])), 3),
            "ndcg5": round(float(np.mean([r[split_key]["per_jd"][jid]["ndcg5"] for r in runs])), 4),
            "spearman": round(float(np.mean([r[split_key]["per_jd"][jid]["spearman"] for r in runs])), 4),
        }

    out: Dict[str, Any] = {
        "n_seeds": len(runs),
        "macro_mae_100": _stats([r[split_key]["macro_mae_100"] for r in runs], 3),
        "macro_ndcg5": _stats([r[split_key]["macro_ndcg5"] for r in runs], 4),
        "macro_spearman": _stats([r[split_key]["macro_spearman"] for r in runs], 4),
        "macro_pearson": _stats([r[split_key]["macro_pearson"] for r in runs], 4),
        "pooled_mae_100": _stats([r[split_key]["pooled_mae_100"] for r in runs], 3),
        "pooled_rmse_100": _stats([r[split_key]["pooled_rmse_100"] for r in runs], 3),
        "per_jd_mean": per_jd_mean,
    }
    if "asym_zero_shot" in runs[0]:
        out["asym_zero_shot_acc"] = _stats([r["asym_zero_shot"]["accuracy"] for r in runs], 4)
        out["asym_zero_shot_gap"] = _stats([r["asym_zero_shot"]["mean_gap"] for r in runs], 4)
        out["asym_with_rel_acc"] = _stats([r["asym_with_rel"]["accuracy"] for r in runs], 4)
        out["asym_with_rel_gap"] = _stats([r["asym_with_rel"]["mean_gap"] for r in runs], 4)
    return out


def jd_cluster_bootstrap_delta(
    per_jd_a: Dict[str, Dict[str, float]],
    per_jd_b: Dict[str, Dict[str, float]],
    metric: str,
    n_boot: int = 5000,
    seed: int = 2026,
) -> Dict[str, float]:
    """Paired JD-cluster bootstrap for delta = A - B across the 14 independent JDs."""
    rng = np.random.default_rng(seed)
    jds = sorted(per_jd_a.keys())
    deltas = np.array([per_jd_a[j][metric] - per_jd_b[j][metric] for j in jds], dtype=np.float64)
    n = len(deltas)
    boot_means = np.empty(n_boot, dtype=np.float64)
    for b in range(n_boot):
        sample = rng.integers(0, n, size=n)
        boot_means[b] = float(np.mean(deltas[sample]))
    lo, hi = np.percentile(boot_means, [2.5, 97.5])
    return {
        "mean_delta": round(float(np.mean(deltas)), 4),
        "ci95_low": round(float(lo), 4),
        "ci95_high": round(float(hi), 4),
        "jds_a_better_or_equal": int(np.sum(deltas <= 0.0) if "mae" in metric else np.sum(deltas >= 0.0)),
        "total_jds": n,
    }


def evaluate_historical_old_checkpoints(
    old_val_graphs: List[HeteroData],
    old_test_graphs: List[HeteroData],
    old_asym_zero_shot: List[Dict[str, Any]],
    old_asym_with_rel: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """Evaluate existing old-architecture checkpoints with the exact same metric function."""
    keep_versions = {
        "gnn_v1_bipartite": "old_gnn_v1_bipartite",
        "gnn_v2_dependency": "old_gnn_v2_dependency",
        "gnn_v3_full": "old_gnn_v3_full",
        "gnn_v3_ablation_no_proficiency": "old_gnn_v3_no_proficiency",
    }
    non_empty_idx = [i for i, g in enumerate(old_test_graphs) if int(g[CV_FWD].edge_index.shape[1]) > 0]
    te_ne = [old_test_graphs[i] for i in non_empty_idx]

    grouped: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    device = torch.device("cpu")
    for ck_path in sorted(glob.glob(str(OLD_EXP_DIR / "checkpoints" / "*.pt"))):
        ck = torch.load(ck_path, map_location="cpu", weights_only=False)
        ver = ck.get("model_version")
        if ver not in keep_versions:
            continue
        cfg = PaperAlignedGNNConfig(**ck["model_config"])
        model = PaperAlignedHybridGNN(cfg).to(device)
        model.load_state_dict(ck["model_state_dict"])
        model.eval()
        with torch.no_grad():
            val_preds = [float(model(g)["bounded_score"].view(-1).item()) for g in old_val_graphs]
            test_preds = [float(model(g)["bounded_score"].view(-1).item()) for g in old_test_graphs]
        grouped[keep_versions[ver]].append(
            {
                "seed": ck.get("random_seed"),
                "val": evaluate_predictions(old_val_graphs, val_preds),
                "test": evaluate_predictions(old_test_graphs, test_preds),
                "test_non_empty_cv82": evaluate_predictions(te_ne, [test_preds[i] for i in non_empty_idx]),
                "asym_zero_shot": evaluate_asymmetry_pairs(model, old_asym_zero_shot, device),
                "asym_with_rel": evaluate_asymmetry_pairs(model, old_asym_with_rel, device),
            }
        )

    summary: Dict[str, Any] = {}
    for name, runs in sorted(grouped.items()):
        summary[name] = {
            "val": aggregate_seed_runs(runs, "val"),
            "test": aggregate_seed_runs(runs, "test"),
            "test_non_empty_cv82": aggregate_seed_runs(runs, "test_non_empty_cv82"),
        }
    return summary


# ---------------------------------------------------------------------------
# Main Orchestrator
# ---------------------------------------------------------------------------
def main() -> None:
    t_start = time.perf_counter()
    logger.info("=== Starting Module 1 v4 (Semantic-Importance) Local 5-Seed Re-evaluation ===")

    # 1. Load locked option1 graphs & diagnostics
    old_train = torch.load(OLD_EXP_DIR / "graphs" / "option1_locked" / "train_graphs.pt", map_location="cpu", weights_only=False)
    old_val = torch.load(OLD_EXP_DIR / "graphs" / "option1_locked" / "val_graphs.pt", map_location="cpu", weights_only=False)
    old_test = torch.load(OLD_EXP_DIR / "graphs" / "option1_locked" / "test_graphs.pt", map_location="cpu", weights_only=False)

    old_asym_train = torch.load(OLD_EXP_DIR / "diagnostics" / "asym_train_pairs.pt", map_location="cpu", weights_only=False)
    old_asym_eval_zs = torch.load(OLD_EXP_DIR / "diagnostics" / "asym_eval_true_zero_shot_no_edge.pt", map_location="cpu", weights_only=False)
    old_asym_eval_rel = torch.load(OLD_EXP_DIR / "diagnostics" / "asym_eval_with_graph_relation.pt", map_location="cpu", weights_only=False)

    logger.info(f"Loaded option1_locked graphs: train={len(old_train)}, val={len(old_val)}, test={len(old_test)}")

    # 2 & 3. Reuse cached v4 graphs if already generated, else compute JSI-v1 w_j and re-weight
    graphs_dir = OUT_DIR / "graphs"
    cached_ok = all(
        (graphs_dir / fn).is_file()
        for fn in ("train_graphs_v4.pt", "val_graphs_v4.pt", "test_graphs_v4.pt")
    ) and (OUT_DIR / "jsi_weights_audit.json").is_file()

    if cached_ok:
        logger.info("Loading cached JSI-v1 re-weighted v4 graphs from disk...")
        v4_train = torch.load(graphs_dir / "train_graphs_v4.pt", map_location="cpu", weights_only=False)
        v4_val = torch.load(graphs_dir / "val_graphs_v4.pt", map_location="cpu", weights_only=False)
        v4_test = torch.load(graphs_dir / "test_graphs_v4.pt", map_location="cpu", weights_only=False)
    else:
        synth_jobs = load_synthetic_jd_texts()
        real_jd_texts, real_match_audit = recover_real_test_jd_texts(old_test)

        jd_weight_maps: Dict[str, Dict[str, float]] = {}
        jsi_audit: Dict[str, Any] = {"synthetic_jds": {}, "real_test_jds": {}, "real_jd_text_recovery": real_match_audit}

        seen_synth: Dict[str, List[str]] = {}
        for g in old_train + old_val:
            jid = str(g.jd_id)
            if jid not in seen_synth:
                j_idx = g[JOB_FWD].edge_index[1].tolist()
                cids = list(g["skill"].canonical_ids)
                seen_synth[jid] = [cids[i] for i in j_idx]
        for jid, sks in sorted(seen_synth.items()):
            job = synth_jobs[jid]
            wmap, audit = compute_jsi_weights_for_jd(
                jd_id=jid,
                jd_text=job.get("jd_text", ""),
                canonical_skills=sks,
                job_title=job.get("title"),
            )
            jd_weight_maps[jid] = wmap
            jsi_audit["synthetic_jds"][jid] = audit

        seen_real: Dict[str, List[str]] = {}
        for g in old_test:
            jid = str(g.jd_id)
            if jid not in seen_real:
                j_idx = g[JOB_FWD].edge_index[1].tolist()
                cids = list(g["skill"].canonical_ids)
                seen_real[jid] = [cids[i] for i in j_idx]
        for jid, sks in sorted(seen_real.items()):
            wmap, audit = compute_jsi_weights_for_jd(
                jd_id=jid,
                jd_text=real_jd_texts[jid],
                canonical_skills=sks,
                job_title=None,
            )
            jd_weight_maps[jid] = wmap
            jsi_audit["real_test_jds"][jid] = audit

        logger.info("Computed JSI-v1 importance weights w_j for all 10 synthetic + 14 real JDs.")
        v4_train = [reweight_graph_to_v4(g, jd_weight_maps[str(g.jd_id)]) for g in old_train]
        v4_val = [reweight_graph_to_v4(g, jd_weight_maps[str(g.jd_id)]) for g in old_val]
        v4_test = [reweight_graph_to_v4(g, jd_weight_maps[str(g.jd_id)]) for g in old_test]

        graphs_dir.mkdir(parents=True, exist_ok=True)
        torch.save(v4_train, graphs_dir / "train_graphs_v4.pt")
        torch.save(v4_val, graphs_dir / "val_graphs_v4.pt")
        torch.save(v4_test, graphs_dir / "test_graphs_v4.pt")
        (OUT_DIR / "jsi_weights_audit.json").write_text(json.dumps(jsi_audit, indent=2), encoding="utf-8")

    v4_asym_train = reweight_asym_pairs_to_v4(old_asym_train)
    v4_asym_eval_zs = reweight_asym_pairs_to_v4(old_asym_eval_zs)
    v4_asym_eval_rel = reweight_asym_pairs_to_v4(old_asym_eval_rel)

    # 4. Run non-graph SBERT baselines
    logger.info("Evaluating SBERT cosine and SBERT + Ridge baselines...")
    baselines = run_sbert_baselines(v4_train, v4_val, v4_test)
    logger.info(
        f"  SBERT cosine  | Val MAE={baselines['sbert_cosine']['val']['macro_mae_100']:.2f} "
        f"| Test MAE={baselines['sbert_cosine']['test']['macro_mae_100']:.2f}, "
        f"NDCG@5={baselines['sbert_cosine']['test']['macro_ndcg5']:.4f}, "
        f"Spearman={baselines['sbert_cosine']['test']['macro_spearman']:.4f}"
    )
    logger.info(
        f"  SBERT + Ridge (alpha={baselines['sbert_ridge']['selected_alpha']}) "
        f"| Val MAE={baselines['sbert_ridge']['val']['macro_mae_100']:.2f} "
        f"| Test MAE={baselines['sbert_ridge']['test']['macro_mae_100']:.2f}, "
        f"NDCG@5={baselines['sbert_ridge']['test']['macro_ndcg5']:.4f}, "
        f"Spearman={baselines['sbert_ridge']['test']['macro_spearman']:.4f}"
    )

    # 5. Define & train v4 GNN variants across 5 fixed seeds
    base_kwargs = dict(
        num_layers=2,
        input_dim=768,
        hidden_dim=128,
        num_heads=1,
        leaky_relu_slope=0.2,
        dropout=0.1,
        mlp_hidden_dims=[128, 64],
        mlp_dropout=0.1,
        missing_job_weight_for_graphconv=1.0,
        use_resume_edge_weights=False,
        missing_resume_weight_for_gat=0.0,
        use_value_weight_modulation=False,
        add_self_loops_in_gat=False,
        score_scale="0_1",
        skill_dependency_gate_init=0.15,
    )

    variants = [
        (
            "gnn_v4_bipartite",
            PaperAlignedGNNConfig(
                **base_kwargs,
                use_job_edge_weights=True,
                use_skill_dependency_edges=False,
                use_reverse_skill_dependency_edges=False,
                skill_dependency_mode="light_sbert_diffusion",
            ),
            1e-3,
            0.0,
        ),
        (
            "gnn_v4_dependency",
            PaperAlignedGNNConfig(
                **base_kwargs,
                use_job_edge_weights=True,
                use_skill_dependency_edges=True,
                use_reverse_skill_dependency_edges=False,
                skill_dependency_mode="light_sbert_diffusion",
            ),
            1e-3,
            0.0,
        ),
        (
            "gnn_v4_full",
            PaperAlignedGNNConfig(
                **base_kwargs,
                use_job_edge_weights=True,
                use_skill_dependency_edges=True,
                use_reverse_skill_dependency_edges=True,
                skill_dependency_mode="asymmetric_sbert_diffusion",
            ),
            5e-4,
            0.1,
        ),
        (
            "gnn_v4_full_no_wj",
            PaperAlignedGNNConfig(
                **base_kwargs,
                use_job_edge_weights=False,
                use_skill_dependency_edges=True,
                use_reverse_skill_dependency_edges=True,
                skill_dependency_mode="asymmetric_sbert_diffusion",
            ),
            5e-4,
            0.1,
        ),
    ]

    v4_results: Dict[str, Any] = {}
    ckpt_dir = OUT_DIR / "checkpoints"
    for vname, cfg, lr, asym_w in variants:
        logger.info(f"Training variant [{vname}] across 5 seeds {SEEDS} (lr={lr}, asym_w={asym_w})...")
        runs: List[Dict[str, Any]] = []
        for seed in SEEDS:
            t0 = time.perf_counter()
            run_res = train_single_seed(
                variant_name=vname,
                model_cfg=cfg,
                train_graphs=v4_train,
                val_graphs=v4_val,
                test_graphs=v4_test,
                asym_train_pairs=v4_asym_train,
                asym_eval_zero_shot=v4_asym_eval_zs,
                asym_eval_with_rel=v4_asym_eval_rel,
                lr=lr,
                asym_loss_weight=asym_w,
                seed=seed,
                ckpt_out=ckpt_dir / f"{vname}_seed{seed}.pt",
            )
            dt = time.perf_counter() - t0
            logger.info(
                f"  [{vname}] seed={seed} (ep={run_res['best_epoch']}, {dt:.1f}s) | "
                f"Val MAE={run_res['val']['macro_mae_100']:.2f} | "
                f"Test MAE={run_res['test']['macro_mae_100']:.2f}, "
                f"NDCG@5={run_res['test']['macro_ndcg5']:.4f}, "
                f"Spearman={run_res['test']['macro_spearman']:.4f}, "
                f"ZS-Asym={run_res['asym_zero_shot']['accuracy']:.2%}"
            )
            runs.append(run_res)

        agg_val = aggregate_seed_runs(runs, "val")
        agg_test = aggregate_seed_runs(runs, "test")
        agg_ne82 = aggregate_seed_runs(runs, "test_non_empty_cv82")
        v4_results[vname] = {
            "config": {"lr": lr, "asym_loss_weight": asym_w, **asdict(cfg)},
            "val": agg_val,
            "test": agg_test,
            "test_non_empty_cv82": agg_ne82,
            "seed_runs": [
                {
                    "seed": r["seed"],
                    "best_epoch": r["best_epoch"],
                    "val_macro_mae_100": r["val"]["macro_mae_100"],
                    "val_macro_ndcg5": r["val"]["macro_ndcg5"],
                    "val_macro_spearman": r["val"]["macro_spearman"],
                    "test_macro_mae_100": r["test"]["macro_mae_100"],
                    "test_macro_ndcg5": r["test"]["macro_ndcg5"],
                    "test_macro_spearman": r["test"]["macro_spearman"],
                    "asym_zero_shot_acc": r["asym_zero_shot"]["accuracy"],
                    "asym_zero_shot_gap": r["asym_zero_shot"]["mean_gap"],
                }
                for r in runs
            ],
        }
        logger.info(
            f"==> SUMMARY [{vname}] Test(112): "
            f"MAE={agg_test['macro_mae_100']['mean']:.2f}±{agg_test['macro_mae_100']['std']:.2f} | "
            f"NDCG@5={agg_test['macro_ndcg5']['mean']:.4f}±{agg_test['macro_ndcg5']['std']:.4f} | "
            f"Spearman={agg_test['macro_spearman']['mean']:.4f}±{agg_test['macro_spearman']['std']:.4f} | "
            f"ZS-Asym={agg_test['asym_zero_shot_acc']['mean']:.2%}"
        )

    # 6. Evaluate historical old checkpoints with identical metric function for apples-to-apples table
    logger.info("Evaluating historical old-architecture checkpoints for side-by-side comparison...")
    old_ref = evaluate_historical_old_checkpoints(old_val, old_test, old_asym_eval_zs, old_asym_eval_rel)

    # 7. Paired JD-cluster bootstrap comparisons (14 independent JDs)
    v4_full_jds = v4_results["gnn_v4_full"]["test"]["per_jd_mean"]
    comparisons: Dict[str, Any] = {}
    compare_targets = [
        ("vs_sbert_cosine", baselines["sbert_cosine"]["test"]["per_jd"]),
        ("vs_sbert_ridge", baselines["sbert_ridge"]["test"]["per_jd"]),
        ("vs_gnn_v4_bipartite", v4_results["gnn_v4_bipartite"]["test"]["per_jd_mean"]),
        ("vs_gnn_v4_dependency", v4_results["gnn_v4_dependency"]["test"]["per_jd_mean"]),
        ("vs_gnn_v4_full_no_wj", v4_results["gnn_v4_full_no_wj"]["test"]["per_jd_mean"]),
        ("vs_old_gnn_v3_full", old_ref["old_gnn_v3_full"]["test"]["per_jd_mean"]),
    ]
    for cname, target_jds in compare_targets:
        comparisons[cname] = {
            metric: jd_cluster_bootstrap_delta(v4_full_jds, target_jds, metric)
            for metric in ("mae_100", "ndcg5", "spearman")
        }

    # Strip bulky raw prediction lists before saving JSON summary
    baselines_clean = {
        k: {kk: vv for kk, vv in v.items() if kk != "test_preds"}
        for k, v in baselines.items()
    }

    report = {
        "experiment_id": "exp_m1_v4_semantic_importance",
        "protocol": {
            "train_pairs": len(v4_train),
            "train_jds": sorted({str(g.jd_id) for g in v4_train}),
            "val_pairs": len(v4_val),
            "val_jds": sorted({str(g.jd_id) for g in v4_val}),
            "test_pairs": len(v4_test),
            "test_jds": sorted({str(g.jd_id) for g in v4_test}),
            "test_non_empty_cv_pairs": sum(1 for g in v4_test if int(g[CV_FWD].edge_index.shape[1]) > 0),
            "seeds": SEEDS,
            "checkpoint_selection": "pure_validation_macro_per_jd_mae",
            "openrouter_calls": 0,
            "runtime_seconds": round(time.perf_counter() - t_start, 2),
        },
        "baselines": baselines_clean,
        "v4_gnn_variants": v4_results,
        "old_architecture_reference": old_ref,
        "paired_jd_bootstrap_v4_full": comparisons,
    }

    report_path = OUT_DIR / "results_summary.json"
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    logger.info(f"Saved complete experiment report to {report_path} (total {report['protocol']['runtime_seconds']}s)")


if __name__ == "__main__":
    main()
