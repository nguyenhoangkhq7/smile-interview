"""Comprehensive Unit & Integrity Tests for Phase 1: Paper-Aligned Bipartite Graph Construction.

Verifies:
1. Shared skill graph (100% overlap).
2. No-overlap graph (0% overlap, all CV-unique and JD-unique skills preserved).
3. Partial-overlap graph (Figure 5 structure: shared + CV-unique + JD-unique).
4. Verified alias merging (React <-> ReactJS, K8s <-> Kubernetes) & LLM equivalence merging.
5. Explicit non-merge tests for confusable & related skills:
   - React <-> React Query
   - Java <-> JavaScript
   - Redis <-> Redux
   - Docker <-> Kubernetes
   - C <-> C++ / C#
   - related / prerequisite / specialization / uncertain relations
6. Paper-exact cosine > 0.8 experimental variant ('paper_cosine_08') vs default ('verified_equivalence').
7. Table 3 proficiency weights, clause-level modifier disambiguation, and missing proficiency ('-').
8. Distinct CV demonstrated proficiency vs JD required proficiency on shared skill nodes.
9. Empty or minimal skill sets.
10. Bipartite edge directions, reverse edges, and absence of skill-skill / doc-doc edges.
11. Deterministic graph construction and seeded document initialization.
"""
from __future__ import annotations

import math
from typing import List
import numpy as np
import pytest
import torch

from matching_cv.app.schemas.semantic_reasoning import SkillPairReasoningResult, SkillRef
from matching_cv.research.paper_aligned_gnn.graph_builder import (
    PaperAlignedGraphBuilder,
    generate_reproducible_document_embedding,
)
from matching_cv.research.paper_aligned_gnn.proficiency_extractor import (
    PAPER_TABLE3_EXPLICIT_MAPPING,
    extract_skill_proficiency,
    map_descriptor_to_proficiency,
)
from matching_cv.research.paper_aligned_gnn.schemas import (
    PaperAlignedGraphConfig,
    SkillInputItem,
)


def _make_unit_vec(dim: int, hot_idx: int, secondary_idx: int = -1, sec_weight: float = 0.0) -> List[float]:
    v = np.zeros(dim, dtype=np.float32)
    v[hot_idx % dim] = 1.0
    if secondary_idx >= 0:
        v[secondary_idx % dim] += sec_weight
    norm = float(np.linalg.norm(v))
    if norm > 0:
        v = v / norm
    return [float(x) for x in v]


# ---------------------------------------------------------------------------
# 1. Shared Skill Graph (All skills shared)
# ---------------------------------------------------------------------------
def test_shared_skill_graph():
    dim = 16
    cfg = PaperAlignedGraphConfig(embedding_dim=dim, random_seed=101, edge_weight_normalization="raw_table3")
    builder = PaperAlignedGraphBuilder(cfg)

    cv_items = [
        SkillInputItem(
            occurrence_id="cv_py",
            canonical_skill_id="python",
            surface_name="Python",
            source_document="CV",
            evidence_sentences=["Strong expertise in Python backend development."],
            embedding_vector=_make_unit_vec(dim, 0),
        ),
        SkillInputItem(
            occurrence_id="cv_git",
            canonical_skill_id="git",
            surface_name="Git",
            source_document="CV",
            evidence_sentences=["Proficient in Git version control."],
            embedding_vector=_make_unit_vec(dim, 1),
        ),
    ]
    jd_items = [
        SkillInputItem(
            occurrence_id="jd_py",
            canonical_skill_id="python",
            surface_name="Python",
            source_document="JD",
            evidence_sentences=["Intermediate Python skills required."],
            embedding_vector=_make_unit_vec(dim, 0),
        ),
        SkillInputItem(
            occurrence_id="jd_git",
            canonical_skill_id="git",
            surface_name="Git",
            source_document="JD",
            evidence_sentences=["Basic Knowledge in Git."],
            embedding_vector=_make_unit_vec(dim, 1),
        ),
    ]

    graph, report = builder.build_graph_from_items(cv_items, jd_items, pair_id="test_shared")
    assert report.is_valid
    assert report.shared_skill_count == 2
    assert report.resume_only_skill_count == 0
    assert report.job_only_skill_count == 0

    pyg, _, summary = builder.export_to_pyg(graph)
    assert summary["shared_skills"] == 2
    assert pyg[("resume", "has_skill", "skill")].edge_index.shape == (2, 2)
    assert pyg[("job", "requires_skill", "skill")].edge_index.shape == (2, 2)
    assert pyg[("skill", "in_resume", "resume")].edge_index.shape == (2, 2)
    assert pyg[("skill", "required_by_job", "job")].edge_index.shape == (2, 2)


