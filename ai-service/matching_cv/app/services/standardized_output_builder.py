"""Builder for the standardized public output (``standardized-output-v1``).

Pure post-processing of data the pipeline has ALREADY computed. It never calls an LLM, never re-runs SBERT,
never re-parses documents and never touches the GNN. Missing source data yields the documented nulls.

Inputs (``PublicOutputContext``):
  * Stage 1 cleaned texts,
  * Stage 2 ``UnifiedExtractFileResponse`` (explicit / accepted implicit skills, confidences, evidences),
  * Stage 3 ``SemanticRepresentationResponse`` (full JD x CV cosine information via the
    ``cv_entities_vs_jd_entities`` matrix; Top-K lists are NOT used because they are CV->JD only),
  * Stage 5 ``PaperAlignedGraphData`` (retained skills, shared-node identity, competency lineage),
  * Stage 6 outcome (score or reason for absence).
"""
from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple, TypedDict

from matching_cv.app.core.config import settings
from matching_cv.app.schemas.standardized_output import (
    ProficiencyInput,
    ProficiencySkill,
    PublicStatus,
    SkillGapRow,
    StandardizedPipelineOutput,
)
from matching_cv.app.services.extraction_adapter import ExtractionDataAdapter
from matching_cv.research.data.canonical_skill_normalizer import normalize_canonical_skill
from matching_cv.app.schemas.module1 import Module1Output
from skill_gap.domain.enums import SkillType
from skill_gap.domain.models import ExtractedCVSkill, ExtractedJDSkill, MatchResult

logger = logging.getLogger(__name__)

MATRIX_KEY = "cv_entities_vs_jd_entities"
IDENTITY_MERGE_REASONS = frozenset(
    {"same_canonical_id", "verified_alias_same_canonical_id", "verified_alias", "verified_llm_equivalent"}
)

# Internal pipeline matching_status -> public status
_STATUS_MAP: Dict[Optional[str], PublicStatus] = {
    "completed": "MODEL_READY",
    "MODEL_READY": "MODEL_READY",
    "COMPLETED": "MODEL_READY",
    "MODEL_NOT_TRAINED": "MODEL_NOT_TRAINED",
    "CHECKPOINT_UNAVAILABLE": "MODEL_NOT_TRAINED",
    "INCOMPATIBLE_CHECKPOINT_ARCHITECTURE": "MODEL_INCOMPATIBLE",
    "MODEL_INCOMPATIBLE": "MODEL_INCOMPATIBLE",
    "failed": "INFERENCE_FAILED",
    "INFERENCE_FAILED": "INFERENCE_FAILED",
}


@dataclass
class PublicOutputContext:
    """Everything the standardized builder needs; attached privately to the internal response DTOs."""

    cv_text: str
    jd_text: str
    unified_response: Any
    graph_data: Any
    stage3_response: Any = None
    matching_score: Optional[float] = None
    matching_status: Optional[str] = None
    run_id: Optional[str] = None
    skill_importance_output: Optional[Any] = None


@dataclass
class StandardizedOutputBuild:
    public: StandardizedPipelineOutput
    internal: Dict[str, Any] = field(default_factory=dict)


def map_public_status(matching_status: Optional[str], has_score: bool) -> PublicStatus:
    if has_score:
        return "MODEL_READY"
    mapped = _STATUS_MAP.get(matching_status)
    if mapped is None or mapped in ("MODEL_READY", "COMPLETED"):
        # No score and no recognised failure code: the only honest statement is that no trained score exists.
        return "MODEL_NOT_TRAINED"
    return mapped


def _valid_confidence(value: Any) -> Optional[float]:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    if not math.isfinite(value) or value < 0.0 or value > 1.0:
        return None
    return float(value)


def _get(obj: Any, name: str, default: Any = None) -> Any:
    return obj.get(name, default) if isinstance(obj, dict) else getattr(obj, name, default)


def _collapse_ws(text: str) -> str:
    return " ".join(text.split())


