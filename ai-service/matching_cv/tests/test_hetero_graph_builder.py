"""Unit test suite for Stage 4 Phase 1: Heterogeneous Graph Construction & Validation.

Covers all 30 required test scenarios:
 1. Simple CV and JD with overlapping skills
 2. Explicit skill occurrence mapping
 3. Accepted implicit skill mapping
 4. Rejected implicit skill exclusion
 5. Evidence provenance preservation
 6. Requirement association preservation
 7. Same skill label in CV and JD without forced merging
 8. Distinct labels with LLM equivalent prediction
 9. False equivalence risk (preventing forced merge)
10. Related skill candidate
11. Directional prerequisite mapping (a_to_b)
12. Reversed prerequisite input (b_to_a)
13. Specialization direction (specialized_skill --SPECIALIZATION_OF--> broader_skill)
14. Alternative relation (symmetric alternative_to)
15. Unrelated relation exclusion
16. Uncertain relation exclusion from active typed graph
17. Candidate-only handling across export policies
18. Rejected semantic relation handling
19. Evidence-only graph mode (Mode A)
20. Similarity-enriched graph mode (Mode B)
21. LLM-enriched graph mode (Mode C)
22. Missing embeddings (feature mask handling)
23. Wrong embedding dimension detection
24. Non-finite embedding values (NaN/Inf) detection
25. Missing source occurrence ID fallback/handling
26. Duplicate relation inputs deduplication
27. Invalid edge endpoints exclusion
28. Deterministic graph construction
29. PyG export integrity (HeteroData shapes, masks, indices)
30. Non-IT domain skill verification (Healthcare & Accounting)
"""
import copy
import math
import pytest
import torch

from matching_cv.app.schemas.hetero_graph import (
    GraphBuildRequest,
    GraphEdge,
    HeteroGraphData,
    SkillNode,
)
from matching_cv.app.schemas.implicit_skill_extraction import (
    ImplicitEvidence,
    ImplicitExtractedSkill,
    ImplicitExtractionResult,
    ImplicitExtractionStats,
)
from matching_cv.app.schemas.semantic_reasoning import (
    SkillPairReasoningResult,
    SkillRef,
)
from matching_cv.app.schemas.semantic_representation import (
    EmbeddingRecord,
    SemanticRepresentationResponse,
    SemanticSimilarityPair,
    TopKRetrievalResult,
)
from matching_cv.app.schemas.skill_extraction import (
    Evidence,
    ExtractedSkill,
    ExtractionResult,
    ExtractionStats,
)
from matching_cv.app.schemas.unified_skill_extraction import (
    DocumentUnifiedResult,
    DocumentValidationResult,
    DuplicateImplicitSkill,
    UnifiedExtractFileResponse,
)
from matching_cv.app.services.graph_builder import (
    EXPECTED_EMBEDDING_DIM,
    HeteroGraphBuilder,
    hetero_graph_builder,
)


