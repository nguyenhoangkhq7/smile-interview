"""Schemas and configuration contracts for Paper-Aligned Bipartite Graph Construction and Hybrid GNN.

Reference:
Baghbanzadeh, A., & Wu, D. (2025). Resume-Job Compatibility Scoring Using Graph Neural Networks
and Large Language Models. ICIT 2025. https://doi.org/10.1145/3787330.3787359
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, Field

DecisionClassification = Literal[
    "PAPER_EXPLICIT",
    "IMPLEMENTATION_ASSUMPTION",
    "PROJECT_ADAPTATION",
]

MergePolicyType = Literal[
    "verified_equivalence",  # Default PROJECT_ADAPTATION / Extension C
    "paper_cosine_08",       # Experimental PAPER_EXPLICIT / Baseline B (cosine > 0.8)
    "canonical_only",        # Strict canonical ID / verified alias match only
]

DocumentInitStrategy = Literal[
    "random_seeded",     # PAPER_EXPLICIT (Fig. 3): randomly initialized document embeddings
    "random_unit_norm",  # IMPLEMENTATION_ASSUMPTION: L2-normalized seeded random vector
    "zeros",             # Ablation baseline: zero vector initialization
]

EdgeWeightNormalization = Literal[
    "raw_table3",   # Raw numeric values from Table 3 (1.0 .. 10.0)
    "scaled_0_1",   # Scaled by / 10.0 into [0.0, 1.0] for numerical stability
]

ProficiencySide = Literal["CV_DEMONSTRATED", "JD_REQUIRED"]

ProficiencyMappingSource = Literal[
    "paper_table3_explicit",
    "paper_table6_7_assumption",
    "missing",
]

SkillMembership = Literal["resume_only", "job_only", "shared"]


class ProficiencyRecord(BaseModel):
    """Structured proficiency record for a document-to-skill edge (Section 3.4, Table 3)."""

    side: ProficiencySide = Field(..., description="Whether this edge represents CV demonstrated or JD required proficiency")
    raw_descriptor: Optional[str] = Field(
        default=None,
        description="Verbatim proficiency descriptor extracted from text (e.g., 'Strong', 'Proficient'), or None if missing",
    )
    numeric_level: Optional[float] = Field(
        default=None,
        description="Numeric value mapped from Table 3 (1..10), or None when proficiency is missing ('-' in Table 7)",
    )
    normalized_weight: Optional[float] = Field(
        default=None,
        description="Normalized weight in [0.0, 1.0] (numeric_level / 10.0) when present, else None",
    )
    is_missing: bool = Field(
        default=True,
        description="True when no proficiency modifier is grounded in the source text",
    )
    mapping_source: ProficiencyMappingSource = Field(
        default="missing",
        description="Origin of the numeric mapping: 'paper_table3_explicit', 'paper_table6_7_assumption', or 'missing'",
    )
    extraction_method: str = Field(
        default="missing",
        description="How the descriptor was obtained: 'explicit_modifier_field', 'context_window_regex', 'provided_override', or 'missing'",
    )
    provenance_sentence: Optional[str] = Field(
        default=None,
        description="Verbatim sentence from which the proficiency descriptor was extracted",
    )
    decision_class: DecisionClassification = Field(
        default="PAPER_EXPLICIT",
        description="Scientific classification of this proficiency mapping",
    )


class SkillInputItem(BaseModel):
    """Normalized input skill entity from either CV or JD prior to bipartite graph construction."""

    occurrence_id: str = Field(..., description="Unique occurrence identifier from upstream extraction")
    canonical_skill_id: str = Field(..., description="Normalized canonical skill slug")
    surface_name: str = Field(..., description="Original surface phrase as extracted from document")
    source_document: Literal["CV", "JD"] = Field(..., description="Originating document ('CV' or 'JD')")
    extraction_type: Literal["explicit", "implicit"] = Field(
        default="explicit",
        description="Whether skill was explicitly mentioned or implicitly inferred",
    )
    category: Optional[str] = Field(default=None, description="Skill category if available")
    kind: Optional[str] = Field(default="skill", description="Entity kind ('skill', 'domain', 'certification', 'context')")
    evidence_sentences: List[str] = Field(
        default_factory=list,
        description="Verbatim evidence or requirement sentences supporting this skill",
    )
    evidence_offsets: List[Dict[str, Optional[int]]] = Field(
        default_factory=list,
        description="Character offset spans [{'start': int, 'end': int}] in source document",
    )
    modifier_text: Optional[str] = Field(
        default=None,
        description="Explicit modifier qualifier if extracted upstream (e.g. 'Strong', 'Basic')",
    )
    proficiency_override: Optional[str] = Field(
        default=None,
        description="Optional explicit descriptor override for controlled synthetic tests",
    )
    embedding_ref: Optional[str] = Field(
        default=None,
        description="Reference ID of the Stage 3 SBERT vector",
    )
    embedding_vector: Optional[List[float]] = Field(
        default=None,
        description="L2-normalized embedding vector (768D SBERT by default)",
    )
    metadata: Dict[str, Any] = Field(default_factory=dict)


class MergeAuditRecord(BaseModel):
    """Audit record explaining why a CV skill and JD skill were merged or kept separate (Section 4.3)."""

    cv_occurrence_ids: List[str] = Field(default_factory=list)
    jd_occurrence_ids: List[str] = Field(default_factory=list)
    cv_canonical_id: str = Field(...)
    jd_canonical_id: str = Field(...)
    cv_surface_names: List[str] = Field(default_factory=list)
    jd_surface_names: List[str] = Field(default_factory=list)
    cosine_similarity: Optional[float] = Field(
        default=None,
        description="Cosine similarity between CV and JD skill embeddings (metadata, never conflated with proficiency)",
    )
    llm_identity: Optional[str] = Field(default=None, description="Upstream LLM identity decision if evaluated")
    llm_relationship: Optional[str] = Field(default=None, description="Upstream LLM semantic relationship if evaluated")
    llm_graph_status: Optional[str] = Field(default=None, description="Upstream LLM graph relation status")
    merged: bool = Field(..., description="True if merged into a shared skill node, False if kept separate")
    merge_reason: str = Field(
        ...,
        description="Deterministic rule that triggered or blocked merging (e.g., 'same_canonical_id', 'verified_alias', 'verified_llm_equivalent', 'paper_cosine_gt_08', 'blocked_confusable_distinct_skills', 'blocked_non_equivalent_relation', 'below_similarity_threshold')",
    )
    policy_used: MergePolicyType = Field(...)
    decision_class: DecisionClassification = Field(...)


class PaperAlignedDocumentNode(BaseModel):
    """Document node ('resume' or 'job') in the paper-aligned bipartite graph (Figure 3)."""

    node_id: str = Field(..., description="Unique node ID ('resume_0' or 'job_0')")
    node_type: Literal["resume", "job"] = Field(..., description="Document node type")
    document_id: str = Field(..., description="Source document filename or identifier")
    source_hash: Optional[str] = Field(default=None, description="SHA-256 hash of document text")
    init_strategy: DocumentInitStrategy = Field(
        default="random_seeded",
        description="Initialization strategy applied to document embedding",
    )
    random_seed: int = Field(..., description="Explicit random seed used for initialization")
    embedding_dim: int = Field(..., description="Feature vector dimensionality")
    embedding_vector: List[float] = Field(..., description="Initialized feature vector")
    decision_class: DecisionClassification = Field(default="PAPER_EXPLICIT")


class PaperAlignedSkillNode(BaseModel):
    """Skill entity node in the paper-aligned bipartite graph (Figures 4 & 5)."""

    node_id: str = Field(..., description="Unique deterministic skill node ID")
    node_type: Literal["skill"] = "skill"
    canonical_skill_id: str = Field(..., description="Primary canonical skill identifier")
    cv_canonical_id: Optional[str] = Field(default=None, description="Canonical ID from CV if present")
    jd_canonical_id: Optional[str] = Field(default=None, description="Canonical ID from JD if present")
    surface_names: List[str] = Field(default_factory=list, description="All surface forms across CV and/or JD")
    cv_surface_names: List[str] = Field(default_factory=list, description="Surface forms appearing in CV")
    jd_surface_names: List[str] = Field(default_factory=list, description="Surface forms appearing in JD")
    source_documents: List[Literal["CV", "JD"]] = Field(
        ...,
        description="Documents containing this skill: ['CV'], ['JD'], or ['CV', 'JD'] for shared skills",
    )
    membership: SkillMembership = Field(
        ...,
        description="'resume_only' (unique to CV), 'job_only' (unique to JD), or 'shared' (in both CV and JD)",
    )
    cv_occurrence_ids: List[str] = Field(default_factory=list)
    jd_occurrence_ids: List[str] = Field(default_factory=list)
    cv_extraction_type: Optional[Literal["explicit", "implicit"]] = Field(default=None)
    jd_extraction_type: Optional[Literal["explicit", "implicit"]] = Field(default=None)
    cv_evidences: List[str] = Field(default_factory=list, description="Verbatim CV evidence sentences")
    jd_evidences: List[str] = Field(default_factory=list, description="Verbatim JD requirement/evidence sentences")
    cv_evidence_offsets: List[Dict[str, Optional[int]]] = Field(default_factory=list)
    jd_evidence_offsets: List[Dict[str, Optional[int]]] = Field(default_factory=list)
    embedding_refs: List[str] = Field(default_factory=list, description="Upstream Stage 3 vector IDs")
    embedding_dim: int = Field(..., description="Dimensionality of the attached SBERT embedding")
    embedding_vector: List[float] = Field(..., description="Feature vector for this skill entity")
    embedding_combination: str = Field(
        default="single_source",
        description="'single_source', 'identical_vectors', or 'l2_normalized_mean'",
    )
    cosine_similarity_if_shared: Optional[float] = Field(
        default=None,
        description="Cosine similarity between CV and JD skill vectors when merged (metadata only)",
    )
    merge_decision: MergeAuditRecord = Field(..., description="Audit record for how this entity was formed")


class CompetencyLineageRecord(BaseModel):
    """Auditable data lineage record for every skill evaluated during Stage 5 graph ingestion."""

    source_side: Literal["CV", "JD"] = Field(..., description="Document source: 'CV' or 'JD'")
    occurrence_id: str = Field(..., description="Unique occurrence ID in the document")
    canonical_id: str = Field(..., description="Canonical skill identifier")
    surface_phrase: str = Field(..., description="Original surface form extracted from document")
    kind: Optional[str] = Field(default=None, description="Original entity kind (skill, context, domain, certification)")
    category: Optional[str] = Field(default=None, description="Taxonomy category")
    evidence_text: Optional[str] = Field(default=None, description="Source sentence evidence anchor")
    original_granularity: str = Field(..., description="Assigned competency granularity")
    retention_decision: Literal["RETAINED", "EXCLUDED"] = Field(..., description="Final graph inclusion decision")
    reason_code: str = Field(..., description="Standardized auditable decision reason code")
    decision_source: str = Field(..., description="Rule, regex, evidence analysis, or manual configuration")
    is_graph_node: bool = Field(default=False, description="Whether this record became an entity node in the graph")
    is_membership: bool = Field(default=False, description="Whether this record formed a document-skill edge")


class PaperAlignedBipartiteEdge(BaseModel):
    """Directed bipartite edge between a document node ('resume'/'job') and an entity node ('skill')."""

    edge_id: str = Field(..., description="Unique edge identifier")
    source_type: Literal["resume", "job", "skill"] = Field(...)
    edge_type: Literal["has_skill", "requires_skill", "in_resume", "required_by_job"] = Field(...)
    target_type: Literal["resume", "job", "skill"] = Field(...)
    source_id: str = Field(...)
    target_id: str = Field(...)
    is_reverse_edge: bool = Field(
        default=False,
        description="False for document->entity edges, True for entity->document reverse message-passing edges",
    )
    proficiency: ProficiencyRecord = Field(..., description="Proficiency metadata and numeric mapping")
    tensor_weight: float = Field(
        ...,
        description="Numeric scalar weight placed in PyG edge_attr according to normalization policy",
    )


class PaperAlignedGraphIntegrityReport(BaseModel):
    """Comprehensive validation report for all 12 graph integrity invariants (Section 4.6)."""

    is_valid: bool = Field(...)
    exactly_one_resume_and_one_job: bool = Field(default=True)
    no_unintended_doc_doc_or_skill_skill_edges: bool = Field(default=True)
    every_entity_belongs_to_at_least_one_doc: bool = Field(default=True)
    shared_entities_connect_to_both_docs: bool = Field(default=True)
    unique_entities_connect_to_single_doc: bool = Field(default=True)
    valid_proficiency_or_explicitly_missing: bool = Field(default=True)
    no_nan_or_inf_features: bool = Field(default=True)
    correct_feature_shapes: bool = Field(default=True)
    correct_edge_indices_and_directions: bool = Field(default=True)
    correct_reverse_edges: bool = Field(default=True)
    no_accidental_confusable_merges: bool = Field(default=True)
    node_counts: Dict[str, int] = Field(default_factory=dict)
    edge_counts: Dict[str, int] = Field(default_factory=dict)
    shared_skill_count: int = Field(default=0)
    resume_only_skill_count: int = Field(default=0)
    job_only_skill_count: int = Field(default=0)
    errors: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)


@dataclass
class PaperAlignedGraphConfig:
    """Configuration for building a paper-aligned bipartite Resume-Job graph."""

    merge_policy: MergePolicyType = "verified_equivalence"
    graph_policy: Literal["policy_a_legacy", "policy_b_semantic"] = "policy_a_legacy"
    paper_cosine_threshold: float = 0.80
    enforce_confusable_guardrails_in_cosine_mode: bool = False
    doc_init_strategy: DocumentInitStrategy = "random_seeded"
    random_seed: int = 42
    embedding_dim: int = 768
    allow_paper_table6_7_descriptors: bool = True
    edge_weight_normalization: EdgeWeightNormalization = "scaled_0_1"
    missing_proficiency_tensor_weight: float = 0.0
    include_reverse_edges: bool = True
    filter_context_non_competencies: bool = True
    filter_unsupported_implicit: bool = True


class PaperAlignedGraphData(BaseModel):
    """Complete in-memory paper-aligned bipartite graph for a single Resume-Job pair."""

    graph_id: str = Field(...)
    pair_id: Optional[str] = Field(default=None)
    run_id: str = Field(default="paper_aligned_run")
    merge_policy: MergePolicyType = Field(...)
    graph_policy: Literal["policy_a_legacy", "policy_b_semantic"] = Field(default="policy_a_legacy")
    edge_weight_normalization: EdgeWeightNormalization = Field(...)
    missing_proficiency_tensor_weight: float = Field(default=0.0)
    embedding_dim: int = Field(default=768)
    resume_node: PaperAlignedDocumentNode = Field(...)
    job_node: PaperAlignedDocumentNode = Field(...)
    skill_nodes: Dict[str, PaperAlignedSkillNode] = Field(default_factory=dict)
    education_nodes: Dict[str, Any] = Field(
        default_factory=dict,
        description="Empty in skill-only adaptation (PROJECT_ADAPTATION); never fabricated",
    )
    experience_nodes: Dict[str, Any] = Field(
        default_factory=dict,
        description="Empty in skill-only adaptation (PROJECT_ADAPTATION); never fabricated",
    )
    edges: List[PaperAlignedBipartiteEdge] = Field(default_factory=list)
    merge_audit: List[MergeAuditRecord] = Field(
        default_factory=list,
        description="Audit trail for every shared entity merge and evaluated candidate pair",
    )
    integrity_report: Optional[PaperAlignedGraphIntegrityReport] = Field(default=None)
    diagnostics: Dict[str, Any] = Field(default_factory=dict)
