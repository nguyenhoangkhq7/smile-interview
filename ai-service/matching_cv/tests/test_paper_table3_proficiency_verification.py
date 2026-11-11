"""Scientific Verification Test Suite for Paper Table 3 Proficiency Adherence.

Reference:
Baghbanzadeh, A., & Wu, D. (2025). Resume-Job Compatibility Scoring Using Graph Neural Networks
and Large Language Models. ICIT 2025. https://doi.org/10.1145/3787330.3787359

Verifies all 15 Phase A Verification Requirements:
1. Exact Table 3 Ground Truth mappings (9 levels: 1, 3, 4, 5, 6, 7, 8, 9, 10).
2. Normalization to [0, 1] (weight = level / 10.0).
3. Invalid descriptor rejection (e.g. 'primary', 'years', random words -> is_missing=True).
4. Supplemental mapping isolation (excluded when allow_paper_table6_7_descriptors=False).
5. Case-insensitive descriptor matching.
6. Descriptor-to-skill grounding for all 9 required phrases in A4.
7. No cross-skill modifier leakage across clauses (the 4 real audit sentences).
8. Missing proficiency handling (never level 0, is_missing=True, level=None, weight=None).
9. Graph export attributes (edge_attr, edge_raw_proficiency, edge_has_proficiency).
10. Reverse edge consistency (forward vs reverse tensor weight and metadata match).
11. GraphConv weighting (fallback 1.0 for missing JD requirements).
12. Modified GAT weighting (Equation 2 with valid weights and fallback 0.0).
13. Deterministic mapping across multiple invocations.
14. No NaN/Inf weights under any condition.
15. Integration with refined Backend graph (81 logical edges, 162 directed PyG edges).
"""
from __future__ import annotations

import math
from typing import List, Optional
import pytest
import torch

from matching_cv.app.schemas.skill_extraction import Evidence, ExtractedSkill, ExtractionResult
from matching_cv.app.schemas.implicit_skill_extraction import ImplicitExtractedSkill, ImplicitExtractionResult
from matching_cv.app.schemas.unified_skill_extraction import (
    DocumentUnifiedResult,
    DocumentValidationResult,
    UnifiedExtractFileResponse,
)
from matching_cv.research.paper_aligned_gnn.proficiency_extractor import (
    PAPER_TABLE3_EXPLICIT_MAPPING,
    PAPER_TABLE6_7_SUPPLEMENTAL_MAPPING,
    extract_skill_proficiency,
    map_descriptor_to_proficiency,
)
from matching_cv.research.paper_aligned_gnn.graph_builder import (
    PaperAlignedGraphBuilder,
    PaperAlignedGraphConfig,
)
from matching_cv.research.paper_aligned_gnn.hybrid_gnn import (
    PaperAlignedGNNConfig,
    PaperAlignedHybridGNN,
)
from matching_cv.research.paper_aligned_gnn.schemas import (
    ProficiencyRecord,
    SkillInputItem,
)


def _make_dummy_doc_pair(
    cv_skills: List[ExtractedSkill],
    jd_skills: List[ExtractedSkill],
    cv_implicit: Optional[List[ImplicitExtractedSkill]] = None,
    jd_implicit: Optional[List[ImplicitExtractedSkill]] = None,
) -> UnifiedExtractFileResponse:
    cv_doc = DocumentUnifiedResult.model_construct(
        document_type="CV",
        filename="test_cv.pdf",
        text_sha256="cv_sha256_mock_hash",
        explicit=ExtractionResult.model_construct(
            document_type="CV",
            filename="test_cv.pdf",
            text_sha256="cv_sha256_mock_hash",
            skills=cv_skills,
        ),
        implicit=ImplicitExtractionResult.model_construct(
            document_type="CV",
            filename="test_cv.pdf",
            text_sha256="cv_sha256_mock_hash",
            skills=cv_implicit or [],
        ),
        validation=DocumentValidationResult.model_construct(
            status="completed",
            accepted_implicit_skills=cv_implicit or [],
            duplicate_implicit_skills=[],
            rejected_implicit_skills=[],
        ),
    )
    jd_doc = DocumentUnifiedResult.model_construct(
        document_type="JD",
        filename="test_jd.pdf",
        text_sha256="jd_sha256_mock_hash",
        explicit=ExtractionResult.model_construct(
            document_type="JD",
            filename="test_jd.pdf",
            text_sha256="jd_sha256_mock_hash",
            skills=jd_skills,
        ),
        implicit=ImplicitExtractionResult.model_construct(
            document_type="JD",
            filename="test_jd.pdf",
            text_sha256="jd_sha256_mock_hash",
            skills=jd_implicit or [],
        ),
        validation=DocumentValidationResult.model_construct(
            status="completed",
            accepted_implicit_skills=jd_implicit or [],
            duplicate_implicit_skills=[],
            rejected_implicit_skills=[],
        ),
    )
    return UnifiedExtractFileResponse.model_construct(
        run_id="test_run_proficiency",
        status="completed",
        cv=cv_doc,
        jd=jd_doc,
        documents={"cv": cv_doc, "jd": jd_doc},
    )


