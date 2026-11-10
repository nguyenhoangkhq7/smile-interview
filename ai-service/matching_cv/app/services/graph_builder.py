"""Stage 4 Phase 1: Heterogeneous Graph Builder for Ontology-Free Skill Matching."""
import copy
import hashlib
import logging
import math
from typing import Any, Dict, List, Optional, Set, Tuple, Union

import numpy as np
import torch
from torch_geometric.data import HeteroData

from matching_cv.app.schemas.hetero_graph import (
    CVNode,
    EdgeExportPolicy,
    EvidenceNode,
    GraphBuildRequest,
    GraphBuildResponse,
    GraphConstructionMode,
    GraphEdge,
    GraphIntegrityReport,
    HeteroGraphData,
    JDNode,
    NodeType,
    RequirementNode,
    SkillNode,
    Stage4ReasoningRecording,
)
from matching_cv.app.schemas.semantic_reasoning import (
    BatchSkillPairReasoningResponse,
    SkillPairReasoningResult,
)
from matching_cv.app.schemas.semantic_representation import (
    EmbeddingRecord,
    SemanticRepresentationResponse,
)
from matching_cv.app.schemas.unified_skill_extraction import (
    DocumentUnifiedResult,
    UnifiedExtractFileResponse,
)
from matching_cv.app.services.extraction_adapter import (
    AdaptedEvidenceOccurrence,
    AdaptedRequirementItem,
    AdaptedSkillItem,
    ExtractionDataAdapter,
    build_term_pattern,
)
from matching_cv.app.services.unified_skill_service import normalize_skill_name

logger = logging.getLogger(__name__)

PINNED_SBERT_MODEL_ID = "sentence-transformers/paraphrase-multilingual-mpnet-base-v2"
PINNED_SBERT_REVISION = "4328cf26390c98c5e3c738b4460a05b95f4911f5"
EXPECTED_EMBEDDING_DIM = 768