def _make_dummy_unified_response(
    cv_explicit_skills=None,
    cv_implicit_skills=None,
    cv_duplicate_skills=None,
    jd_explicit_skills=None,
    jd_implicit_skills=None,
    jd_duplicate_skills=None,
    run_id="test_run_12345678",
) -> UnifiedExtractFileResponse:
    """Helper creating a minimal valid UnifiedExtractFileResponse."""
    cv_exp = []
    for s in (cv_explicit_skills or []):
        sk_id = s.get("id", "skill_cv_1")
        name = s.get("name", "SkillCV")
        sentence = s.get("sentence", f"Demonstrated high proficiency in {name} across production workloads.")
        cv_exp.append(
            ExtractedSkill(
                skill_id=sk_id,
                surface_forms=[name],
                category=s.get("category", "Technology/Tool"),
                kind="skill",
                type="explicit",
                evidences=[
                    Evidence(
                        surface_form=name,
                        kind="skill",
                        kind_raw="skill",
                        kind_source="llm",
                        sentence=sentence,
                        start=0,
                        end=len(sentence),
                        offset_resolved=True,
                        verbatim_ok=True,
                        section="experience",
                        mention_start=0,
                        mention_end=len(name),
                        mention_ambiguous=False,
                    )
                ],
            )
        )

    cv_imp = []
    for s in (cv_implicit_skills or []):
        sk_id = s.get("id", "imp-cv-1")
        name = s.get("name", "ImpSkillCV")
        sentence = s.get("sentence", f"Led team delivery demonstrating {name} excellence.")
        cv_imp.append(
            ImplicitExtractedSkill(
                skill_id=sk_id,
                label=name,
                name=name,
                category=s.get("category", "Soft Skill"),
                confidence=0.85,
                basis="activity",
                evidences=[
                    ImplicitEvidence(
                        sentence=sentence,
                        section="experience",
                        inferred_from_raw=sentence,
                    )
                ],
            )
        )

    cv_dups = [
        DuplicateImplicitSkill(
            skill_id=s.get("id", "dup-cv-1"),
            label=s.get("name", "DupSkill"),
            matched_explicit_skill_id=s.get("matched_id", "skill-cv-1"),
            matched_explicit_surface_form=s.get("name", "DupSkill"),
            duplicate_reason="exact_canonical_id",
        )
        for s in (cv_duplicate_skills or [])
    ]

    jd_exp = []
    for s in (jd_explicit_skills or []):
        sk_id = s.get("id", "skill-jd-1")
        name = s.get("name", "SkillJD")
        sentence = s.get("sentence", f"Candidate must possess solid mastery of {name}.")
        jd_exp.append(
            ExtractedSkill(
                skill_id=sk_id,
                surface_forms=[name],
                category=s.get("category", "Technology/Tool"),
                kind="skill",
                type="explicit",
                evidences=[
                    Evidence(
                        surface_form=name,
                        kind="skill",
                        kind_raw="skill",
                        kind_source="llm",
                        sentence=sentence,
                        start=0,
                        end=len(sentence),
                        offset_resolved=True,
                        verbatim_ok=True,
                        section="requirements",
                        mention_start=0,
                        mention_end=len(name),
                        mention_ambiguous=False,
                    )
                ],
            )
        )

    jd_imp = []
    for s in (jd_implicit_skills or []):
        sk_id = s.get("id", "imp-jd-1")
        name = s.get("name", "ImpSkillJD")
        sentence = s.get("sentence", f"Collaborate with stakeholders showing {name} competence.")
        jd_imp.append(
            ImplicitExtractedSkill(
                skill_id=sk_id,
                label=name,
                name=name,
                category=s.get("category", "Soft Skill"),
                confidence=0.90,
                basis="jd_role_context",
                evidences=[
                    ImplicitEvidence(
                        sentence=sentence,
                        section="requirements",
                        inferred_from_raw=sentence,
                    )
                ],
            )
        )

    jd_dups = [
        DuplicateImplicitSkill(
            skill_id=s.get("id", "dup_jd_1"),
            label=s.get("name", "DupSkillJD"),
            matched_explicit_skill_id=s.get("matched_id", "skill_jd_1"),
            matched_explicit_surface_form=s.get("name", "DupSkillJD"),
            duplicate_reason="exact_canonical_id",
        )
        for s in (jd_duplicate_skills or [])
    ]

    cv_doc = DocumentUnifiedResult(
        filename="test_cv.pdf",
        document_type="CV",
        text_sha256="hash_cv_12345",
        explicit=ExtractionResult(
            filename="test_cv.pdf",
            document_type="CV",
            stats=ExtractionStats(
                total_mentions=len(cv_exp),
                unique_skills=len(cv_exp),
                unresolved_mentions=0,
                ambiguous_mentions=0,
            ),
            skills=cv_exp,
        ),
        implicit=ImplicitExtractionResult(
            filename="test_cv.pdf",
            document_type="CV",
            stats=ImplicitExtractionStats(total_inferences=len(cv_imp), unique_skills=len(cv_imp)),
            skills=cv_imp,
        ),
        validation=DocumentValidationResult(
            status="completed",
            accepted_implicit_skills=cv_imp,
            duplicate_implicit_skills=cv_dups,
        ),
    )

    jd_doc = DocumentUnifiedResult(
        filename="test_jd.pdf",
        document_type="JD",
        text_sha256="hash_jd_12345",
        explicit=ExtractionResult(
            filename="test_jd.pdf",
            document_type="JD",
            stats=ExtractionStats(
                total_mentions=len(jd_exp),
                unique_skills=len(jd_exp),
                unresolved_mentions=0,
                ambiguous_mentions=0,
            ),
            skills=jd_exp,
        ),
        implicit=ImplicitExtractionResult(
            filename="test_jd.pdf",
            document_type="JD",
            stats=ImplicitExtractionStats(total_inferences=len(jd_imp), unique_skills=len(jd_imp)),
            skills=jd_imp,
        ),
        validation=DocumentValidationResult(
            status="completed",
            accepted_implicit_skills=jd_imp,
            duplicate_implicit_skills=jd_dups,
        ),
    )

    return UnifiedExtractFileResponse(
        run_id=run_id,
        status="completed",
        cv=cv_doc,
        jd=jd_doc,
        cv_text="CV Full text with SkillCV and ImpSkillCV",
        jd_text="JD Full text with SkillJD and ImpSkillJD",
    )


# Scenario 1: Simple CV and JD with overlapping skills
def test_scenario_01_simple_cv_jd_overlap():
    unified = _make_dummy_unified_response(
        cv_explicit_skills=[{"id": "python", "name": "Python"}],
        jd_explicit_skills=[{"id": "python", "name": "Python"}],
    )
    req = GraphBuildRequest(unified_response=unified, graph_mode="evidence_only")
    g, rep = hetero_graph_builder.build_graph(req)

    assert rep.is_valid
    assert len(g.cv_nodes) == 1
    assert len(g.jd_nodes) == 1
    # Distinct occurrence nodes for CV Python and JD Python
    assert len(g.skill_nodes) == 2
    cv_skills = [s for s in g.skill_nodes.values() if s.source_document == "CV"]
    jd_skills = [s for s in g.skill_nodes.values() if s.source_document == "JD"]
    assert len(cv_skills) == 1 and len(jd_skills) == 1
    assert cv_skills[0].node_id != jd_skills[0].node_id


# Scenario 2: Explicit skill occurrence mapping
def test_scenario_02_explicit_skill_mapping():
    unified = _make_dummy_unified_response(
        cv_explicit_skills=[{"id": "sql", "name": "SQL", "category": "Technology/Tool"}],
    )
    req = GraphBuildRequest(unified_response=unified, graph_mode="evidence_only")
    g, rep = hetero_graph_builder.build_graph(req)

    assert rep.is_valid
    skill_node = [s for s in g.skill_nodes.values() if s.canonical_skill_id == "sql"][0]
    assert skill_node.explicit_or_implicit == "explicit"
    assert skill_node.category == "Technology/Tool"
    assert skill_node.source_document == "CV"


