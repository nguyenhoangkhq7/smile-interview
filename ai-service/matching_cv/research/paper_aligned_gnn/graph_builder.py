"""Paper-Aligned Bipartite Graph Builder for Resume-Job Compatibility Scoring.

Reference:
Baghbanzadeh, A., & Wu, D. (2025). Resume-Job Compatibility Scoring Using Graph Neural Networks
and Large Language Models. ICIT 2025. Section 3.4, Figures 3-5, Table 3.
"""
from __future__ import annotations

import hashlib
import math
from typing import Any, Dict, List, Optional, Set, Tuple, Union

import numpy as np
import torch
from torch_geometric.data import HeteroData

from matching_cv.app.core.config import settings
from matching_cv.app.schemas.semantic_reasoning import SkillPairReasoningResult
from matching_cv.app.schemas.semantic_representation import (
    EmbeddingRecord,
    SemanticRepresentationResponse,
)
from matching_cv.app.schemas.unified_skill_extraction import UnifiedExtractFileResponse
from matching_cv.app.services.competency_granularity import evaluate_competency_retention
from matching_cv.app.services.extraction_adapter import ExtractionDataAdapter
from matching_cv.research.data.canonical_skill_normalizer import normalize_canonical_skill
from matching_cv.research.paper_aligned_gnn.proficiency_extractor import (
    PAPER_TABLE3_EXPLICIT_MAPPING,
    PAPER_TABLE6_7_SUPPLEMENTAL_MAPPING,
    compute_tensor_edge_weight,
    extract_skill_proficiency,
)
from matching_cv.research.paper_aligned_gnn.schemas import (
    CompetencyLineageRecord,
    DecisionClassification,
    DocumentInitStrategy,
    PaperAlignedBipartiteEdge,
    PaperAlignedDocumentNode,
    PaperAlignedGraphConfig,
    PaperAlignedGraphData,
    PaperAlignedGraphIntegrityReport,
    PaperAlignedSkillNode,
    SkillInputItem,
)
from matching_cv.research.paper_aligned_gnn.shared_skill_matcher import (
    are_confusable_distinct_skills,
    combine_shared_embeddings,
    match_and_merge_skills,
)


def generate_reproducible_document_embedding(
    dim: int,
    seed: int,
    strategy: DocumentInitStrategy = "random_seeded",
) -> Tuple[List[float], DecisionClassification]:
    """
    Generate reproducible initial feature vector for a document node ('resume' or 'job').
    - 'random_seeded': N(0, 1) using explicit torch.Generator(seed) [PAPER_EXPLICIT]
    - 'random_unit_norm': L2-normalized N(0, 1) using explicit torch.Generator(seed) [IMPLEMENTATION_ASSUMPTION]
    - 'zeros': All zeros [IMPLEMENTATION_ASSUMPTION]
    """
    if strategy == "zeros":
        return [0.0] * dim, "IMPLEMENTATION_ASSUMPTION"

    gen = torch.Generator(device="cpu")
    gen.manual_seed(int(seed))
    vec = torch.randn((dim,), generator=gen, dtype=torch.float32)

    if strategy == "random_unit_norm":
        norm = torch.linalg.norm(vec)
        if norm > 1e-12:
            vec = vec / norm
        return [float(x) for x in vec.tolist()], "IMPLEMENTATION_ASSUMPTION"

    return [float(x) for x in vec.tolist()], "PAPER_EXPLICIT"


def generate_deterministic_fallback_skill_embedding(
    canonical_id: str,
    dim: int,
) -> List[float]:
    """
    Generate a deterministic unit-norm vector from the SHA-256 of canonical_id ONLY when
    no upstream SBERT vector was attached (e.g., synthetic tests that omit explicit vectors).
    """
    digest = hashlib.sha256(f"paper_skill_seed::{canonical_id}".encode("utf-8")).digest()
    seed_int = int.from_bytes(digest[:8], byteorder="big") % (2**31 - 1)
    gen = torch.Generator(device="cpu")
    gen.manual_seed(seed_int)
    vec = torch.randn((dim,), generator=gen, dtype=torch.float32)
    norm = torch.linalg.norm(vec)
    if norm > 1e-12:
        vec = vec / norm
    return [float(x) for x in vec.tolist()]


