"""Dataset Preparation & Graph Serialization for Paper-Aligned Hybrid GNN.

Transforms Synthetic CV-JD Matching Dataset v2.1.0 into PyTorch Geometric
HeteroData graphs with exact Baghbanzadeh & Wu (ICIT 2025) bipartite graph topology:
- 'resume', 'job', and 'skill' nodes.
- GraphConv edge types: ('job', 'requires_skill', 'skill') & ('skill', 'required_by_job', 'job').
- Modified GAT edge types: ('resume', 'has_skill', 'skill') & ('skill', 'in_resume', 'resume').
- Scalar proficiency weights on edges.
- Group-split strictly by `jd_id` (zero CV or JD leakage across splits).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import logging
from pathlib import Path
import re
import sys
from typing import Any, Dict, List, Tuple

import torch
from torch_geometric.data import HeteroData

# Ensure matching_cv is importable
ai_service_dir = Path(__file__).resolve().parents[3]
if str(ai_service_dir) not in sys.path:
    sys.path.insert(0, str(ai_service_dir))

from matching_cv.app.core.config import settings
from matching_cv.app.core.model_loader import ModelLoader
from matching_cv.research.data.canonical_skill_normalizer import normalize_canonical_skill
from matching_cv.research.paper_aligned_gnn.graph_builder import (
    PaperAlignedGraphBuilder,
    PaperAlignedGraphConfig,
)
from matching_cv.research.paper_aligned_gnn.schemas import SkillInputItem

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("prepare_dataset")


def parse_cv_skills_section(cv_text: str) -> List[Tuple[str, str]]:
    """Extract candidate skills listed in resume text outside of job requirements.
    Returns list of (surface_name, descriptor) tuples.
    """
    found_skills: List[Tuple[str, str]] = []
    match = re.findall(
        r"(?:Skills|TECHNICAL SKILLS|SKILLS|CORE COMPETENCIES)[:\n](.*?)(?:\n\n|\Z)",
        cv_text,
        re.DOTALL | re.IGNORECASE,
    )
    if not match:
        return found_skills

    lines = [
        re.sub(r"^[•\-\*\s]+", "", l).strip()
        for l in match[0].split("\n")
        if l.strip() and not l.strip().endswith(":")
    ]
    for line in lines[:8]:
        parts = [p.strip() for p in re.split(r"[,|;]", line) if p.strip() and len(p.strip()) > 1]
        for part in parts[:4]:
            # Detect basic descriptor modifiers
            desc = "proficient"
            part_lower = part.lower()
            if any(w in part_lower for w in ["expert", "master", "advanced", "lead"]):
                desc = "strong"
            elif any(w in part_lower for w in ["basic", "fundamental", "beginner", "introductory"]):
                desc = "basic"
            elif any(w in part_lower for w in ["intermediate", "working"]):
                desc = "intermediate"

            # Clean cleaned phrase
            clean_phrase = re.sub(
                r"\s*\((?:basic|expert|advanced|proficient|beginner|intermediate|years?|\d+\+?\s*years?)\)",
                "",
                part,
                flags=re.IGNORECASE,
            ).strip()
            clean_phrase = re.sub(r"^(?:Languages|Frameworks|Cloud|Databases|Tools|Other|Concepts|Operating Systems):\s*", "", clean_phrase, flags=re.IGNORECASE).strip()
            if clean_phrase and len(clean_phrase) > 1:
                found_skills.append((clean_phrase, desc))
    return found_skills


class EmbeddingCache:
    """In-memory cache for SBERT text embeddings to eliminate redundant encodes."""

    def __init__(self, model: Any):
        self.model = model
        self.cache: Dict[str, List[float]] = {}

    def get_embedding(self, text: str) -> List[float]:
        key = text.strip()
        if key not in self.cache:
            emb = self.model.encode(key)
            self.cache[key] = [float(x) for x in emb.tolist()]
        return self.cache[key]


def build_pair_graph(
    pair: Dict[str, Any],
    job: Dict[str, Any],
    resume: Dict[str, Any],
    builder: PaperAlignedGraphBuilder,
    emb_cache: EmbeddingCache,
) -> Tuple[HeteroData, Dict[str, Any]]:
    """Build a single bipartite HeteroData graph for a CV-JD pair."""
    jd_id = job["jd_id"]
    cv_id = resume["cv_id"]
    req_map = {r["req_id"]: r for r in job["requirements"]}

    # 1. Build JD items from requirements
    jd_items: List[SkillInputItem] = []
    for req in job["requirements"]:
        is_crit = req.get("is_critical", False)
        min_yrs = req.get("min_years", 0) or 0
        req_type = req.get("type", "mandatory")

        if is_crit or min_yrs >= 5:
            jd_desc = "strong"
        elif min_yrs >= 3 or req_type == "mandatory":
            jd_desc = "proficient"
        else:
            jd_desc = "intermediate"

        for term in req.get("skill_terms", []):
            canon = normalize_canonical_skill(term)
            emb = emb_cache.get_embedding(term)
            jd_items.append(
                SkillInputItem(
                    occurrence_id=f"{jd_id}_{req['req_id']}_{canon}",
                    canonical_skill_id=canon,
                    surface_name=term,
                    source_document="JD",
                    evidence_sentences=[req.get("text", "")],
                    proficiency_override=jd_desc,
                    embedding_vector=emb,
                )
            )

    # 2. Build CV items from realized requirements + text parsing
    cv_items: List[SkillInputItem] = []
    seen_cv_canons = set()

    for real in resume.get("realized", []):
        req = req_map.get(real.get("req_id"))
        if not req:
            continue
        tgt = real.get("target", "missing")
        if tgt == "met_strong":
            cv_desc = "strong"
        elif tgt == "met_light":
            cv_desc = "proficient"
        elif tgt == "partial_adjacent":
            cv_desc = "intermediate"
        else:
            continue  # missing requirement -> candidate lacks this skill, no edge!

        quote = real.get("evidence_quote", "")
        for term in req.get("skill_terms", []):
            canon = normalize_canonical_skill(term)
            seen_cv_canons.add(canon)
            emb = emb_cache.get_embedding(term)
            cv_items.append(
                SkillInputItem(
                    occurrence_id=f"{cv_id}_{req['req_id']}_{canon}",
                    canonical_skill_id=canon,
                    surface_name=term,
                    source_document="CV",
                    evidence_sentences=[quote] if quote else [],
                    proficiency_override=cv_desc,
                    embedding_vector=emb,
                )
            )

    # Extract additional CV-only skills from resume text
    cv_text_skills = parse_cv_skills_section(resume.get("cv_text", ""))
    for phrase, desc in cv_text_skills:
        canon = normalize_canonical_skill(phrase)
        if canon not in seen_cv_canons:
            seen_cv_canons.add(canon)
            emb = emb_cache.get_embedding(phrase)
            cv_items.append(
                SkillInputItem(
                    occurrence_id=f"{cv_id}_extra_{canon}",
                    canonical_skill_id=canon,
                    surface_name=phrase,
                    source_document="CV",
                    evidence_sentences=[phrase],
                    proficiency_override=desc,
                    embedding_vector=emb,
                )
            )

    # 3. Construct graph
    graph_data, report = builder.build_graph_from_items(
        cv_items=cv_items,
        jd_items=jd_items,
        pair_id=pair["pair_id"],
        cv_doc_id=cv_id,
        jd_doc_id=jd_id,
    )
    pyg, _, summary = builder.export_to_pyg(graph_data)

    # 4. Attach targets & metadata
    target_score = float(pair["scores"]["final_score"])
    pyg.y = torch.tensor([target_score], dtype=torch.float32)
    pyg.pair_id = pair["pair_id"]
    pyg.jd_id = jd_id
    pyg.cv_id = cv_id
    pyg.label = pair.get("label", "UNCERTAIN")
    pyg.slot_id = pair.get("construction", {}).get("slot_id") or pair["pair_id"].split("_")[-1]

    meta = {
        "pair_id": pair["pair_id"],
        "jd_id": jd_id,
        "cv_id": cv_id,
        "label": pyg.label,
        "slot_id": pyg.slot_id,
        "final_score": target_score,
        "coverage_score": float(pair["scores"].get("coverage_score", target_score)),
        "shared_skills": summary.get("shared_skills", 0),
        "resume_only_skills": summary.get("resume_only_skills", 0),
        "job_only_skills": summary.get("job_only_skills", 0),
        "is_valid": report.is_valid,
    }
    return pyg, meta


def run_dataset_preparation(
    raw_dir: str,
    processed_file: str,
    output_dir: str,
    train_ratio: float = 0.7,
    val_ratio: float = 0.1,
    test_ratio: float = 0.2,
) -> None:
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    logger.info("Initializing SBERT ModelLoader...")
    loader = ModelLoader()
    sbert = loader.load_model()
    emb_cache = EmbeddingCache(sbert)

    cfg = PaperAlignedGraphConfig(
        embedding_dim=settings.STAGE3_EMBEDDING_DIM,
        edge_weight_normalization="scaled_0_1",
    )
    builder = PaperAlignedGraphBuilder(cfg)

    # Load raw jobs and resumes
    raw_path = Path(raw_dir)
    jobs_file = raw_path / "jobs.jsonl"
    resumes_file = raw_path / "resumes.jsonl"

    logger.info(f"Loading jobs from {jobs_file}")
    with open(jobs_file, "r", encoding="utf-8") as f:
        jobs = {j["jd_id"]: j for j in [json.loads(l) for l in f]}

    logger.info(f"Loading resumes from {resumes_file}")
    with open(resumes_file, "r", encoding="utf-8") as f:
        resumes = {r["cv_id"]: r for r in [json.loads(l) for l in f]}

    logger.info(f"Loading accepted pairs from {processed_file}")
    with open(processed_file, "r", encoding="utf-8") as f:
        pairs = [json.loads(l) for l in f]

    logger.info(f"Total jobs: {len(jobs)}, resumes: {len(resumes)}, pairs: {len(pairs)}")

    # Group split by jd_id strictly
    all_jds = sorted(list(jobs.keys()))
    n_jds = len(all_jds)
    n_train_jds = max(1, int(round(n_jds * train_ratio)))
    n_val_jds = max(1, int(round(n_jds * val_ratio)))
    
    # 7 train, 1 val, 2 test for 10 JDs
    train_jds = set(all_jds[:7])
    val_jds = set(all_jds[7:8])
    test_jds = set(all_jds[8:])

    logger.info(f"Group Split: Train JDs={sorted(train_jds)}, Val JDs={sorted(val_jds)}, Test JDs={sorted(test_jds)}")

    train_graphs: List[HeteroData] = []
    val_graphs: List[HeteroData] = []
    test_graphs: List[HeteroData] = []
    metadata_list: List[Dict[str, Any]] = []

    for idx, pair in enumerate(pairs):
        jd_id = pair["jd_id"]
        cv_id = pair["cv_id"]
        job = jobs[jd_id]
        resume = resumes[cv_id]

        pyg, meta = build_pair_graph(pair, job, resume, builder, emb_cache)
        metadata_list.append(meta)

        if jd_id in train_jds:
            train_graphs.append(pyg)
        elif jd_id in val_jds:
            val_graphs.append(pyg)
        elif jd_id in test_jds:
            test_graphs.append(pyg)

        if (idx + 1) % 20 == 0 or (idx + 1) == len(pairs):
            logger.info(f"Processed {idx + 1}/{len(pairs)} pairs...")

    logger.info(f"Split results: Train={len(train_graphs)}, Val={len(val_graphs)}, Test={len(test_graphs)}")

    # Save graphs
    torch.save(train_graphs, output_path / "train_graphs.pt")
    torch.save(val_graphs, output_path / "val_graphs.pt")
    torch.save(test_graphs, output_path / "test_graphs.pt")

    manifest = {
        "dataset_name": "synthetic_cv_jd_dataset_v2",
        "total_pairs": len(pairs),
        "split_counts": {
            "train": len(train_graphs),
            "val": len(val_graphs),
            "test": len(test_graphs),
        },
        "group_split_jds": {
            "train": sorted(list(train_jds)),
            "val": sorted(list(val_jds)),
            "test": sorted(list(test_jds)),
        },
        "sbert_model": settings.STAGE3_MODEL_NAME,
        "sbert_revision": settings.STAGE3_MODEL_REVISION,
        "embedding_dim": settings.STAGE3_EMBEDDING_DIM,
        "pairs_metadata": metadata_list,
    }

    with open(output_path / "manifest.json", "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)

    logger.info(f"All graphs and manifest successfully saved to {output_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Prepare GNN graphs from synthetic dataset.")
    parser.add_argument(
        "--raw-dir",
        type=str,
        default=r"ai-service\matching_cv\dataset\synthetic_cv_jd_dataset_v2-20261118T164928Z-1-001\synthetic_cv_jd_dataset_v2\raw",
        help="Path to raw dataset directory containing jobs.jsonl and resumes.jsonl",
    )
    parser.add_argument(
        "--processed-file",
        type=str,
        default=r"ai-service\matching_cv\dataset\synthetic_cv_jd_dataset_v2-20261118T164928Z-1-001\synthetic_cv_jd_dataset_v2\processed\accepted_pairs.jsonl",
        help="Path to accepted_pairs.jsonl",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default=r"ai-service\matching_cv\data\processed\paper_aligned_gnn",
        help="Directory to save serialized graphs and manifest",
    )
    args = parser.parse_args()
    run_dataset_preparation(
        raw_dir=args.raw_dir,
        processed_file=args.processed_file,
        output_dir=args.output_dir,
    )