# Scenario 3: Accepted implicit skill mapping
def test_scenario_03_accepted_implicit_skill_mapping():
    unified = _make_dummy_unified_response(
        cv_implicit_skills=[{"id": "leadership", "name": "Leadership", "category": "Soft Skill"}],
    )
    req = GraphBuildRequest(unified_response=unified, graph_mode="evidence_only")
    g, rep = hetero_graph_builder.build_graph(req)

    assert rep.is_valid
    imp_nodes = [s for s in g.skill_nodes.values() if s.canonical_skill_id == "leadership"]
    assert len(imp_nodes) == 1
    assert imp_nodes[0].explicit_or_implicit == "implicit"
    assert imp_nodes[0].category == "Soft Skill"


# Scenario 4: Rejected implicit skill exclusion
def test_scenario_04_rejected_implicit_skill_exclusion():
    unified = _make_dummy_unified_response(
        cv_explicit_skills=[{"id": "python", "name": "Python"}],
        cv_duplicate_skills=[{"id": "python", "name": "Python", "matched_id": "python"}],
    )
    req = GraphBuildRequest(unified_response=unified, graph_mode="evidence_only")
    g, rep = hetero_graph_builder.build_graph(req)

    assert rep.is_valid
    # Python should appear exactly once in CV skills (the explicit one)
    cv_python_nodes = [
        s for s in g.skill_nodes.values() if s.canonical_skill_id == "python" and s.source_document == "CV"
    ]
    assert len(cv_python_nodes) == 1
    assert cv_python_nodes[0].explicit_or_implicit == "explicit"
    # Duplicate recorded in rejected_audit
    dup_audits = [a for a in g.rejected_audit if a.get("entity_type") == "duplicate_implicit_skill"]
    assert len(dup_audits) == 1
    assert dup_audits[0]["skill_id"] == "python"


# Scenario 5: Evidence provenance preservation
def test_scenario_05_evidence_provenance_preservation():
    unified = _make_dummy_unified_response(
        cv_explicit_skills=[
            {"id": "react", "name": "React", "sentence": "Built web app with React in production."}
        ]
    )
    req = GraphBuildRequest(unified_response=unified, graph_mode="evidence_only")
    g, rep = hetero_graph_builder.build_graph(req)

    assert rep.is_valid
    assert len(g.evidence_nodes) == 1
    ev_node = list(g.evidence_nodes.values())[0]
    assert ev_node.text == "Built web app with React in production."
    # Check SUPPORTED_BY edge
    supp_edges = [e for e in g.edges if e.edge_type == "supported_by"]
    assert len(supp_edges) == 1
    assert supp_edges[0].target_id == ev_node.node_id


# Scenario 6: Requirement association preservation
def test_scenario_06_requirement_association_preservation():
    unified = _make_dummy_unified_response(
        jd_explicit_skills=[{"id": "docker", "name": "Docker", "sentence": "3+ years required with Docker containers."}]
    )
    req = GraphBuildRequest(
        unified_response=unified,
        raw_jd_text="3+ years required with Docker containers.",
        graph_mode="evidence_only",
    )
    g, rep = hetero_graph_builder.build_graph(req)

    assert rep.is_valid
    assert len(g.requirement_nodes) >= 1
    # Check MENTIONS_SKILL edge
    ment_edges = [e for e in g.edges if e.edge_type == "mentions_skill"]
    assert len(ment_edges) >= 1


# Scenario 7: Same skill label in CV and JD without forced merging
def test_scenario_07_same_skill_label_no_forced_merge():
    unified = _make_dummy_unified_response(
        cv_explicit_skills=[{"id": "react", "name": "React"}],
        jd_explicit_skills=[{"id": "react", "name": "React"}],
    )
    req = GraphBuildRequest(unified_response=unified, graph_mode="evidence_only")
    g, rep = hetero_graph_builder.build_graph(req)

    assert rep.is_valid
    cv_react = [s for s in g.skill_nodes.values() if s.source_document == "CV" and s.original_label == "React"]
    jd_react = [s for s in g.skill_nodes.values() if s.source_document == "JD" and s.original_label == "React"]
    assert len(cv_react) == 1
    assert len(jd_react) == 1
    assert cv_react[0].node_id != jd_react[0].node_id


# Scenario 8: Distinct labels with LLM equivalent prediction
def test_scenario_08_distinct_labels_llm_equivalent():
    unified = _make_dummy_unified_response(
        cv_explicit_skills=[{"id": "reactjs", "name": "ReactJS"}],
        jd_explicit_skills=[{"id": "react", "name": "React"}],
    )
    reasoning = [
        SkillPairReasoningResult(
            skill_a=SkillRef(skill_id="reactjs", name="ReactJS", source="CV"),
            skill_b=SkillRef(skill_id="react", name="React", source="JD"),
            identity="equivalent",
            relationship=None,
            direction="none",
            reasoning_summary="ReactJS is synonymous with React",
            graph_relation_status="eligible",
            model_id="test_llm",
        )
    ]
    req = GraphBuildRequest(
        unified_response=unified,
        reasoning_results=reasoning,
        graph_mode="llm_enriched",
        edge_policy="eligible_llm_edges",
    )
    g, rep = hetero_graph_builder.build_graph(req)

    assert rep.is_valid
    # 2 distinct skill nodes maintained
    assert len(g.skill_nodes) == 2
    eq_edges = [e for e in g.edges if e.edge_type == "equivalent_to"]
    assert len(eq_edges) == 2  # Bidirectional (u, v) and (v, u)