class HeteroGraphBuilder:
    """
    Constructs, enriches, validates, and exports heterogeneous skill graphs for GNN readiness.
    Preserves source provenance, distinct occurrence identity, and strict boundary distinctions
    between document-grounded facts, SBERT similarity candidates, and LLM semantic inferences.
    """

    def __init__(self) -> None:
        pass

    def build_graph(self, request: GraphBuildRequest) -> Tuple[HeteroGraphData, GraphIntegrityReport]:
        """
        Main graph construction entry point.
        Executes Mode A (evidence_only), Mode B (similarity_enriched), or Mode C (llm_enriched).
        """
        unified = request.unified_response
        stage3 = request.stage3_response

        # Resolve run_id
        run_id = "unknown_run"
        if unified and unified.run_id:
            run_id = unified.run_id
        elif stage3:
            run_id = (
                stage3.run_id
                if isinstance(stage3, SemanticRepresentationResponse)
                else stage3.get("run_id", "unknown_run")
            )

        graph_id = f"graph_{request.graph_mode}_{run_id[:8]}"

        # Initialize container
        graph_data = HeteroGraphData(
            graph_id=graph_id,
            run_id=run_id,
            mode=request.graph_mode,
            edge_policy=request.edge_policy,
            cv_nodes={},
            jd_nodes={},
            skill_nodes={},
            evidence_nodes={},
            requirement_nodes={},
            edges=[],
            rejected_audit=[],
            diagnostics={
                "graph_mode": request.graph_mode,
                "edge_policy": request.edge_policy,
                "sbert_model_id": PINNED_SBERT_MODEL_ID,
                "sbert_revision": PINNED_SBERT_REVISION,
            },
        )

        reasoning_res = self._extract_reasoning_results(request, graph_data=graph_data)

        # Step 1: Build Document-Grounded Nodes & Edges (Core Safe Skeleton)
        self._build_grounded_structure(
            graph_data=graph_data,
            unified=unified,
            stage3=stage3,
            raw_cv_text=request.raw_cv_text,
            raw_jd_text=request.raw_jd_text,
        )

        # Step 2: Enrich with SBERT Embeddings if Stage 3 response available
        if stage3 is not None:
            self._attach_sbert_embeddings(graph_data, stage3)

        # Step 3: Enrich with SBERT Candidate Similarity Edges (Mode B & C)
        if request.graph_mode in ("similarity_enriched", "llm_enriched") and stage3 is not None:
            self._build_sbert_similarity_edges(graph_data, stage3)

        # Step 4: Enrich with LLM Semantic Relationship Edges (Mode C)
        if request.graph_mode == "llm_enriched" and reasoning_res:
            self._build_llm_semantic_edges(graph_data, reasoning_res, request.edge_policy)

        # Step 5: Deterministic Ordering
        self._order_graph_deterministically(graph_data)

        # Step 6: Validate Integrity
        report = self.validate_graph_integrity(graph_data)

        return graph_data, report

    def _extract_reasoning_results(
        self, request: GraphBuildRequest, graph_data: Optional[HeteroGraphData] = None
    ) -> List[SkillPairReasoningResult]:
        """Extract reasoning result list from request fields, recording execution provenance."""
        if request.reasoning_recording is not None:
            rec = request.reasoning_recording
            if isinstance(rec, dict):
                rec = Stage4ReasoningRecording.model_validate(rec)
            if graph_data is not None:
                graph_data.diagnostics["reasoning_source"] = "recording"
                graph_data.diagnostics["reasoning_execution_source"] = rec.execution_source
                graph_data.diagnostics["reasoning_model_id"] = rec.model_id
                graph_data.diagnostics["reasoning_prompt_version"] = rec.prompt_version
                graph_data.diagnostics["recording_source_fixture_sha256"] = rec.source_fixture_sha256
                graph_data.diagnostics["recording_total_pairs"] = rec.total_pairs
            return rec.results

        if request.reasoning_results is not None:
            if graph_data is not None:
                graph_data.diagnostics["reasoning_source"] = "direct_results"
            return request.reasoning_results

        if request.reasoning_response is not None:
            if graph_data is not None:
                graph_data.diagnostics["reasoning_source"] = "batch_response"
            if isinstance(request.reasoning_response, BatchSkillPairReasoningResponse):
                return request.reasoning_response.results
            elif isinstance(request.reasoning_response, dict):
                raw_results = request.reasoning_response.get("results", [])
                parsed = []
                for r in raw_results:
                    if isinstance(r, SkillPairReasoningResult):
                        parsed.append(r)
                    elif isinstance(r, dict):
                        parsed.append(SkillPairReasoningResult.model_validate(r))
                return parsed
        return []

    def _build_grounded_structure(
        self,
        graph_data: HeteroGraphData,
        unified: Optional[UnifiedExtractFileResponse],
        stage3: Optional[Union[SemanticRepresentationResponse, Dict[str, Any]]],
        raw_cv_text: Optional[str] = None,
        raw_jd_text: Optional[str] = None,
    ) -> None:
        """Build CV, JD, Skill, Evidence, and Requirement nodes and their grounded edges."""
        # 1. Document Nodes
        cv_doc_id = "cv_doc"
        jd_doc_id = "jd_doc"
        cv_hash = None
        jd_hash = None

        if unified:
            if unified.cv:
                cv_doc_id = unified.cv.filename or f"cv_{unified.run_id[:8]}"
                cv_hash = unified.cv.text_sha256
            if unified.jd:
                jd_doc_id = unified.jd.filename or f"jd_{unified.run_id[:8]}"
                jd_hash = unified.jd.text_sha256

        if raw_cv_text and not cv_hash:
            cv_hash = hashlib.sha256(raw_cv_text.encode("utf-8")).hexdigest()
        if raw_jd_text and not jd_hash:
            jd_hash = hashlib.sha256(raw_jd_text.encode("utf-8")).hexdigest()

        cv_node_id = f"cv_{hashlib.sha256(cv_doc_id.encode()).hexdigest()[:8]}"
        jd_node_id = f"jd_{hashlib.sha256(jd_doc_id.encode()).hexdigest()[:8]}"

        cv_node = CVNode(
            node_id=cv_node_id,
            document_id=cv_doc_id,
            source_identifier=cv_doc_id,
            run_id=graph_data.run_id,
            source_type="CV",
            source_hash=cv_hash,
            metadata={"filename": cv_doc_id},
        )
        jd_node = JDNode(
            node_id=jd_node_id,
            document_id=jd_doc_id,
            source_identifier=jd_doc_id,
            run_id=graph_data.run_id,
            source_type="JD",
            source_hash=jd_hash,
            metadata={"filename": jd_doc_id},
        )
        graph_data.cv_nodes[cv_node_id] = cv_node
        graph_data.jd_nodes[jd_node_id] = jd_node

        # 2. Extract Active Skills & Duplicates from Unified Response if available
        cv_active_skills: List[AdaptedSkillItem] = []
        jd_active_skills: List[AdaptedSkillItem] = []
        cv_evidences: List[AdaptedEvidenceOccurrence] = []
        jd_requirements: List[AdaptedRequirementItem] = []

        if unified:
            # CV active skills
            cv_res = ExtractionDataAdapter.extract_active_skills(
                unified.cv, run_id=unified.run_id
            )
            cv_active_skills = cv_res.active_skills
            for dup in cv_res.duplicate_audit:
                graph_data.rejected_audit.append(
                    {
                        "entity_type": "duplicate_implicit_skill",
                        "document": "CV",
                        "skill_id": dup.skill_id,
                        "label": dup.label,
                        "matched_explicit_id": dup.matched_explicit_skill_id,
                        "reason": dup.duplicate_reason,
                    }
                )

            # JD active skills
            jd_res = ExtractionDataAdapter.extract_active_skills(
                unified.jd, run_id=unified.run_id
            )
            jd_active_skills = jd_res.active_skills
            for dup in jd_res.duplicate_audit:
                graph_data.rejected_audit.append(
                    {
                        "entity_type": "duplicate_implicit_skill",
                        "document": "JD",
                        "skill_id": dup.skill_id,
                        "label": dup.label,
                        "matched_explicit_id": dup.matched_explicit_skill_id,
                        "reason": dup.duplicate_reason,
                    }
                )

            # CV Evidence
            cv_evidences = ExtractionDataAdapter.extract_evidence_items(
                unified.cv, "CV", cv_doc_id, run_id=unified.run_id
            )

            # JD Requirements
            effective_jd_text = raw_jd_text or (
                unified.jd.raw_text if unified.jd and getattr(unified.jd, "raw_text", None) else ""
            )
            jd_requirements, _ = ExtractionDataAdapter.segment_jd_requirements(
                unified.jd, effective_jd_text, jd_doc_id
            )

        elif stage3:
            # Fallback when only stage3 is provided
            cv_embeddings = (
                stage3.cv_skill_embeddings
                if isinstance(stage3, SemanticRepresentationResponse)
                else stage3.get("cv_skill_embeddings", [])
            )
            jd_embeddings = (
                stage3.jd_skill_embeddings
                if isinstance(stage3, SemanticRepresentationResponse)
                else stage3.get("jd_skill_embeddings", [])
            )

            for rec in cv_embeddings:
                r_dict = rec if isinstance(rec, dict) else rec.model_dump()
                meta = r_dict.get("metadata", {})
                cv_active_skills.append(
                    AdaptedSkillItem(
                        occurrence_id=r_dict["occurrence_id"],
                        skill_id=r_dict.get("associated_skill_ids", [r_dict["occurrence_id"]])[0],
                        display_name=r_dict["source_text"],
                        extraction_type=r_dict.get("extraction_type") or "explicit",
                        category=meta.get("category"),
                        confidence=meta.get("confidence"),
                        basis=meta.get("basis"),
                    )
                )

            for rec in jd_embeddings:
                r_dict = rec if isinstance(rec, dict) else rec.model_dump()
                meta = r_dict.get("metadata", {})
                jd_active_skills.append(
                    AdaptedSkillItem(
                        occurrence_id=r_dict["occurrence_id"],
                        skill_id=r_dict.get("associated_skill_ids", [r_dict["occurrence_id"]])[0],
                        display_name=r_dict["source_text"],
                        extraction_type=r_dict.get("extraction_type") or "explicit",
                        category=meta.get("category"),
                        confidence=meta.get("confidence"),
                        basis=meta.get("basis"),
                    )
                )

        # 3. Create CV Skill Nodes and HAS_SKILL Edges
        # Keep an index from canonical_skill_id -> list of CV skill occurrence IDs
        cv_canonical_to_node_ids: Dict[str, List[str]] = {}
        for s in cv_active_skills:
            node_id = s.occurrence_id
            s_meta = dict(getattr(s, "metadata", {}) or {})
            s_meta["legacy_id"] = getattr(s, "legacy_id", node_id)
            granularity = getattr(s, "granularity", None) or s_meta.get("competency_granularity") or "atomic_skill"
            s_meta["competency_granularity"] = granularity
            s_meta["is_competency"] = (granularity in ("atomic_skill", "compound_competency"))
            s_meta["entity_kind"] = getattr(s, "kind", None)
            if s.extraction_type == "explicit" and getattr(s, "kind", None) == "context":
                s_meta["is_competency"] = False

            ev_status = "contextual_artifact" if granularity == "contextual_activity_or_product" else "unsupported"

            skill_node = SkillNode(
                node_id=node_id,
                skill_occurrence_id=s.occurrence_id,
                original_label=s.display_name,
                canonical_skill_id=s.skill_id,
                source_document="CV",
                explicit_or_implicit=s.extraction_type,
                category=s.category,
                confidence=s.confidence,
                basis=s.basis,
                source_identifier=cv_doc_id,
                evidence_status=ev_status,
                semantic_identity_status="occurrence",
                metadata=s_meta,
            )
            graph_data.skill_nodes[node_id] = skill_node
            cv_canonical_to_node_ids.setdefault(s.skill_id, []).append(node_id)
            # Edge: CV --HAS_SKILL--> Skill
            graph_data.edges.append(
                GraphEdge(
                    edge_type="has_skill",
                    source_type="cv",
                    target_type="skill",
                    source_id=cv_node_id,
                    target_id=node_id,
                    attributes={
                        "extraction_type": s.extraction_type,
                        "confidence": s.confidence,
                        "source_occurrence_id": s.occurrence_id,
                    },
                )
            )

        # 4. Create JD Skill Nodes and REQUIRES_SKILL Edges
        jd_canonical_to_node_ids: Dict[str, List[str]] = {}
        for s in jd_active_skills:
            node_id = s.occurrence_id
            s_meta = dict(getattr(s, "metadata", {}) or {})
            s_meta["legacy_id"] = getattr(s, "legacy_id", node_id)
            granularity = getattr(s, "granularity", None) or s_meta.get("competency_granularity") or "atomic_skill"
            s_meta["competency_granularity"] = granularity
            s_meta["is_competency"] = (granularity in ("atomic_skill", "compound_competency"))
            s_meta["entity_kind"] = getattr(s, "kind", None)
            if s.extraction_type == "explicit" and getattr(s, "kind", None) == "context":
                s_meta["is_competency"] = False

            ev_status = "contextual_artifact" if granularity == "contextual_activity_or_product" else "unsupported"

            skill_node = SkillNode(
                node_id=node_id,
                skill_occurrence_id=s.occurrence_id,
                original_label=s.display_name,
                canonical_skill_id=s.skill_id,
                source_document="JD",
                explicit_or_implicit=s.extraction_type,
                category=s.category,
                confidence=s.confidence,
                basis=s.basis,
                source_identifier=jd_doc_id,
                evidence_status=ev_status,
                semantic_identity_status="occurrence",
                metadata=s_meta,
            )
            graph_data.skill_nodes[node_id] = skill_node
            jd_canonical_to_node_ids.setdefault(s.skill_id, []).append(node_id)
            # Edge: JD --REQUIRES_SKILL--> Skill
            graph_data.edges.append(
                GraphEdge(
                    edge_type="requires_skill",
                    source_type="jd",
                    target_type="skill",
                    source_id=jd_node_id,
                    target_id=node_id,
                    attributes={
                        "extraction_type": s.extraction_type,
                        "confidence": s.confidence,
                        "source_occurrence_id": s.occurrence_id,
                    },
                )
            )

        # 5. Create CV Evidence Nodes, HAS_EVIDENCE Edges, and SUPPORTED_BY Edges
        for ev in cv_evidences:
            ev_node_id = ev.occurrence_id
            ev_node = EvidenceNode(
                node_id=ev_node_id,
                evidence_id=ev.occurrence_id,
                document_id=cv_doc_id,
                text=ev.text,
                source_span={"start": ev.start, "end": ev.end} if ev.start is not None else None,
                section=ev.section,
                verification_status="context_verified" if ev.verbatim_ok else "model_inferred",
                source_identifier=cv_doc_id,
                metadata={
                    "offset_resolved": ev.offset_resolved,
                    "verbatim_ok": ev.verbatim_ok,
                },
            )
            graph_data.evidence_nodes[ev_node_id] = ev_node

            # Edge: CV --HAS_EVIDENCE--> Evidence
            graph_data.edges.append(
                GraphEdge(
                    edge_type="has_evidence",
                    source_type="cv",
                    target_type="evidence",
                    source_id=cv_node_id,
                    target_id=ev_node_id,
                    attributes={"section": ev.section},
                )
            )

            # Link supported CV skills
            for sk_id in ev.associated_skill_ids:
                matching_nodes = cv_canonical_to_node_ids.get(sk_id, [])
                for sk_node_id in matching_nodes:
                    graph_data.skill_nodes[sk_node_id].evidence_status = "has_evidence"
                    graph_data.edges.append(
                        GraphEdge(
                            edge_type="supported_by",
                            source_type="skill",
                            target_type="evidence",
                            source_id=sk_node_id,
                            target_id=ev_node_id,
                            attributes={
                                "section": ev.section,
                                "provenance": "cv_evidence_occurrence",
                            },
                        )
                    )

        # 6. Create JD Requirement Nodes, HAS_REQUIREMENT Edges, and MENTIONS_SKILL Edges
        for req in jd_requirements:
            req_node_id = req.occurrence_id
            req_node = RequirementNode(
                node_id=req_node_id,
                requirement_id=req.occurrence_id,
                document_id=jd_doc_id,
                text=req.text,
                source_span={"start": req.start, "end": req.end} if req.start is not None else None,
                section=req.section,
                source_identifier=jd_doc_id,
                metadata={"source_strategy": req.source_strategy},
            )
            graph_data.requirement_nodes[req_node_id] = req_node

            # Edge: JD --HAS_REQUIREMENT--> Requirement
            graph_data.edges.append(
                GraphEdge(
                    edge_type="has_requirement",
                    source_type="jd",
                    target_type="requirement",
                    source_id=jd_node_id,
                    target_id=req_node_id,
                    attributes={"section": req.section},
                )
            )

            # Link mentioned JD skills
            for sk_id in req.associated_skill_ids:
                matching_nodes = jd_canonical_to_node_ids.get(sk_id, [])
                for sk_node_id in matching_nodes:
                    graph_data.edges.append(
                        GraphEdge(
                            edge_type="mentions_skill",
                            source_type="requirement",
                            target_type="skill",
                            source_id=req_node_id,
                            target_id=sk_node_id,
                            attributes={
                                "section": req.section,
                                "provenance": "jd_requirement_occurrence",
                            },
                        )
                    )

    def _attach_sbert_embeddings(
        self,
        graph_data: HeteroGraphData,
        stage3: Union[SemanticRepresentationResponse, Dict[str, Any]],
    ) -> None:
        """Attach 768D embeddings and vector references from Stage 3 response to graph nodes."""
        if isinstance(stage3, SemanticRepresentationResponse):
            cv_skill_recs = stage3.cv_skill_embeddings
            jd_skill_recs = stage3.jd_skill_embeddings
            cv_ev_recs = stage3.cv_evidence_embeddings
            jd_req_recs = stage3.jd_requirement_embeddings
        else:
            cv_skill_recs = [
                EmbeddingRecord.model_validate(r) for r in stage3.get("cv_skill_embeddings", [])
            ]
            jd_skill_recs = [
                EmbeddingRecord.model_validate(r) for r in stage3.get("jd_skill_embeddings", [])
            ]
            cv_ev_recs = [
                EmbeddingRecord.model_validate(r) for r in stage3.get("cv_evidence_embeddings", [])
            ]
            jd_req_recs = [
                EmbeddingRecord.model_validate(r) for r in stage3.get("jd_requirement_embeddings", [])
            ]

        # Map to nodes
        for rec in cv_skill_recs + jd_skill_recs:
            if rec.occurrence_id in graph_data.skill_nodes:
                node = graph_data.skill_nodes[rec.occurrence_id]
                node.embedding_ref = rec.vector_id
                if rec.vector is not None:
                    node.embedding_vector = rec.vector
                    node.has_embedding = True
                node.metadata["model_id"] = rec.model_id
                node.metadata["model_revision"] = rec.model_revision

        for rec in cv_ev_recs:
            if rec.occurrence_id in graph_data.evidence_nodes:
                node = graph_data.evidence_nodes[rec.occurrence_id]
                node.embedding_ref = rec.vector_id
                if rec.vector is not None:
                    node.embedding_vector = rec.vector
                    node.has_embedding = True

        for rec in jd_req_recs:
            if rec.occurrence_id in graph_data.requirement_nodes:
                node = graph_data.requirement_nodes[rec.occurrence_id]
                node.embedding_ref = rec.vector_id
                if rec.vector is not None:
                    node.embedding_vector = rec.vector
                    node.has_embedding = True

    def _build_sbert_similarity_edges(
        self,
        graph_data: HeteroGraphData,
        stage3: Union[SemanticRepresentationResponse, Dict[str, Any]],
    ) -> None:
        """Construct candidate similarity edges from Stage 3 Top-K retrieval."""
        ret_map = (
            stage3.top_k_retrievals
            if isinstance(stage3, SemanticRepresentationResponse)
            else stage3.get("top_k_retrievals", {})
        ) or {}

        skill_retrievals = ret_map.get("cv_skills_to_jd_skills") or ret_map.get("skill_to_skill") or []

        seen_edges: Set[Tuple[str, str]] = set()

        for ret in skill_retrievals:
            q_id = ret.query_id if hasattr(ret, "query_id") else ret.get("query_id")
            candidates = ret.candidates if hasattr(ret, "candidates") else ret.get("candidates", [])

            if q_id not in graph_data.skill_nodes:
                continue

            for cand in candidates:
                t_id = cand.target_id if hasattr(cand, "target_id") else cand.get("target_id")
                if t_id not in graph_data.skill_nodes:
                    continue

                edge_key = (q_id, t_id)
                if edge_key in seen_edges:
                    continue
                seen_edges.add(edge_key)

                cosine = float(cand.cosine_similarity if hasattr(cand, "cosine_similarity") else cand.get("cosine_similarity", 0.0))
                raw_score = float(cand.raw_score if hasattr(cand, "raw_score") else cand.get("raw_score", cosine))
                rank = int(cand.rank if hasattr(cand, "rank") else cand.get("rank", 1))

                graph_data.edges.append(
                    GraphEdge(
                        edge_type="similar_to_candidate",
                        source_type="skill",
                        target_type="skill",
                        source_id=q_id,
                        target_id=t_id,
                        attributes={
                            "cosine_similarity": cosine,
                            "raw_score": raw_score,
                            "retrieval_rank": rank,
                            "retrieval_method": "sbert_top_k",
                            "source_occurrence_ids": [q_id, t_id],
                            "candidate_status": "retrieved_candidate",
                        },
                    )
                )

    def _build_llm_semantic_edges(
        self,
        graph_data: HeteroGraphData,
        reasoning_results: List[SkillPairReasoningResult],
        edge_policy: EdgeExportPolicy,
    ) -> None:
        """
        Enrich graph with LLM semantic relationships under strict gating and directionality.
        Policies:
        - 'trusted_structural_only': No LLM semantic edges added.
        - 'eligible_llm_edges': Only 'eligible' relations added.
        - 'experimental_include_candidates': 'eligible' + 'candidate_only' relations added.
        """
        if edge_policy == "trusted_structural_only":
            return

        # Pre-build lookup maps for endpoint resolution
        # Map: occurrence_id -> node_id
        # Map: (canonical_skill_id, source_doc) -> list of node_ids
        # Map: (normalized_label, source_doc) -> list of node_ids
        cv_slug_map: Dict[str, List[str]] = {}
        jd_slug_map: Dict[str, List[str]] = {}
        cv_label_map: Dict[str, List[str]] = {}
        jd_label_map: Dict[str, List[str]] = {}

        for n_id, n in graph_data.skill_nodes.items():
            norm_label = normalize_skill_name(n.original_label)
            if n.source_document == "CV":
                cv_slug_map.setdefault(n.canonical_skill_id, []).append(n_id)
                cv_label_map.setdefault(norm_label, []).append(n_id)
            else:
                jd_slug_map.setdefault(n.canonical_skill_id, []).append(n_id)
                jd_label_map.setdefault(norm_label, []).append(n_id)

        seen_edges: Set[Tuple[str, str, str]] = set()

        for res in reasoning_results:
            # 1. Gate by graph_relation_status
            if res.graph_relation_status == "rejected":
                graph_data.rejected_audit.append(
                    {
                        "entity_type": "semantic_relation",
                        "skill_a": res.skill_a.name,
                        "skill_b": res.skill_b.name,
                        "status": "rejected",
                        "reason": res.error_status or res.reasoning_summary,
                    }
                )
                continue

            if res.graph_relation_status == "candidate_only" and edge_policy != "experimental_include_candidates":
                graph_data.rejected_audit.append(
                    {
                        "entity_type": "semantic_relation",
                        "skill_a": res.skill_a.name,
                        "skill_b": res.skill_b.name,
                        "status": "candidate_only",
                        "reason": "Filtered by edge_policy (requires experimental_include_candidates)",
                    }
                )
                continue

            # 2. Gate out negative and uncertain relations
            if res.identity == "uncertain" or res.relationship == "uncertain":
                graph_data.rejected_audit.append(
                    {
                        "entity_type": "semantic_relation",
                        "skill_a": res.skill_a.name,
                        "skill_b": res.skill_b.name,
                        "status": "uncertain",
                        "reason": res.reasoning_summary,
                    }
                )
                continue

            if res.relationship == "unrelated":
                graph_data.rejected_audit.append(
                    {
                        "entity_type": "semantic_relation",
                        "skill_a": res.skill_a.name,
                        "skill_b": res.skill_b.name,
                        "status": "unrelated",
                        "reason": res.reasoning_summary,
                    }
                )
                continue

            # 3. Resolve endpoints
            src_node_ids = self._resolve_node_ids(res.skill_a, res.source_occurrence_ids, 0, graph_data, cv_slug_map, cv_label_map)
            tgt_node_ids = self._resolve_node_ids(res.skill_b, res.source_occurrence_ids, 1, graph_data, jd_slug_map, jd_label_map)

            if not src_node_ids or not tgt_node_ids:
                graph_data.rejected_audit.append(
                    {
                        "entity_type": "semantic_relation_unresolved_endpoint",
                        "skill_a": res.skill_a.name,
                        "skill_b": res.skill_b.name,
                        "resolved_src_count": len(src_node_ids),
                        "resolved_tgt_count": len(tgt_node_ids),
                    }
                )
                continue

            # Provenance Invariant Check:
            # Model knowledge cannot claim context_verified without contextual text.
            has_context = bool(
                (res.skill_a.context and res.skill_a.context.strip())
                or (res.skill_b.context and res.skill_b.context.strip())
            )
            v_status = res.verification_status
            if not has_context and res.evidence_basis == "model_knowledge" and v_status == "context_verified":
                v_status = "model_inferred"
                graph_data.rejected_audit.append(
                    {
                        "entity_type": "provenance_sanitization",
                        "skill_a": res.skill_a.name,
                        "skill_b": res.skill_b.name,
                        "action": "downgraded_verification_status",
                        "original_status": res.verification_status,
                        "new_status": v_status,
                        "reason": "evidence_basis=model_knowledge without context text cannot be context_verified",
                    }
                )

            # Build typed attributes
            pair_id = getattr(res, "pair_id", None) or f"{res.skill_a.skill_id}__{res.skill_b.skill_id}"
            src_occ_id = (res.source_occurrence_ids[0] if (res.source_occurrence_ids and len(res.source_occurrence_ids) > 0) else res.skill_a.skill_id)
            tgt_occ_id = (res.source_occurrence_ids[1] if (res.source_occurrence_ids and len(res.source_occurrence_ids) > 1) else res.skill_b.skill_id)

            attr = {
                "identity": res.identity,
                "relationship": res.relationship,
                "direction": res.direction,
                "reasoning_summary": res.reasoning_summary,
                "evidence_basis": res.evidence_basis,
                "verification_status": v_status,
                "requires_external_verification": res.requires_external_verification,
                "model_id": res.model_id,
                "prompt_version": res.prompt_version,
                "retrieval_cosine": res.retrieval_cosine,
                "graph_relation_status": res.graph_relation_status,
                "resolution_method": res.resolution_method,
                "is_tentative": (res.graph_relation_status == "candidate_only"),
                "contradiction_detected": res.contradiction_detected,
                "is_hypothesis": True,
                "gating_status": "eligible_llm_edge",
                "edge_layer": "semantic_reasoning",
                "source_reasoning_pair_id": pair_id,
                "source_occurrence_id": src_occ_id,
                "target_occurrence_id": tgt_occ_id,
                "edge_export_policy": edge_policy,
                "run_id": getattr(graph_data, "run_id", None),
            }

            for u in src_node_ids:
                for v in tgt_node_ids:
                    if u == v:
                        # Prevent self-loops
                        continue

                    # Determine typed edges & directions
                    if res.identity == "equivalent":
                        # Equivalent identity candidate edge (bidirectional)
                        for s_id, t_id in [(u, v), (v, u)]:
                            k = (s_id, t_id, "equivalent_to")
                            if k not in seen_edges:
                                seen_edges.add(k)
                                edge_id = f"{s_id}__equivalent_to__{t_id}"
                                graph_data.edges.append(
                                    GraphEdge(
                                        edge_type="equivalent_to",
                                        source_type="skill",
                                        target_type="skill",
                                        source_id=s_id,
                                        target_id=t_id,
                                        attributes={**attr, "graph_edge_id": edge_id},
                                    )
                                )

                    elif res.relationship == "prerequisite":
                        # Direction: a_to_b means u is prerequisite for v
                        # Direction: b_to_a means v is prerequisite for u
                        pairs = []
                        if res.direction == "a_to_b":
                            pairs.append((u, v))
                        elif res.direction == "b_to_a":
                            pairs.append((v, u))
                        elif res.direction == "bidirectional":
                            pairs.extend([(u, v), (v, u)])
                        else:
                            pairs.append((u, v))

                        for s_id, t_id in pairs:
                            k = (s_id, t_id, "prerequisite_for")
                            if k not in seen_edges:
                                seen_edges.add(k)
                                edge_id = f"{s_id}__prerequisite_for__{t_id}"
                                graph_data.edges.append(
                                    GraphEdge(
                                        edge_type="prerequisite_for",
                                        source_type="skill",
                                        target_type="skill",
                                        source_id=s_id,
                                        target_id=t_id,
                                        attributes={**attr, "graph_edge_id": edge_id},
                                    )
                                )

                    elif res.relationship == "specialization":
                        # Specialization convention: specialized_skill --SPECIALIZATION_OF--> broader_skill
                        # If a_to_b: u is specialization of v
                        # If b_to_a: v is specialization of u
                        pairs = []
                        if res.direction == "a_to_b":
                            pairs.append((u, v))
                        elif res.direction == "b_to_a":
                            pairs.append((v, u))
                        else:
                            pairs.append((u, v))

                        for s_id, t_id in pairs:
                            k = (s_id, t_id, "specialization_of")
                            if k not in seen_edges:
                                seen_edges.add(k)
                                edge_id = f"{s_id}__specialization_of__{t_id}"
                                graph_data.edges.append(
                                    GraphEdge(
                                        edge_type="specialization_of",
                                        source_type="skill",
                                        target_type="skill",
                                        source_id=s_id,
                                        target_id=t_id,
                                        attributes={**attr, "graph_edge_id": edge_id},
                                    )
                                )

                    elif res.relationship == "alternative":
                        for s_id, t_id in [(u, v), (v, u)]:
                            k = (s_id, t_id, "alternative_to")
                            if k not in seen_edges:
                                seen_edges.add(k)
                                edge_id = f"{s_id}__alternative_to__{t_id}"
                                graph_data.edges.append(
                                    GraphEdge(
                                        edge_type="alternative_to",
                                        source_type="skill",
                                        target_type="skill",
                                        source_id=s_id,
                                        target_id=t_id,
                                        attributes={**attr, "graph_edge_id": edge_id},
                                    )
                                )

                    elif res.relationship == "related":
                        for s_id, t_id in [(u, v), (v, u)]:
                            k = (s_id, t_id, "related_to")
                            if k not in seen_edges:
                                seen_edges.add(k)
                                edge_id = f"{s_id}__related_to__{t_id}"
                                graph_data.edges.append(
                                    GraphEdge(
                                        edge_type="related_to",
                                        source_type="skill",
                                        target_type="skill",
                                        source_id=s_id,
                                        target_id=t_id,
                                        attributes={**attr, "graph_edge_id": edge_id},
                                    )
                                )

    def _resolve_node_ids(
        self,
        skill_ref: Any,
        source_occurrence_ids: Optional[List[str]],
        occurrence_idx: int,
        graph_data: HeteroGraphData,
        slug_map: Dict[str, List[str]],
        label_map: Dict[str, List[str]],
    ) -> List[str]:
        """
        Resolve a SkillRef to matching skill node IDs unambiguously.
        Priority:
        1. Direct occurrence ID match
        2. source_occurrence_ids[occurrence_idx] match
        3. Canonical slug match within expected document role (unambiguous only)
        4. Normalized label match within expected document role (unambiguous only)
        5. Term pattern search within expected document role (unambiguous only)
        If multiple candidate occurrences match a label/slug without an occurrence ID,
        it is rejected as ambiguous and recorded in rejected_audit.
        """
        expected_doc = getattr(skill_ref, "source", None)

        # 1. Direct occurrence id match
        if skill_ref.skill_id in graph_data.skill_nodes:
            n = graph_data.skill_nodes[skill_ref.skill_id]
            if not expected_doc or n.source_document == expected_doc:
                return [skill_ref.skill_id]

        # 2. Check source_occurrence_ids
        if source_occurrence_ids and len(source_occurrence_ids) > occurrence_idx:
            cand = source_occurrence_ids[occurrence_idx]
            if cand in graph_data.skill_nodes:
                n = graph_data.skill_nodes[cand]
                if not expected_doc or n.source_document == expected_doc:
                    return [cand]

        # 3. Canonical slug lookup
        if skill_ref.skill_id in slug_map:
            cands = slug_map[skill_ref.skill_id]
            if expected_doc:
                cands = [c for c in cands if graph_data.skill_nodes[c].source_document == expected_doc]
            if len(cands) == 1:
                return cands
            elif len(cands) > 1:
                graph_data.rejected_audit.append(
                    {
                        "entity_type": "ambiguous_endpoint_mapping",
                        "skill_name": skill_ref.name,
                        "skill_id": skill_ref.skill_id,
                        "expected_doc": expected_doc,
                        "matched_candidates": cands,
                        "reason": f"Multiple occurrences ({len(cands)}) found for canonical slug without occurrence_id disambiguation",
                    }
                )
                return []

        # 4. Normalized label lookup
        norm = normalize_skill_name(skill_ref.name)
        if norm in label_map:
            cands = label_map[norm]
            if expected_doc:
                cands = [c for c in cands if graph_data.skill_nodes[c].source_document == expected_doc]
            if len(cands) == 1:
                return cands
            elif len(cands) > 1:
                graph_data.rejected_audit.append(
                    {
                        "entity_type": "ambiguous_endpoint_mapping",
                        "skill_name": skill_ref.name,
                        "norm_label": norm,
                        "expected_doc": expected_doc,
                        "matched_candidates": cands,
                        "reason": f"Multiple occurrences ({len(cands)}) found for normalized label without occurrence_id disambiguation",
                    }
                )
                return []

        # 5. Regex / boundary pattern match on original label
        pattern = build_term_pattern(skill_ref.name)
        matches = []
        for n_id, n in graph_data.skill_nodes.items():
            if expected_doc and n.source_document != expected_doc:
                continue
            if n.canonical_skill_id == skill_ref.skill_id or normalize_skill_name(n.original_label) == norm:
                matches.append(n_id)
            elif pattern.search(n.original_label):
                matches.append(n_id)

        if len(matches) == 1:
            return matches
        elif len(matches) > 1:
            graph_data.rejected_audit.append(
                {
                    "entity_type": "ambiguous_endpoint_mapping",
                    "skill_name": skill_ref.name,
                    "expected_doc": expected_doc,
                    "matched_candidates": matches,
                    "reason": f"Pattern search matched multiple occurrences ({len(matches)}) without occurrence_id disambiguation",
                }
            )
            return []

        return []

    def _order_graph_deterministically(self, graph_data: HeteroGraphData) -> None:
        """Sort nodes and edges deterministically to guarantee reproducible outputs."""
        graph_data.cv_nodes = dict(sorted(graph_data.cv_nodes.items(), key=lambda x: x[0]))
        graph_data.jd_nodes = dict(sorted(graph_data.jd_nodes.items(), key=lambda x: x[0]))
        graph_data.skill_nodes = dict(sorted(graph_data.skill_nodes.items(), key=lambda x: x[0]))
        graph_data.evidence_nodes = dict(sorted(graph_data.evidence_nodes.items(), key=lambda x: x[0]))
        graph_data.requirement_nodes = dict(sorted(graph_data.requirement_nodes.items(), key=lambda x: x[0]))

        graph_data.edges.sort(
            key=lambda e: (e.source_type, e.edge_type, e.target_type, e.source_id, e.target_id)
        )

    def validate_graph_integrity(self, graph_data: HeteroGraphData) -> GraphIntegrityReport:
        """Run structural, embedding, provenance, and cycle integrity validations."""
        errors: List[str] = []
        warnings: List[str] = []

        all_node_ids: Dict[NodeType, Set[str]] = {
            "cv": set(graph_data.cv_nodes.keys()),
            "jd": set(graph_data.jd_nodes.keys()),
            "skill": set(graph_data.skill_nodes.keys()),
            "evidence": set(graph_data.evidence_nodes.keys()),
            "requirement": set(graph_data.requirement_nodes.keys()),
        }

        # 1. Node Integrity: unique IDs and valid source documents
        flat_node_ids = set()
        node_counts = {t: len(s) for t, s in all_node_ids.items()}
        for t, s in all_node_ids.items():
            for nid in s:
                if nid in flat_node_ids:
                    errors.append(f"Duplicate node ID across types: {nid}")
                flat_node_ids.add(nid)

        for s_id, s in graph_data.skill_nodes.items():
            if s.source_document not in ("CV", "JD"):
                errors.append(f"Invalid source_document '{s.source_document}' on skill {s_id}")

        node_integrity = {
            "node_counts": node_counts,
            "total_nodes": sum(node_counts.values()),
            "unique_node_ids": len(flat_node_ids),
        }

        # 2. Edge Integrity: valid endpoints, no self-loops, no duplicate edges
        seen_edges: Set[Tuple[str, str, str]] = set()
        edge_type_counts: Dict[str, int] = {}
        orphan_evidence = 0
        self_loops = 0

        for edge in graph_data.edges:
            edge_type_counts[edge.edge_type] = edge_type_counts.get(edge.edge_type, 0) + 1

            if edge.source_id not in all_node_ids[edge.source_type]:
                errors.append(
                    f"Edge {edge.edge_type} has missing source: {edge.source_type}:{edge.source_id}"
                )
            if edge.target_id not in all_node_ids[edge.target_type]:
                errors.append(
                    f"Edge {edge.edge_type} has missing target: {edge.target_type}:{edge.target_id}"
                )

            if edge.source_id == edge.target_id:
                self_loops += 1
                errors.append(f"Forbidden self-loop on node {edge.source_id} for edge {edge.edge_type}")

            edge_key = (edge.source_id, edge.target_id, edge.edge_type)
            if edge_key in seen_edges:
                warnings.append(f"Duplicate edge detected: {edge_key}")
            seen_edges.add(edge_key)

        # Check for rejected relations mistakenly present
        for edge in graph_data.edges:
            status = edge.attributes.get("graph_relation_status")
            if status == "rejected":
                errors.append(
                    f"Rejected semantic edge present in active graph: {edge.source_id} -> {edge.target_id}"
                )

        edge_integrity = {
            "edge_counts": edge_type_counts,
            "total_edges": len(graph_data.edges),
            "self_loops": self_loops,
            "duplicate_edges": len(graph_data.edges) - len(seen_edges),
        }

        # 3. Embedding Integrity: 768-dim, finite floats, no NaN/Inf
        nan_count = 0
        inf_count = 0
        dim_mismatches = 0
        nodes_with_vector = 0

        for s_id, s in graph_data.skill_nodes.items():
            if s.has_embedding and s.embedding_vector is not None:
                nodes_with_vector += 1
                vec = s.embedding_vector
                if len(vec) != EXPECTED_EMBEDDING_DIM:
                    dim_mismatches += 1
                    errors.append(f"Skill {s_id} has wrong embedding dimension: {len(vec)} != {EXPECTED_EMBEDDING_DIM}")
                for val in vec:
                    if math.isnan(val):
                        nan_count += 1
                    elif math.isinf(val):
                        inf_count += 1

        if nan_count > 0:
            errors.append(f"Detected {nan_count} NaN values in skill embedding vectors")
        if inf_count > 0:
            errors.append(f"Detected {inf_count} Infinite values in skill embedding vectors")

        embedding_integrity = {
            "expected_dimension": EXPECTED_EMBEDDING_DIM,
            "nodes_with_vectors": nodes_with_vector,
            "dimension_mismatches": dim_mismatches,
            "nan_count": nan_count,
            "inf_count": inf_count,
            "model_revision_pinned": PINNED_SBERT_REVISION,
        }

        # 4. Provenance Integrity
        provenance_integrity = {
            "cv_skills_grounded": sum(1 for s in graph_data.skill_nodes.values() if s.source_document == "CV"),
            "jd_skills_grounded": sum(1 for s in graph_data.skill_nodes.values() if s.source_document == "JD"),
            "skills_with_evidence": sum(1 for s in graph_data.skill_nodes.values() if s.evidence_status == "has_evidence"),
            "rejected_audit_entries": len(graph_data.rejected_audit),
        }

        # 5. Prerequisite Cycle Detection
        prereq_cycles = self._detect_prerequisite_cycles(graph_data)
        if prereq_cycles:
            warnings.append(f"Detected {len(prereq_cycles)} cycles in prerequisite relation subgraph")

        is_valid = len(errors) == 0

        return GraphIntegrityReport(
            is_valid=is_valid,
            node_integrity=node_integrity,
            edge_integrity=edge_integrity,
            embedding_integrity=embedding_integrity,
            provenance_integrity=provenance_integrity,
            prerequisite_cycles=prereq_cycles,
            errors=errors,
            warnings=warnings,
        )

    def _detect_prerequisite_cycles(self, graph_data: HeteroGraphData) -> List[List[str]]:
        """Find simple cycles in directed prerequisite edges using DFS."""
        adj: Dict[str, List[str]] = {}
        for edge in graph_data.edges:
            if edge.edge_type == "prerequisite_for":
                adj.setdefault(edge.source_id, []).append(edge.target_id)

        visited: Dict[str, int] = {}  # 0: unvisited, 1: visiting, 2: visited
        cycles: List[List[str]] = []
        path: List[str] = []

        def dfs(node: str):
            visited[node] = 1
            path.append(node)
            for neighbor in adj.get(node, []):
                if visited.get(neighbor, 0) == 1:
                    # Cycle detected
                    idx = path.index(neighbor)
                    cycles.append(path[idx:] + [neighbor])
                elif visited.get(neighbor, 0) == 0:
                    dfs(neighbor)
            path.pop()
            visited[node] = 2

        for node in list(adj.keys()):
            if visited.get(node, 0) == 0:
                dfs(node)

        return cycles

    def export_to_pyg(
        self, graph_data: HeteroGraphData
    ) -> Tuple[HeteroData, Dict[str, Dict[str, int]], Dict[str, Any]]:
        """
        Export HeteroGraphData to torch_geometric.data.HeteroData.
        Produces:
        - PyG HeteroData container
        - node_id_to_idx mappings per node type
        - Summary diagnostics
        """
        pyg_data = HeteroData()

        # Stable sorted indexing
        node_id_to_idx: Dict[str, Dict[str, int]] = {
            "cv": {nid: idx for idx, nid in enumerate(sorted(graph_data.cv_nodes.keys()))},
            "jd": {nid: idx for idx, nid in enumerate(sorted(graph_data.jd_nodes.keys()))},
            "skill": {nid: idx for idx, nid in enumerate(sorted(graph_data.skill_nodes.keys()))},
            "evidence": {nid: idx for idx, nid in enumerate(sorted(graph_data.evidence_nodes.keys()))},
            "requirement": {nid: idx for idx, nid in enumerate(sorted(graph_data.requirement_nodes.keys()))},
        }

        # 1. Nodes & Node Features
        # Document nodes
        pyg_data["cv"].num_nodes = len(graph_data.cv_nodes)
        pyg_data["cv"].node_ids = list(sorted(graph_data.cv_nodes.keys()))
        pyg_data["cv"].has_feature_mask = torch.zeros(len(graph_data.cv_nodes), dtype=torch.bool)

        pyg_data["jd"].num_nodes = len(graph_data.jd_nodes)
        pyg_data["jd"].node_ids = list(sorted(graph_data.jd_nodes.keys()))
        pyg_data["jd"].has_feature_mask = torch.zeros(len(graph_data.jd_nodes), dtype=torch.bool)

        # Skill nodes
        num_skills = len(graph_data.skill_nodes)
        pyg_data["skill"].num_nodes = num_skills
        pyg_data["skill"].node_ids = list(sorted(graph_data.skill_nodes.keys()))

        skill_vecs = []
        skill_mask = []
        sorted_skill_nodes = [graph_data.skill_nodes[nid] for nid in sorted(graph_data.skill_nodes.keys())]

        for s in sorted_skill_nodes:
            if s.has_embedding and s.embedding_vector is not None:
                skill_vecs.append(s.embedding_vector)
                skill_mask.append(True)
            else:
                skill_vecs.append([0.0] * EXPECTED_EMBEDDING_DIM)
                skill_mask.append(False)

        if num_skills > 0:
            pyg_data["skill"].x = torch.tensor(skill_vecs, dtype=torch.float32)
            pyg_data["skill"].has_embedding_mask = torch.tensor(skill_mask, dtype=torch.bool)
        else:
            pyg_data["skill"].x = torch.empty((0, EXPECTED_EMBEDDING_DIM), dtype=torch.float32)
            pyg_data["skill"].has_embedding_mask = torch.empty(0, dtype=torch.bool)

        # Evidence nodes
        num_ev = len(graph_data.evidence_nodes)
        pyg_data["evidence"].num_nodes = num_ev
        pyg_data["evidence"].node_ids = list(sorted(graph_data.evidence_nodes.keys()))
        ev_vecs = []
        ev_mask = []
        for nid in sorted(graph_data.evidence_nodes.keys()):
            ev = graph_data.evidence_nodes[nid]
            if ev.has_embedding and ev.embedding_vector is not None:
                ev_vecs.append(ev.embedding_vector)
                ev_mask.append(True)
            else:
                ev_vecs.append([0.0] * EXPECTED_EMBEDDING_DIM)
                ev_mask.append(False)

        if num_ev > 0:
            pyg_data["evidence"].x = torch.tensor(ev_vecs, dtype=torch.float32)
            pyg_data["evidence"].has_embedding_mask = torch.tensor(ev_mask, dtype=torch.bool)

        # Requirement nodes
        num_req = len(graph_data.requirement_nodes)
        pyg_data["requirement"].num_nodes = num_req
        pyg_data["requirement"].node_ids = list(sorted(graph_data.requirement_nodes.keys()))
        req_vecs = []
        req_mask = []
        for nid in sorted(graph_data.requirement_nodes.keys()):
            req = graph_data.requirement_nodes[nid]
            if req.has_embedding and req.embedding_vector is not None:
                req_vecs.append(req.embedding_vector)
                req_mask.append(True)
            else:
                req_vecs.append([0.0] * EXPECTED_EMBEDDING_DIM)
                req_mask.append(False)

        if num_req > 0:
            pyg_data["requirement"].x = torch.tensor(req_vecs, dtype=torch.float32)
            pyg_data["requirement"].has_embedding_mask = torch.tensor(req_mask, dtype=torch.bool)

        # 2. Edges
        # Group by (src_type, rel, dst_type)
        grouped_edges: Dict[Tuple[str, str, str], List[Tuple[int, int]]] = {}
        grouped_attrs: Dict[Tuple[str, str, str], List[float]] = {}

        for edge in graph_data.edges:
            rel_key = (edge.source_type, edge.edge_type, edge.target_type)
            u_idx = node_id_to_idx[edge.source_type][edge.source_id]
            v_idx = node_id_to_idx[edge.target_type][edge.target_id]
            grouped_edges.setdefault(rel_key, []).append((u_idx, v_idx))

            # Store similarity cosine as edge_attr for similar_to_candidate
            if edge.edge_type == "similar_to_candidate":
                grouped_attrs.setdefault(rel_key, []).append(
                    float(edge.attributes.get("cosine_similarity", 0.0))
                )

        for rel_key, pairs in grouped_edges.items():
            if pairs:
                src_indices = [p[0] for p in pairs]
                dst_indices = [p[1] for p in pairs]
                pyg_data[rel_key].edge_index = torch.tensor(
                    [src_indices, dst_indices], dtype=torch.long
                )
                if rel_key in grouped_attrs and len(grouped_attrs[rel_key]) == len(pairs):
                    pyg_data[rel_key].edge_attr = torch.tensor(
                        grouped_attrs[rel_key], dtype=torch.float32
                    ).unsqueeze(1)

        summary = {
            "graph_id": graph_data.graph_id,
            "node_types": list(pyg_data.node_types),
            "edge_types": [f"{s}__{r}__{d}" for s, r, d in pyg_data.edge_types],
            "num_nodes_by_type": {t: pyg_data[t].num_nodes for t in pyg_data.node_types},
            "num_edges_by_type": {
                f"{s}__{r}__{d}": int(pyg_data[s, r, d].edge_index.size(1))
                for s, r, d in pyg_data.edge_types
            },
            "total_nodes": sum(pyg_data[t].num_nodes for t in pyg_data.node_types),
            "total_edges": sum(int(pyg_data[s, r, d].edge_index.size(1)) for s, r, d in pyg_data.edge_types),
        }

        return pyg_data, node_id_to_idx, summary