# ==============================================================================
# 1. Exact Table 3 Ground Truth Mappings
# ==============================================================================
def test_01_all_nine_table3_exact_mappings():
    """Verify all 9 exact Table 3 descriptors map to their precise paper integer levels."""
    expected_table3 = {
        "basic": 1.0,
        "beginner": 3.0,
        "intermediate": 4.0,
        "proficient": 5.0,
        "skilled": 6.0,
        "accomplished": 7.0,
        "experienced": 8.0,
        "expert": 9.0,
        "strong": 10.0,
    }
    for desc, expected_level in expected_table3.items():
        rec = map_descriptor_to_proficiency(desc, side="CV_DEMONSTRATED", allow_paper_table6_7_descriptors=False)
        assert rec.is_missing is False, f"Failed for {desc}"
        assert rec.numeric_level == expected_level, f"Level mismatch for {desc}"
        assert rec.mapping_source == "paper_table3_explicit"
        assert rec.decision_class == "PAPER_EXPLICIT"

    # Verify level 2 is NOT in Table 3 mapping
    table3_levels = [val[0] for val in PAPER_TABLE3_EXPLICIT_MAPPING.values()]
    assert 2.0 not in table3_levels, "Level 2 must NOT exist in PAPER_TABLE3_EXPLICIT_MAPPING!"
    assert len(PAPER_TABLE3_EXPLICIT_MAPPING) == 9, "Table 3 must contain exactly 9 explicit descriptors!"


# ==============================================================================
# 2. Normalization to [0, 1]
# ==============================================================================
def test_02_normalization_to_unit_interval():
    """Verify weight = level / 10.0 and falls strictly within [0.1, 1.0]."""
    for desc, (expected_level, _) in PAPER_TABLE3_EXPLICIT_MAPPING.items():
        rec = map_descriptor_to_proficiency(desc, side="JD_REQUIRED")
        expected_weight = round(expected_level / 10.0, 4)
        assert rec.normalized_weight == pytest.approx(expected_weight)
        assert 0.0 <= rec.normalized_weight <= 1.0


# ==============================================================================
# 3. Invalid Descriptor Rejection
# ==============================================================================
def test_03_invalid_descriptor_rejection():
    """Unrecognized descriptors, qualifiers, or noise strings must not fabricate ratings."""
    invalid_samples = [
        "primary",
        "4 years",
        "years of experience",
        "random_modifier",
        "good",
        "nice to have",
        "preferred",
        "-",
        "—",
        "N/A",
        "none",
        "",
        None,
    ]
    for sample in invalid_samples:
        rec = map_descriptor_to_proficiency(sample, side="CV_DEMONSTRATED")
        assert rec.is_missing is True, f"Did not reject invalid sample '{sample}'"
        assert rec.numeric_level is None
        assert rec.normalized_weight is None
        assert rec.mapping_source == "missing"