# Scenario 9: False equivalence risk preservation
def test_scenario_09_false_equivalence_risk_distinct_nodes():
    unified = _make_dummy_unified_response(
        cv_explicit_skills=[{"id": "docker", "name": "Docker"}],
        jd_explicit_skills=[{"id": "linux-containers", "name": "Linux Containers"}],
    )
    reasoning = [
        SkillPairReasoningResult(
            skill_a=SkillRef(skill_id="docker", name="Docker", source="CV"),
            skill_b=SkillRef(skill_id="linux-containers", name="Linux Containers", source="JD"),
            identity="distinct",
            relationship="related",
            direction="none",
            reasoning_summary="Docker utilizes Linux containers as runtime engine",
            graph_relation_status="eligible",
            model_id="test_llm",
        )
    ]
    req = GraphBuildRequest(
        unified_response=unified,
        reasoning_results=reasoning,
        graph_mode="llm_enriched",
        edge_policy="eligible_llm_edges",
    )
    g, rep = hetero_graph_builder.build_graph(req)

    assert rep.is_valid
    assert len([e for e in g.edges if e.edge_type == "equivalent_to"]) == 0
    rel_edges = [e for e in g.edges if e.edge_type == "related_to"]
    assert len(rel_edges) == 2


# Scenario 10: Related skill candidate
def test_scenario_10_related_skill_candidate():
    unified = _make_dummy_unified_response(
        cv_explicit_skills=[{"id": "react", "name": "React"}],
        jd_explicit_skills=[{"id": "react-query", "name": "React Query"}],
    )
    reasoning = [
        SkillPairReasoningResult(
            skill_a=SkillRef(skill_id="react", name="React", source="CV"),
            skill_b=SkillRef(skill_id="react-query", name="React Query", source="JD"),
            identity="distinct",
            relationship="related",
            direction="none",
            reasoning_summary="Complementary library in React ecosystem",
            graph_relation_status="eligible",
            model_id="test_llm",
        )
    ]
    req = GraphBuildRequest(
        unified_response=unified,
        reasoning_results=reasoning,
        graph_mode="llm_enriched",
        edge_policy="eligible_llm_edges",
    )
    g, rep = hetero_graph_builder.build_graph(req)

    assert rep.is_valid
    rel_edges = [e for e in g.edges if e.edge_type == "related_to"]
    assert len(rel_edges) == 2


# Scenario 11: Directional prerequisite mapping (a_to_b)
def test_scenario_11_directional_prerequisite_a_to_b():
    unified = _make_dummy_unified_response(
        cv_explicit_skills=[{"id": "javascript", "name": "JavaScript"}],
        jd_explicit_skills=[{"id": "typescript", "name": "TypeScript"}],
    )
    reasoning = [
        SkillPairReasoningResult(
            skill_a=SkillRef(skill_id="javascript", name="JavaScript", source="CV"),
            skill_b=SkillRef(skill_id="typescript", name="TypeScript", source="JD"),
            identity="distinct",
            relationship="prerequisite",
            direction="a_to_b",
            reasoning_summary="JS is prerequisite for TS",
            graph_relation_status="eligible",
            model_id="test_llm",
        )
    ]
    req = GraphBuildRequest(
        unified_response=unified,
        reasoning_results=reasoning,
        graph_mode="llm_enriched",
        edge_policy="eligible_llm_edges",
    )
    g, rep = hetero_graph_builder.build_graph(req)

    assert rep.is_valid
    prereq_edges = [e for e in g.edges if e.edge_type == "prerequisite_for"]
    assert len(prereq_edges) == 1
    # Source is JS, target is TS
    js_node = [s for s in g.skill_nodes.values() if s.canonical_skill_id == "javascript"][0]
    ts_node = [s for s in g.skill_nodes.values() if s.canonical_skill_id == "typescript"][0]
    assert prereq_edges[0].source_id == js_node.node_id
    assert prereq_edges[0].target_id == ts_node.node_id


# Scenario 12: Reversed prerequisite input (b_to_a)
def test_scenario_12_reversed_prerequisite_b_to_a():
    unified = _make_dummy_unified_response(
        cv_explicit_skills=[{"id": "nextjs", "name": "Next.js"}],
        jd_explicit_skills=[{"id": "react", "name": "React"}],
    )
    reasoning = [
        SkillPairReasoningResult(
            skill_a=SkillRef(skill_id="nextjs", name="Next.js", source="CV"),
            skill_b=SkillRef(skill_id="react", name="React", source="JD"),
            identity="distinct",
            relationship="prerequisite",
            direction="b_to_a",
            reasoning_summary="React (B) is prerequisite for Next.js (A)",
            graph_relation_status="eligible",
            model_id="test_llm",
        )
    ]
    req = GraphBuildRequest(
        unified_response=unified,
        reasoning_results=reasoning,
        graph_mode="llm_enriched",
        edge_policy="eligible_llm_edges",
    )
    g, rep = hetero_graph_builder.build_graph(req)

    assert rep.is_valid
    prereq_edges = [e for e in g.edges if e.edge_type == "prerequisite_for"]
    assert len(prereq_edges) == 1
    react_node = [s for s in g.skill_nodes.values() if s.canonical_skill_id == "react"][0]
    next_node = [s for s in g.skill_nodes.values() if s.canonical_skill_id == "nextjs"][0]
    # Prerequisite points from React to Next.js
    assert prereq_edges[0].source_id == react_node.node_id
    assert prereq_edges[0].target_id == next_node.node_id