# ---------------------------------------------------------------------------------------------
# Importance lookup helper
# ---------------------------------------------------------------------------------------------
class ImportanceLookup:
    """Canonical ID-based lookup helper for JD skill importance weights and metadata."""

    def __init__(self, skill_importance_output: Optional[Any] = None) -> None:
        self.weights: Dict[str, float] = {}
        self.display_names: Dict[str, str] = {}
        self.status: Optional[str] = None
        self.estimator_version: Optional[str] = None

        if not skill_importance_output:
            return

        st = (
            skill_importance_output.get("status")
            if isinstance(skill_importance_output, dict)
            else getattr(skill_importance_output, "status", None)
        )
        self.status = st.value if hasattr(st, "value") else (str(st) if st else None)
        ver = (
            skill_importance_output.get("estimator_version")
            if isinstance(skill_importance_output, dict)
            else getattr(skill_importance_output, "estimator_version", None)
        )
        self.estimator_version = str(ver) if ver else None

        recs = (
            skill_importance_output.get("records", [])
            if isinstance(skill_importance_output, dict)
            else getattr(skill_importance_output, "records", [])
        )
        for r in recs:
            sk_id = r.get("skill_id") if isinstance(r, dict) else getattr(r, "skill_id", None)
            c_sk_id = r.get("canonical_skill_id") if isinstance(r, dict) else getattr(r, "canonical_skill_id", None)
            wt = r.get("weight") if isinstance(r, dict) else getattr(r, "weight", None)
            if wt is None:
                wt = r.get("importance_weight") if isinstance(r, dict) else getattr(r, "importance_weight", None)
            name = r.get("skill_name") if isinstance(r, dict) else getattr(r, "skill_name", None)
            if not name:
                name = r.get("skill_display_name") if isinstance(r, dict) else getattr(r, "skill_display_name", None)

            if wt is not None:
                try:
                    f_wt = float(wt)
                    if math.isfinite(f_wt):
                        for k in (sk_id, c_sk_id):
                            if k:
                                self._register(str(k), f_wt, str(name) if name else None)
                except (ValueError, TypeError):
                    continue

    def _register(self, key_id: str, weight: float, name: Optional[str]) -> None:
        clean = key_id.strip()
        norm = normalize_canonical_skill(clean)
        for variant in (clean, clean.lower(), norm, norm.lower() if norm else None):
            if not variant:
                continue
            self.weights[variant] = weight
            self.weights[variant.replace("_", "-")] = weight
            self.weights[variant.replace("-", "_")] = weight
            if name:
                self.display_names[variant] = name
                self.display_names[variant.replace("_", "-")] = name
                self.display_names[variant.replace("-", "_")] = name

    def get_weight(self, skill_id: Optional[str]) -> Optional[float]:
        if not skill_id or not self.weights:
            return None
        clean = skill_id.strip()
        norm = normalize_canonical_skill(clean)
        for cand in (
            clean,
            norm,
            clean.lower(),
            norm.lower() if norm else None,
            clean.replace("_", "-").lower(),
            norm.replace("_", "-").lower() if norm else None,
        ):
            if cand and cand in self.weights:
                return self.weights[cand]
        return None

    def get_display_name(self, skill_id: Optional[str]) -> Optional[str]:
        if not skill_id or not self.display_names:
            return None
        clean = skill_id.strip()
        norm = normalize_canonical_skill(clean)
        for cand in (
            clean,
            norm,
            clean.lower(),
            norm.lower() if norm else None,
            clean.replace("_", "-").lower(),
            norm.replace("_", "-").lower() if norm else None,
        ):
            if cand and cand in self.display_names:
                return self.display_names[cand]
        return None


# ---------------------------------------------------------------------------------------------
# Proficiency input
# ---------------------------------------------------------------------------------------------
def _candidate_spans(raw_skill: Any, extraction_type: str) -> List[str]:
    spans: List[str] = []
    for ev in _get(raw_skill, "evidences", None) or []:
        if extraction_type == "explicit":
            cands = [_get(ev, "sentence")]
        else:
            primary = _get(ev, "inferred_from_raw") or _get(ev, "sentence")
            if primary:
                cands = [primary]
            else:  # fall back to individually verified snippets
                cands = [
                    _get(sn, "text")
                    for sn in (_get(ev, "snippets", None) or [])
                    if _get(sn, "verbatim_ok", True)
                ]
        spans.extend(c for c in cands if isinstance(c, str) and c.strip())
    return spans