# ---------------------------------------------------------------------------
# 2. No-Overlap Graph (Disjoint CV and JD skills)
# ---------------------------------------------------------------------------
def test_no_overlap_graph():
    dim = 16
    cfg = PaperAlignedGraphConfig(embedding_dim=dim, random_seed=42)
    builder = PaperAlignedGraphBuilder(cfg)

    cv_items = [
        SkillInputItem(
            occurrence_id="cv_1",
            canonical_skill_id="python",
            surface_name="Python",
            source_document="CV",
            evidence_sentences=["Expert in Python."],
            embedding_vector=_make_unit_vec(dim, 0),
        ),
        SkillInputItem(
            occurrence_id="cv_2",
            canonical_skill_id="fastapi",
            surface_name="FastAPI",
            source_document="CV",
            evidence_sentences=["Skilled in FastAPI."],
            embedding_vector=_make_unit_vec(dim, 1),
        ),
    ]
    jd_items = [
        SkillInputItem(
            occurrence_id="jd_1",
            canonical_skill_id="rust",
            surface_name="Rust",
            source_document="JD",
            evidence_sentences=["Strong in Rust."],
            embedding_vector=_make_unit_vec(dim, 5),
        ),
        SkillInputItem(
            occurrence_id="jd_2",
            canonical_skill_id="kubernetes",
            surface_name="Kubernetes",
            source_document="JD",
            evidence_sentences=["Experienced in Kubernetes."],
            embedding_vector=_make_unit_vec(dim, 6),
        ),
    ]

    graph, report = builder.build_graph_from_items(cv_items, jd_items, pair_id="test_no_overlap")
    assert report.is_valid
    assert report.shared_skill_count == 0
    assert report.resume_only_skill_count == 2
    assert report.job_only_skill_count == 2
    assert len(graph.skill_nodes) == 4


# ---------------------------------------------------------------------------
# 3. Partial-Overlap Graph (Paper Figure 5 Topology)
# ---------------------------------------------------------------------------
def test_partial_overlap_paper_figure5_topology():
    """
    Mirrors Figure 5 of Baghbanzadeh & Wu (2025):
    - Shared skills: Git, TS (connected to both Job and CV)
    - Job-unique skills: Python, NodeJS, VueJS (connected only to Job)
    - CV-unique skills: SQL, MongoDB, Express (connected only to CV)
    """
    dim = 16
    cfg = PaperAlignedGraphConfig(embedding_dim=dim, random_seed=7)
    builder = PaperAlignedGraphBuilder(cfg)

    cv_items = [
        SkillInputItem(occurrence_id="c1", canonical_skill_id="git", surface_name="Git", source_document="CV", evidence_sentences=["Proficient in Git"]),
        SkillInputItem(occurrence_id="c2", canonical_skill_id="typescript", surface_name="TS", source_document="CV", evidence_sentences=["Strong TS skills"]),
        SkillInputItem(occurrence_id="c3", canonical_skill_id="sql", surface_name="SQL", source_document="CV", evidence_sentences=["Experienced in SQL"]),
        SkillInputItem(occurrence_id="c4", canonical_skill_id="mongodb", surface_name="MongoDB", source_document="CV", evidence_sentences=["Intermediate MongoDB"]),
        SkillInputItem(occurrence_id="c5", canonical_skill_id="express", surface_name="Express", source_document="CV", evidence_sentences=["Skilled in Express"]),
    ]
    jd_items = [
        SkillInputItem(occurrence_id="j1", canonical_skill_id="git", surface_name="Git", source_document="JD", evidence_sentences=["Basic Git"]),
        SkillInputItem(occurrence_id="j2", canonical_skill_id="typescript", surface_name="TypeScript", source_document="JD", evidence_sentences=["Expert TypeScript"]),
        SkillInputItem(occurrence_id="j3", canonical_skill_id="python", surface_name="Python", source_document="JD", evidence_sentences=["Strong Python"]),
        SkillInputItem(occurrence_id="j4", canonical_skill_id="nodejs", surface_name="NodeJS", source_document="JD", evidence_sentences=["Proficient NodeJS"]),
        SkillInputItem(occurrence_id="j5", canonical_skill_id="vue", surface_name="VueJS", source_document="JD", evidence_sentences=["Beginner VueJS"]),
    ]

    graph, report = builder.build_graph_from_items(cv_items, jd_items, pair_id="fig5")
    assert report.is_valid
    assert report.shared_skill_count == 2       # Git, TypeScript
    assert report.resume_only_skill_count == 3  # SQL, MongoDB, Express
    assert report.job_only_skill_count == 3     # Python, NodeJS, VueJS
    assert len(graph.skill_nodes) == 8          # 2 shared + 3 CV-only + 3 JD-only (not 10!)