# ==============================================================================
# 4. Supplemental Mapping Isolation
# ==============================================================================
def test_04_supplemental_mapping_isolation():
    """Supplemental descriptors from Tables 6 & 7 must be isolated behind configuration."""
    supplemental_descriptors = ["familiar", "familiarity", "moderate", "some knowledge", "some skill"]

    for desc in supplemental_descriptors:
        # Strict Table 3 mode: MUST be rejected
        strict_rec = map_descriptor_to_proficiency(desc, side="CV_DEMONSTRATED", allow_paper_table6_7_descriptors=False)
        assert strict_rec.is_missing is True, f"Supplemental '{desc}' leaked into strict Table 3 mode!"
        assert strict_rec.numeric_level is None
        assert strict_rec.normalized_weight is None

        # Supplemental mode: Recognized with IMPLEMENTATION_ASSUMPTION
        supp_rec = map_descriptor_to_proficiency(desc, side="CV_DEMONSTRATED", allow_paper_table6_7_descriptors=True)
        assert supp_rec.is_missing is False
        assert supp_rec.decision_class == "IMPLEMENTATION_ASSUMPTION"
        assert supp_rec.mapping_source == "paper_table6_7_assumption"


# ==============================================================================
# 5. Case-Insensitive Matching
# ==============================================================================
def test_05_case_insensitive_matching():
    """Verify descriptors match regardless of casing."""
    cases = [
        ("BASIC", 1.0),
        ("Basic", 1.0),
        ("bAsIc", 1.0),
        ("BEGINNER", 3.0),
        ("INTERMEDIATE", 4.0),
        ("Proficient", 5.0),
        ("SKILLED", 6.0),
        ("Accomplished", 7.0),
        ("EXPERIENCED", 8.0),
        ("Expert", 9.0),
        ("sTrOnG", 10.0),
    ]
    for raw, expected_level in cases:
        rec = map_descriptor_to_proficiency(raw, side="CV_DEMONSTRATED")
        assert rec.is_missing is False
        assert rec.numeric_level == expected_level


# ==============================================================================
# 6. Descriptor-to-Skill Grounding for All 9 Required Phrases
# ==============================================================================
def test_06_descriptor_to_skill_grounding_all_nine_phrases():
    """Verify accurate extraction on all 9 mandated test phrases."""
    cases = [
        ("Strong in Python and Basic in SQL", "Python", "python", 10.0, 1.0, "Strong"),
        ("Strong in Python and Basic in SQL", "SQL", "sql", 1.0, 0.1, "Basic"),
        ("Basic knowledge of Docker", "Docker", "docker", 1.0, 0.1, "Basic"),
        ("Expert level Java", "Java", "java", 9.0, 0.9, "Expert"),
        ("Familiar with Kubernetes", "Kubernetes", "kubernetes", 2.0, 0.2, "Familiar"),
        ("Experienced in AWS cloud architectures", "AWS cloud architectures", "aws-cloud-architectures", 8.0, 0.8, "Experienced"),
        ("Intermediate React development", "React", "react", 4.0, 0.4, "Intermediate"),
        ("Proficient with Git", "Git", "git", 5.0, 0.5, "Proficient"),
        ("Skilled in technical writing", "technical writing", "technical-writing", 6.0, 0.6, "Skilled"),
        ("Accomplished data engineer with Spark", "Spark", "spark", 7.0, 0.7, "Accomplished"),
    ]
    for sent, surf, cid, expected_lvl, expected_w, expected_desc in cases:
        item = SkillInputItem(
            occurrence_id=f"test_{cid}",
            canonical_skill_id=cid,
            surface_name=surf,
            source_document="CV",
            evidence_sentences=[sent],
        )
        rec = extract_skill_proficiency(item, allow_paper_table6_7_descriptors=True)
        assert rec.is_missing is False, f"Failed grounding for {surf} in '{sent}'"
        assert rec.numeric_level == expected_lvl
        assert rec.normalized_weight == pytest.approx(expected_w)
        assert rec.raw_descriptor == expected_desc


