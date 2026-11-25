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
import json
import logging
from pathlib import Path
import re
import sys
from typing import Any, Dict, List, Optional, Tuple

import torch
from torch_geometric.data import HeteroData

# Ensure matching_cv is importable
ai_service_dir = Path(__file__).resolve().parents[3]
if str(ai_service_dir) not in sys.path:
    sys.path.insert(0, str(ai_service_dir))

from matching_cv.app.core.config import settings
from matching_cv.app.core.model_loader import ModelLoader
from matching_cv.app.services.production_skill_importance_service import (
    production_skill_importance_service,
)
from matching_cv.research.data.canonical_skill_normalizer import normalize_canonical_skill
from matching_cv.research.paper_aligned_gnn.graph_builder import (
    PaperAlignedGraphBuilder,
    PaperAlignedGraphConfig,
)
from matching_cv.research.paper_aligned_gnn.schemas import EdgeWeightMode, SkillInputItem
from matching_cv.research.paper_aligned_gnn.skill_dependency_resolver import (
    CURATED_SKILL_PREREQUISITE_DAG,
)

# Held-out canonical prerequisite pairs strictly EXCLUDED from counterfactual training
# so zero-shot asymmetric generalization (including docker <-> kubernetes) is evaluated honestly.
HELD_OUT_ASYMMETRIC_DAG_PAIRS = frozenset({
    ("docker", "kubernetes"),
    ("kubernetes", "helm"),
    ("linux", "docker"),
    ("sql", "postgresql"),
    ("react", "next.js"),
    ("java", "spring-boot"),
    ("javascript", "typescript"),
    ("python", "pytorch"),
    ("aws", "ec2"),
    ("ci-cd", "github-actions"),
})

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("prepare_dataset")


def parse_cv_skills_section(cv_text: str) -> List[Tuple[str, Optional[str]]]:
    """Extract candidate skills listed in resume text outside of job requirements.
    Returns list of (surface_name, explicit_descriptor_or_None) tuples so missing
    modifiers naturally trigger Approach 2 evidence-based continuous fallback.
    """
    found_skills: List[Tuple[str, Optional[str]]] = []
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
            # Only set explicit descriptor if actually present in text; else None -> Approach 2 fallback
            desc: Optional[str] = None
            part_lower = part.lower()
            if any(w in part_lower for w in ["expert", "master", "advanced", "lead"]):
                desc = "expert"
            elif any(w in part_lower for w in ["basic", "fundamental", "beginner", "introductory"]):
                desc = "basic"
            elif any(w in part_lower for w in ["intermediate", "working"]):
                desc = "intermediate"
            elif "proficient" in part_lower:
                desc = "proficient"

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
            emb = self.model.encode(key, normalize_embeddings=True, show_progress_bar=False)
            self.cache[key] = [float(x) for x in emb.tolist()]
        return self.cache[key]


def compute_jd_importance_weights(job: Dict[str, Any]) -> Dict[str, float]:
    """Compute JSI-v1 importance weights w_j for all skills in a synthetic JD."""
    jd_id = job["jd_id"]
    jd_text = job.get("jd_text", "")
    explicit_skills: List[Dict[str, Any]] = []
    fallback_weights: Dict[str, float] = {}

    for req in job.get("requirements", []):
        is_crit = bool(req.get("is_critical", False))
        req_type = str(req.get("type", "mandatory")).lower()
        prior_w = 0.92 if is_crit else (0.75 if req_type == "mandatory" else 0.45)
        sentence = req.get("jd_quote") or req.get("text", "")
        for term in req.get("skill_terms", []):
            canon = normalize_canonical_skill(term)
            if not canon:
                continue
            fallback_weights[canon] = max(fallback_weights.get(canon, 0.0), prior_w)
            explicit_skills.append(
                {
                    "skill_id": canon,
                    "surface_forms": [term],
                    "evidences": [{"surface_form": term, "sentence": sentence}],
                }
            )

    weights = dict(fallback_weights)
    try:
        jsi_out = production_skill_importance_service.evaluate_jd_importance(
            jd_text=jd_text,
            explicit_skills=explicit_skills,
            implicit_skills=[],
            job_title=job.get("title"),
            jd_id=jd_id,
            force_enable=True,
        )
        for rec in jsi_out.records:
            cid = normalize_canonical_skill(rec.skill_id) or rec.skill_id
            if cid:
                weights[cid] = float(rec.weight)
    except Exception as exc:
        logger.warning(f"JSI importance fallback used for {jd_id}: {exc}")
    return weights