class PaperAlignedGraphBuilder:
    """
    Constructs, validates, and exports the paper-aligned document-entity bipartite graph
    for a single Resume-Job pair.
    """

    def __init__(self, config: Optional[PaperAlignedGraphConfig] = None) -> None:
        self.config = config or PaperAlignedGraphConfig(
            embedding_dim=settings.STAGE3_EMBEDDING_DIM
        )

    def adapt_pipeline_inputs(
        self,
        unified_response: Optional[UnifiedExtractFileResponse],
        stage3_response: Optional[Union[SemanticRepresentationResponse, Dict[str, Any]]],
    ) -> Tuple[List[SkillInputItem], List[SkillInputItem], str, str, Optional[str], Optional[str]]:
        """
        Adapt upstream Stage 2 (UnifiedExtractFileResponse) and Stage 3 (SemanticRepresentationResponse)
        into normalized CV and JD SkillInputItem lists while preserving verbatim evidence sentences,
        modifier_text, and 768D SBERT embeddings.
        """
        cv_items, jd_items, cv_doc_id, jd_doc_id, cv_hash, jd_hash, _ = self.adapt_pipeline_inputs_with_lineage(
            unified_response=unified_response,
            stage3_response=stage3_response,
        )
        return cv_items, jd_items, cv_doc_id, jd_doc_id, cv_hash, jd_hash

    def adapt_pipeline_inputs_with_lineage(
        self,
        unified_response: Optional[UnifiedExtractFileResponse],
        stage3_response: Optional[Union[SemanticRepresentationResponse, Dict[str, Any]]],
    ) -> Tuple[
        List[SkillInputItem],
        List[SkillInputItem],
        str,
        str,
        Optional[str],
        Optional[str],
        List[CompetencyLineageRecord],
    ]:
        """
        Same as `adapt_pipeline_inputs` but also returns the per-record competency lineage.
        Pure function of its inputs (no builder state is written, so the singleton builder is thread-safe).
        """
        cv_doc_id = "resume_doc"
        jd_doc_id = "job_doc"
        cv_hash: Optional[str] = None
        jd_hash: Optional[str] = None

        # Index Stage 3 embeddings by occurrence_id and canonical skill_id
        cv_emb_by_occ: Dict[str, EmbeddingRecord] = {}
        jd_emb_by_occ: Dict[str, EmbeddingRecord] = {}
        cv_emb_by_skill: Dict[str, EmbeddingRecord] = {}
        jd_emb_by_skill: Dict[str, EmbeddingRecord] = {}

        if stage3_response is not None:
            if isinstance(stage3_response, SemanticRepresentationResponse):
                cv_recs = stage3_response.cv_skill_embeddings
                jd_recs = stage3_response.jd_skill_embeddings
            else:
                cv_recs = [
                    EmbeddingRecord.model_validate(r)
                    for r in stage3_response.get("cv_skill_embeddings", [])
                ]
                jd_recs = [
                    EmbeddingRecord.model_validate(r)
                    for r in stage3_response.get("jd_skill_embeddings", [])
                ]

            for r in cv_recs:
                cv_emb_by_occ[r.occurrence_id] = r
                for sid in r.associated_skill_ids:
                    cv_emb_by_skill.setdefault(sid, r)
            for r in jd_recs:
                jd_emb_by_occ[r.occurrence_id] = r
                for sid in r.associated_skill_ids:
                    jd_emb_by_skill.setdefault(sid, r)

        cv_items: List[SkillInputItem] = []
        jd_items: List[SkillInputItem] = []
        lineage_records: List[CompetencyLineageRecord] = []

        if unified_response is not None:
            run_id = unified_response.run_id or "paper_run"
            if unified_response.cv:
                cv_doc_id = unified_response.cv.filename or f"cv_{run_id[:8]}"
                cv_hash = unified_response.cv.text_sha256
            if unified_response.jd:
                jd_doc_id = unified_response.jd.filename or f"jd_{run_id[:8]}"
                jd_hash = unified_response.jd.text_sha256

            cv_text = (
                getattr(unified_response.cv, "raw_text", None)
                or getattr(unified_response.cv, "clean_text", None)
            )
            jd_text = (
                getattr(unified_response.jd, "raw_text", None)
                or getattr(unified_response.jd, "clean_text", None)
            )

            cv_active = ExtractionDataAdapter.extract_active_skills(
                unified_response.cv, run_id=run_id
            ).active_skills
            jd_active = ExtractionDataAdapter.extract_active_skills(
                unified_response.jd, run_id=run_id
            ).active_skills

            for s in cv_active:
                ev_sents: List[str] = []
                ev_offsets: List[Dict[str, Optional[int]]] = []
                mod_text: Optional[str] = None
                raw_sk = s.raw_skill
                if raw_sk is not None and hasattr(raw_sk, "evidences") and raw_sk.evidences:
                    for ev in raw_sk.evidences:
                        sent = (ev.get("sentence") if isinstance(ev, dict) else getattr(ev, "sentence", None)) or (
                            ev.get("inferred_from_raw") if isinstance(ev, dict) else getattr(ev, "inferred_from_raw", None)
                        )
                        if sent and sent not in ev_sents:
                            ev_sents.append(sent)
                        st = ev.get("start") if isinstance(ev, dict) else getattr(ev, "start", None)
                        en = ev.get("end") if isinstance(ev, dict) else getattr(ev, "end", None)
                        if st is not None or en is not None:
                            ev_offsets.append({"start": st, "end": en})
                        m_txt = ev.get("modifier_text") if isinstance(ev, dict) else getattr(ev, "modifier_text", None)
                        if not mod_text and m_txt:
                            mod_text = m_txt

                canon_id = normalize_canonical_skill(s.skill_id or s.display_name)

                # Enforce implicit evidence eligibility before graph construction (Phase I2-A)
                if self.config.filter_unsupported_implicit and s.extraction_type == "implicit":
                    from matching_cv.app.services.implicit_evidence_verifier import ImplicitEvidenceVerifier
                    anchored_spans, is_eligible, _ = ImplicitEvidenceVerifier.verify_implicit_evidence_anchoring(
                        ev_sents, cv_text
                    )
                    if not is_eligible:
                        lineage_records.append(
                            CompetencyLineageRecord(
                                source_side="CV",
                                occurrence_id=s.occurrence_id,
                                canonical_id=canon_id,
                                surface_phrase=s.display_name,
                                kind=s.kind,
                                category=s.category,
                                evidence_text=ev_sents[0] if ev_sents else None,
                                original_granularity="implicit",
                                retention_decision="EXCLUDED",
                                reason_code="UNSUPPORTED_IMPLICIT_EVIDENCE",
                                decision_source="implicit_evidence_anchoring",
                                is_graph_node=False,
                                is_membership=False,
                            )
                        )
                        continue
                    else:
                        ev_sents = anchored_spans

                ev_joined = " ".join(ev_sents).strip()
                decision = evaluate_competency_retention(
                    label=s.display_name or s.skill_id,
                    kind=s.kind,
                    category=s.category,
                    evidence=ev_joined,
                    side="CV",
                )

                if self.config.filter_context_non_competencies and not decision.should_retain:
                    lineage_records.append(
                        CompetencyLineageRecord(
                            source_side="CV",
                            occurrence_id=s.occurrence_id,
                            canonical_id=canon_id,
                            surface_phrase=s.display_name,
                            kind=s.kind,
                            category=s.category,
                            evidence_text=ev_sents[0] if ev_sents else None,
                            original_granularity=decision.granularity,
                            retention_decision="EXCLUDED",
                            reason_code=decision.reason_code,
                            decision_source=decision.decision_source,
                            is_graph_node=False,
                            is_membership=False,
                        )
                    )
                    continue

                lineage_records.append(
                    CompetencyLineageRecord(
                        source_side="CV",
                        occurrence_id=s.occurrence_id,
                        canonical_id=canon_id,
                        surface_phrase=s.display_name,
                        kind=s.kind,
                        category=s.category,
                        evidence_text=ev_sents[0] if ev_sents else None,
                        original_granularity=decision.granularity,
                        retention_decision="RETAINED",
                        reason_code=decision.reason_code,
                        decision_source=decision.decision_source,
                        is_graph_node=False,
                        is_membership=True,
                    )
                )

                emb_rec = cv_emb_by_occ.get(s.occurrence_id) or cv_emb_by_skill.get(s.skill_id)
                vec = emb_rec.vector if (emb_rec and emb_rec.vector) else None
                vec_ref = emb_rec.vector_id if emb_rec else None

                cv_items.append(
                    SkillInputItem(
                        occurrence_id=s.occurrence_id,
                        canonical_skill_id=canon_id,
                        surface_name=s.display_name,
                        source_document="CV",
                        extraction_type=s.extraction_type,
                        category=s.category,
                        kind=s.kind or "skill",
                        evidence_sentences=ev_sents,
                        evidence_offsets=ev_offsets,
                        modifier_text=mod_text,
                        embedding_ref=vec_ref,
                        embedding_vector=vec,
                        metadata=dict(s.metadata or {}),
                    )
                )

            for s in jd_active:
                ev_sents = []
                ev_offsets = []
                mod_text = None
                raw_sk = s.raw_skill
                if raw_sk is not None and hasattr(raw_sk, "evidences") and raw_sk.evidences:
                    for ev in raw_sk.evidences:
                        sent = (ev.get("sentence") if isinstance(ev, dict) else getattr(ev, "sentence", None)) or (
                            ev.get("inferred_from_raw") if isinstance(ev, dict) else getattr(ev, "inferred_from_raw", None)
                        )
                        if sent and sent not in ev_sents:
                            ev_sents.append(sent)
                        st = ev.get("start") if isinstance(ev, dict) else getattr(ev, "start", None)
                        en = ev.get("end") if isinstance(ev, dict) else getattr(ev, "end", None)
                        if st is not None or en is not None:
                            ev_offsets.append({"start": st, "end": en})
                        m_txt = ev.get("modifier_text") if isinstance(ev, dict) else getattr(ev, "modifier_text", None)
                        if not mod_text and m_txt:
                            mod_text = m_txt

                canon_id = normalize_canonical_skill(s.skill_id or s.display_name)

                # Enforce implicit evidence eligibility before graph construction (Phase I2-A)
                if self.config.filter_unsupported_implicit and s.extraction_type == "implicit":
                    from matching_cv.app.services.implicit_evidence_verifier import ImplicitEvidenceVerifier
                    anchored_spans, is_eligible, _ = ImplicitEvidenceVerifier.verify_implicit_evidence_anchoring(
                        ev_sents, jd_text
                    )
                    if not is_eligible:
                        lineage_records.append(
                            CompetencyLineageRecord(
                                source_side="JD",
                                occurrence_id=s.occurrence_id,
                                canonical_id=canon_id,
                                surface_phrase=s.display_name,
                                kind=s.kind,
                                category=s.category,
                                evidence_text=ev_sents[0] if ev_sents else None,
                                original_granularity="implicit",
                                retention_decision="EXCLUDED",
                                reason_code="UNSUPPORTED_IMPLICIT_EVIDENCE",
                                decision_source="implicit_evidence_anchoring",
                                is_graph_node=False,
                                is_membership=False,
                            )
                        )
                        continue
                    else:
                        ev_sents = anchored_spans

                ev_joined = " ".join(ev_sents).strip()
                decision = evaluate_competency_retention(
                    label=s.display_name or s.skill_id,
                    kind=s.kind,
                    category=s.category,
                    evidence=ev_joined,
                    side="JD",
                )

                if self.config.filter_context_non_competencies and not decision.should_retain:
                    lineage_records.append(
                        CompetencyLineageRecord(
                            source_side="JD",
                            occurrence_id=s.occurrence_id,
                            canonical_id=canon_id,
                            surface_phrase=s.display_name,
                            kind=s.kind,
                            category=s.category,
                            evidence_text=ev_sents[0] if ev_sents else None,
                            original_granularity=decision.granularity,
                            retention_decision="EXCLUDED",
                            reason_code=decision.reason_code,
                            decision_source=decision.decision_source,
                            is_graph_node=False,
                            is_membership=False,
                        )
                    )
                    continue

                lineage_records.append(
                    CompetencyLineageRecord(
                        source_side="JD",
                        occurrence_id=s.occurrence_id,
                        canonical_id=canon_id,
                        surface_phrase=s.display_name,
                        kind=s.kind,
                        category=s.category,
                        evidence_text=ev_sents[0] if ev_sents else None,
                        original_granularity=decision.granularity,
                        retention_decision="RETAINED",
                        reason_code=decision.reason_code,
                        decision_source=decision.decision_source,
                        is_graph_node=False,
                        is_membership=True,
                    )
                )

                emb_rec = jd_emb_by_occ.get(s.occurrence_id) or jd_emb_by_skill.get(s.skill_id)
                vec = emb_rec.vector if (emb_rec and emb_rec.vector) else None
                vec_ref = emb_rec.vector_id if emb_rec else None

                jd_items.append(
                    SkillInputItem(
                        occurrence_id=s.occurrence_id,
                        canonical_skill_id=canon_id,
                        surface_name=s.display_name,
                        source_document="JD",
                        extraction_type=s.extraction_type,
                        category=s.category,
                        kind=s.kind or "skill",
                        evidence_sentences=ev_sents,
                        evidence_offsets=ev_offsets,
                        modifier_text=mod_text,
                        embedding_ref=vec_ref,
                        embedding_vector=vec,
                        metadata=dict(s.metadata or {}),
                    )
                )

        elif stage3_response is not None:
            # Adapt from Stage 3 records alone if unified_response is not supplied
            for r in cv_emb_by_occ.values():
                sid = r.associated_skill_ids[0] if r.associated_skill_ids else r.occurrence_id
                canon_id = normalize_canonical_skill(sid or r.source_text)
                decision = evaluate_competency_retention(
                    label=r.source_text,
                    side="CV",
                )
                if self.config.filter_context_non_competencies and not decision.should_retain:
                    lineage_records.append(
                        CompetencyLineageRecord(
                            source_side="CV",
                            occurrence_id=r.occurrence_id,
                            canonical_id=canon_id,
                            surface_phrase=r.source_text,
                            original_granularity=decision.granularity,
                            retention_decision="EXCLUDED",
                            reason_code=decision.reason_code,
                            decision_source=decision.decision_source,
                            is_graph_node=False,
                            is_membership=False,
                        )
                    )
                    continue

                lineage_records.append(
                    CompetencyLineageRecord(
                        source_side="CV",
                        occurrence_id=r.occurrence_id,
                        canonical_id=canon_id,
                        surface_phrase=r.source_text,
                        original_granularity=decision.granularity,
                        retention_decision="RETAINED",
                        reason_code=decision.reason_code,
                        decision_source=decision.decision_source,
                        is_graph_node=False,
                        is_membership=True,
                    )
                )
                cv_items.append(
                    SkillInputItem(
                        occurrence_id=r.occurrence_id,
                        canonical_skill_id=canon_id,
                        surface_name=r.source_text,
                        source_document="CV",
                        extraction_type=(r.extraction_type if r.extraction_type in ("explicit", "implicit") else "explicit"),
                        embedding_ref=r.vector_id,
                        embedding_vector=r.vector,
                        metadata=dict(r.metadata or {}),
                    )
                )
            for r in jd_emb_by_occ.values():
                sid = r.associated_skill_ids[0] if r.associated_skill_ids else r.occurrence_id
                canon_id = normalize_canonical_skill(sid or r.source_text)
                decision = evaluate_competency_retention(
                    label=r.source_text,
                    side="JD",
                )
                if self.config.filter_context_non_competencies and not decision.should_retain:
                    lineage_records.append(
                        CompetencyLineageRecord(
                            source_side="JD",
                            occurrence_id=r.occurrence_id,
                            canonical_id=canon_id,
                            surface_phrase=r.source_text,
                            original_granularity=decision.granularity,
                            retention_decision="EXCLUDED",
                            reason_code=decision.reason_code,
                            decision_source=decision.decision_source,
                            is_graph_node=False,
                            is_membership=False,
                        )
                    )
                    continue

                lineage_records.append(
                    CompetencyLineageRecord(
                        source_side="JD",
                        occurrence_id=r.occurrence_id,
                        canonical_id=canon_id,
                        surface_phrase=r.source_text,
                        original_granularity=decision.granularity,
                        retention_decision="RETAINED",
                        reason_code=decision.reason_code,
                        decision_source=decision.decision_source,
                        is_graph_node=False,
                        is_membership=True,
                    )
                )
                jd_items.append(
                    SkillInputItem(
                        occurrence_id=r.occurrence_id,
                        canonical_skill_id=canon_id,
                        surface_name=r.source_text,
                        source_document="JD",
                        extraction_type=(r.extraction_type if r.extraction_type in ("explicit", "implicit") else "explicit"),
                        embedding_ref=r.vector_id,
                        embedding_vector=r.vector,
                        metadata=dict(r.metadata or {}),
                    )
                )

        return cv_items, jd_items, cv_doc_id, jd_doc_id, cv_hash, jd_hash, lineage_records

    def build_graph_from_items(
        self,
        cv_items: List[SkillInputItem],
        jd_items: List[SkillInputItem],
        reasoning_results: Optional[List[SkillPairReasoningResult]] = None,
        pair_id: Optional[str] = None,
        run_id: str = "paper_aligned_run",
        cv_doc_id: str = "resume_doc",
        jd_doc_id: str = "job_doc",
        cv_hash: Optional[str] = None,
        jd_hash: Optional[str] = None,
        lineage_records: Optional[List[CompetencyLineageRecord]] = None,
    ) -> Tuple[PaperAlignedGraphData, PaperAlignedGraphIntegrityReport]:
        """
        Construct a validated paper-aligned bipartite graph from CV and JD SkillInputItems.
        """
        dim = self.config.embedding_dim

        # 1. Initialize Document Nodes ('resume_0' and 'job_0') with reproducible distinct seeds
        resume_seed = int(self.config.random_seed) * 2 + 1
        job_seed = int(self.config.random_seed) * 2 + 2

        resume_vec, resume_dec_cls = generate_reproducible_document_embedding(
            dim=dim,
            seed=resume_seed,
            strategy=self.config.doc_init_strategy,
        )
        job_vec, job_dec_cls = generate_reproducible_document_embedding(
            dim=dim,
            seed=job_seed,
            strategy=self.config.doc_init_strategy,
        )

        resume_node = PaperAlignedDocumentNode(
            node_id="resume_0",
            node_type="resume",
            document_id=cv_doc_id,
            source_hash=cv_hash,
            init_strategy=self.config.doc_init_strategy,
            random_seed=resume_seed,
            embedding_dim=dim,
            embedding_vector=resume_vec,
            decision_class=resume_dec_cls,
        )
        job_node = PaperAlignedDocumentNode(
            node_id="job_0",
            node_type="job",
            document_id=jd_doc_id,
            source_hash=jd_hash,
            init_strategy=self.config.doc_init_strategy,
            random_seed=job_seed,
            embedding_dim=dim,
            embedding_vector=job_vec,
            decision_class=job_dec_cls,
        )

        # Ensure every skill input item has a valid embedding vector of length `dim`
        # and filter out unsupported implicit skills if filter_unsupported_implicit is enabled
        prepared_cv: List[SkillInputItem] = []
        for item in cv_items:
            if self.config.filter_unsupported_implicit and item.extraction_type == "implicit" and not item.evidence_sentences:
                continue
            cloned = item.model_copy(deep=True)
            canon = normalize_canonical_skill(cloned.canonical_skill_id or cloned.surface_name)
            cloned.canonical_skill_id = canon or cloned.canonical_skill_id
            if not cloned.embedding_vector:
                cloned.embedding_vector = generate_deterministic_fallback_skill_embedding(
                    cloned.canonical_skill_id, dim
                )
            prepared_cv.append(cloned)

        prepared_jd: List[SkillInputItem] = []
        for item in jd_items:
            if self.config.filter_unsupported_implicit and item.extraction_type == "implicit" and not item.evidence_sentences:
                continue
            cloned = item.model_copy(deep=True)
            canon = normalize_canonical_skill(cloned.canonical_skill_id or cloned.surface_name)
            cloned.canonical_skill_id = canon or cloned.canonical_skill_id
            if not cloned.embedding_vector:
                cloned.embedding_vector = generate_deterministic_fallback_skill_embedding(
                    cloned.canonical_skill_id, dim
                )
            prepared_jd.append(cloned)

        # 1B. Policy B Semantic Requirement Alignment Transformation (if enabled)
        semantic_transform_audit = None
        if getattr(self.config, "graph_policy", "policy_a_legacy") == "policy_b_semantic":
            from matching_cv.research.paper_aligned_gnn.semantic_alignment import SemanticGraphTransformer
            transformer = SemanticGraphTransformer()
            prepared_cv, prepared_jd, semantic_transform_audit = transformer.transform_policy_b(
                cv_items=prepared_cv,
                jd_items=prepared_jd,
            )
            # Ensure any newly created decomposed items have embeddings
            for item in prepared_jd:
                if not item.embedding_vector:
                    item.embedding_vector = generate_deterministic_fallback_skill_embedding(
                        item.canonical_skill_id, dim
                    )
            for item in prepared_cv:
                if not item.embedding_vector:
                    item.embedding_vector = generate_deterministic_fallback_skill_embedding(
                        item.canonical_skill_id, dim
                    )

        # 2. Match & Merge Shared Skills vs Unique CV/JD Skills
        shared_pairs, unique_cv, unique_jd, all_audit = match_and_merge_skills(
            cv_items=prepared_cv,
            jd_items=prepared_jd,
            merge_policy=self.config.merge_policy,
            paper_cosine_threshold=self.config.paper_cosine_threshold,
            enforce_confusable_guardrails_in_cosine_mode=self.config.enforce_confusable_guardrails_in_cosine_mode,
            reasoning_results=reasoning_results,
        )

        skill_nodes: Dict[str, PaperAlignedSkillNode] = {}
        edges: List[PaperAlignedBipartiteEdge] = []

        # Sort shared, unique_cv, unique_jd deterministically
        shared_pairs.sort(key=lambda x: (x[0].canonical_skill_id, x[1].canonical_skill_id))
        unique_cv.sort(key=lambda x: x[0].canonical_skill_id)
        unique_jd.sort(key=lambda x: x[0].canonical_skill_id)

        # 3A. Build Shared Skill Nodes & Bipartite Edges to BOTH 'resume_0' and 'job_0'
        for idx, (cv_sk, jd_sk, audit_rec) in enumerate(shared_pairs):
            primary_canon = cv_sk.canonical_skill_id or jd_sk.canonical_skill_id
            node_id = f"skill_shared_{idx:03d}_{primary_canon}"

            cv_surfaces = cv_sk.metadata.get("all_surface_names", [cv_sk.surface_name])
            jd_surfaces = jd_sk.metadata.get("all_surface_names", [jd_sk.surface_name])
            combined_surfaces = list(dict.fromkeys(cv_surfaces + jd_surfaces))

            cv_occs = cv_sk.metadata.get("all_occurrence_ids", [cv_sk.occurrence_id])
            jd_occs = jd_sk.metadata.get("all_occurrence_ids", [jd_sk.occurrence_id])

            emb_refs = [r for r in [cv_sk.embedding_ref, jd_sk.embedding_ref] if r]
            combined_vec, comb_mode = combine_shared_embeddings(
                cv_sk.embedding_vector or [0.0] * dim,
                jd_sk.embedding_vector or [0.0] * dim,
            )

            skill_nodes[node_id] = PaperAlignedSkillNode(
                node_id=node_id,
                canonical_skill_id=primary_canon,
                cv_canonical_id=cv_sk.canonical_skill_id,
                jd_canonical_id=jd_sk.canonical_skill_id,
                surface_names=combined_surfaces,
                cv_surface_names=cv_surfaces,
                jd_surface_names=jd_surfaces,
                source_documents=["CV", "JD"],
                membership="shared",
                cv_occurrence_ids=cv_occs,
                jd_occurrence_ids=jd_occs,
                cv_extraction_type=cv_sk.extraction_type,
                jd_extraction_type=jd_sk.extraction_type,
                cv_evidences=cv_sk.evidence_sentences,
                jd_evidences=jd_sk.evidence_sentences,
                cv_evidence_offsets=cv_sk.evidence_offsets,
                jd_evidence_offsets=jd_sk.evidence_offsets,
                embedding_refs=emb_refs,
                embedding_dim=len(combined_vec),
                embedding_vector=combined_vec,
                embedding_combination=comb_mode,
                cosine_similarity_if_shared=audit_rec.cosine_similarity,
                merge_decision=audit_rec,
            )

            # Extract separate CV demonstrated proficiency and JD required proficiency
            cv_prof = extract_skill_proficiency(
                cv_sk, allow_paper_table6_7_descriptors=self.config.allow_paper_table6_7_descriptors
            )
            jd_prof = extract_skill_proficiency(
                jd_sk, allow_paper_table6_7_descriptors=self.config.allow_paper_table6_7_descriptors
            )

            w_cv = compute_tensor_edge_weight(
                cv_prof,
                normalization=self.config.edge_weight_normalization,
                missing_tensor_weight=self.config.missing_proficiency_tensor_weight,
            )
            w_jd = compute_tensor_edge_weight(
                jd_prof,
                normalization=self.config.edge_weight_normalization,
                missing_tensor_weight=self.config.missing_proficiency_tensor_weight,
            )

            # Resume -> Shared Skill ('has_skill') and reverse ('in_resume')
            edges.append(
                PaperAlignedBipartiteEdge(
                    edge_id=f"resume_0__has_skill__{node_id}",
                    source_type="resume",
                    edge_type="has_skill",
                    target_type="skill",
                    source_id="resume_0",
                    target_id=node_id,
                    is_reverse_edge=False,
                    proficiency=cv_prof,
                    tensor_weight=w_cv,
                )
            )
            if self.config.include_reverse_edges:
                edges.append(
                    PaperAlignedBipartiteEdge(
                        edge_id=f"{node_id}__in_resume__resume_0",
                        source_type="skill",
                        edge_type="in_resume",
                        target_type="resume",
                        source_id=node_id,
                        target_id="resume_0",
                        is_reverse_edge=True,
                        proficiency=cv_prof,
                        tensor_weight=w_cv,
                    )
                )

            # Job -> Shared Skill ('requires_skill') and reverse ('required_by_job')
            edges.append(
                PaperAlignedBipartiteEdge(
                    edge_id=f"job_0__requires_skill__{node_id}",
                    source_type="job",
                    edge_type="requires_skill",
                    target_type="skill",
                    source_id="job_0",
                    target_id=node_id,
                    is_reverse_edge=False,
                    proficiency=jd_prof,
                    tensor_weight=w_jd,
                )
            )
            if self.config.include_reverse_edges:
                edges.append(
                    PaperAlignedBipartiteEdge(
                        edge_id=f"{node_id}__required_by_job__job_0",
                        source_type="skill",
                        edge_type="required_by_job",
                        target_type="job",
                        source_id=node_id,
                        target_id="job_0",
                        is_reverse_edge=True,
                        proficiency=jd_prof,
                        tensor_weight=w_jd,
                    )
                )

        # 3B. Build CV-Unique Skill Nodes & Edges ONLY to 'resume_0'
        for idx, (cv_sk, audit_rec) in enumerate(unique_cv):
            node_id = f"skill_cv_{idx:03d}_{cv_sk.canonical_skill_id}"
            cv_surfaces = cv_sk.metadata.get("all_surface_names", [cv_sk.surface_name])
            cv_occs = cv_sk.metadata.get("all_occurrence_ids", [cv_sk.occurrence_id])
            vec = cv_sk.embedding_vector or [0.0] * dim

            skill_nodes[node_id] = PaperAlignedSkillNode(
                node_id=node_id,
                canonical_skill_id=cv_sk.canonical_skill_id,
                cv_canonical_id=cv_sk.canonical_skill_id,
                jd_canonical_id=None,
                surface_names=cv_surfaces,
                cv_surface_names=cv_surfaces,
                jd_surface_names=[],
                source_documents=["CV"],
                membership="resume_only",
                cv_occurrence_ids=cv_occs,
                jd_occurrence_ids=[],
                cv_extraction_type=cv_sk.extraction_type,
                jd_extraction_type=None,
                cv_evidences=cv_sk.evidence_sentences,
                jd_evidences=[],
                cv_evidence_offsets=cv_sk.evidence_offsets,
                jd_evidence_offsets=[],
                embedding_refs=[cv_sk.embedding_ref] if cv_sk.embedding_ref else [],
                embedding_dim=len(vec),
                embedding_vector=vec,
                embedding_combination="single_source",
                cosine_similarity_if_shared=None,
                merge_decision=audit_rec,
            )

            cv_prof = extract_skill_proficiency(
                cv_sk, allow_paper_table6_7_descriptors=self.config.allow_paper_table6_7_descriptors
            )
            w_cv = compute_tensor_edge_weight(
                cv_prof,
                normalization=self.config.edge_weight_normalization,
                missing_tensor_weight=self.config.missing_proficiency_tensor_weight,
            )

            edges.append(
                PaperAlignedBipartiteEdge(
                    edge_id=f"resume_0__has_skill__{node_id}",
                    source_type="resume",
                    edge_type="has_skill",
                    target_type="skill",
                    source_id="resume_0",
                    target_id=node_id,
                    is_reverse_edge=False,
                    proficiency=cv_prof,
                    tensor_weight=w_cv,
                )
            )
            if self.config.include_reverse_edges:
                edges.append(
                    PaperAlignedBipartiteEdge(
                        edge_id=f"{node_id}__in_resume__resume_0",
                        source_type="skill",
                        edge_type="in_resume",
                        target_type="resume",
                        source_id=node_id,
                        target_id="resume_0",
                        is_reverse_edge=True,
                        proficiency=cv_prof,
                        tensor_weight=w_cv,
                    )
                )

        # 3C. Build JD-Unique Skill Nodes & Edges ONLY to 'job_0'
        for idx, (jd_sk, audit_rec) in enumerate(unique_jd):
            node_id = f"skill_jd_{idx:03d}_{jd_sk.canonical_skill_id}"
            jd_surfaces = jd_sk.metadata.get("all_surface_names", [jd_sk.surface_name])
            jd_occs = jd_sk.metadata.get("all_occurrence_ids", [jd_sk.occurrence_id])
            vec = jd_sk.embedding_vector or [0.0] * dim

            skill_nodes[node_id] = PaperAlignedSkillNode(
                node_id=node_id,
                canonical_skill_id=jd_sk.canonical_skill_id,
                cv_canonical_id=None,
                jd_canonical_id=jd_sk.canonical_skill_id,
                surface_names=jd_surfaces,
                cv_surface_names=[],
                jd_surface_names=jd_surfaces,
                source_documents=["JD"],
                membership="job_only",
                cv_occurrence_ids=[],
                jd_occurrence_ids=jd_occs,
                cv_extraction_type=None,
                jd_extraction_type=jd_sk.extraction_type,
                cv_evidences=[],
                jd_evidences=jd_sk.evidence_sentences,
                cv_evidence_offsets=[],
                jd_evidence_offsets=jd_sk.evidence_offsets,
                embedding_refs=[jd_sk.embedding_ref] if jd_sk.embedding_ref else [],
                embedding_dim=len(vec),
                embedding_vector=vec,
                embedding_combination="single_source",
                cosine_similarity_if_shared=None,
                merge_decision=audit_rec,
            )

            jd_prof = extract_skill_proficiency(
                jd_sk, allow_paper_table6_7_descriptors=self.config.allow_paper_table6_7_descriptors
            )
            w_jd = compute_tensor_edge_weight(
                jd_prof,
                normalization=self.config.edge_weight_normalization,
                missing_tensor_weight=self.config.missing_proficiency_tensor_weight,
            )

            edges.append(
                PaperAlignedBipartiteEdge(
                    edge_id=f"job_0__requires_skill__{node_id}",
                    source_type="job",
                    edge_type="requires_skill",
                    target_type="skill",
                    source_id="job_0",
                    target_id=node_id,
                    is_reverse_edge=False,
                    proficiency=jd_prof,
                    tensor_weight=w_jd,
                )
            )
            if self.config.include_reverse_edges:
                edges.append(
                    PaperAlignedBipartiteEdge(
                        edge_id=f"{node_id}__required_by_job__job_0",
                        source_type="skill",
                        edge_type="required_by_job",
                        target_type="job",
                        source_id=node_id,
                        target_id="job_0",
                        is_reverse_edge=True,
                        proficiency=jd_prof,
                        tensor_weight=w_jd,
                    )
                )

        # Deterministic ordering of skill_nodes and edges
        skill_nodes = dict(sorted(skill_nodes.items(), key=lambda x: x[0]))
        edges.sort(
            key=lambda e: (e.source_type, e.edge_type, e.target_type, e.source_id, e.target_id)
        )

        graph_id_str = f"paper_graph_{self.config.merge_policy}_{pair_id or run_id[:8]}"

        # Compile Stage 4 reasoning audit & representation limitations
        non_equiv_relations = []
        rejected_or_uncertain_relations = []
        verified_equiv_relations = []
        if reasoning_results:
            for r in reasoning_results:
                rec_summary = {
                    "skill_a": r.skill_a.skill_id or r.skill_a.name,
                    "skill_b": r.skill_b.skill_id or r.skill_b.name,
                    "identity": r.identity,
                    "relationship": r.relationship,
                    "graph_relation_status": r.graph_relation_status,
                }
                if (
                    r.identity == "equivalent"
                    and r.graph_relation_status == "eligible"
                    and not r.contradiction_detected
                ):
                    verified_equiv_relations.append(rec_summary)
                elif (
                    r.identity == "uncertain"
                    or r.relationship == "uncertain"
                    or r.graph_relation_status in ("rejected", "candidate_only")
                    or r.contradiction_detected
                ):
                    rejected_or_uncertain_relations.append(rec_summary)
                else:
                    non_equiv_relations.append(rec_summary)

        cv_missing_prof = sum(
            1 for e in edges if not e.is_reverse_edge and e.source_type == "resume" and e.proficiency.is_missing
        )
        jd_missing_prof = sum(
            1 for e in edges if not e.is_reverse_edge and e.source_type == "job" and e.proficiency.is_missing
        )

        effective_lineage = list(lineage_records) if lineage_records is not None else []
        canonical_to_node = {node.canonical_skill_id: node for node in skill_nodes.values()}
        for rec in effective_lineage:
            if rec.retention_decision == "RETAINED" and rec.canonical_id in canonical_to_node:
                rec.is_graph_node = True

        retained_recs = [r for r in effective_lineage if r.retention_decision == "RETAINED"]
        excluded_recs = [r for r in effective_lineage if r.retention_decision == "EXCLUDED"]
        retained_by_reason: Dict[str, int] = {}
        for r in retained_recs:
            retained_by_reason[r.reason_code] = retained_by_reason.get(r.reason_code, 0) + 1
        excluded_by_reason: Dict[str, int] = {}
        for r in excluded_recs:
            excluded_by_reason[r.reason_code] = excluded_by_reason.get(r.reason_code, 0) + 1

        lineage_summary = {
            "total_input_records": len(effective_lineage),
            "retained_records": len(retained_recs),
            "excluded_records": len(excluded_recs),
            "cv_input_count": sum(1 for r in effective_lineage if r.source_side == "CV"),
            "cv_retained_count": sum(1 for r in retained_recs if r.source_side == "CV"),
            "cv_excluded_count": sum(1 for r in excluded_recs if r.source_side == "CV"),
            "jd_input_count": sum(1 for r in effective_lineage if r.source_side == "JD"),
            "jd_retained_count": sum(1 for r in retained_recs if r.source_side == "JD"),
            "jd_excluded_count": sum(1 for r in excluded_recs if r.source_side == "JD"),
            "retained_by_reason": retained_by_reason,
            "excluded_by_reason": excluded_by_reason,
        }

        graph_data = PaperAlignedGraphData(
            graph_id=graph_id_str,
            pair_id=pair_id,
            run_id=run_id,
            merge_policy=self.config.merge_policy,
            graph_policy=getattr(self.config, "graph_policy", "policy_a_legacy"),
            edge_weight_normalization=self.config.edge_weight_normalization,
            missing_proficiency_tensor_weight=self.config.missing_proficiency_tensor_weight,
            embedding_dim=dim,
            resume_node=resume_node,
            job_node=job_node,
            skill_nodes=skill_nodes,
            education_nodes={},
            experience_nodes={},
            edges=edges,
            merge_audit=all_audit,
            diagnostics={
                "architecture": "PaperAlignedBipartiteGraph",
                "entity_scope": "skill_only_adaptation",
                "entity_scope_classification": "PROJECT_ADAPTATION",
                "embedding_source_classification": "PROJECT_ADAPTATION",
                "doc_init_strategy": self.config.doc_init_strategy,
                "random_seed": self.config.random_seed,
                "merge_policy": self.config.merge_policy,
                "graph_policy": getattr(self.config, "graph_policy", "policy_a_legacy"),
                "semantic_transform_audit": semantic_transform_audit,
                "paper_cosine_threshold": self.config.paper_cosine_threshold,
                "edge_weight_normalization": self.config.edge_weight_normalization,
                "missing_proficiency_tensor_weight": self.config.missing_proficiency_tensor_weight,
                "shared_skills_count": len(shared_pairs),
                "shared_skill_count": len(shared_pairs),
                "resume_only_skills_count": len(unique_cv),
                "resume_only_skill_count": len(unique_cv),
                "job_only_skills_count": len(unique_jd),
                "job_only_skill_count": len(unique_jd),
                "total_skill_nodes": len(skill_nodes),
                "cv_edges_missing_proficiency": cv_missing_prof,
                "missing_resume_proficiency_edges": cv_missing_prof,
                "jd_edges_missing_proficiency": jd_missing_prof,
                "missing_job_proficiency_edges": jd_missing_prof,
                "competency_lineage": [r.model_dump() for r in effective_lineage],
                "competency_lineage_summary": lineage_summary,
                "stage4_reasoning_audit": {
                    "enabled": reasoning_results is not None,
                    "total_pairs_received": len(reasoning_results) if reasoning_results else 0,
                    "verified_equivalent_eligible_count": len(verified_equiv_relations),
                    "preserved_non_equivalent_relations_count": len(non_equiv_relations),
                    "preserved_non_equivalent_count": len(non_equiv_relations),
                    "preserved_rejected_or_uncertain_count": len(rejected_or_uncertain_relations),
                    "preserved_non_equivalent_relations": non_equiv_relations,
                    "preserved_rejected_or_uncertain_pairs": rejected_or_uncertain_relations,
                },
                "representation_limitations": {
                    "omitted_entity_types": ["education", "experience"],
                    "omitted_entity_reason": (
                        "Upstream Stage 2 skill extractor only extracts skill competencies (Rule 10); "
                        "no synthetic education or experience nodes are fabricated."
                    ),
                    "standalone_evidence_and_requirement_nodes": (
                        "Represented as provenance metadata (cv_evidences, jd_evidences, evidence_offsets) "
                        "on skill entity nodes rather than separate graph node types, preserving the "
                        "paper's document-entity bipartite topology."
                    ),
                    "non_equivalent_skill_skill_edges": (
                        "Omitted from bipartite graph topology per Baghbanzadeh & Wu (2025) Section 3.4; "
                        "non-equivalent LLM relations are preserved in diagnostics.stage4_reasoning_audit."
                    ),
                },
            },
        )

        report = self.validate_graph_integrity(graph_data)
        graph_data.integrity_report = report
        return graph_data, report

    def build_graph(
        self,
        unified_response: Optional[Any] = None,
        stage3_response: Optional[Union[SemanticRepresentationResponse, Dict[str, Any]]] = None,
        reasoning_results: Optional[List[SkillPairReasoningResult]] = None,
        pair_id: Optional[str] = None,
    ) -> Tuple[PaperAlignedGraphData, PaperAlignedGraphIntegrityReport]:
        """
        Build paper-aligned graph directly from Stage 2 / Stage 3 / Stage 4 pipeline outputs
        or from a `GraphBuildRequest` instance.
        """
        from matching_cv.app.schemas.hetero_graph import GraphBuildRequest

        req_mode: Optional[str] = None
        if isinstance(unified_response, GraphBuildRequest):
            req = unified_response
            unified_response = req.unified_response
            stage3_response = req.stage3_response
            req_mode = req.graph_mode
            if req.reasoning_results:
                reasoning_results = req.reasoning_results
            elif req.reasoning_recording is not None:
                if isinstance(req.reasoning_recording, dict):
                    reasoning_results = [
                        SkillPairReasoningResult.model_validate(r)
                        for r in req.reasoning_recording.get("results", [])
                    ]
                else:
                    reasoning_results = req.reasoning_recording.results
            elif req.reasoning_response is not None:
                if isinstance(req.reasoning_response, dict):
                    reasoning_results = [
                        SkillPairReasoningResult.model_validate(r)
                        for r in req.reasoning_response.get("results", [])
                    ]
                else:
                    reasoning_results = req.reasoning_response.results

        cv_items, jd_items, cv_doc_id, jd_doc_id, cv_hash, jd_hash, lineage_records = (
            self.adapt_pipeline_inputs_with_lineage(
                unified_response=unified_response,
                stage3_response=stage3_response,
            )
        )
        run_id = (
            unified_response.run_id
            if (unified_response and getattr(unified_response, "run_id", None))
            else (
                stage3_response.run_id
                if isinstance(stage3_response, SemanticRepresentationResponse)
                else "paper_aligned_run"
            )
        )
        graph_data, report = self.build_graph_from_items(
            cv_items=cv_items,
            jd_items=jd_items,
            reasoning_results=reasoning_results,
            pair_id=pair_id,
            run_id=run_id,
            cv_doc_id=cv_doc_id,
            jd_doc_id=jd_doc_id,
            cv_hash=cv_hash,
            jd_hash=jd_hash,
            lineage_records=lineage_records,
        )
        if req_mode:
            graph_data.diagnostics["requested_graph_mode"] = req_mode
        return graph_data, report

    def validate_graph_integrity(
        self, graph_data: PaperAlignedGraphData
    ) -> PaperAlignedGraphIntegrityReport:
        """
        Validate all 12 mandatory graph integrity invariants specified in Section 4.6:
        1. Exactly one Resume document node and one Job document node.
        2. No unintended document-document or skill-skill edges in the paper-aligned baseline.
        3. Every entity belongs to at least one document.
        4. Shared entities connect to both document nodes.
        5. Unique entities connect to their respective document node only.
        6. Every proficiency weight has a valid source or is explicitly missing.
        7. No NaN/Inf node features.
        8. Correct feature shapes.
        9. Correct edge indices and directions.
        10. Correct treatment of reverse edges if needed for message passing.
        11. No accidental merge of different confusable skill identities (under verified policy).
        12. Deterministic ordering.
        """
        errors: List[str] = []
        warnings: List[str] = []
        expected_dim = graph_data.embedding_dim

        # Check 1: Exactly one Resume node and one Job node
        c1_one_resume_one_job = (
            graph_data.resume_node is not None
            and graph_data.resume_node.node_type == "resume"
            and graph_data.resume_node.node_id == "resume_0"
            and graph_data.job_node is not None
            and graph_data.job_node.node_type == "job"
            and graph_data.job_node.node_id == "job_0"
        )
        if not c1_one_resume_one_job:
            errors.append("Graph must have exactly one Resume node ('resume_0') and one Job node ('job_0').")

        # Check 2: No doc-doc or skill-skill edges
        c2_no_forbidden_edges = True
        for e in graph_data.edges:
            if e.source_type == "skill" and e.target_type == "skill":
                c2_no_forbidden_edges = False
                errors.append(f"Forbidden skill-to-skill edge detected: {e.edge_id}")
            if e.source_type in ("resume", "job") and e.target_type in ("resume", "job"):
                c2_no_forbidden_edges = False
                errors.append(f"Forbidden document-to-document edge detected: {e.edge_id}")

        # Track document connections per skill node
        resume_connected_skills: Set[str] = set()
        job_connected_skills: Set[str] = set()
        forward_edges_map: Dict[Tuple[str, str, str], PaperAlignedBipartiteEdge] = {}
        reverse_edges_map: Dict[Tuple[str, str, str], PaperAlignedBipartiteEdge] = {}

        c9_directions_ok = True
        for e in graph_data.edges:
            if not e.is_reverse_edge:
                if e.edge_type == "has_skill":
                    if e.source_type != "resume" or e.target_type != "skill" or e.source_id != "resume_0":
                        c9_directions_ok = False
                        errors.append(f"Invalid has_skill edge endpoints: {e.edge_id}")
                    if e.target_id not in graph_data.skill_nodes:
                        c9_directions_ok = False
                        errors.append(f"has_skill target missing from skill_nodes: {e.target_id}")
                    resume_connected_skills.add(e.target_id)
                    forward_edges_map[("resume", "has_skill", e.target_id)] = e
                elif e.edge_type == "requires_skill":
                    if e.source_type != "job" or e.target_type != "skill" or e.source_id != "job_0":
                        c9_directions_ok = False
                        errors.append(f"Invalid requires_skill edge endpoints: {e.edge_id}")
                    if e.target_id not in graph_data.skill_nodes:
                        c9_directions_ok = False
                        errors.append(f"requires_skill target missing from skill_nodes: {e.target_id}")
                    job_connected_skills.add(e.target_id)
                    forward_edges_map[("job", "requires_skill", e.target_id)] = e
                else:
                    c9_directions_ok = False
                    errors.append(f"Unexpected forward edge_type: {e.edge_type}")
            else:
                if e.edge_type == "in_resume":
                    if e.source_type != "skill" or e.target_type != "resume" or e.target_id != "resume_0":
                        c9_directions_ok = False
                        errors.append(f"Invalid reverse in_resume edge endpoints: {e.edge_id}")
                    reverse_edges_map[(e.source_id, "in_resume", "resume")] = e
                elif e.edge_type == "required_by_job":
                    if e.source_type != "skill" or e.target_type != "job" or e.target_id != "job_0":
                        c9_directions_ok = False
                        errors.append(f"Invalid reverse required_by_job edge endpoints: {e.edge_id}")
                    reverse_edges_map[(e.source_id, "required_by_job", "job")] = e
                else:
                    c9_directions_ok = False
                    errors.append(f"Unexpected reverse edge_type: {e.edge_type}")

        # Check 3, 4, 5: Entity membership and document connectivity
        c3_all_entities_connected = True
        c4_shared_connect_both = True
        c5_unique_connect_single = True

        for sid, snode in graph_data.skill_nodes.items():
            in_cv = sid in resume_connected_skills
            in_jd = sid in job_connected_skills
            if not (in_cv or in_jd):
                c3_all_entities_connected = False
                errors.append(f"Orphan skill node {sid} is not connected to either resume or job.")

            if snode.membership == "shared":
                if not (in_cv and in_jd):
                    c4_shared_connect_both = False
                    errors.append(
                        f"Shared skill node {sid} must connect to both resume and job (in_cv={in_cv}, in_jd={in_jd})."
                    )
            elif snode.membership == "resume_only":
                if not (in_cv and not in_jd):
                    c5_unique_connect_single = False
                    errors.append(
                        f"Resume-only skill node {sid} must connect ONLY to resume (in_cv={in_cv}, in_jd={in_jd})."
                    )
            elif snode.membership == "job_only":
                if not (in_jd and not in_cv):
                    c5_unique_connect_single = False
                    errors.append(
                        f"Job-only skill node {sid} must connect ONLY to job (in_cv={in_cv}, in_jd={in_jd})."
                    )

        # Check 6: Proficiency weights valid source or explicitly missing
        c6_valid_proficiency = True
        valid_table3_vals = {v[0] for v in PAPER_TABLE3_EXPLICIT_MAPPING.values()}
        valid_supp_vals = {v[0] for v in PAPER_TABLE6_7_SUPPLEMENTAL_MAPPING.values()}

        for e in graph_data.edges:
            prof = e.proficiency
            if prof.is_missing:
                if prof.numeric_level is not None or prof.mapping_source != "missing":
                    c6_valid_proficiency = False
                    errors.append(
                        f"Edge {e.edge_id} marked is_missing=True but has numeric_level={prof.numeric_level}, mapping_source={prof.mapping_source}"
                    )
            else:
                if prof.numeric_level is None or not prof.raw_descriptor:
                    c6_valid_proficiency = False
                    errors.append(f"Edge {e.edge_id} marked is_missing=False but missing numeric_level or raw_descriptor")
                elif prof.mapping_source == "paper_table3_explicit" and prof.numeric_level not in valid_table3_vals:
                    c6_valid_proficiency = False
                    errors.append(f"Edge {e.edge_id} has invalid Table 3 level: {prof.numeric_level}")
                elif prof.mapping_source == "paper_table6_7_assumption" and prof.numeric_level not in valid_supp_vals:
                    c6_valid_proficiency = False
                    errors.append(f"Edge {e.edge_id} has invalid Table 6/7 level: {prof.numeric_level}")

        # Check 7 & 8: No NaN/Inf and correct feature shapes
        c7_no_nan_inf = True
        c8_shapes_ok = True

        all_vecs: List[Tuple[str, List[float]]] = [
            ("resume_0", graph_data.resume_node.embedding_vector),
            ("job_0", graph_data.job_node.embedding_vector),
        ]
        for sid, snode in graph_data.skill_nodes.items():
            all_vecs.append((sid, snode.embedding_vector))

        for nid, vec in all_vecs:
            if len(vec) != expected_dim:
                c8_shapes_ok = False
                errors.append(f"Node {nid} embedding dimension mismatch: {len(vec)} != {expected_dim}")
            for val in vec:
                if math.isnan(val) or math.isinf(val):
                    c7_no_nan_inf = False
                    errors.append(f"Node {nid} contains NaN or Inf in embedding vector")
                    break

        # Check 10: Reverse edges consistency
        c10_reverse_ok = True
        if self.config.include_reverse_edges:
            if len(reverse_edges_map) != len(forward_edges_map):
                c10_reverse_ok = False
                errors.append(
                    f"Reverse edge count ({len(reverse_edges_map)}) != forward edge count ({len(forward_edges_map)})"
                )
            for (src_t, rel, sk_id), fwd_e in forward_edges_map.items():
                rev_key = (sk_id, "in_resume" if src_t == "resume" else "required_by_job", src_t)
                if rev_key not in reverse_edges_map:
                    c10_reverse_ok = False
                    errors.append(f"Missing reverse edge for {fwd_e.edge_id}")
                else:
                    rev_e = reverse_edges_map[rev_key]
                    if abs(rev_e.tensor_weight - fwd_e.tensor_weight) > 1e-6:
                        c10_reverse_ok = False
                        errors.append(f"Reverse edge weight mismatch on {rev_e.edge_id}")

        # Check 11: No accidental merge of confusable distinct skill identities
        c11_no_confusable_merges = True
        for sid, snode in graph_data.skill_nodes.items():
            if snode.membership == "shared" and snode.cv_canonical_id and snode.jd_canonical_id:
                if are_confusable_distinct_skills(snode.cv_canonical_id, snode.jd_canonical_id):
                    if graph_data.merge_policy != "paper_cosine_08" or self.config.enforce_confusable_guardrails_in_cosine_mode:
                        c11_no_confusable_merges = False
                        errors.append(
                            f"Accidental merge of confusable distinct skills on {sid}: '{snode.cv_canonical_id}' vs '{snode.jd_canonical_id}'"
                        )
                    else:
                        warnings.append(
                            f"Paper cosine > 0.8 mode merged confusable distinct skills on {sid}: '{snode.cv_canonical_id}' vs '{snode.jd_canonical_id}'"
                        )

        edge_counts: Dict[str, int] = {}
        for e in graph_data.edges:
            k = f"{e.source_type}__{e.edge_type}__{e.target_type}"
            edge_counts[k] = edge_counts.get(k, 0) + 1
        edge_counts["total"] = len(graph_data.edges)

        shared_cnt = sum(1 for s in graph_data.skill_nodes.values() if s.membership == "shared")
        cv_only_cnt = sum(1 for s in graph_data.skill_nodes.values() if s.membership == "resume_only")
        jd_only_cnt = sum(1 for s in graph_data.skill_nodes.values() if s.membership == "job_only")

        node_counts = {
            "resume": 1,
            "job": 1,
            "skill": len(graph_data.skill_nodes),
            "education": len(graph_data.education_nodes),
            "experience": len(graph_data.experience_nodes),
            "total": 2 + len(graph_data.skill_nodes) + len(graph_data.education_nodes) + len(graph_data.experience_nodes),
        }

        return PaperAlignedGraphIntegrityReport(
            is_valid=len(errors) == 0,
            exactly_one_resume_and_one_job=c1_one_resume_one_job,
            no_unintended_doc_doc_or_skill_skill_edges=c2_no_forbidden_edges,
            every_entity_belongs_to_at_least_one_doc=c3_all_entities_connected,
            shared_entities_connect_to_both_docs=c4_shared_connect_both,
            unique_entities_connect_to_single_doc=c5_unique_connect_single,
            valid_proficiency_or_explicitly_missing=c6_valid_proficiency,
            no_nan_or_inf_features=c7_no_nan_inf,
            correct_feature_shapes=c8_shapes_ok,
            correct_edge_indices_and_directions=c9_directions_ok,
            correct_reverse_edges=c10_reverse_ok,
            no_accidental_confusable_merges=c11_no_confusable_merges,
            node_counts=node_counts,
            edge_counts=edge_counts,
            shared_skill_count=shared_cnt,
            resume_only_skill_count=cv_only_cnt,
            job_only_skill_count=jd_only_cnt,
            errors=errors,
            warnings=warnings,
        )

    def export_to_pyg(
        self, graph_data: PaperAlignedGraphData
    ) -> Tuple[HeteroData, Dict[str, Dict[str, int]], Dict[str, Any]]:
        """
        Export PaperAlignedGraphData to PyTorch Geometric HeteroData.
        Preserves exact document-entity bipartite structure and proficiency edge tensors.
        """
        pyg = HeteroData()
        dim = graph_data.embedding_dim

        # 1. Document Nodes: 'resume' (index 0) and 'job' (index 0)
        pyg["resume"].x = torch.tensor([graph_data.resume_node.embedding_vector], dtype=torch.float32)
        pyg["resume"].num_nodes = 1
        pyg["resume"].node_ids = [graph_data.resume_node.node_id]

        pyg["job"].x = torch.tensor([graph_data.job_node.embedding_vector], dtype=torch.float32)
        pyg["job"].num_nodes = 1
        pyg["job"].node_ids = [graph_data.job_node.node_id]

        # 2. Skill Entity Nodes
        sorted_skill_ids = list(sorted(graph_data.skill_nodes.keys()))
        skill_id_to_idx = {sid: idx for idx, sid in enumerate(sorted_skill_ids)}
        num_skills = len(sorted_skill_ids)

        pyg["skill"].num_nodes = num_skills
        pyg["skill"].node_ids = sorted_skill_ids
        pyg["skill"].canonical_ids = [graph_data.skill_nodes[sid].canonical_skill_id for sid in sorted_skill_ids]

        membership_map = {"resume_only": 0, "job_only": 1, "shared": 2}
        if num_skills > 0:
            skill_vecs = [graph_data.skill_nodes[sid].embedding_vector for sid in sorted_skill_ids]
            mem_codes = [membership_map[graph_data.skill_nodes[sid].membership] for sid in sorted_skill_ids]
            pyg["skill"].x = torch.tensor(skill_vecs, dtype=torch.float32)
            pyg["skill"].membership_code = torch.tensor(mem_codes, dtype=torch.long)
        else:
            pyg["skill"].x = torch.empty((0, dim), dtype=torch.float32)
            pyg["skill"].membership_code = torch.empty((0,), dtype=torch.long)

        node_id_to_idx: Dict[str, Dict[str, int]] = {
            "resume": {graph_data.resume_node.node_id: 0},
            "job": {graph_data.job_node.node_id: 0},
            "skill": skill_id_to_idx,
        }

        # 3. Bipartite Edges & Proficiency Attributes
        canonical_bipartite_edge_types: List[Tuple[str, str, str]] = [
            ("job", "requires_skill", "skill"),
            ("skill", "required_by_job", "job"),
            ("resume", "has_skill", "skill"),
            ("skill", "in_resume", "resume"),
        ]

        grouped_pairs: Dict[Tuple[str, str, str], List[Tuple[int, int]]] = {
            et: [] for et in canonical_bipartite_edge_types
        }
        grouped_weights: Dict[Tuple[str, str, str], List[float]] = {
            et: [] for et in canonical_bipartite_edge_types
        }
        grouped_effective_weights: Dict[Tuple[str, str, str], List[float]] = {
            et: [] for et in canonical_bipartite_edge_types
        }
        grouped_raw_levels: Dict[Tuple[str, str, str], List[float]] = {
            et: [] for et in canonical_bipartite_edge_types
        }
        grouped_has_prof: Dict[Tuple[str, str, str], List[bool]] = {
            et: [] for et in canonical_bipartite_edge_types
        }

        job_missing_eff = (
            1.0 if self.config.edge_weight_normalization == "scaled_0_1" else 10.0
        )
        resume_missing_eff = 0.0

        for edge in graph_data.edges:
            et = (edge.source_type, edge.edge_type, edge.target_type)
            u_idx = node_id_to_idx[edge.source_type][edge.source_id]
            v_idx = node_id_to_idx[edge.target_type][edge.target_id]
            grouped_pairs.setdefault(et, []).append((u_idx, v_idx))
            stored_w = float(edge.tensor_weight)
            grouped_weights.setdefault(et, []).append(stored_w)
            is_job_edge = edge.edge_type in ("requires_skill", "required_by_job")
            if edge.proficiency.is_missing:
                eff_w = job_missing_eff if is_job_edge else resume_missing_eff
            else:
                eff_w = stored_w
            grouped_effective_weights.setdefault(et, []).append(float(eff_w))
            raw_lvl = float(edge.proficiency.numeric_level) if edge.proficiency.numeric_level is not None else 0.0
            grouped_raw_levels.setdefault(et, []).append(raw_lvl)
            grouped_has_prof.setdefault(et, []).append(not edge.proficiency.is_missing)

        proficiency_edge_audit: Dict[str, Any] = {}
        for et in canonical_bipartite_edge_types:
            pairs = grouped_pairs[et]
            et_key = f"{et[0]}__{et[1]}__{et[2]}"
            is_job_edge = et[1] in ("requires_skill", "required_by_job")
            eff_fallback = job_missing_eff if is_job_edge else resume_missing_eff
            if pairs:
                src_indices = [p[0] for p in pairs]
                dst_indices = [p[1] for p in pairs]
                pyg[et].edge_index = torch.tensor([src_indices, dst_indices], dtype=torch.long)
                pyg[et].edge_attr = torch.tensor(grouped_weights[et], dtype=torch.float32).unsqueeze(1)
                pyg[et].edge_effective_weight = torch.tensor(
                    grouped_effective_weights[et], dtype=torch.float32
                ).unsqueeze(1)
                pyg[et].edge_raw_proficiency = torch.tensor(grouped_raw_levels[et], dtype=torch.float32).unsqueeze(1)
                pyg[et].edge_has_proficiency = torch.tensor(grouped_has_prof[et], dtype=torch.bool)

                total_e = len(pairs)
                with_prof = sum(1 for flag in grouped_has_prof[et] if flag)
                missing_prof = total_e - with_prof
                stored_mean = float(pyg[et].edge_attr.mean().item())
                eff_mean = float(pyg[et].edge_effective_weight.mean().item())
                expected_eff_mean = (
                    float(pyg[et].edge_attr.sum().item()) + missing_prof * eff_fallback
                ) / total_e
                proficiency_edge_audit[et_key] = {
                    "total_edges": total_e,
                    "edges_with_proficiency": with_prof,
                    "missing_proficiency_edges": missing_prof,
                    "stored_tensor_missing_fallback": float(self.config.missing_proficiency_tensor_weight),
                    "effective_layer_missing_fallback": float(eff_fallback),
                    "stored_edge_attr_mean": round(stored_mean, 8),
                    "effective_edge_weight_mean": round(eff_mean, 8),
                    "numerical_consistency_verified": abs(eff_mean - expected_eff_mean) < 1e-6,
                }
            else:
                pyg[et].edge_index = torch.empty((2, 0), dtype=torch.long)
                pyg[et].edge_attr = torch.empty((0, 1), dtype=torch.float32)
                pyg[et].edge_effective_weight = torch.empty((0, 1), dtype=torch.float32)
                pyg[et].edge_raw_proficiency = torch.empty((0, 1), dtype=torch.float32)
                pyg[et].edge_has_proficiency = torch.empty((0,), dtype=torch.bool)
                proficiency_edge_audit[et_key] = {
                    "total_edges": 0,
                    "edges_with_proficiency": 0,
                    "missing_proficiency_edges": 0,
                    "stored_tensor_missing_fallback": float(self.config.missing_proficiency_tensor_weight),
                    "effective_layer_missing_fallback": float(eff_fallback),
                    "stored_edge_attr_mean": 0.0,
                    "effective_edge_weight_mean": 0.0,
                    "numerical_consistency_verified": True,
                }

        pyg.graph_id = graph_data.graph_id
        pyg.pair_id = graph_data.pair_id
        pyg.merge_policy = graph_data.merge_policy
        pyg.edge_weight_normalization = graph_data.edge_weight_normalization

        num_nodes_by_type = {nt: int(pyg[nt].num_nodes) for nt in pyg.node_types}
        num_edges_by_type = {
            f"{s}__{r}__{d}": int(pyg[s, r, d].edge_index.size(1))
            for s, r, d in pyg.edge_types
        }
        summary = {
            "graph_id": graph_data.graph_id,
            "pair_id": graph_data.pair_id,
            "merge_policy": graph_data.merge_policy,
            "node_types": list(pyg.node_types),
            "edge_types": [f"{s}__{r}__{d}" for s, r, d in pyg.edge_types],
            "num_nodes_by_type": num_nodes_by_type,
            "num_edges_by_type": num_edges_by_type,
            "total_nodes": sum(num_nodes_by_type.values()),
            "total_edges": sum(num_edges_by_type.values()),
            "shared_skills": int((pyg["skill"].membership_code == 2).sum().item()) if num_skills > 0 else 0,
            "resume_only_skills": int((pyg["skill"].membership_code == 0).sum().item()) if num_skills > 0 else 0,
            "job_only_skills": int((pyg["skill"].membership_code == 1).sum().item()) if num_skills > 0 else 0,
            "proficiency_edge_audit": proficiency_edge_audit,
        }

        return pyg, node_id_to_idx, summary