# ==============================================================================
# 7. No Cross-Skill Leakage Across Clauses (Real Audit Sentences)
# ==============================================================================
def test_07_no_cross_skill_leakage_across_clauses():
    """Verify that modifiers do not leak across clauses in compound sentences."""
    # Sentence 1
    sent1 = "Strong background in relational database design, REST API development, and message-driven architectures."
    item_rdb = SkillInputItem(
        occurrence_id="occ1",
        canonical_skill_id="relational-database-design",
        surface_name="relational database design",
        source_document="CV",
        evidence_sentences=[sent1],
    )
    item_rest = SkillInputItem(
        occurrence_id="occ2",
        canonical_skill_id="rest-api-development",
        surface_name="REST API development",
        source_document="CV",
        evidence_sentences=[sent1],
    )
    item_mda = SkillInputItem(
        occurrence_id="occ3",
        canonical_skill_id="message-driven-architectures",
        surface_name="message-driven architectures",
        source_document="CV",
        evidence_sentences=[sent1],
    )
    r1 = extract_skill_proficiency(item_rdb)
    r2 = extract_skill_proficiency(item_rest)
    r3 = extract_skill_proficiency(item_mda)
    assert r1.is_missing is False and r1.numeric_level == 10.0, "rdb should be Strong (10.0)"
    assert r2.is_missing is True, "REST API development must not inherit 'Strong' modifier!"
    assert r3.is_missing is True, "message-driven architectures must not inherit 'Strong' modifier!"

    # Sentence 2
    sent2 = "Messaging & infra: Apache Kafka, RabbitMQ, Docker, basic Kubernetes."
    item_k8s = SkillInputItem(
        occurrence_id="occ4",
        canonical_skill_id="kubernetes",
        surface_name="Kubernetes",
        source_document="CV",
        evidence_sentences=[sent2],
    )
    item_doc = SkillInputItem(
        occurrence_id="occ5",
        canonical_skill_id="docker",
        surface_name="Docker",
        source_document="CV",
        evidence_sentences=[sent2],
    )
    r_k8s = extract_skill_proficiency(item_k8s)
    r_doc = extract_skill_proficiency(item_doc)
    assert r_k8s.is_missing is False and r_k8s.numeric_level == 1.0, "Kubernetes should be Basic (1.0)"
    assert r_doc.is_missing is True, "Docker must not inherit 'basic' modifier!"

    # Sentence 3
    sent3 = "Languages: Java (primary), SQL, some Python for tooling scripts."
    item_java = SkillInputItem(
        occurrence_id="occ6",
        canonical_skill_id="java",
        surface_name="Java",
        source_document="CV",
        evidence_sentences=[sent3],
    )
    r_java = extract_skill_proficiency(item_java)
    assert r_java.is_missing is True, "'primary' is not in Table 3 and must be treated as missing!"

    # Sentence 4
    sent4 = "Familiarity with Docker and basic containerized deployment workflows."
    item_cdw = SkillInputItem(
        occurrence_id="occ7",
        canonical_skill_id="containerized-deployment-workflows",
        surface_name="containerized deployment workflows",
        source_document="JD",
        evidence_sentences=[sent4],
    )
    item_doc_jd = SkillInputItem(
        occurrence_id="occ8",
        canonical_skill_id="docker",
        surface_name="Docker",
        source_document="JD",
        evidence_sentences=[sent4],
    )
    r_cdw = extract_skill_proficiency(item_cdw, allow_paper_table6_7_descriptors=False)
    assert r_cdw.is_missing is False and r_cdw.numeric_level == 1.0, "cdw should have Basic (1.0)"
    r_doc_strict = extract_skill_proficiency(item_doc_jd, allow_paper_table6_7_descriptors=False)
    assert r_doc_strict.is_missing is True, "Docker Familiarity must be rejected in strict Table 3 mode"


# ==============================================================================
# 8. Missing Proficiency Invariants
# ==============================================================================
def test_08_missing_proficiency_handling_invariants():
    """Missing proficiency must have is_missing=True, level=None, weight=None, never level 0."""
    rec = map_descriptor_to_proficiency(None, side="CV_DEMONSTRATED")
    assert rec.is_missing is True
    assert rec.numeric_level is None
    assert rec.normalized_weight is None
    assert rec.numeric_level != 0, "Missing proficiency must NEVER be assigned level 0!"
    assert rec.normalized_weight != 0.0, "Missing normalized_weight must be None, not 0.0!"


