"""Deterministic Shared Entity Identification and Merging Policy.

Reference:
Baghbanzadeh, A., & Wu, D. (2025). ICIT 2025.
- Section 3.4 & Figures 4-5: Shared entities connect to both job and resume nodes;
  unique entities connect only to their respective document node.
- Project-adapted matching rules (Section 4.3 of task specification):
  - Same validated canonical skill ID / verified alias -> shared skill.
  - Verified LLM equivalence relation -> shared skill.
  - Merely high cosine similarity -> candidate, NOT automatically merged in default policy.
  - related / used_together_with / prerequisite / specialization / alternative -> DO NOT merge.
  - Uncertain identity -> preserve separate entities.
  - Paper cosine > 0.8 exposed as an explicit experimental variant ('paper_cosine_08').
"""
from __future__ import annotations

from typing import Dict, FrozenSet, List, Optional, Set, Tuple
import numpy as np

from matching_cv.app.schemas.semantic_reasoning import SkillPairReasoningResult
from matching_cv.research.data.canonical_skill_normalizer import normalize_canonical_skill
from matching_cv.research.paper_aligned_gnn.schemas import (
    DecisionClassification,
    MergeAuditRecord,
    MergePolicyType,
    SkillInputItem,
)

# ---------------------------------------------------------------------------
# Confusable Distinct Skill Families (Hard Guardrail)
# Any two distinct canonical IDs within any of these sets are strictly distinct
# technologies and must NEVER be merged into a shared skill node under verified
# equivalence, even if an LLM or embedding cosine suggests similarity.
# ---------------------------------------------------------------------------
CONFUSABLE_DISTINCT_FAMILIES: List[FrozenSet[str]] = [
    frozenset({"react", "react-query", "react-native", "react-router", "next.js", "nextjs", "redux"}),
    frozenset({"java", "javascript", "typescript"}),
    frozenset({"redis", "redux", "redux-toolkit", "redshift", "redshift"}),
    frozenset({"docker", "kubernetes", "helm", "podman", "terraform"}),
    frozenset({"c", "c++", "c#", "objective-c"}),
    frozenset({"sql", "nosql", "postgresql", "mysql", "sqlite", "sql-server", "pl-sql", "t-sql"}),
    frozenset({"git", "github", "gitlab", "github-actions", "bitbucket"}),
    frozenset({"python", "pytorch", "pyspark", "pytest", "pydantic", "pandas", "numpy"}),
    frozenset({"angular", "nestjs", "rxjs", "vue", "svelte"}),
    frozenset({"aws", "azure", "gcp"}),
]

NON_EQUIVALENT_RELATIONS: FrozenSet[str] = frozenset({
    "related",
    "used_together_with",
    "prerequisite",
    "specialization",
    "alternative",
    "unrelated",
    "uncertain",
})


def are_confusable_distinct_skills(canon_a: str, canon_b: str) -> bool:
    """
    Return True if canon_a and canon_b are distinct canonical IDs that belong to
    a known confusable technical family (e.g., 'react' vs 'react-query',
    'java' vs 'javascript', 'redis' vs 'redux', 'docker' vs 'kubernetes',
    'c' vs 'c++' vs 'c#').
    """
    a = normalize_canonical_skill(canon_a)
    b = normalize_canonical_skill(canon_b)
    if not a or not b or a == b:
        return False
    for family in CONFUSABLE_DISTINCT_FAMILIES:
        if a in family and b in family:
            return True
    return False


def compute_vector_cosine(vec_a: Optional[List[float]], vec_b: Optional[List[float]]) -> Optional[float]:
    """Compute cosine similarity between two embedding vectors."""
    if not vec_a or not vec_b or len(vec_a) != len(vec_b):
        return None
    arr_a = np.asarray(vec_a, dtype=np.float64)
    arr_b = np.asarray(vec_b, dtype=np.float64)
    norm_a = float(np.linalg.norm(arr_a))
    norm_b = float(np.linalg.norm(arr_b))
    if norm_a < 1e-12 or norm_b < 1e-12:
        return 0.0
    cos_val = float(np.dot(arr_a, arr_b) / (norm_a * norm_b))
    return round(float(np.clip(cos_val, -1.0, 1.0)), 6)


def combine_shared_embeddings(
    vec_cv: List[float],
    vec_jd: List[float],
) -> Tuple[List[float], str]:
    """
    Combine CV and JD skill embeddings for a merged shared skill node.
    If identical within floating-point tolerance, returns vec_cv ('identical_vectors').
    Otherwise returns L2-normalized mean ('l2_normalized_mean').
    """
    arr_cv = np.asarray(vec_cv, dtype=np.float64)
    arr_jd = np.asarray(vec_jd, dtype=np.float64)
    if np.allclose(arr_cv, arr_jd, atol=1e-5):
        return [float(x) for x in arr_cv.astype(np.float32)], "identical_vectors"
    mean_vec = 0.5 * (arr_cv + arr_jd)
    norm = float(np.linalg.norm(mean_vec))
    if norm > 1e-12:
        mean_vec = mean_vec / norm
    return [float(x) for x in mean_vec.astype(np.float32)], "l2_normalized_mean"