def verify_paper_aligned_subgraphs(
    graph_data: PaperAlignedGraphData,
    reasoning_results: Optional[List[SkillPairReasoningResult]] = None,
) -> Dict[str, Any]:
    """
    Programmatically verify paper-aligned bipartite subgraph invariants for Stage 5 pipeline diagnostics:
    - Bipartite document-entity structure (1 resume, 1 job, 0 skill-skill edges).
    - React/ReactJS identity normalization & confusable React Query separation.
    - Non-equivalent LLM relation isolation (never merged into shared nodes).
    """
    report = graph_data.integrity_report or PaperAlignedGraphBuilder().validate_graph_integrity(graph_data)

    # Check React / ReactJS vs React Query if present
    react_nodes = [
        n for n in graph_data.skill_nodes.values()
        if n.canonical_skill_id == "react"
    ]
    react_query_nodes = [
        n for n in graph_data.skill_nodes.values()
        if n.canonical_skill_id == "react-query"
    ]
    react_verified = True
    for rn in react_nodes:
        if any("query" in s.lower() for s in rn.surface_names):
            react_verified = False

    # Verify non-equivalent LLM relations were never merged
    non_eq_isolated = True
    if reasoning_results:
        for r in reasoning_results:
            if r.identity != "equivalent" or r.relationship in ("related", "prerequisite", "specialization", "alternative", "unrelated"):
                ca = normalize_canonical_skill(r.skill_a.skill_id or r.skill_a.name)
                cb = normalize_canonical_skill(r.skill_b.skill_id or r.skill_b.name)
                if ca != cb:
                    for sn in graph_data.skill_nodes.values():
                        if sn.membership == "shared" and {sn.cv_canonical_id, sn.jd_canonical_id} == {ca, cb}:
                            non_eq_isolated = False

    bipartite_ok = (
        report.exactly_one_resume_and_one_job
        and report.no_unintended_doc_doc_or_skill_skill_edges
        and report.shared_entities_connect_to_both_docs
        and report.unique_entities_connect_to_single_doc
    )

    all_ok = bool(report.is_valid and bipartite_ok and react_verified and non_eq_isolated)
    return {
        "all_subgraphs_verified": all_ok,
        "no_skill_to_skill_edges": report.no_unintended_doc_doc_or_skill_skill_edges,
        "bipartite_structure_check": {
            "verified": bipartite_ok,
            "shared_skills_count": report.shared_skill_count,
            "resume_only_skills_count": report.resume_only_skill_count,
            "job_only_skills_count": report.job_only_skill_count,
        },
        "react_identity": {
            "verified": react_verified,
            "react_nodes_count": len(react_nodes),
            "react_query_nodes_count": len(react_query_nodes),
        },
        "synthetic_relation_check": {
            "verified": non_eq_isolated,
            "no_skill_skill_edges": report.no_unintended_doc_doc_or_skill_skill_edges,
        },
    }


paper_aligned_graph_builder = PaperAlignedGraphBuilder()