# ---------------------------------------------------------------------------
# 4 & 5. Aliases vs Confusable Non-Equivalent Skills (Mandatory Explicit Tests)
# ---------------------------------------------------------------------------
def test_aliases_merge_and_confusable_skills_stay_separate():
    """
    Explicitly tests Section 4.3 rules:
    - React <-> ReactJS: shared node (verified alias -> 'react')
    - React <-> React Query: separate nodes (even if cosine = 0.92!)
    - Java <-> JavaScript: separate nodes (even if cosine = 0.89!)
    - Redis <-> Redux: separate nodes (even if cosine = 0.88!)
    - Docker <-> Kubernetes: separate nodes (even if LLM says 'related' and cosine = 0.86!)
    - C <-> C++ / C#: separate nodes (even if cosine = 0.91!)
    """
    dim = 16
    cfg = PaperAlignedGraphConfig(
        merge_policy="verified_equivalence",
        embedding_dim=dim,
        random_seed=42,
    )
    builder = PaperAlignedGraphBuilder(cfg)

    # Give confusable pairs artificially high cosine similarity (> 0.88) to prove
    # verified_equivalence does NOT blindly merge them!
    v_react = _make_unit_vec(dim, 0)
    v_react_query = _make_unit_vec(dim, 0, 1, 0.25)  # cosine ~ 0.97 with v_react!
    v_java = _make_unit_vec(dim, 2)
    v_javascript = _make_unit_vec(dim, 2, 3, 0.25)   # cosine ~ 0.97 with v_java!
    v_redis = _make_unit_vec(dim, 4)
    v_redux = _make_unit_vec(dim, 4, 5, 0.25)        # cosine ~ 0.97 with v_redis!
    v_docker = _make_unit_vec(dim, 6)
    v_k8s = _make_unit_vec(dim, 6, 7, 0.25)           # cosine ~ 0.97 with v_docker!
    v_c = _make_unit_vec(dim, 8)
    v_cpp = _make_unit_vec(dim, 8, 9, 0.20)           # cosine ~ 0.98 with v_c!
    v_csharp = _make_unit_vec(dim, 8, 10, 0.20)       # cosine ~ 0.98 with v_c!

    cv_items = [
        SkillInputItem(occurrence_id="cv_react", canonical_skill_id="react", surface_name="React", source_document="CV", embedding_vector=v_react),
        SkillInputItem(occurrence_id="cv_java", canonical_skill_id="java", surface_name="Java", source_document="CV", embedding_vector=v_java),
        SkillInputItem(occurrence_id="cv_redis", canonical_skill_id="redis", surface_name="Redis", source_document="CV", embedding_vector=v_redis),
        SkillInputItem(occurrence_id="cv_docker", canonical_skill_id="docker", surface_name="Docker", source_document="CV", embedding_vector=v_docker),
        SkillInputItem(occurrence_id="cv_c", canonical_skill_id="c", surface_name="C", source_document="CV", embedding_vector=v_c),
    ]
    jd_items = [
        SkillInputItem(occurrence_id="jd_reactjs", canonical_skill_id="reactjs", surface_name="ReactJS", source_document="JD", embedding_vector=v_react),
        SkillInputItem(occurrence_id="jd_rq", canonical_skill_id="react-query", surface_name="React Query", source_document="JD", embedding_vector=v_react_query),
        SkillInputItem(occurrence_id="jd_js", canonical_skill_id="javascript", surface_name="JavaScript", source_document="JD", embedding_vector=v_javascript),
        SkillInputItem(occurrence_id="jd_redux", canonical_skill_id="redux", surface_name="Redux", source_document="JD", embedding_vector=v_redux),
        SkillInputItem(occurrence_id="jd_k8s", canonical_skill_id="kubernetes", surface_name="Kubernetes", source_document="JD", embedding_vector=v_k8s),
        SkillInputItem(occurrence_id="jd_cpp", canonical_skill_id="c++", surface_name="C++", source_document="JD", embedding_vector=v_cpp),
        SkillInputItem(occurrence_id="jd_csharp", canonical_skill_id="c#", surface_name="C#", source_document="JD", embedding_vector=v_csharp),
    ]

    # Also pass LLM reasoning results classifying Docker <-> Kubernetes as 'related' and React <-> React Query as 'specialization'
    reasoning_results = [
        SkillPairReasoningResult(
            skill_a=SkillRef(skill_id="docker", name="Docker", source="CV"),
            skill_b=SkillRef(skill_id="kubernetes", name="Kubernetes", source="JD"),
            identity="distinct",
            relationship="related",
            direction="bidirectional",
            reasoning_summary="Docker and Kubernetes are used together in container orchestration.",
            model_id="test",
            graph_relation_status="eligible",
            source_occurrence_ids=["cv_docker", "jd_k8s"],
        ),
        SkillPairReasoningResult(
            skill_a=SkillRef(skill_id="react", name="React", source="CV"),
            skill_b=SkillRef(skill_id="react-query", name="React Query", source="JD"),
            identity="distinct",
            relationship="prerequisite",
            direction="a_to_b",
            reasoning_summary="React is a prerequisite for React Query.",
            model_id="test",
            graph_relation_status="eligible",
            source_occurrence_ids=["cv_react", "jd_rq"],
        ),
    ]

    graph, report = builder.build_graph_from_items(
        cv_items=cv_items,
        jd_items=jd_items,
        reasoning_results=reasoning_results,
        pair_id="test_confusables",
    )

    assert report.is_valid
    assert report.no_accidental_confusable_merges

    # ONLY React <-> ReactJS should be merged into a shared skill node!
    assert report.shared_skill_count == 1
    shared_nodes = [n for n in graph.skill_nodes.values() if n.membership == "shared"]
    assert len(shared_nodes) == 1
    assert shared_nodes[0].canonical_skill_id == "react"
    assert set(shared_nodes[0].surface_names) == {"React", "ReactJS"}

    # All 4 other CV skills (java, redis, docker, c) must remain resume_only
    assert report.resume_only_skill_count == 4
    cv_only_canons = {n.canonical_skill_id for n in graph.skill_nodes.values() if n.membership == "resume_only"}
    assert cv_only_canons == {"java", "redis", "docker", "c"}

    # All 6 other JD skills (react-query, javascript, redux, kubernetes, c++, c#) must remain job_only
    assert report.job_only_skill_count == 6
    jd_only_canons = {n.canonical_skill_id for n in graph.skill_nodes.values() if n.membership == "job_only"}
    assert jd_only_canons == {"react-query", "javascript", "redux", "kubernetes", "c++", "c#"}