def _confidence_candidates(raw_skill: Any, adapted_confidence: Any, extraction_type: str) -> Tuple[List[float], str]:
    """Return (valid source confidences, provenance label). Never invents a value."""
    direct = _valid_confidence(adapted_confidence)
    if direct is None:
        direct = _valid_confidence(_get(raw_skill, "confidence"))
    if direct is not None:
        return [direct], "skill.confidence"
    if extraction_type == "implicit":
        ev_vals = [
            v
            for v in (
                _valid_confidence(_get(ev, "llm_confidence_raw")) for ev in (_get(raw_skill, "evidences", None) or [])
            )
            if v is not None
        ]
        if ev_vals:
            return ev_vals, "evidence.llm_confidence_raw"
    return [], "none"


def build_proficiency_side(
    doc_result: Any,
    doc_text: str,
    side: str,
    run_id: str,
    retained_occurrences: Optional[set],
    retained_canonicals: set,
    skill_importance_output: Optional[Any] = None,
) -> Tuple[List[ProficiencySkill], Dict[str, Any]]:
    """Build the retained-skill list for ONE document side from that side's own extraction only."""
    if doc_result is None:
        return [], {"side": side, "skills": 0, "dropped_unverified_spans": 0}

    active = ExtractionDataAdapter.extract_active_skills(doc_result, run_id=run_id).active_skills
    norm_text = _collapse_ws(doc_text or "")

    groups: Dict[Tuple[str, str], Dict[str, Any]] = {}
    order: List[Tuple[str, str]] = []
    dropped: List[Dict[str, str]] = []

    for s in active:
        canon = normalize_canonical_skill(s.skill_id or s.display_name)
        if retained_occurrences is not None:
            if s.occurrence_id not in retained_occurrences:
                continue
        elif canon not in retained_canonicals:
            continue

        etype = "implicit" if s.extraction_type == "implicit" else "explicit"
        key = (canon, etype)
        if key not in groups:
            groups[key] = {
                "spans": [],
                "confs": [],
                "conf_sources": set(),
                "occurrences": 0,
                "display_name": getattr(s, "display_name", canon),
            }
            order.append(key)
        g = groups[key]
        g["occurrences"] += 1

        cands = _candidate_spans(s.raw_skill, etype)
        if etype == "implicit":
            from matching_cv.app.services.implicit_evidence_verifier import ImplicitEvidenceVerifier
            anchored_spans, is_eligible, _ = ImplicitEvidenceVerifier.verify_implicit_evidence_anchoring(
                cands, doc_text
            )
            if is_eligible:
                for span in anchored_spans:
                    if span not in g["spans"]:
                        g["spans"].append(span)
            else:
                for span in cands:
                    dropped.append({"skill_id": canon, "span": span})
        else:
            for span in cands:
                if _collapse_ws(span) in norm_text:
                    if span not in g["spans"]:
                        g["spans"].append(span)
                else:
                    dropped.append({"skill_id": canon, "span": span})

        confs, src = _confidence_candidates(s.raw_skill, s.confidence, etype)
        g["confs"].extend(confs)
        g["conf_sources"].add(src)

    lookup = ImportanceLookup(skill_importance_output) if (side == "JD" and skill_importance_output) else None

    skills: List[ProficiencySkill] = []
    conf_prov: Dict[str, str] = {}
    dropped_unsupported_implicit: List[str] = []
    for key in order:
        canon, etype = key
        g = groups[key]
        if etype == "implicit" and len(g["spans"]) == 0:
            # Policy B2: Implicit skills without verifiable anchored evidence must NOT enter public output
            dropped_unsupported_implicit.append(canon)
            continue
        conf = max(g["confs"]) if g["confs"] else None  # deterministic: max of REAL source values, else null

        w_val: Optional[float] = None
        s_name: Optional[str] = g.get("display_name")
        imp_status: Optional[str] = None
        imp_ver: Optional[str] = None

        if side == "JD" and lookup:
            w_val = lookup.get_weight(canon)
            s_name = lookup.get_display_name(canon) or s_name or canon
            imp_status = lookup.status if w_val is not None else None
            imp_ver = lookup.estimator_version if w_val is not None else None

        skills.append(
            ProficiencySkill(
                skill_id=canon,
                skill_name=s_name,
                type=etype,
                confidence=conf,
                w_j=round(w_val, 4) if (w_val is not None and math.isfinite(w_val)) else None,
                evidence_spans=g["spans"],
                importance_status=imp_status,
                importance_estimator_version=imp_ver,
            )
        )
        conf_prov[f"{canon}|{etype}"] = ",".join(sorted(g["conf_sources"] - {"none"})) or "none"

    return skills, {
        "side": side,
        "skills": len(skills),
        "dropped_unverified_spans": len(dropped),
        "dropped_unverified_span_samples": dropped[:20],
        "dropped_unsupported_implicit_skills": dropped_unsupported_implicit,
        "confidence_provenance": conf_prov,
    }