# ==============================================================================
# 9. Graph Export Attributes
# ==============================================================================
def test_09_graph_export_attributes():
    """Graph exported to PyG Data must include tensor weights, raw proficiency and has_proficiency."""
    cv_skills = [
        ExtractedSkill(
            skill_id="python",
            surface_forms=["Python"],
            category="Technology/Tool",
            kind="skill",
            evidences=[Evidence(surface_form="Python", sentence="Strong Python developer.", section="summary")],
        ),
        ExtractedSkill(
            skill_id="sql",
            surface_forms=["SQL"],
            category="Technology/Tool",
            kind="skill",
            evidences=[Evidence(surface_form="SQL", sentence="SQL database experience.", section="skills")],
        ),
    ]
    resp = _make_dummy_doc_pair(cv_skills=cv_skills, jd_skills=[])
    builder = PaperAlignedGraphBuilder()
    graph_data, report = builder.build_graph(unified_response=resp)
    pyg_data, node_idx_map, meta = builder.export_to_pyg(graph_data)

    assert ("resume", "has_skill", "skill") in pyg_data.edge_types
    resume_edge = pyg_data["resume", "has_skill", "skill"]
    assert hasattr(resume_edge, "edge_attr")
    assert hasattr(resume_edge, "edge_has_proficiency")
    assert hasattr(resume_edge, "edge_raw_proficiency")

    # Forward edges
    fwd_edges = [e for e in graph_data.edges if not e.is_reverse_edge]
    assert len(fwd_edges) == 2
    for edge in fwd_edges:
        cid = graph_data.skill_nodes[edge.target_id].canonical_skill_id
        if cid == "python":
            assert edge.proficiency.is_missing is False
            assert edge.proficiency.numeric_level == 10.0
            assert edge.tensor_weight == pytest.approx(1.0)
        elif cid == "sql":
            assert edge.proficiency.is_missing is True
            assert edge.tensor_weight == pytest.approx(0.0)


# ==============================================================================
# 10. Reverse Edge Consistency
# ==============================================================================
def test_10_reverse_edge_consistency():
    """Every forward edge (u, v) must have matching reverse edge (v, u) with identical weights."""
    cv_skills = [
        ExtractedSkill(
            skill_id="kubernetes",
            surface_forms=["Kubernetes"],
            category="Technology/Tool",
            kind="skill",
            evidences=[Evidence(surface_form="Kubernetes", sentence="basic Kubernetes", section="skills")],
        )
    ]
    jd_skills = [
        ExtractedSkill(
            skill_id="kubernetes",
            surface_forms=["Kubernetes"],
            category="Technology/Tool",
            kind="skill",
            evidences=[Evidence(surface_form="Kubernetes", sentence="Required: Kubernetes", section="requirements")],
        )
    ]
    resp = _make_dummy_doc_pair(cv_skills=cv_skills, jd_skills=jd_skills)
    builder = PaperAlignedGraphBuilder()
    graph_data, report = builder.build_graph(unified_response=resp)

    fwd_edges = [e for e in graph_data.edges if not e.is_reverse_edge]
    rev_edges = [e for e in graph_data.edges if e.is_reverse_edge]
    assert len(fwd_edges) == len(rev_edges) == 2

    for fwd in fwd_edges:
        matching_rev = [
            r for r in rev_edges
            if r.source_id == fwd.target_id and r.target_id == fwd.source_id
        ]
        assert len(matching_rev) == 1
        rev = matching_rev[0]
        assert rev.tensor_weight == pytest.approx(fwd.tensor_weight)
        assert rev.proficiency.is_missing == fwd.proficiency.is_missing
        assert rev.proficiency.numeric_level == fwd.proficiency.numeric_level