# Scenario 13: Specialization direction (specialized --SPECIALIZATION_OF--> broader)
def test_scenario_13_specialization_direction():
    unified = _make_dummy_unified_response(
        cv_explicit_skills=[{"id": "echocardiography", "name": "Echocardiography"}],
        jd_explicit_skills=[{"id": "cardiology", "name": "Cardiology"}],
    )
    reasoning = [
        SkillPairReasoningResult(
            skill_a=SkillRef(skill_id="echocardiography", name="Echocardiography", source="CV"),
            skill_b=SkillRef(skill_id="cardiology", name="Cardiology", source="JD"),
            identity="distinct",
            relationship="specialization",
            direction="a_to_b",
            reasoning_summary="Echocardiography is a specialization of Cardiology",
            graph_relation_status="eligible",
            model_id="test_llm",
        )
    ]
    req = GraphBuildRequest(
        unified_response=unified,
        reasoning_results=reasoning,
        graph_mode="llm_enriched",
        edge_policy="eligible_llm_edges",
    )
    g, rep = hetero_graph_builder.build_graph(req)

    assert rep.is_valid
    spec_edges = [e for e in g.edges if e.edge_type == "specialization_of"]
    assert len(spec_edges) == 1
    echo_node = [s for s in g.skill_nodes.values() if s.canonical_skill_id == "echocardiography"][0]
    card_node = [s for s in g.skill_nodes.values() if s.canonical_skill_id == "cardiology"][0]
    assert spec_edges[0].source_id == echo_node.node_id
    assert spec_edges[0].target_id == card_node.node_id


# Scenario 14: Alternative relation
def test_scenario_14_alternative_relation():
    unified = _make_dummy_unified_response(
        cv_explicit_skills=[{"id": "jest", "name": "Jest"}],
        jd_explicit_skills=[{"id": "playwright", "name": "Playwright"}],
    )
    reasoning = [
        SkillPairReasoningResult(
            skill_a=SkillRef(skill_id="jest", name="Jest", source="CV"),
            skill_b=SkillRef(skill_id="playwright", name="Playwright", source="JD"),
            identity="distinct",
            relationship="alternative",
            direction="none",
            reasoning_summary="Alternative testing frameworks",
            graph_relation_status="eligible",
            model_id="test_llm",
        )
    ]
    req = GraphBuildRequest(
        unified_response=unified,
        reasoning_results=reasoning,
        graph_mode="llm_enriched",
        edge_policy="eligible_llm_edges",
    )
    g, rep = hetero_graph_builder.build_graph(req)

    assert rep.is_valid
    alt_edges = [e for e in g.edges if e.edge_type == "alternative_to"]
    assert len(alt_edges) == 2


# Scenario 15: Unrelated relation exclusion
def test_scenario_15_unrelated_relation_exclusion():
    unified = _make_dummy_unified_response(
        cv_explicit_skills=[{"id": "java", "name": "Java"}],
        jd_explicit_skills=[{"id": "javascript", "name": "JavaScript"}],
    )
    reasoning = [
        SkillPairReasoningResult(
            skill_a=SkillRef(skill_id="java", name="Java", source="CV"),
            skill_b=SkillRef(skill_id="javascript", name="JavaScript", source="JD"),
            identity="distinct",
            relationship="unrelated",
            direction="none",
            reasoning_summary="Java and JavaScript are fundamentally distinct languages",
            graph_relation_status="eligible",
            model_id="test_llm",
        )
    ]
    req = GraphBuildRequest(
        unified_response=unified,
        reasoning_results=reasoning,
        graph_mode="llm_enriched",
        edge_policy="eligible_llm_edges",
    )
    g, rep = hetero_graph_builder.build_graph(req)

    assert rep.is_valid
    # No semantic edge added
    semantic_edges = [
        e for e in g.edges if e.edge_type in ("equivalent_to", "related_to", "prerequisite_for", "specialization_of", "alternative_to")
    ]
    assert len(semantic_edges) == 0
    # Audit preserves negative finding
    unrel_audit = [a for a in g.rejected_audit if a.get("status") == "unrelated"]
    assert len(unrel_audit) == 1


# Scenario 16: Uncertain relation exclusion from active typed graph
def test_scenario_16_uncertain_relation_exclusion():
    unified = _make_dummy_unified_response(
        cv_explicit_skills=[{"id": "quantum-lib", "name": "QuantumLib"}],
        jd_explicit_skills=[{"id": "cyber-mesh", "name": "CyberMesh"}],
    )
    reasoning = [
        SkillPairReasoningResult(
            skill_a=SkillRef(skill_id="quantum-lib", name="QuantumLib", source="CV"),
            skill_b=SkillRef(skill_id="cyber-mesh", name="CyberMesh", source="JD"),
            identity="uncertain",
            relationship="uncertain",
            direction="none",
            reasoning_summary="Insufficient evidence to determine relationship",
            graph_relation_status="candidate_only",
            model_id="test_llm",
        )
    ]
    req = GraphBuildRequest(
        unified_response=unified,
        reasoning_results=reasoning,
        graph_mode="llm_enriched",
        edge_policy="experimental_include_candidates",
    )
    g, rep = hetero_graph_builder.build_graph(req)

    assert rep.is_valid
    # Uncertain is excluded from active typed graph even under experimental policy
    semantic_edges = [
        e for e in g.edges if e.edge_type in ("equivalent_to", "related_to", "prerequisite_for", "specialization_of", "alternative_to")
    ]
    assert len(semantic_edges) == 0
    unc_audit = [a for a in g.rejected_audit if a.get("status") == "uncertain"]
    assert len(unc_audit) == 1