# ---------------------------------------------------------------------------------------------
# Skill gap input
# ---------------------------------------------------------------------------------------------
def _node_index(nodes: List[Any], side: str) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """Map occurrence_id -> node and canonical_id -> node for one side."""
    by_occ: Dict[str, Any] = {}
    by_canon: Dict[str, Any] = {}
    for n in nodes:
        canon = n.cv_canonical_id if side == "CV" else n.jd_canonical_id
        if not canon:
            continue
        by_canon[canon] = n
        for occ in (n.cv_occurrence_ids if side == "CV" else n.jd_occurrence_ids) or []:
            by_occ[occ] = n
    return by_occ, by_canon


def _resolve_node(rec: Any, by_occ: Dict[str, Any], by_canon: Dict[str, Any]) -> Optional[Any]:
    node = by_occ.get(getattr(rec, "occurrence_id", None))
    if node is not None:
        return node
    for sid in getattr(rec, "associated_skill_ids", None) or []:
        node = by_canon.get(normalize_canonical_skill(sid))
        if node is not None:
            return node
    for sname in getattr(rec, "associated_skill_names", None) or []:
        node = by_canon.get(normalize_canonical_skill(sname))
        if node is not None:
            return node
    return None


def _classify_semantic_relation_category(jd_cid: str, cv_cid: Optional[str], is_shared: bool) -> str:
    """Classify the semantic relationship between a JD skill and its matched CV skill for audit diagnostics."""
    if not cv_cid:
        return "unmatched"
    if is_shared or jd_cid == cv_cid:
        return "exact_or_alias_equivalent"

    pair = frozenset({jd_cid, cv_cid})
    unrelated_or_confusable_pairs = {
        frozenset({"webpack", "core-web-vitals"}),
        frozenset({"zustand", "jest"}),
        frozenset({"react", "react-query"}),
        frozenset({"react", "react-router"}),
        frozenset({"react", "react-testing-library"}),
        frozenset({"java", "javascript"}),
        frozenset({"c", "c++"}),
        frozenset({"c", "c#"}),
    }
    if pair in unrelated_or_confusable_pairs:
        return "confusable_distinct_or_unrelated_guard"

    alternative_pairs = {
        frozenset({"postgresql", "mysql"}),
        frozenset({"express", "nestjs"}),
        frozenset({"graphql", "rest"}),
        frozenset({"graphql", "rest-api"}),
        frozenset({"react", "vue"}),
        frozenset({"react", "angular"}),
        frozenset({"jest", "vitest"}),
        frozenset({"playwright", "cypress"}),
    }
    if pair in alternative_pairs:
        return "alternative_in_or_group"

    specialization_pairs = {
        frozenset({"react-typescript-application", "typescript"}),
        frozenset({"react-typescript-application", "react"}),
        frozenset({"unit-and-end-to-end-tests", "react-testing-library"}),
        frozenset({"unit-and-end-to-end-tests", "jest"}),
        frozenset({"unit-and-end-to-end-tests", "playwright"}),
        frozenset({"aws", "ec2"}),
        frozenset({"aws", "s3"}),
        frozenset({"aws", "aws-lambda"}),
        frozenset({"aws-services", "ec2"}),
        frozenset({"aws-services", "s3"}),
        frozenset({"aws-services", "aws-lambda"}),
    }
    if pair in specialization_pairs or (jd_cid in cv_cid or cv_cid in jd_cid):
        return "specialization_or_parent"

    return "related_skill"