def test_verified_llm_equivalence_merge_and_non_equivalent_blocking():
    """
    Verify that a genuine LLM-verified equivalence ('identity=equivalent', 'graph_relation_status=eligible')
    between non-confusable skills merges them under 'verified_equivalence', whereas 'prerequisite',
    'specialization', 'related', and 'uncertain' do NOT merge.
    """
    dim = 16
    cfg = PaperAlignedGraphConfig(merge_policy="verified_equivalence", embedding_dim=dim)
    builder = PaperAlignedGraphBuilder(cfg)

    cv_items = [
        SkillInputItem(occurrence_id="cv_1", canonical_skill_id="message-queuing", surface_name="Message Queuing", source_document="CV", embedding_vector=_make_unit_vec(dim, 0)),
        SkillInputItem(occurrence_id="cv_2", canonical_skill_id="python", surface_name="Python", source_document="CV", embedding_vector=_make_unit_vec(dim, 1)),
    ]
    jd_items = [
        SkillInputItem(occurrence_id="jd_1", canonical_skill_id="message-brokers", surface_name="Message Brokers", source_document="JD", embedding_vector=_make_unit_vec(dim, 0, 1, 0.1)),
        SkillInputItem(occurrence_id="jd_2", canonical_skill_id="django", surface_name="Django", source_document="JD", embedding_vector=_make_unit_vec(dim, 1, 2, 0.1)),
    ]

    reasoning = [
        SkillPairReasoningResult(
            skill_a=SkillRef(skill_id="message-queuing", name="Message Queuing", source="CV"),
            skill_b=SkillRef(skill_id="message-brokers", name="Message Brokers", source="JD"),
            identity="equivalent",
            relationship=None,
            direction="bidirectional",
            reasoning_summary="Equivalent competency in distributed messaging.",
            model_id="test",
            graph_relation_status="eligible",
            source_occurrence_ids=["cv_1", "jd_1"],
        ),
        SkillPairReasoningResult(
            skill_a=SkillRef(skill_id="python", name="Python", source="CV"),
            skill_b=SkillRef(skill_id="django", name="Django", source="JD"),
            identity="distinct",
            relationship="prerequisite",
            direction="a_to_b",
            reasoning_summary="Python is prerequisite for Django.",
            model_id="test",
            graph_relation_status="eligible",
            source_occurrence_ids=["cv_2", "jd_2"],
        ),
    ]

    graph, report = builder.build_graph_from_items(cv_items, jd_items, reasoning_results=reasoning)
    assert report.is_valid
    assert report.shared_skill_count == 1
    assert report.resume_only_skill_count == 1
    assert report.job_only_skill_count == 1