def deduplicate_within_document(items: List[SkillInputItem]) -> List[SkillInputItem]:
    """
    Deduplicate multiple skill occurrences within the same document (CV or JD)
    that resolve to the same canonical skill ID, preserving all surface forms,
    verbatim evidence sentences, offsets, and explicit modifier qualifiers.
    """
    grouped: Dict[str, SkillInputItem] = {}
    surface_history: Dict[str, List[str]] = {}
    occ_history: Dict[str, List[str]] = {}

    for item in items:
        canon = normalize_canonical_skill(item.canonical_skill_id or item.surface_name)
        if not canon:
            canon = normalize_canonical_skill(item.surface_name) or item.canonical_skill_id

        if canon not in grouped:
            cloned = item.model_copy(deep=True)
            cloned.canonical_skill_id = canon
            grouped[canon] = cloned
            surface_history[canon] = [item.surface_name]
            occ_history[canon] = [item.occurrence_id]
        else:
            existing = grouped[canon]
            if item.surface_name not in surface_history[canon]:
                surface_history[canon].append(item.surface_name)
            if item.occurrence_id not in occ_history[canon]:
                occ_history[canon].append(item.occurrence_id)

            # Prefer explicit over implicit if both exist
            if item.extraction_type == "explicit":
                existing.extraction_type = "explicit"

            for sent in item.evidence_sentences:
                if sent and sent not in existing.evidence_sentences:
                    existing.evidence_sentences.append(sent)
            for off in item.evidence_offsets:
                if off not in existing.evidence_offsets:
                    existing.evidence_offsets.append(off)

            if not existing.modifier_text and item.modifier_text:
                existing.modifier_text = item.modifier_text
            if not existing.proficiency_override and item.proficiency_override:
                existing.proficiency_override = item.proficiency_override
            if not existing.embedding_vector and item.embedding_vector:
                existing.embedding_vector = item.embedding_vector
                existing.embedding_ref = item.embedding_ref

    result: List[SkillInputItem] = []
    for canon, merged_item in grouped.items():
        merged_item.metadata["all_surface_names"] = surface_history[canon]
        merged_item.metadata["all_occurrence_ids"] = occ_history[canon]
        result.append(merged_item)

    return result


def _index_reasoning_results(
    reasoning_results: Optional[List[SkillPairReasoningResult]],
) -> Dict[Tuple[str, str], SkillPairReasoningResult]:
    """Index Stage 4 LLM reasoning results by normalized (cv_canon, jd_canon) and (occ_a, occ_b)."""
    index: Dict[Tuple[str, str], SkillPairReasoningResult] = {}
    if not reasoning_results:
        return index

    for res in reasoning_results:
        a_canon = normalize_canonical_skill(res.skill_a.skill_id or res.skill_a.name)
        b_canon = normalize_canonical_skill(res.skill_b.skill_id or res.skill_b.name)
        if a_canon and b_canon:
            index[(a_canon, b_canon)] = res
            index[(b_canon, a_canon)] = res

        a_name_canon = normalize_canonical_skill(res.skill_a.name)
        b_name_canon = normalize_canonical_skill(res.skill_b.name)
        if a_name_canon and b_name_canon:
            index.setdefault((a_name_canon, b_name_canon), res)
            index.setdefault((b_name_canon, a_name_canon), res)

        if res.source_occurrence_ids and len(res.source_occurrence_ids) >= 2:
            occ_0, occ_1 = res.source_occurrence_ids[0], res.source_occurrence_ids[1]
            index[(occ_0, occ_1)] = res
            index[(occ_1, occ_0)] = res

    return index