def build_skill_gap(
    graph_data: Any,
    stage3_response: Any,
    jd_order: List[str],
    min_soft_match: float,
    skill_importance_output: Optional[Any] = None,
    suppress_cross_category_soft_match: bool = False,
    eligible_cv_ids: Optional[set[str]] = None,
) -> Tuple[List[SkillGapRow], List[Dict[str, Any]]]:
    nodes = list(graph_data.skill_nodes.values())
    jd_nodes = [n for n in nodes if n.jd_canonical_id]
    cv_by_occ, cv_by_canon = _node_index(nodes, "CV")
    jd_by_occ, jd_by_canon = _node_index(nodes, "JD")

    # Importance weights lookup map if available
    lookup = ImportanceLookup(skill_importance_output)

    # --- full JD x CV similarity structure (reverse retrieval; independent of CV->JD Top-K) ---
    pair_cos: Dict[Tuple[str, str], float] = {}  # (jd_node_id, cv_node_id) -> max raw cosine
    matrix_available = False
    if stage3_response is not None:
        matrices = getattr(stage3_response, "similarity_matrices", None) or {}
        mat = matrices.get(MATRIX_KEY)
        if mat is not None:
            scores = mat.raw_matrix or mat.matrix
            cv_recs = {r.embedding_id: r for r in stage3_response.cv_skill_embeddings}
            jd_recs = {r.embedding_id: r for r in stage3_response.jd_skill_embeddings}
            row_nodes = [
                _resolve_node(cv_recs[i], cv_by_occ, cv_by_canon) if i in cv_recs else None for i in mat.source_ids
            ]
            col_nodes = [
                _resolve_node(jd_recs[j], jd_by_occ, jd_by_canon) if j in jd_recs else None for j in mat.target_ids
            ]
            if scores and all(len(r) == len(col_nodes) for r in scores) and len(scores) == len(row_nodes):
                matrix_available = True
                for ri, cv_node in enumerate(row_nodes):
                    if cv_node is None:
                        continue  # CV record not retained in the graph -> not eligible
                    for ci, jd_node in enumerate(col_nodes):
                        if jd_node is None:
                            continue
                        key = (jd_node.node_id, cv_node.node_id)
                        val = float(scores[ri][ci])
                        if not math.isfinite(val):
                            continue
                        if key not in pair_cos or val > pair_cos[key]:
                            pair_cos[key] = val

    cv_nodes_sorted = sorted(
        (n for n in nodes if n.cv_canonical_id
         and (eligible_cv_ids is None or n.cv_canonical_id in eligible_cv_ids)),
        key=lambda n: n.cv_canonical_id,
    )

    rank = {c: i for i, c in enumerate(jd_order)}
    jd_nodes.sort(key=lambda n: (rank.get(n.jd_canonical_id, len(rank)), n.jd_canonical_id))

    rows: List[SkillGapRow] = []
    details: List[Dict[str, Any]] = []
    for jn in jd_nodes:
        detail: Dict[str, Any] = {"jd_skill_id": jn.jd_canonical_id, "jd_node_id": jn.node_id}
        matched: Optional[str] = None
        soft: Optional[float] = None
        is_shared = bool(jn.cv_canonical_id) and (
            eligible_cv_ids is None or jn.cv_canonical_id in eligible_cv_ids
        )

        if is_shared:  # Priority A: shared graph node (verified identity under active merge policy)
            matched = jn.cv_canonical_id
            reason = jn.merge_decision.merge_reason if jn.merge_decision else None
            measured = pair_cos.get((jn.node_id, jn.node_id))
            if measured is None or not math.isfinite(measured):
                measured = jn.cosine_similarity_if_shared
            if measured is not None and math.isfinite(measured):
                soft = measured
            else:
                soft = None
            detail.update(
                match_type="verified_identity" if reason in IDENTITY_MERGE_REASONS else "graph_merge_other",
                merge_reason=reason,
                similarity_source=(
                    "stage3_matrix" if (jn.node_id, jn.node_id) in pair_cos else
                    ("graph_node.cosine_similarity_if_shared" if soft is not None else "unavailable")
                ),
            )
        else:  # Priority B: best semantic candidate via reverse retrieval argmax
            best: Optional[Tuple[float, Any]] = None
            for cn in cv_nodes_sorted:
                val = pair_cos.get((jn.node_id, cn.node_id))
                if val is None or not math.isfinite(val):
                    continue
                if suppress_cross_category_soft_match:
                    rel_cat = _classify_semantic_relation_category(jn.jd_canonical_id, cn.cv_canonical_id, False)
                    if rel_cat == "confusable_distinct_or_unrelated_guard":
                        continue
                if best is None or val > best[0]:  # strict '>' + sorted iteration -> deterministic tie-break
                    best = (val, cn)
            if best is not None and best[0] >= min_soft_match:
                matched, soft = best[1].cv_canonical_id, best[0]
                detail.update(match_type="semantic_related", similarity_source="stage3_matrix")
            else:  # Priority C: unmatched
                detail.update(
                    match_type="no_match",
                    similarity_source="stage3_matrix" if matrix_available else "unavailable",
                    best_below_threshold=(
                        {"cv_skill_id": best[1].cv_canonical_id, "cosine": best[0]} if best is not None else None
                    ),
                )

        sem_cat = _classify_semantic_relation_category(jn.jd_canonical_id, matched, is_shared)
        detail.update(
            threshold=min_soft_match,
            matched_cv_skill_id=matched,
            soft_match=soft,
            semantic_relation_category=sem_cat,
            influences_gnn_graph=is_shared,
        )
        details.append(detail)
        w_val = lookup.get_weight(jn.jd_canonical_id)
        rows.append(
            SkillGapRow(
                jd_skill_id=jn.jd_canonical_id,
                w_j=round(w_val, 4) if (w_val is not None and math.isfinite(w_val)) else None,
                matched_cv_skill_id=matched,
                soft_match=round(soft, 6) if (soft is not None and math.isfinite(soft)) else None,
            )
        )
    return rows, details