# ---------------------------------------------------------------------------
# 6. Paper-Exact Cosine > 0.8 Variant ('paper_cosine_08')
# ---------------------------------------------------------------------------
def test_paper_cosine_08_experimental_variant():
    dim = 16
    v1 = _make_unit_vec(dim, 0)
    v2 = _make_unit_vec(dim, 0, 1, 0.3)  # cosine = 1 / sqrt(1 + 0.09) = 0.9578 > 0.80
    v3 = _make_unit_vec(dim, 5)          # cosine = 0.0 <= 0.80

    cv_items = [
        SkillInputItem(occurrence_id="cv_a", canonical_skill_id="data-analysis", surface_name="Data Analysis", source_document="CV", embedding_vector=v1),
    ]
    jd_items = [
        SkillInputItem(occurrence_id="jd_a", canonical_skill_id="analytical-modeling", surface_name="Analytical Modeling", source_document="JD", embedding_vector=v2),
        SkillInputItem(occurrence_id="jd_b", canonical_skill_id="cybersecurity", surface_name="Cybersecurity", source_document="JD", embedding_vector=v3),
    ]

    # Under default 'verified_equivalence', Data Analysis and Analytical Modeling are NOT merged without verification
    default_builder = PaperAlignedGraphBuilder(PaperAlignedGraphConfig(merge_policy="verified_equivalence", embedding_dim=dim))
    g_def, _ = default_builder.build_graph_from_items(cv_items, jd_items)
    assert g_def.diagnostics["shared_skills_count"] == 0

    # Under 'paper_cosine_08', cosine 0.9578 > 0.80 merges them as a PAPER_EXPLICIT variant
    paper_builder = PaperAlignedGraphBuilder(PaperAlignedGraphConfig(merge_policy="paper_cosine_08", embedding_dim=dim))
    g_pap, rep_pap = paper_builder.build_graph_from_items(cv_items, jd_items)
    assert rep_pap.is_valid
    assert g_pap.diagnostics["shared_skills_count"] == 1
    shared_node = [n for n in g_pap.skill_nodes.values() if n.membership == "shared"][0]
    assert shared_node.merge_decision.merge_reason == "paper_cosine_gt_08"
    assert shared_node.merge_decision.decision_class == "PAPER_EXPLICIT"