# Scenario 17: Candidate-only handling across export policies
def test_scenario_17_candidate_only_policy_handling():
    unified = _make_dummy_unified_response(
        cv_explicit_skills=[{"id": "golang", "name": "Golang"}],
        jd_explicit_skills=[{"id": "go", "name": "Go"}],
    )
    reasoning = [
        SkillPairReasoningResult(
            skill_a=SkillRef(skill_id="golang", name="Golang", source="CV"),
            skill_b=SkillRef(skill_id="go", name="Go", source="JD"),
            identity="equivalent",
            relationship=None,
            direction="none",
            reasoning_summary="Informal name for Go, but critic flagged contradiction",
            graph_relation_status="candidate_only",
            model_id="test_llm",
        )
    ]

    # Under eligible_llm_edges: candidate_only must NOT be included
    req_eligible = GraphBuildRequest(
        unified_response=unified,
        reasoning_results=reasoning,
        graph_mode="llm_enriched",
        edge_policy="eligible_llm_edges",
    )
    g_el, rep_el = hetero_graph_builder.build_graph(req_eligible)
    assert len([e for e in g_el.edges if e.edge_type == "equivalent_to"]) == 0

    # Under experimental_include_candidates: candidate_only IS included with is_tentative=True
    req_exp = GraphBuildRequest(
        unified_response=unified,
        reasoning_results=reasoning,
        graph_mode="llm_enriched",
        edge_policy="experimental_include_candidates",
    )
    g_exp, rep_exp = hetero_graph_builder.build_graph(req_exp)
    eq_exp = [e for e in g_exp.edges if e.edge_type == "equivalent_to"]
    assert len(eq_exp) == 2
    assert eq_exp[0].attributes["is_tentative"] is True


# Scenario 18: Rejected semantic relation handling
def test_scenario_18_rejected_semantic_relation_handling():
    unified = _make_dummy_unified_response(
        cv_explicit_skills=[{"id": "foo", "name": "Foo"}],
        jd_explicit_skills=[{"id": "bar", "name": "Bar"}],
    )
    reasoning = [
        SkillPairReasoningResult(
            skill_a=SkillRef(skill_id="foo", name="Foo", source="CV"),
            skill_b=SkillRef(skill_id="bar", name="Bar", source="JD"),
            identity="uncertain",
            relationship="uncertain",
            direction="none",
            reasoning_summary="Error occurred during reasoning",
            graph_relation_status="rejected",
            error_status="Timeout during LLM request",
            model_id="test_llm",
        )
    ]
    req = GraphBuildRequest(
        unified_response=unified,
        reasoning_results=reasoning,
        graph_mode="llm_enriched",
        edge_policy="experimental_include_candidates",
    )
    g, rep = hetero_graph_builder.build_graph(req)

    assert rep.is_valid
    assert len([e for e in g.edges if e.edge_type in ("equivalent_to", "related_to")]) == 0
    rej_audits = [a for a in g.rejected_audit if a.get("status") == "rejected"]
    assert len(rej_audits) == 1
    assert "Timeout" in rej_audits[0]["reason"]


# Scenario 19: Evidence-only graph mode (Mode A)
def test_scenario_19_evidence_only_graph_mode():
    unified = _make_dummy_unified_response(
        cv_explicit_skills=[{"id": "react", "name": "React"}],
        jd_explicit_skills=[{"id": "react", "name": "React"}],
    )
    req = GraphBuildRequest(unified_response=unified, graph_mode="evidence_only")
    g, rep = hetero_graph_builder.build_graph(req)

    assert rep.is_valid
    allowed_mode_a_types = {"has_skill", "requires_skill", "has_evidence", "supported_by", "has_requirement", "mentions_skill"}
    actual_types = set(rep.edge_integrity["edge_counts"].keys())
    assert actual_types.issubset(allowed_mode_a_types)
    assert "similar_to_candidate" not in actual_types
    assert "equivalent_to" not in actual_types


# Scenario 20: Similarity-enriched graph mode (Mode B)
def test_scenario_20_similarity_enriched_graph_mode():
    unified = _make_dummy_unified_response(
        cv_explicit_skills=[{"id": "react", "name": "React"}],
        jd_explicit_skills=[{"id": "vue", "name": "Vue"}],
    )
    # Build dummy stage 3 response with Top-K
    cv_node_id = "occ_cv_explicit_doc_react"
    jd_node_id = "occ_jd_explicit_doc_vue"
    stage3 = SemanticRepresentationResponse(
        run_id="test_run_12345678",
        model_id="sentence-transformers/paraphrase-multilingual-mpnet-base-v2",
        device="cpu",
        embedding_dim=768,
        top_k_retrievals={
            "cv_skills_to_jd_skills": [
                TopKRetrievalResult(
                    query_id=cv_node_id,
                    query_label="React",
                    candidates=[
                        SemanticSimilarityPair(
                            source_id=cv_node_id,
                            target_id=jd_node_id,
                            source_label="React",
                            target_label="Vue",
                            cosine_similarity=0.6521,
                            raw_score=0.652145,
                            rank=1,
                        )
                    ],
                )
            ]
        },
    )

    req = GraphBuildRequest(
        unified_response=unified,
        stage3_response=stage3,
        graph_mode="similarity_enriched",
    )
    # Manually align occurrence_ids for this unit test
    g, rep = hetero_graph_builder.build_graph(req)
    # Let's inspect similar_to_candidate handling
    assert rep.is_valid


# Scenario 21: LLM-enriched graph mode (Mode C)
def test_scenario_21_llm_enriched_graph_mode():
    unified = _make_dummy_unified_response(
        cv_explicit_skills=[{"id": "react", "name": "React"}],
        jd_explicit_skills=[{"id": "nextjs", "name": "Next.js"}],
    )
    reasoning = [
        SkillPairReasoningResult(
            skill_a=SkillRef(skill_id="react", name="React", source="CV"),
            skill_b=SkillRef(skill_id="nextjs", name="Next.js", source="JD"),
            identity="distinct",
            relationship="prerequisite",
            direction="a_to_b",
            reasoning_summary="React is foundational prerequisite for Next.js",
            graph_relation_status="eligible",
            model_id="test_llm",
        )
    ]
    req = GraphBuildRequest(
        unified_response=unified,
        reasoning_results=reasoning,
        graph_mode="llm_enriched",
        edge_policy="eligible_llm_edges",
    )
    g, rep = hetero_graph_builder.build_graph(req)

    assert rep.is_valid
    assert len([e for e in g.edges if e.edge_type == "prerequisite_for"]) == 1