# ---------------------------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------------------------
def _extract_output_skills(
    ctx: PublicOutputContext,
) -> tuple[list[ProficiencySkill], list[ProficiencySkill], dict[str, Any], dict[str, Any]]:
    unified = ctx.unified_response
    graph = ctx.graph_data
    run_id = (getattr(unified, "run_id", None) or "paper_run") if unified is not None else "paper_run"

    nodes = list(graph.skill_nodes.values())
    retained_cv = {n.cv_canonical_id for n in nodes if n.cv_canonical_id}
    retained_jd = {n.jd_canonical_id for n in nodes if n.jd_canonical_id}

    lineage = (graph.diagnostics or {}).get("competency_lineage")
    occ_cv: Optional[set] = None
    occ_jd: Optional[set] = None
    if lineage:
        occ_cv = {r["occurrence_id"] for r in lineage if r["source_side"] == "CV" and r["retention_decision"] == "RETAINED"}
        occ_jd = {r["occurrence_id"] for r in lineage if r["source_side"] == "JD" and r["retention_decision"] == "RETAINED"}

    cv_skills, cv_dbg = build_proficiency_side(
        _get(unified, "cv"), ctx.cv_text, "CV", run_id, occ_cv, retained_cv
    ) if unified is not None else ([], {})
    jd_skills, jd_dbg = (
        build_proficiency_side(
            _get(unified, "jd"),
            ctx.jd_text,
            "JD",
            run_id,
            occ_jd,
            retained_jd,
            skill_importance_output=ctx.skill_importance_output,
        )
        if unified is not None
        else ([], {})
    )

    return cv_skills, jd_skills, cv_dbg, jd_dbg


def build_standardized_output(
    ctx: PublicOutputContext,
    min_soft_match: Optional[float] = None,
) -> StandardizedOutputBuild:
    threshold = settings.SKILL_GAP_MIN_SOFT_MATCH if min_soft_match is None else float(min_soft_match)
    cv_skills, jd_skills, cv_dbg, jd_dbg = _extract_output_skills(ctx)
    jd_order = list(dict.fromkeys(skill.skill_id for skill in jd_skills))
    graph = ctx.graph_data
    rows, gap_details = build_skill_gap(graph, ctx.stage3_response, jd_order, threshold, ctx.skill_importance_output)

    has_score = ctx.matching_score is not None
    public = StandardizedPipelineOutput(
        match_score=float(ctx.matching_score) if has_score else None,
        status=map_public_status(ctx.matching_status, has_score),
        cv_text=ctx.cv_text,
        jd_text=ctx.jd_text,
        skill_gap_input=rows,
        proficiency_input=ProficiencyInput(cv_skills=cv_skills, jd_skills=jd_skills),
    )
    internal = {
        "run_id": ctx.run_id,
        "schema_version": "standardized-output-v1",
        "min_soft_match": threshold,
        "similarity_matrix_available": ctx.stage3_response is not None,
        "skill_gap_details": gap_details,
        "proficiency_debug": {"cv": cv_dbg, "jd": jd_dbg},
        "internal_matching_status": ctx.matching_status,
        "graph_policy": graph.diagnostics.get("graph_policy", "policy_a_legacy") if (graph and hasattr(graph, "diagnostics") and graph.diagnostics) else "policy_a_legacy",
        "semantic_transform_audit": graph.diagnostics.get("semantic_transform_audit") if (graph and hasattr(graph, "diagnostics") and graph.diagnostics) else None,
        "score_contract_metadata": {
            "raw_model_score": float(ctx.matching_score) if has_score else None,
            "predicted_target_name": "skill_score",
            "score_version": "skill-target-regression-v1",
            "calibrated_score": None,
            "calibration_status": "UNCALIBRATED",
            "fit_category": "Uncalibrated" if has_score else None,
            "display_semantic_matches_isolated_from_gnn_graph": True,
        },
    }
    return StandardizedOutputBuild(public=public, internal=internal)