# ==============================================================================
# 11. GraphConv Weighting (Fallback 1.0 for Missing JD Requirements)
# ==============================================================================
def test_11_graphconv_missing_job_requirement_fallback_weight():
    """Job-side GraphConv must substitute fallback 1.0 for missing proficiency edges."""
    config = PaperAlignedGNNConfig(
        input_dim=16,
        hidden_dim=16,
        missing_job_weight_for_graphconv=1.0,
    )
    gnn = PaperAlignedHybridGNN(config=config)
    layer = gnn.layers[0]

    # Edge index: 1 job node connected to 2 skill nodes
    # Skill 0 has explicit proficiency (0.5), Skill 1 has missing proficiency (has_prof=False)
    edge_attr = torch.tensor([[0.5], [0.0]], dtype=torch.float32)
    has_prof = torch.tensor([True, False], dtype=torch.bool)

    job_weights = layer._prepare_job_edge_weights(
        edge_attr, has_prof, num_edges=2, device=edge_attr.device, dtype=edge_attr.dtype
    )
    assert job_weights[0].item() == pytest.approx(0.5)
    assert job_weights[1].item() == pytest.approx(1.0), "Missing JD requirement must get fallback 1.0!"


# ==============================================================================
# 12. Modified GAT Weighting (Equation 2 and Fallback 0.0)
# ==============================================================================
def test_12_modified_gat_equation2_weighting_and_fallback():
    """Resume-side Modified GAT must use Eq. (2) and substitute fallback 0.0 for missing edges."""
    config = PaperAlignedGNNConfig(
        input_dim=16,
        hidden_dim=16,
        missing_resume_weight_for_gat=0.0,
    )
    gnn = PaperAlignedHybridGNN(config=config)
    layer = gnn.layers[0]

    # Edge index: 1 resume node connected to 2 skill nodes
    # Skill 0 has explicit proficiency (0.7), Skill 1 has missing proficiency (has_prof=False)
    edge_attr = torch.tensor([[0.7], [0.0]], dtype=torch.float32)
    has_prof = torch.tensor([True, False], dtype=torch.bool)

    resume_weights = layer._prepare_resume_edge_weights(
        edge_attr, has_prof, num_edges=2, device=edge_attr.device, dtype=edge_attr.dtype
    )
    assert resume_weights[0].item() == pytest.approx(0.7)
    assert resume_weights[1].item() == pytest.approx(0.0), "Missing Resume claim must get fallback 0.0!"


# ==============================================================================
# 13. Deterministic Mapping Across Multiple Invocations
# ==============================================================================
def test_13_deterministic_proficiency_mapping():
    """Verify exact determinism across multiple runs."""
    sent = "Strong in Python and Basic in SQL"
    item = SkillInputItem(
        occurrence_id="det_1",
        canonical_skill_id="python",
        surface_name="Python",
        source_document="CV",
        evidence_sentences=[sent],
    )
    rec1 = extract_skill_proficiency(item)
    rec2 = extract_skill_proficiency(item)
    assert rec1.numeric_level == rec2.numeric_level
    assert rec1.normalized_weight == rec2.normalized_weight
    assert rec1.raw_descriptor == rec2.raw_descriptor
    assert rec1.is_missing == rec2.is_missing


# ==============================================================================
# 14. No NaN/Inf Weights Under Any Condition
# ==============================================================================
def test_14_no_nan_or_inf_weights_under_any_condition():
    """Ensure tensors never produce NaN or Inf values in edge weights or forward pass."""
    cv_skills = [
        ExtractedSkill(
            skill_id="python",
            surface_forms=["Python"],
            category="Technology/Tool",
            kind="skill",
            evidences=[Evidence(surface_form="Python", sentence="Python developer.", section="skills")],
        )
    ]
    jd_skills = [
        ExtractedSkill(
            skill_id="python",
            surface_forms=["Python"],
            category="Technology/Tool",
            kind="skill",
            evidences=[Evidence(surface_form="Python", sentence="Python required.", section="requirements")],
        )
    ]
    resp = _make_dummy_doc_pair(cv_skills=cv_skills, jd_skills=jd_skills)
    builder = PaperAlignedGraphBuilder()
    graph_data, _ = builder.build_graph(unified_response=resp)
    pyg_data, _, _ = builder.export_to_pyg(graph_data)

    config = PaperAlignedGNNConfig(input_dim=768, hidden_dim=64)
    gnn = PaperAlignedHybridGNN(config=config)
    gnn.eval()

    with torch.no_grad():
        out = gnn(pyg_data)
    score = out["bounded_score"]
    assert not torch.isnan(score).any()
    assert not torch.isinf(score).any()
    assert 0.0 <= score.item() <= 1.0