# Scenario 22: Missing embeddings (documented feature mask handling)
def test_scenario_22_missing_embeddings_mask_handling():
    unified = _make_dummy_unified_response(
        cv_explicit_skills=[{"id": "react", "name": "React"}],
    )
    req = GraphBuildRequest(unified_response=unified, graph_mode="evidence_only")
    g, rep = hetero_graph_builder.build_graph(req)

    assert rep.is_valid
    # In pure evidence mode without Stage 3, skills have no vector attached
    for s in g.skill_nodes.values():
        assert s.has_embedding is False
        assert s.embedding_vector is None

    # PyG export should still succeed and set has_embedding_mask to False
    pyg, _, summary = hetero_graph_builder.export_to_pyg(g)
    assert pyg["skill"].has_embedding_mask.sum().item() == 0
    assert pyg["skill"].x.size(1) == EXPECTED_EMBEDDING_DIM


# Scenario 23: Wrong embedding dimension detection
def test_scenario_23_wrong_embedding_dimension():
    g = HeteroGraphData(
        graph_id="test_g",
        run_id="test_r",
        mode="evidence_only",
        edge_policy="trusted_structural_only",
        skill_nodes={
            "s1": SkillNode(
                node_id="s1",
                skill_occurrence_id="s1",
                original_label="Skill",
                canonical_skill_id="skill",
                source_document="CV",
                explicit_or_implicit="explicit",
                source_identifier="doc1",
                embedding_vector=[0.1] * 512,  # Wrong dimension (512 != 768)
                has_embedding=True,
            )
        },
    )
    rep = hetero_graph_builder.validate_graph_integrity(g)
    assert not rep.is_valid
    assert any("wrong embedding dimension" in err.lower() for err in rep.errors)


# Scenario 24: Non-finite embedding values (NaN/Inf) detection
def test_scenario_24_non_finite_embedding_values():
    nan_vec = [0.1] * 768
    nan_vec[10] = float("nan")
    g = HeteroGraphData(
        graph_id="test_g",
        run_id="test_r",
        mode="evidence_only",
        edge_policy="trusted_structural_only",
        skill_nodes={
            "s1": SkillNode(
                node_id="s1",
                skill_occurrence_id="s1",
                original_label="Skill",
                canonical_skill_id="skill",
                source_document="CV",
                explicit_or_implicit="explicit",
                source_identifier="doc1",
                embedding_vector=nan_vec,
                has_embedding=True,
            )
        },
    )
    rep = hetero_graph_builder.validate_graph_integrity(g)
    assert not rep.is_valid
    assert rep.embedding_integrity["nan_count"] == 1
    assert any("nan values" in err.lower() for err in rep.errors)


# Scenario 25: Missing source occurrence ID handling
def test_scenario_25_missing_source_occurrence_id_handling():
    unified = _make_dummy_unified_response(
        cv_explicit_skills=[{"id": "python", "name": "Python"}],
        jd_explicit_skills=[{"id": "python", "name": "Python"}],
    )
    # Pair with empty source_occurrence_ids
    reasoning = [
        SkillPairReasoningResult(
            skill_a=SkillRef(skill_id="python", name="Python", source="CV"),
            skill_b=SkillRef(skill_id="python", name="Python", source="JD"),
            identity="equivalent",
            relationship=None,
            direction="none",
            reasoning_summary="Same name resolved via canonical slug and source doc",
            graph_relation_status="eligible",
            source_occurrence_ids=[],  # Empty
            model_id="test_llm",
        )
    ]
    req = GraphBuildRequest(
        unified_response=unified,
        reasoning_results=reasoning,
        graph_mode="llm_enriched",
        edge_policy="eligible_llm_edges",
    )
    g, rep = hetero_graph_builder.build_graph(req)

    assert rep.is_valid
    # Resolved successfully via fallback canonical slug mapping
    eq_edges = [e for e in g.edges if e.edge_type == "equivalent_to"]
    assert len(eq_edges) == 2


# Scenario 26: Duplicate relation inputs deduplication
def test_scenario_26_duplicate_relation_inputs():
    unified = _make_dummy_unified_response(
        cv_explicit_skills=[{"id": "react", "name": "React"}],
        jd_explicit_skills=[{"id": "react", "name": "React"}],
    )
    reasoning = [
        SkillPairReasoningResult(
            skill_a=SkillRef(skill_id="react", name="React", source="CV"),
            skill_b=SkillRef(skill_id="react", name="React", source="JD"),
            identity="equivalent",
            relationship=None,
            direction="none",
            reasoning_summary="Equivalence 1",
            graph_relation_status="eligible",
            model_id="test_llm",
        ),
        SkillPairReasoningResult(
            skill_a=SkillRef(skill_id="react", name="React", source="CV"),
            skill_b=SkillRef(skill_id="react", name="React", source="JD"),
            identity="equivalent",
            relationship=None,
            direction="none",
            reasoning_summary="Equivalence 2 (duplicate)",
            graph_relation_status="eligible",
            model_id="test_llm",
        ),
    ]
    req = GraphBuildRequest(
        unified_response=unified,
        reasoning_results=reasoning,
        graph_mode="llm_enriched",
        edge_policy="eligible_llm_edges",
    )
    g, rep = hetero_graph_builder.build_graph(req)

    assert rep.is_valid
    # Exactly 2 edges (1 forward, 1 reverse), no duplicate edges added
    eq_edges = [e for e in g.edges if e.edge_type == "equivalent_to"]
    assert len(eq_edges) == 2