class Module1OutputError(ValueError):
    """The pipeline did not produce enough data to run skill gap analysis."""


def _unique_skills(skills: list[ProficiencySkill]) -> dict[str, ProficiencySkill]:
    unique: dict[str, ProficiencySkill] = {}
    for skill in skills:
        if skill.skill_id not in unique or skill.type == "explicit":
            unique[skill.skill_id] = skill
    return unique


class _SkillFields(TypedDict):
    skill_id: str
    type: SkillType
    confidence: float
    evidence_spans: list[str]


def _skill_fields(skill: ProficiencySkill) -> _SkillFields:
    return {
        "skill_id": skill.skill_id,
        "type": SkillType(skill.type),
        "confidence": skill.confidence if skill.confidence is not None else 0.0,
        "evidence_spans": skill.evidence_spans,
    }


def _build_match(skill: ProficiencySkill, row: Optional[SkillGapRow]) -> MatchResult:
    weight = row.w_j if row and row.w_j is not None else skill.w_j
    if weight is None:
        raise Module1OutputError(f"Missing JD skill importance for {skill.skill_id}")
    cv_id = row.matched_cv_skill_id if row else None
    score = row.soft_match if row else None
    if cv_id is None or score is None or score <= 0:
        cv_id, score = "none", 0.0
    return MatchResult(
        jd_skill_id=skill.skill_id,
        matched_cv_skill_id=cv_id,
        soft_match=min(1.0, score),
        w_j=weight,
    )


def build_module1_output(ctx: PublicOutputContext) -> Module1Output:
    """Build the native Smile Interview contract from the matching pipeline's results."""
    documents = (ctx.unified_response.cv, ctx.unified_response.jd)
    if any(document is None or document.explicit is None for document in documents):
        raise Module1OutputError("Skill extraction did not complete for both documents")
    cv_skills, jd_skills, _, _ = _extract_output_skills(ctx)
    cv_by_id = _unique_skills(cv_skills)
    jd_by_id = _unique_skills(jd_skills)
    if not jd_by_id:
        raise Module1OutputError("No JD skills were retained")
    rows, _ = build_skill_gap(
        ctx.graph_data, ctx.stage3_response, list(jd_by_id),
        settings.SKILL_GAP_MIN_SOFT_MATCH, ctx.skill_importance_output,
        eligible_cv_ids=set(cv_by_id),
    )
    by_jd_id = {row.jd_skill_id: row for row in rows}
    return Module1Output(
        matcher_source="MATCHING_CV",
        cv_skills=[ExtractedCVSkill(**_skill_fields(skill)) for skill in cv_by_id.values()],
        jd_skills=[ExtractedJDSkill(**_skill_fields(skill)) for skill in jd_by_id.values()],
        match_results=[_build_match(skill, by_jd_id.get(skill.skill_id)) for skill in jd_by_id.values()],
    )


def standardized_output_from_internal(internal_response: Any) -> StandardizedOutputBuild:
    """Single shared serialization path for the analyze endpoint.

    ``internal_response`` is a ``PipelineAnalyzeResponse`` carrying the private in-memory context.
    Raises ``ValueError`` if no context is attached (e.g. a failed run).
    """
    ctx = getattr(internal_response, "_public_context", None)
    if ctx is None:
        raise ValueError("No standardized-output context is attached to this response (run did not reach Stage 5).")
    return build_standardized_output(ctx)