def build_pair_graph(
    pair: Dict[str, Any],
    job: Dict[str, Any],
    resume: Dict[str, Any],
    builder: PaperAlignedGraphBuilder,
    emb_cache: EmbeddingCache,
    jd_importance_weights: Optional[Dict[str, float]] = None,
) -> Tuple[HeteroData, Dict[str, Any]]:
    """Build a single bipartite HeteroData graph for a CV-JD pair."""
    jd_id = job["jd_id"]
    cv_id = resume["cv_id"]
    req_map = {r["req_id"]: r for r in job["requirements"]}

    # 1. Build JD items from requirements (aligned with Module 2 P_JD / 5.0 scale in [0.2, 1.0])
    jd_items: List[SkillInputItem] = []
    for req in job["requirements"]:
        is_crit = req.get("is_critical", False)
        min_yrs = req.get("min_years", 0) or 0
        req_type = req.get("type", "mandatory")

        if is_crit or min_yrs >= 5:
            jd_desc = "expert"        # 0.90 <-> P_JD = 4.5
        elif min_yrs >= 3 or req_type == "mandatory":
            jd_desc = "accomplished"  # 0.70 <-> P_JD = 3.5
        else:
            jd_desc = "proficient"    # 0.50 <-> P_JD = 2.5

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
                    metadata={"sections": ["requirements" if req_type == "mandatory" else "bonus"]},
                )
            )

    # 2. Build CV items from realized requirements + text parsing (aligned with Module 2 P_CV / 5.0)
    cv_items: List[SkillInputItem] = []
    seen_cv_canons = set()

    for real in resume.get("realized", []):
        req = req_map.get(real.get("req_id"))
        if not req:
            continue
        tgt = real.get("target", "missing")
        if tgt == "met_strong":
            cv_desc = "expert"        # 0.90 <-> P_CV = 4.5
        elif tgt == "met_light":
            cv_desc = "skilled"       # 0.60 <-> P_CV = 3.0
        elif tgt in ("partial_adjacent", "partial_years"):
            cv_desc = "intermediate"  # 0.40 <-> P_CV = 2.0
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
                    metadata={"sections": ["experience"]},
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
                    metadata={"sections": ["skills"]},
                )
            )

    # 3. Construct graph
    graph_data, report = builder.build_graph_from_items(
        cv_items=cv_items,
        jd_items=jd_items,
        pair_id=pair["pair_id"],
        cv_doc_id=cv_id,
        jd_doc_id=jd_id,
        jd_importance_weights=jd_importance_weights,
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

    # Compute real SBERT Mean Max-Cosine Similarity Baseline (JD skills -> best CV skill)
    sbert_cosine_score = 0.0
    jd_vecs = [it.embedding_vector for it in jd_items if it.embedding_vector]
    cv_vecs = [it.embedding_vector for it in cv_items if it.embedding_vector]
    if jd_vecs and cv_vecs:
        jd_mat = torch.tensor(jd_vecs, dtype=torch.float32)
        cv_mat = torch.tensor(cv_vecs, dtype=torch.float32)
        jd_mat = torch.nn.functional.normalize(jd_mat, p=2, dim=-1)
        cv_mat = torch.nn.functional.normalize(cv_mat, p=2, dim=-1)
        sim_mat = torch.matmul(jd_mat, cv_mat.T)
        max_per_jd = sim_mat.max(dim=-1).values.clamp(min=0.0, max=1.0)
        sbert_cosine_score = round(float(max_per_jd.mean().item()), 6)

    meta = {
        "pair_id": pair["pair_id"],
        "jd_id": jd_id,
        "cv_id": cv_id,
        "label": pyg.label,
        "slot_id": pyg.slot_id,
        "final_score": target_score,
        "coverage_score": float(pair["scores"].get("coverage_score", target_score)),
        "sbert_cosine_score": sbert_cosine_score,
        "shared_skills": summary.get("shared_skills", 0),
        "resume_only_skills": summary.get("resume_only_skills", 0),
        "job_only_skills": summary.get("job_only_skills", 0),
        "skill_dependency_edges": report.skill_dependency_edge_count,
        "is_valid": report.is_valid,
    }
    return pyg, meta


def _display_from_slug(slug: str) -> str:
    special = {
        "sql": "SQL",
        "aws": "AWS",
        "gcp": "GCP",
        "css": "CSS",
        "html": "HTML",
        "ci-cd": "CI/CD",
        "ec2": "EC2",
        "s3": "S3",
        "rds": "RDS",
        "mlops": "MLOps",
        "next.js": "Next.js",
        "nodejs": "Node.js",
        "rest-api": "REST API",
        "postgresql": "PostgreSQL",
        "mysql": "MySQL",
        "pytorch": "PyTorch",
        "tensorflow": "TensorFlow",
        "graphql": "GraphQL",
        "typescript": "TypeScript",
        "javascript": "JavaScript",
        "spring-boot": "Spring Boot",
    }
    if slug in special:
        return special[slug]
    return " ".join(tok.capitalize() for tok in slug.replace("_", "-").split("-"))


def _build_synthetic_graph(
    cv_specs: List[Tuple[str, str]],
    jd_specs: List[Tuple[str, str]],
    target_score: float,
    pair_id: str,
    builder: PaperAlignedGraphBuilder,
    emb_cache: EmbeddingCache,
    tag: str,
) -> HeteroData:
    cv_items = [
        SkillInputItem(
            occurrence_id=f"{pair_id}_cv_{i}_{canon}",
            canonical_skill_id=canon,
            surface_name=_display_from_slug(canon),
            source_document="CV",
            evidence_sentences=[f"{desc} {_display_from_slug(canon)}"],
            proficiency_override=desc,
            embedding_vector=emb_cache.get_embedding(_display_from_slug(canon)),
        )
        for i, (canon, desc) in enumerate(cv_specs)
    ]
    jd_items = [
        SkillInputItem(
            occurrence_id=f"{pair_id}_jd_{i}_{canon}",
            canonical_skill_id=canon,
            surface_name=_display_from_slug(canon),
            source_document="JD",
            evidence_sentences=[f"{desc} {_display_from_slug(canon)}"],
            proficiency_override=desc,
            embedding_vector=emb_cache.get_embedding(_display_from_slug(canon)),
        )
        for i, (canon, desc) in enumerate(jd_specs)
    ]
    g_data, _ = builder.build_graph_from_items(
        cv_items=cv_items,
        jd_items=jd_items,
        pair_id=pair_id,
    )
    pyg, _, _ = builder.export_to_pyg(g_data)
    pyg.y = torch.tensor([float(target_score)], dtype=torch.float32)
    pyg.pair_id = pair_id
    pyg.jd_id = tag
    pyg.cv_id = pair_id
    return pyg


def build_asymmetric_counterfactual_pairs(
    builder: PaperAlignedGraphBuilder,
    emb_cache: EmbeddingCache,
    dag_pairs: List[Tuple[str, str]],
    prefix: str,
    max_pairs: int = 45,
) -> List[Dict[str, Any]]:
    """
    Build paired (g_supersede, g_prereq_only) counterfactual graphs for prerequisite DAG pairs:
    - g_supersede:   JD requires `base`, CV demonstrates `adv` (e.g., JD=docker, CV=kubernetes) -> higher score
    - g_prereq_only: JD requires `adv`,  CV demonstrates `base` (e.g., JD=kubernetes, CV=docker) -> lower score

    Creates both standalone 1-skill pairs and realistic multi-skill contextual pairs (with 3 shared
    background skills) so the GNN learns directed asymmetry across both small and rich graphs.
    """
    bg_pools = [
        ["git", "agile", "rest-api"],
        ["git", "linux", "testing", "communication"],
        ["version-control", "code-review", "debugging"],
        ["api-integration", "documentation", "collaboration"],
    ]
    paired_records: List[Dict[str, Any]] = []
    for idx, (base_sk, adv_sk) in enumerate(dag_pairs[:max_pairs]):
        # 1. Standalone 1-skill vs 1-skill pair
        g_sup_solo = _build_synthetic_graph(
            cv_specs=[(adv_sk, "accomplished")],
            jd_specs=[(base_sk, "accomplished")],
            target_score=0.76,
            pair_id=f"{prefix}_solo_sup_{idx:03d}_{base_sk}__{adv_sk}",
            builder=builder,
            emb_cache=emb_cache,
            tag=f"{prefix}_asym_solo",
        )
        g_pre_solo = _build_synthetic_graph(
            cv_specs=[(base_sk, "accomplished")],
            jd_specs=[(adv_sk, "accomplished")],
            target_score=0.30,
            pair_id=f"{prefix}_solo_pre_{idx:03d}_{adv_sk}__{base_sk}",
            builder=builder,
            emb_cache=emb_cache,
            tag=f"{prefix}_asym_solo",
        )
        paired_records.append({
            "kind": "solo",
            "base_skill": base_sk,
            "advanced_skill": adv_sk,
            "margin": 0.25,
            "g_higher": g_sup_solo,
            "g_lower": g_pre_solo,
        })

        # 2. Multi-skill contextual pair (shared background + swapped prerequisite)
        bg = [s for s in bg_pools[idx % len(bg_pools)] if s not in (base_sk, adv_sk)]
        n_bg = len(bg)
        bg_specs = [(s, "accomplished") for s in bg]
        y_sup_ctx = round((n_bg * 0.85 + 0.76) / (n_bg + 1), 4)
        y_pre_ctx = round((n_bg * 0.85 + 0.30) / (n_bg + 1), 4)
        g_sup_ctx = _build_synthetic_graph(
            cv_specs=bg_specs + [(adv_sk, "accomplished")],
            jd_specs=bg_specs + [(base_sk, "accomplished")],
            target_score=y_sup_ctx,
            pair_id=f"{prefix}_ctx_sup_{idx:03d}_{base_sk}__{adv_sk}",
            builder=builder,
            emb_cache=emb_cache,
            tag=f"{prefix}_asym_ctx",
        )
        g_pre_ctx = _build_synthetic_graph(
            cv_specs=bg_specs + [(base_sk, "accomplished")],
            jd_specs=bg_specs + [(adv_sk, "accomplished")],
            target_score=y_pre_ctx,
            pair_id=f"{prefix}_ctx_pre_{idx:03d}_{adv_sk}__{base_sk}",
            builder=builder,
            emb_cache=emb_cache,
            tag=f"{prefix}_asym_ctx",
        )
        paired_records.append({
            "kind": "contextual",
            "base_skill": base_sk,
            "advanced_skill": adv_sk,
            "margin": 0.08,
            "g_higher": g_sup_ctx,
            "g_lower": g_pre_ctx,
        })
    return paired_records


def build_depth_sensitivity_pairs(
    builder: PaperAlignedGraphBuilder,
    emb_cache: EmbeddingCache,
    jobs: Dict[str, Any],
    jd_ids: List[str],
    prefix: str,
) -> List[Dict[str, Any]]:
    """
    Build paired (g_strong_cv, g_mid_cv, g_weak_cv) graphs with IDENTICAL skill topology
    differing ONLY in CV proficiency depth, so the GNN learns monotonic depth sensitivity
    (e.g., 'Python basic 3 months' < 'Python no modifier' < 'Python expert 6 years').
    """
    records: List[Dict[str, Any]] = []
    # A. Multi-skill JD-anchored depth triples
    for jd_id in sorted(jd_ids):
        job = jobs[jd_id]
        terms = []
        seen = set()
        for req in job.get("requirements", []):
            for t in req.get("skill_terms", []):
                c = normalize_canonical_skill(t)
                if c and c not in seen:
                    seen.add(c)
                    terms.append(c)
        if not terms:
            continue
        selected = terms[:6]
        jd_specs = [(c, "expert") for c in selected]
        g_high = _build_synthetic_graph(
            cv_specs=[(c, "expert") for c in selected],
            jd_specs=jd_specs,
            target_score=0.92,
            pair_id=f"{prefix}_depth_high_{jd_id}",
            builder=builder,
            emb_cache=emb_cache,
            tag=f"{prefix}_depth",
        )
        g_mid = _build_synthetic_graph(
            cv_specs=[(c, "proficient") for c in selected],
            jd_specs=jd_specs,
            target_score=0.68,
            pair_id=f"{prefix}_depth_mid_{jd_id}",
            builder=builder,
            emb_cache=emb_cache,
            tag=f"{prefix}_depth",
        )
        g_low = _build_synthetic_graph(
            cv_specs=[(c, "basic") for c in selected],
            jd_specs=jd_specs,
            target_score=0.36,
            pair_id=f"{prefix}_depth_low_{jd_id}",
            builder=builder,
            emb_cache=emb_cache,
            tag=f"{prefix}_depth",
        )
        records.append({"kind": "jd_high_vs_low", "jd_id": jd_id, "margin": 0.30, "g_higher": g_high, "g_lower": g_low})
        records.append({"kind": "jd_high_vs_mid", "jd_id": jd_id, "margin": 0.12, "g_higher": g_high, "g_lower": g_mid})
        records.append({"kind": "jd_mid_vs_low", "jd_id": jd_id, "margin": 0.15, "g_higher": g_mid, "g_lower": g_low})

    # B. Single-skill depth triples (ensures 1-skill CVs preserve depth sensitivity!)
    solo_skills = (
        ["java", "javascript", "sql", "aws", "react", "nodejs", "docker", "golang", "terraform", "kafka"]
        if prefix == "train"
        else ["python", "kubernetes", "postgresql", "typescript"]
    )
    for sk in solo_skills:
        g_high = _build_synthetic_graph(
            cv_specs=[(sk, "expert")],
            jd_specs=[(sk, "expert")],
            target_score=0.90,
            pair_id=f"{prefix}_solo_depth_high_{sk}",
            builder=builder,
            emb_cache=emb_cache,
            tag=f"{prefix}_solo_depth",
        )
        g_mid = _build_synthetic_graph(
            cv_specs=[(sk, "proficient")],
            jd_specs=[(sk, "expert")],
            target_score=0.65,
            pair_id=f"{prefix}_solo_depth_mid_{sk}",
            builder=builder,
            emb_cache=emb_cache,
            tag=f"{prefix}_solo_depth",
        )
        g_low = _build_synthetic_graph(
            cv_specs=[(sk, "basic")],
            jd_specs=[(sk, "expert")],
            target_score=0.32,
            pair_id=f"{prefix}_solo_depth_low_{sk}",
            builder=builder,
            emb_cache=emb_cache,
            tag=f"{prefix}_solo_depth",
        )
        records.append({"kind": "solo_high_vs_low", "skill": sk, "margin": 0.30, "g_higher": g_high, "g_lower": g_low})
        records.append({"kind": "solo_high_vs_mid", "skill": sk, "margin": 0.12, "g_higher": g_high, "g_lower": g_mid})
        records.append({"kind": "solo_mid_vs_low", "skill": sk, "margin": 0.15, "g_higher": g_mid, "g_lower": g_low})
    return records


def run_dataset_preparation(
    raw_dir: str,
    processed_file: str,
    output_dir: str,
    train_ratio: float = 0.7,
    val_ratio: float = 0.1,
    test_ratio: float = 0.2,
    enable_skill_dependencies: bool = True,
    dependency_scope: str = "jd_bidirectional",
    include_counterfactuals: bool = True,
    edge_weight_mode: EdgeWeightMode = "semantic_importance",
) -> None:
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    logger.info("Initializing SBERT ModelLoader...")
    loader = ModelLoader()
    sbert = loader.load_model()
    emb_cache = EmbeddingCache(sbert)

    cfg = PaperAlignedGraphConfig(
        embedding_dim=settings.STAGE3_EMBEDDING_DIM,
        edge_weight_mode=edge_weight_mode,
        edge_weight_normalization="scaled_0_1",
        enable_skill_dependencies=enable_skill_dependencies,
        dependency_scope=dependency_scope,
        enable_evidence_proficiency_fallback=(edge_weight_mode == "paper_proficiency"),
    )
    builder = PaperAlignedGraphBuilder(cfg)

    # Load raw jobs and resumes
    raw_path = Path(raw_dir)
    jobs_file = raw_path / "jobs.jsonl"
    resumes_file = raw_path / "resumes.jsonl"

    logger.info(f"Loading jobs from {jobs_file}")
    with open(jobs_file, "r", encoding="utf-8") as f:
        jobs = {j["jd_id"]: j for j in [json.loads(line) for line in f]}

    logger.info(f"Loading resumes from {resumes_file}")
    with open(resumes_file, "r", encoding="utf-8") as f:
        resumes = {r["cv_id"]: r for r in [json.loads(line) for line in f]}

    logger.info(f"Loading accepted pairs from {processed_file}")
    with open(processed_file, "r", encoding="utf-8") as f:
        pairs = [json.loads(line) for line in f]

    logger.info(
        f"Total jobs: {len(jobs)}, resumes: {len(resumes)}, pairs: {len(pairs)}, "
        f"edge_weight_mode={edge_weight_mode}"
    )

    jd_importance_by_id: Dict[str, Dict[str, float]] = {}
    if edge_weight_mode == "semantic_importance":
        for jid, job in jobs.items():
            jd_importance_by_id[jid] = compute_jd_importance_weights(job)

    # Group split by jd_id strictly (7 train, 1 val, 2 test for 10 JDs)
    all_jds = sorted(list(jobs.keys()))
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

        pyg, meta = build_pair_graph(
            pair,
            job,
            resume,
            builder,
            emb_cache,
            jd_importance_weights=jd_importance_by_id.get(jd_id),
        )
        metadata_list.append(meta)

        if jd_id in train_jds:
            train_graphs.append(pyg)
        elif jd_id in val_jds:
            val_graphs.append(pyg)
        elif jd_id in test_jds:
            test_graphs.append(pyg)

        if (idx + 1) % 20 == 0 or (idx + 1) == len(pairs):
            logger.info(f"Processed {idx + 1}/{len(pairs)} pairs...")

    total_dep_edges = sum(m.get("skill_dependency_edges", 0) for m in metadata_list)
    avg_dep_edges = round(total_dep_edges / max(1, len(metadata_list)), 2)
    logger.info(
        f"Split results: Train={len(train_graphs)}, Val={len(val_graphs)}, Test={len(test_graphs)} | "
        f"Skill Dependencies enabled={enable_skill_dependencies}, total_prereq_edges={total_dep_edges} (avg={avg_dep_edges}/pair)"
    )

    # Save real dataset splits (zero leakage across JDs)
    torch.save(train_graphs, output_path / "train_graphs.pt")
    torch.save(val_graphs, output_path / "val_graphs.pt")
    torch.save(test_graphs, output_path / "test_graphs.pt")

    asym_train_pairs: List[Dict[str, Any]] = []
    asym_eval_pairs: List[Dict[str, Any]] = []
    depth_train_pairs: List[Dict[str, Any]] = []
    depth_eval_pairs: List[Dict[str, Any]] = []

    if include_counterfactuals and enable_skill_dependencies:
        train_dag_pairs = [
            (u, v) for (u, v) in CURATED_SKILL_PREREQUISITE_DAG
            if (u, v) not in HELD_OUT_ASYMMETRIC_DAG_PAIRS
        ]
        eval_dag_pairs = [
            (u, v) for (u, v) in CURATED_SKILL_PREREQUISITE_DAG
            if (u, v) in HELD_OUT_ASYMMETRIC_DAG_PAIRS
        ]
        asym_train_pairs = build_asymmetric_counterfactual_pairs(
            builder, emb_cache, train_dag_pairs, prefix="train", max_pairs=45
        )
        asym_eval_pairs = build_asymmetric_counterfactual_pairs(
            builder, emb_cache, eval_dag_pairs, prefix="eval", max_pairs=len(eval_dag_pairs)
        )
        torch.save(asym_train_pairs, output_path / "asymmetric_train_pairs.pt")
        torch.save(asym_eval_pairs, output_path / "asymmetric_eval_pairs.pt")
        if edge_weight_mode == "paper_proficiency":
            depth_train_pairs = build_depth_sensitivity_pairs(
                builder, emb_cache, jobs, sorted(train_jds), prefix="train"
            )
            depth_eval_pairs = build_depth_sensitivity_pairs(
                builder, emb_cache, jobs, sorted(test_jds), prefix="eval"
            )
            torch.save(depth_train_pairs, output_path / "depth_train_pairs.pt")
            torch.save(depth_eval_pairs, output_path / "depth_eval_pairs.pt")
        logger.info(
            f"Saved counterfactual sets: asym_train={len(asym_train_pairs)} pairs, "
            f"asym_eval(zero-shot)={len(asym_eval_pairs)} pairs, "
            f"depth_train={len(depth_train_pairs)} pairs, depth_eval={len(depth_eval_pairs)} pairs"
        )

    manifest = {
        "dataset_name": "synthetic_cv_jd_dataset_v2",
        "total_pairs": len(pairs),
        "edge_weight_mode": edge_weight_mode,
        "enable_skill_dependencies": enable_skill_dependencies,
        "dependency_scope": dependency_scope,
        "enable_evidence_proficiency_fallback": edge_weight_mode == "paper_proficiency",
        "total_skill_dependency_edges": total_dep_edges,
        "avg_skill_dependency_edges_per_pair": avg_dep_edges,
        "counterfactual_counts": {
            "asymmetric_train_pairs": len(asym_train_pairs),
            "asymmetric_eval_zero_shot_pairs": len(asym_eval_pairs),
            "depth_train_pairs": len(depth_train_pairs),
            "depth_eval_pairs": len(depth_eval_pairs),
        },
        "held_out_asymmetric_dag_pairs": sorted([list(p) for p in HELD_OUT_ASYMMETRIC_DAG_PAIRS]),
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
        default=r"ai-service\matching_cv\dataset\synthetic_cv_jd_dataset_v2\synthetic_cv_jd_dataset_v2\raw",
        help="Path to raw dataset directory containing jobs.jsonl and resumes.jsonl",
    )
    parser.add_argument(
        "--processed-file",
        type=str,
        default=r"ai-service\matching_cv\dataset\synthetic_cv_jd_dataset_v2\synthetic_cv_jd_dataset_v2\processed\accepted_pairs.jsonl",
        help="Path to accepted_pairs.jsonl",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default=r"ai-service\matching_cv\data\processed\paper_aligned_gnn_v4_semantic_importance",
        help="Directory to save serialized graphs and manifest",
    )
    parser.add_argument(
        "--edge-weight-mode",
        type=str,
        choices=["semantic_importance", "paper_proficiency"],
        default="semantic_importance",
        help="Edge weighting policy: semantic_importance (v4 decoupled M1) or paper_proficiency (ICIT 2025 ablation)",
    )
    parser.add_argument(
        "--no-skill-dependencies",
        action="store_true",
        help="Disable skill prerequisite dependency edges (strict Baghbanzadeh & Wu bipartite baseline)",
    )
    parser.add_argument(
        "--dependency-scope",
        type=str,
        choices=["jd_bidirectional", "jd_anchored", "jd_only", "all_skills"],
        default="jd_bidirectional",
        help="Scope of prerequisite edges to include in the graph",
    )
    parser.add_argument(
        "--no-counterfactuals",
        action="store_true",
        help="Skip building train-only asymmetric counterfactual pairs",
    )
    args = parser.parse_args()
    run_dataset_preparation(
        raw_dir=args.raw_dir,
        processed_file=args.processed_file,
        output_dir=args.output_dir,
        enable_skill_dependencies=not args.no_skill_dependencies,
        dependency_scope=args.dependency_scope,
        include_counterfactuals=not args.no_counterfactuals,
        edge_weight_mode=args.edge_weight_mode,
    )