def match_and_merge_skills(
    cv_items: List[SkillInputItem],
    jd_items: List[SkillInputItem],
    merge_policy: MergePolicyType = "verified_equivalence",
    paper_cosine_threshold: float = 0.80,
    enforce_confusable_guardrails_in_cosine_mode: bool = False,
    reasoning_results: Optional[List[SkillPairReasoningResult]] = None,
) -> Tuple[
    List[Tuple[SkillInputItem, SkillInputItem, MergeAuditRecord]],
    List[Tuple[SkillInputItem, MergeAuditRecord]],
    List[Tuple[SkillInputItem, MergeAuditRecord]],
    List[MergeAuditRecord],
]:
    """
    Execute deterministic bipartite skill matching and merging between CV and JD skills.

    Returns:
        - shared_pairs: List of (cv_item, jd_item, merge_audit_record) for merged shared skills
        - unique_cv_items: List of (cv_item, merge_audit_record) for CV-only skills
        - unique_jd_items: List of (jd_item, merge_audit_record) for JD-only skills
        - all_audit_records: Complete list of MergeAuditRecords (including non-merged candidate pairs)
    """
    dedup_cv = deduplicate_within_document(cv_items)
    dedup_jd = deduplicate_within_document(jd_items)
    reasoning_idx = _index_reasoning_results(reasoning_results)

    matched_cv_indices: Set[int] = set()
    matched_jd_indices: Set[int] = set()
    shared_pairs: List[Tuple[SkillInputItem, SkillInputItem, MergeAuditRecord]] = []
    all_audit_records: List[MergeAuditRecord] = []

    # Evaluate all candidate pairs (i, j) to rank and audit deterministically
    candidate_evaluations: List[Tuple[int, float, int, int, MergeAuditRecord]] = []

    for i, cv_sk in enumerate(dedup_cv):
        cv_canon = normalize_canonical_skill(cv_sk.canonical_skill_id or cv_sk.surface_name)
        cv_surfaces = cv_sk.metadata.get("all_surface_names", [cv_sk.surface_name])
        cv_occs = cv_sk.metadata.get("all_occurrence_ids", [cv_sk.occurrence_id])

        for j, jd_sk in enumerate(dedup_jd):
            jd_canon = normalize_canonical_skill(jd_sk.canonical_skill_id or jd_sk.surface_name)
            jd_surfaces = jd_sk.metadata.get("all_surface_names", [jd_sk.surface_name])
            jd_occs = jd_sk.metadata.get("all_occurrence_ids", [jd_sk.occurrence_id])

            cosine = compute_vector_cosine(cv_sk.embedding_vector, jd_sk.embedding_vector)

            # Look up any LLM semantic reasoning record
            llm_res = (
                reasoning_idx.get((cv_sk.occurrence_id, jd_sk.occurrence_id))
                or reasoning_idx.get((cv_canon, jd_canon))
            )
            llm_id = llm_res.identity if llm_res else None
            llm_rel = llm_res.relationship if llm_res else None
            llm_status = llm_res.graph_relation_status if llm_res else None
            llm_contra = bool(llm_res.contradiction_detected) if llm_res else False

            is_confusable_distinct = are_confusable_distinct_skills(cv_canon, jd_canon)

            # Determine merge eligibility under active policy
            merged = False
            merge_reason = "distinct_skills"
            decision_cls: DecisionClassification = "PROJECT_ADAPTATION"
            priority_tier = 0

            if cv_canon == jd_canon and cv_canon != "":
                # Same canonical ID (either identical surface or verified canonical alias like React <-> ReactJS)
                raw_cv_lower = cv_sk.surface_name.strip().casefold()
                raw_jd_lower = jd_sk.surface_name.strip().casefold()
                merged = True
                merge_reason = "same_canonical_id" if raw_cv_lower == raw_jd_lower else "verified_alias_same_canonical_id"
                decision_cls = "PROJECT_ADAPTATION" if merge_policy != "paper_cosine_08" else "PAPER_EXPLICIT"
                priority_tier = 3

            elif merge_policy == "canonical_only":
                merged = False
                if is_confusable_distinct:
                    merge_reason = "blocked_confusable_distinct_skills"
                elif cosine is not None and cosine > paper_cosine_threshold:
                    merge_reason = "candidate_high_cosine_unverified"
                else:
                    merge_reason = "distinct_canonical_id"
                decision_cls = "PROJECT_ADAPTATION"

            elif merge_policy == "verified_equivalence":
                decision_cls = "PROJECT_ADAPTATION"
                if is_confusable_distinct:
                    merged = False
                    merge_reason = "blocked_confusable_distinct_skills"
                elif llm_res is not None:
                    if llm_id == "uncertain" or llm_rel == "uncertain" or llm_contra:
                        merged = False
                        merge_reason = "blocked_uncertain_identity"
                    elif llm_rel in NON_EQUIVALENT_RELATIONS and llm_id != "equivalent":
                        merged = False
                        merge_reason = f"blocked_non_equivalent_relation_{llm_rel}"
                    elif (
                        llm_id == "equivalent"
                        and llm_status == "eligible"
                        and not llm_contra
                        and (llm_rel is None or llm_rel not in NON_EQUIVALENT_RELATIONS)
                    ):
                        merged = True
                        merge_reason = "verified_llm_equivalent"
                        priority_tier = 2
                    else:
                        merged = False
                        merge_reason = f"blocked_llm_status_{llm_status or 'unverified'}"
                else:
                    merged = False
                    if cosine is not None and cosine > paper_cosine_threshold:
                        merge_reason = "candidate_high_cosine_unverified"
                    else:
                        merge_reason = "distinct_canonical_id_no_llm_equivalence"

            elif merge_policy == "paper_cosine_08":
                decision_cls = "PAPER_EXPLICIT"
                if enforce_confusable_guardrails_in_cosine_mode and is_confusable_distinct:
                    merged = False
                    merge_reason = "blocked_confusable_distinct_skills"
                    decision_cls = "PROJECT_ADAPTATION"
                elif cosine is not None and cosine > paper_cosine_threshold:
                    merged = True
                    merge_reason = "paper_cosine_gt_08"
                    priority_tier = 1
                else:
                    merged = False
                    merge_reason = "below_paper_cosine_threshold"

            audit_rec = MergeAuditRecord(
                cv_occurrence_ids=cv_occs,
                jd_occurrence_ids=jd_occs,
                cv_canonical_id=cv_canon,
                jd_canonical_id=jd_canon,
                cv_surface_names=cv_surfaces,
                jd_surface_names=jd_surfaces,
                cosine_similarity=cosine,
                llm_identity=llm_id,
                llm_relationship=llm_rel,
                llm_graph_status=llm_status,
                merged=merged,
                merge_reason=merge_reason,
                policy_used=merge_policy,
                decision_class=decision_cls,
            )

            if merged:
                sort_cos = cosine if cosine is not None else 1.0
                candidate_evaluations.append((priority_tier, sort_cos, i, j, audit_rec))
            else:
                # Record interesting non-merged candidates (e.g., confusable pairs, LLM relations, or cosine >= 0.5)
                if (
                    is_confusable_distinct
                    or llm_res is not None
                    or (cosine is not None and cosine >= 0.50)
                ):
                    all_audit_records.append(audit_rec)

    # Deterministic greedy one-to-one matching for eligible merges
    candidate_evaluations.sort(
        key=lambda x: (
            -x[0],
            -x[1],
            dedup_cv[x[2]].canonical_skill_id,
            dedup_jd[x[3]].canonical_skill_id,
        )
    )

    for _, _, i, j, audit_rec in candidate_evaluations:
        if i not in matched_cv_indices and j not in matched_jd_indices:
            matched_cv_indices.add(i)
            matched_jd_indices.add(j)
            shared_pairs.append((dedup_cv[i], dedup_jd[j], audit_rec))
            all_audit_records.append(audit_rec)
        else:
            # Already matched to a higher-priority partner in one-to-one bipartite assignment
            demoted = audit_rec.model_copy(deep=True)
            demoted.merged = False
            demoted.merge_reason = f"{audit_rec.merge_reason}_superseded_by_higher_priority_one_to_one_match"
            all_audit_records.append(demoted)

    # Collect unmatched CV-unique and JD-unique skills
    unique_cv_items: List[Tuple[SkillInputItem, MergeAuditRecord]] = []
    for i, cv_sk in enumerate(dedup_cv):
        if i not in matched_cv_indices:
            cv_canon = normalize_canonical_skill(cv_sk.canonical_skill_id or cv_sk.surface_name)
            cv_surfaces = cv_sk.metadata.get("all_surface_names", [cv_sk.surface_name])
            cv_occs = cv_sk.metadata.get("all_occurrence_ids", [cv_sk.occurrence_id])
            u_audit = MergeAuditRecord(
                cv_occurrence_ids=cv_occs,
                jd_occurrence_ids=[],
                cv_canonical_id=cv_canon,
                jd_canonical_id="",
                cv_surface_names=cv_surfaces,
                jd_surface_names=[],
                cosine_similarity=None,
                merged=False,
                merge_reason="unique_to_cv",
                policy_used=merge_policy,
                decision_class="PAPER_EXPLICIT",
            )
            unique_cv_items.append((cv_sk, u_audit))

    unique_jd_items: List[Tuple[SkillInputItem, MergeAuditRecord]] = []
    for j, jd_sk in enumerate(dedup_jd):
        if j not in matched_jd_indices:
            jd_canon = normalize_canonical_skill(jd_sk.canonical_skill_id or jd_sk.surface_name)
            jd_surfaces = jd_sk.metadata.get("all_surface_names", [jd_sk.surface_name])
            jd_occs = jd_sk.metadata.get("all_occurrence_ids", [jd_sk.occurrence_id])
            u_audit = MergeAuditRecord(
                cv_occurrence_ids=[],
                jd_occurrence_ids=jd_occs,
                cv_canonical_id="",
                jd_canonical_id=jd_canon,
                cv_surface_names=[],
                jd_surface_names=jd_surfaces,
                cosine_similarity=None,
                merged=False,
                merge_reason="unique_to_jd",
                policy_used=merge_policy,
                decision_class="PAPER_EXPLICIT",
            )
            unique_jd_items.append((jd_sk, u_audit))

    return shared_pairs, unique_cv_items, unique_jd_items, all_audit_records