# ---------------------------------------------------------------------------
# 7 & 8. Proficiency Extraction, Table 3 Mapping, Missingness, CV vs JD Proficiency
# ---------------------------------------------------------------------------
def test_table3_proficiency_mapping_and_missingness():
    expected_table3 = {
        "Basic": 1.0,
        "Beginner": 3.0,
        "Intermediate": 4.0,
        "Proficient": 5.0,
        "Skilled": 6.0,
        "Accomplished": 7.0,
        "Experienced": 8.0,
        "Expert": 9.0,
        "Strong": 10.0,
    }
    for desc, level in expected_table3.items():
        rec = map_descriptor_to_proficiency(desc, side="CV_DEMONSTRATED")
        assert not rec.is_missing
        assert rec.numeric_level == level
        assert rec.raw_descriptor == desc
        assert rec.mapping_source == "paper_table3_explicit"
        assert rec.decision_class == "PAPER_EXPLICIT"

    # Missing proficiency ('-' in Paper Table 7 or None)
    for missing_input in (None, "", "-", "N/A"):
        m_rec = map_descriptor_to_proficiency(missing_input, side="JD_REQUIRED")
        assert m_rec.is_missing
        assert m_rec.numeric_level is None
        assert m_rec.normalized_weight is None
        assert m_rec.mapping_source == "missing"


def test_different_cv_and_jd_proficiency_on_shared_skill_and_clause_disambiguation():
    """
    Tests:
    1. Clause disambiguation when two skills appear in the same sentence with different modifiers:
       'Strong expertise in Python, and Basic knowledge in SQL.'
    2. Shared skill node carrying different CV demonstrated proficiency vs JD required proficiency,
       plus missing proficiency on JD skill ('-' in Table 7).
    """
    dim = 16
    cfg = PaperAlignedGraphConfig(
        embedding_dim=dim,
        edge_weight_normalization="raw_table3",
        missing_proficiency_tensor_weight=0.0,
    )
    builder = PaperAlignedGraphBuilder(cfg)

    shared_sentence = "Strong expertise in Python, and Basic knowledge in SQL."
    cv_items = [
        SkillInputItem(
            occurrence_id="cv_py",
            canonical_skill_id="python",
            surface_name="Python",
            source_document="CV",
            evidence_sentences=[shared_sentence],
            embedding_vector=_make_unit_vec(dim, 0),
        ),
        SkillInputItem(
            occurrence_id="cv_sql",
            canonical_skill_id="sql",
            surface_name="SQL",
            source_document="CV",
            evidence_sentences=[shared_sentence],
            embedding_vector=_make_unit_vec(dim, 1),
        ),
    ]
    jd_items = [
        SkillInputItem(
            occurrence_id="jd_py",
            canonical_skill_id="python",
            surface_name="Python",
            source_document="JD",
            evidence_sentences=["Required: Python for data pipelines."],  # No proficiency modifier!
            embedding_vector=_make_unit_vec(dim, 0),
        ),
        SkillInputItem(
            occurrence_id="jd_sql",
            canonical_skill_id="sql",
            surface_name="SQL",
            source_document="JD",
            evidence_sentences=["Intermediate SQL skills required."],    # Intermediate = 4.0
            embedding_vector=_make_unit_vec(dim, 1),
        ),
    ]

    graph, report = builder.build_graph_from_items(cv_items, jd_items)
    assert report.is_valid
    assert report.shared_skill_count == 2

    # Inspect forward edges
    fwd_edges = {(e.source_type, e.target_id): e for e in graph.edges if not e.is_reverse_edge}
    py_node_id = [nid for nid, n in graph.skill_nodes.items() if n.canonical_skill_id == "python"][0]
    sql_node_id = [nid for nid, n in graph.skill_nodes.items() if n.canonical_skill_id == "sql"][0]

    # Python: CV = Strong (10.0), JD = Missing (None, tensor_weight = 0.0)
    cv_py_edge = fwd_edges[("resume", py_node_id)]
    jd_py_edge = fwd_edges[("job", py_node_id)]
    assert not cv_py_edge.proficiency.is_missing
    assert cv_py_edge.proficiency.raw_descriptor == "Strong"
    assert cv_py_edge.proficiency.numeric_level == 10.0
    assert cv_py_edge.tensor_weight == 10.0

    assert jd_py_edge.proficiency.is_missing
    assert jd_py_edge.proficiency.numeric_level is None
    assert jd_py_edge.tensor_weight == 0.0

    # SQL: CV = Basic (1.0), JD = Intermediate (4.0)
    cv_sql_edge = fwd_edges[("resume", sql_node_id)]
    jd_sql_edge = fwd_edges[("job", sql_node_id)]
    assert cv_sql_edge.proficiency.raw_descriptor == "Basic"
    assert cv_sql_edge.proficiency.numeric_level == 1.0
    assert jd_sql_edge.proficiency.raw_descriptor == "Intermediate"
    assert jd_sql_edge.proficiency.numeric_level == 4.0