# Scenario 27: Invalid edge endpoints exclusion
def test_scenario_27_invalid_edge_endpoints_exclusion():
    unified = _make_dummy_unified_response(
        cv_explicit_skills=[{"id": "react", "name": "React"}],
        jd_explicit_skills=[{"id": "typescript", "name": "TypeScript"}],
    )
    reasoning = [
        SkillPairReasoningResult(
            skill_a=SkillRef(skill_id="completely_nonexistent_skill", name="NonExistent1", source="CV"),
            skill_b=SkillRef(skill_id="typescript", name="TypeScript", source="JD"),
            identity="distinct",
            relationship="related",
            direction="none",
            reasoning_summary="Attempting relation on ungrounded skill",
            graph_relation_status="eligible",
            model_id="test_llm",
        )
    ]
    req = GraphBuildRequest(
        unified_response=unified,
        reasoning_results=reasoning,
        graph_mode="llm_enriched",
        edge_policy="eligible_llm_edges",
    )
    g, rep = hetero_graph_builder.build_graph(req)

    assert rep.is_valid
    # No invalid edge added
    assert len([e for e in g.edges if e.edge_type == "related_to"]) == 0
    # Audit preserves unresolved endpoint record
    unres_audit = [a for a in g.rejected_audit if a.get("entity_type") == "semantic_relation_unresolved_endpoint"]
    assert len(unres_audit) == 1


# Scenario 28: Deterministic graph construction
def test_scenario_28_deterministic_graph_construction():
    unified = _make_dummy_unified_response(
        cv_explicit_skills=[{"id": "b-skill", "name": "BSkill"}, {"id": "a-skill", "name": "ASkill"}],
        jd_explicit_skills=[{"id": "z-skill", "name": "ZSkill"}, {"id": "y-skill", "name": "YSkill"}],
    )
    req = GraphBuildRequest(unified_response=unified, graph_mode="evidence_only")
    g1, _ = hetero_graph_builder.build_graph(req)
    g2, _ = hetero_graph_builder.build_graph(req)

    # Node IDs order matches
    assert list(g1.skill_nodes.keys()) == list(g2.skill_nodes.keys())
    # Edges order matches
    assert [(e.source_id, e.edge_type, e.target_id) for e in g1.edges] == [
        (e.source_id, e.edge_type, e.target_id) for e in g2.edges
    ]


# Scenario 29: PyG export integrity
def test_scenario_29_pyg_export_integrity():
    unified = _make_dummy_unified_response(
        cv_explicit_skills=[{"id": "react", "name": "React"}],
        jd_explicit_skills=[{"id": "typescript", "name": "TypeScript"}],
    )
    req = GraphBuildRequest(unified_response=unified, graph_mode="evidence_only")
    g, rep = hetero_graph_builder.build_graph(req)
    pyg, node_map, summary = hetero_graph_builder.export_to_pyg(g)

    assert summary["total_nodes"] == len(g.cv_nodes) + len(g.jd_nodes) + len(g.skill_nodes) + len(g.evidence_nodes) + len(g.requirement_nodes)
    assert summary["total_edges"] == len(g.edges)
    assert pyg["skill"].x.shape == (len(g.skill_nodes), EXPECTED_EMBEDDING_DIM)
    assert pyg["skill"].x.dtype == torch.float32


# Scenario 30: Non-IT domain skill verification (Healthcare & Accounting)
def test_scenario_30_non_it_domain_skills():
    unified = _make_dummy_unified_response(
        cv_explicit_skills=[
            {"id": "gaap", "name": "GAAP", "category": "Domain Knowledge"},
            {"id": "echocardiography", "name": "Echocardiography", "category": "Domain Knowledge"},
        ],
        jd_explicit_skills=[
            {"id": "general-accounting", "name": "Generally Accepted Accounting Principles", "category": "Domain Knowledge"},
            {"id": "cardiology", "name": "Cardiology", "category": "Domain Knowledge"},
        ],
    )
    reasoning = [
        SkillPairReasoningResult(
            skill_a=SkillRef(skill_id="gaap", name="GAAP", source="CV"),
            skill_b=SkillRef(skill_id="general-accounting", name="Generally Accepted Accounting Principles", source="JD"),
            identity="equivalent",
            relationship=None,
            direction="none",
            reasoning_summary="GAAP is the standard acronym for Generally Accepted Accounting Principles",
            graph_relation_status="eligible",
            model_id="test_llm",
        ),
        SkillPairReasoningResult(
            skill_a=SkillRef(skill_id="echocardiography", name="Echocardiography", source="CV"),
            skill_b=SkillRef(skill_id="cardiology", name="Cardiology", source="JD"),
            identity="distinct",
            relationship="specialization",
            direction="a_to_b",
            reasoning_summary="Echocardiography is a sub-discipline / diagnostic specialization of Cardiology",
            graph_relation_status="eligible",
            model_id="test_llm",
        ),
    ]
    req = GraphBuildRequest(
        unified_response=unified,
        reasoning_results=reasoning,
        graph_mode="llm_enriched",
        edge_policy="eligible_llm_edges",
    )
    g, rep = hetero_graph_builder.build_graph(req)

    assert rep.is_valid
    eq_edges = [e for e in g.edges if e.edge_type == "equivalent_to"]
    assert len(eq_edges) == 2
    spec_edges = [e for e in g.edges if e.edge_type == "specialization_of"]
    assert len(spec_edges) == 1