# Global singleton instance
hetero_graph_builder = HeteroGraphBuilder()


def verify_subgraphs_dynamically(
    graph_data: HeteroGraphData,
    reasoning_results: Optional[List[SkillPairReasoningResult]] = None,
) -> Dict[str, Any]:
    """
    Programmatically inspects the constructed graph without hardcoded assertions.
    Validates existence, directionality, and provenance of representative subgraphs.
    """
    results: Dict[str, Any] = {}

    cv_skills_by_label = {
        s.original_label.strip(): s
        for s in graph_data.skill_nodes.values()
        if s.source_document == "CV"
    }
    jd_skills_by_label = {
        s.original_label.strip(): s
        for s in graph_data.skill_nodes.values()
        if s.source_document == "JD"
    }

    def find_edges(u: str, v: str) -> List[GraphEdge]:
        return [
            e
            for e in graph_data.edges
            if (e.source_id == u and e.target_id == v) or (e.source_id == v and e.target_id == u)
        ]

    # 1. React <-> React
    react_cv = cv_skills_by_label.get("React")
    react_jd = jd_skills_by_label.get("React")
    if react_cv and react_jd:
        edges = find_edges(react_cv.node_id, react_jd.node_id)
        equiv_edges = [e for e in edges if e.edge_type == "equivalent_to"]
        results["react_identity"] = {
            "cv_node_id": react_cv.node_id,
            "jd_node_id": react_jd.node_id,
            "edges_found": len(equiv_edges),
            "edge_type": equiv_edges[0].edge_type if equiv_edges else None,
            "resolution_method": equiv_edges[0].attributes.get("resolution_method") if equiv_edges else None,
            "verified": len(equiv_edges) >= 2,
        }
    else:
        results["react_identity"] = {"verified": False, "reason": "React nodes not found"}

    # 2. React <-> React Query
    rq_jd = jd_skills_by_label.get("React Query")
    if react_cv and rq_jd:
        edges = find_edges(react_cv.node_id, rq_jd.node_id)
        rel_edges = [e for e in edges if e.edge_type == "related_to"]
        results["react_react_query"] = {
            "cv_node_id": react_cv.node_id,
            "jd_node_id": rq_jd.node_id,
            "edges_found": len(rel_edges),
            "edge_type": rel_edges[0].edge_type if rel_edges else None,
            "relationship": rel_edges[0].attributes.get("relationship") if rel_edges else None,
            "verified": len(rel_edges) >= 1,
        }
    else:
        results["react_react_query"] = {"verified": False, "reason": "React or React Query nodes not found"}

    # 3. React <-> Zustand
    zustand_jd = jd_skills_by_label.get("Zustand")
    if react_cv and zustand_jd:
        edges = find_edges(react_cv.node_id, zustand_jd.node_id)
        rel_edges = [e for e in edges if e.edge_type == "related_to"]
        results["react_zustand"] = {
            "cv_node_id": react_cv.node_id,
            "jd_node_id": zustand_jd.node_id,
            "edges_found": len(rel_edges),
            "edge_type": rel_edges[0].edge_type if rel_edges else None,
            "relationship": rel_edges[0].attributes.get("relationship") if rel_edges else None,
            "verified": len(rel_edges) >= 1,
        }
    else:
        results["react_zustand"] = {"verified": False, "reason": "React or Zustand nodes not found"}

    # 4. TypeScript <-> TypeScript
    ts_cv = cv_skills_by_label.get("TypeScript")
    ts_jd = jd_skills_by_label.get("TypeScript")
    if ts_cv and ts_jd:
        edges = find_edges(ts_cv.node_id, ts_jd.node_id)
        equiv_edges = [e for e in edges if e.edge_type == "equivalent_to"]
        results["typescript_identity"] = {
            "cv_node_id": ts_cv.node_id,
            "jd_node_id": ts_jd.node_id,
            "edges_found": len(equiv_edges),
            "edge_type": equiv_edges[0].edge_type if equiv_edges else None,
            "resolution_method": equiv_edges[0].attributes.get("resolution_method") if equiv_edges else None,
            "verified": len(equiv_edges) >= 2,
        }
    else:
        results["typescript_identity"] = {"verified": False, "reason": "TypeScript nodes not found"}

    # 5. TypeScript <-> code review (Unrelated / candidate_only)
    cr_jd = jd_skills_by_label.get("code review")
    if ts_cv and cr_jd:
        edges = find_edges(ts_cv.node_id, cr_jd.node_id)
        semantic_edges = [
            e
            for e in edges
            if e.edge_type in ("equivalent_to", "related_to", "prerequisite_for", "specialization_of", "alternative_to")
        ]
        audit_match = [
            a
            for a in graph_data.rejected_audit
            if ("code review" in str(a.get("skill_b", "")) or "code review" in str(a.get("reason", "")))
        ]
        results["typescript_code_review_gating"] = {
            "cv_node_id": ts_cv.node_id,
            "jd_node_id": cr_jd.node_id,
            "semantic_edges_found": len(semantic_edges),
            "audit_entries_found": len(audit_match),
            "verified": len(semantic_edges) == 0,
        }
    else:
        results["typescript_code_review_gating"] = {
            "verified": True,
            "note": "Target node not present or already gated",
        }

    # 6. component architecture <-> Design System Implementation (Prerequisite)
    ca_cv = cv_skills_by_label.get("component architecture")
    dsi_jd = jd_skills_by_label.get("Design System Implementation")
    if ca_cv and dsi_jd:
        direct_edges = [
            e
            for e in graph_data.edges
            if e.source_id == ca_cv.node_id
            and e.target_id == dsi_jd.node_id
            and e.edge_type == "prerequisite_for"
        ]
        results["component_architecture_prerequisite"] = {
            "cv_node_id": ca_cv.node_id,
            "jd_node_id": dsi_jd.node_id,
            "prerequisite_edges_found": len(direct_edges),
            "direction": direct_edges[0].attributes.get("direction") if direct_edges else None,
            "verified": len(direct_edges) == 1,
        }
    else:
        results["component_architecture_prerequisite"] = {"verified": False, "reason": "Nodes not found"}

    # 7. Absence of synthetic / fabricated relations (e.g., Jest <-> Playwright alternative)
    jest_nodes = [s for s in graph_data.skill_nodes.values() if "jest" in s.original_label.lower()]
    playwright_nodes = [s for s in graph_data.skill_nodes.values() if "playwright" in s.original_label.lower()]
    synthetic_found = False
    if jest_nodes and playwright_nodes:
        edges = find_edges(jest_nodes[0].node_id, playwright_nodes[0].node_id)
        if any(e.attributes.get("relationship") == "alternative" for e in edges):
            synthetic_found = True
    results["synthetic_relation_check"] = {
        "synthetic_jest_playwright_detected": synthetic_found,
        "verified": not synthetic_found,
    }

    # 8. Provenance distribution across semantic edges
    semantic_edges = [
        e
        for e in graph_data.edges
        if e.edge_type in ("equivalent_to", "related_to", "prerequisite_for", "specialization_of", "alternative_to")
    ]
    prov_counts: Dict[str, int] = {}
    for e in semantic_edges:
        v_status = e.attributes.get("verification_status", "unknown")
        prov_counts[v_status] = prov_counts.get(v_status, 0) + 1

    results["semantic_provenance_summary"] = {
        "total_semantic_edges": len(semantic_edges),
        "verification_status_counts": prov_counts,
        "sanitized_provenance_audit_count": sum(
            1 for a in graph_data.rejected_audit if a.get("entity_type") == "provenance_sanitization"
        ),
        "ambiguous_mappings_count": sum(
            1 for a in graph_data.rejected_audit if a.get("entity_type") == "ambiguous_endpoint_mapping"
        ),
    }

    all_verified = all(
        v.get("verified", False) for k, v in results.items() if isinstance(v, dict) and "verified" in v
    )
    results["all_subgraphs_verified"] = all_verified
    return results