# ---------------------------------------------------------------------------
# 9. Empty or Minimal Skill Sets
# ---------------------------------------------------------------------------
def test_empty_and_single_skill_sets():
    dim = 16
    builder = PaperAlignedGraphBuilder(PaperAlignedGraphConfig(embedding_dim=dim))

    # Completely empty CV and JD skill sets
    g_empty, rep_empty = builder.build_graph_from_items([], [], pair_id="empty")
    assert rep_empty.is_valid
    assert len(g_empty.skill_nodes) == 0
    assert len(g_empty.edges) == 0
    pyg_empty, _, sum_empty = builder.export_to_pyg(g_empty)
    assert pyg_empty["resume"].x.shape == (1, dim)
    assert pyg_empty["job"].x.shape == (1, dim)
    assert pyg_empty["skill"].x.shape == (0, dim)
    assert sum_empty["shared_skills"] == 0

    # Single CV skill, 0 JD skills
    g_one, rep_one = builder.build_graph_from_items(
        [SkillInputItem(occurrence_id="c1", canonical_skill_id="python", surface_name="Python", source_document="CV")],
        [],
        pair_id="one_cv",
    )
    assert rep_one.is_valid
    assert rep_one.resume_only_skill_count == 1
    assert rep_one.job_only_skill_count == 0


# ---------------------------------------------------------------------------
# 10 & 11. Deterministic Graph Construction & Reproducible Seeded Init
# ---------------------------------------------------------------------------
def test_deterministic_graph_construction_and_seeded_init():
    dim = 32
    cfg1 = PaperAlignedGraphConfig(embedding_dim=dim, random_seed=12345)
    cfg2 = PaperAlignedGraphConfig(embedding_dim=dim, random_seed=12345)
    cfg_diff = PaperAlignedGraphConfig(embedding_dim=dim, random_seed=99999)

    items_cv = [
        SkillInputItem(occurrence_id="c2", canonical_skill_id="docker", surface_name="Docker", source_document="CV", evidence_sentences=["Skilled in Docker"]),
        SkillInputItem(occurrence_id="c1", canonical_skill_id="python", surface_name="Python", source_document="CV", evidence_sentences=["Strong in Python"]),
    ]
    items_jd = [
        SkillInputItem(occurrence_id="j1", canonical_skill_id="python", surface_name="Python", source_document="JD", evidence_sentences=["Expert in Python"]),
    ]

    g1, _ = PaperAlignedGraphBuilder(cfg1).build_graph_from_items(items_cv, items_jd)
    g2, _ = PaperAlignedGraphBuilder(cfg2).build_graph_from_items(list(reversed(items_cv)), items_jd)
    g3, _ = PaperAlignedGraphBuilder(cfg_diff).build_graph_from_items(items_cv, items_jd)

    assert g1.resume_node.embedding_vector == g2.resume_node.embedding_vector
    assert g1.job_node.embedding_vector == g2.job_node.embedding_vector
    assert g1.resume_node.embedding_vector != g1.job_node.embedding_vector
    assert g1.resume_node.embedding_vector != g3.resume_node.embedding_vector
    assert list(g1.skill_nodes.keys()) == list(g2.skill_nodes.keys())
    assert [e.edge_id for e in g1.edges] == [e.edge_id for e in g2.edges]