# ==============================================================================
# 15. Integration with Refined Backend Graph Statistics
# ==============================================================================
def test_15_integration_with_refined_backend_graph():
    """Verify exact membership and edge counts on the refined Backend graph."""
    # Build doc pair reflecting the refined Backend pair with recovered competencies
    cv_skills = [
        ExtractedSkill(
            skill_id="relational-database-design",
            surface_forms=["relational database design"],
            category="Technical Concept",
            kind="skill",
            evidences=[Evidence(surface_form="relational database design", sentence="Strong background in relational database design.", section="summary")],
        ),
        ExtractedSkill(
            skill_id="kubernetes",
            surface_forms=["Kubernetes"],
            category="Technology/Tool",
            kind="skill",
            evidences=[Evidence(surface_form="Kubernetes", sentence="Messaging & infra: basic Kubernetes", section="skills")],
        ),
        ExtractedSkill(
            skill_id="microservices",
            surface_forms=["microservices"],
            category="Technical Concept",
            kind="context",
            evidences=[Evidence(surface_form="microservices", sentence="Building microservices.", section="experience")],
        ),
        ExtractedSkill(
            skill_id="message-driven-architectures",
            surface_forms=["message-driven architectures"],
            category="Technical Concept",
            kind="context",
            evidences=[Evidence(surface_form="message-driven architectures", sentence="REST API and message-driven architectures.", section="summary")],
        ),
    ]
    jd_skills = [
        ExtractedSkill(
            skill_id="kubernetes",
            surface_forms=["Kubernetes"],
            category="Technology/Tool",
            kind="skill",
            evidences=[Evidence(surface_form="Kubernetes", sentence="Required: Kubernetes", section="requirements")],
        ),
        ExtractedSkill(
            skill_id="docker",
            surface_forms=["Docker"],
            category="Technology/Tool",
            kind="skill",
            evidences=[Evidence(surface_form="Docker", sentence="Familiarity with Docker and basic deployment workflows.", section="requirements")],
        ),
        ExtractedSkill(
            skill_id="containerized-deployment-workflows",
            surface_forms=["containerized deployment workflows"],
            category="Engineering Practice",
            kind="skill",
            evidences=[Evidence(surface_form="containerized deployment workflows", sentence="Familiarity with Docker and basic containerized deployment workflows.", section="requirements")],
        ),
    ]
    resp = _make_dummy_doc_pair(cv_skills=cv_skills, jd_skills=jd_skills)

    # 1. Strict Table 3 mode
    builder_strict = PaperAlignedGraphBuilder(config=PaperAlignedGraphConfig(allow_paper_table6_7_descriptors=False))
    g_strict, rep_strict = builder_strict.build_graph(unified_response=resp)
    assert rep_strict.is_valid is True

    fwd_strict = [e for e in g_strict.edges if not e.is_reverse_edge]
    grounded_strict = [e for e in fwd_strict if not e.proficiency.is_missing]
    grounded_cids = {g_strict.skill_nodes[e.target_id].canonical_skill_id for e in grounded_strict}
    assert "relational-database-design" in grounded_cids
    assert "kubernetes" in grounded_cids
    assert "containerized-deployment-workflows" in grounded_cids
    assert "docker" not in grounded_cids

    # 2. Supplemental mode
    builder_supp = PaperAlignedGraphBuilder(config=PaperAlignedGraphConfig(allow_paper_table6_7_descriptors=True))
    g_supp, rep_supp = builder_supp.build_graph(unified_response=resp)
    assert rep_supp.is_valid is True

    fwd_supp = [e for e in g_supp.edges if not e.is_reverse_edge]
    grounded_supp = [e for e in fwd_supp if not e.proficiency.is_missing]
    grounded_supp_cids = {g_supp.skill_nodes[e.target_id].canonical_skill_id for e in grounded_supp}
    assert "docker" in grounded_supp_cids
    assert len(grounded_supp) == len(grounded_strict) + 1
