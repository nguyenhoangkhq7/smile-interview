"""Unit tests for Phase J Candidate Inference Adapter & Edge Case Hardening."""
import math
import os
import pytest
import torch
from torch_geometric.data import HeteroData

from matching_cv.app.schemas.gnn_inference import FitCategory
from matching_cv.research.paper_aligned_gnn.candidate_inference_adapter import CandidateInferenceAdapter
from matching_cv.research.paper_aligned_gnn.schemas import PaperAlignedGraphConfig
from matching_cv.research.paper_aligned_gnn.graph_builder import PaperAlignedGraphBuilder

BASELINE_CKPT = "data/checkpoints/paper_aligned_gnn/paper_aligned_hybrid_gnn_v1.pt"
POLICY_A_CKPT = "research/experiments/phase_j_retraining/checkpoints/paper_aligned_gnn_policy_a_retrained_best.pt"
POLICY_B_CKPT = "research/experiments/phase_j_retraining/checkpoints/paper_aligned_gnn_policy_b_decomposed_best.pt"


@pytest.fixture
def policy_a_adapter():
    if not os.path.exists(POLICY_A_CKPT):
        pytest.skip("Policy A retrained checkpoint not yet generated.")
    return CandidateInferenceAdapter(
        checkpoint_path=POLICY_A_CKPT,
        policy_label="POLICY_A_RETRAINED",
        model_version="test_policy_a",
        device="cpu",
    )


@pytest.fixture
def policy_b_adapter():
    if not os.path.exists(POLICY_B_CKPT):
        pytest.skip("Policy B decomposed checkpoint not yet generated.")
    return CandidateInferenceAdapter(
        checkpoint_path=POLICY_B_CKPT,
        policy_label="POLICY_B_DECOMPOSED",
        model_version="test_policy_b",
        device="cpu",
    )


def test_adapter_initialization_and_metadata(policy_a_adapter, policy_b_adapter):
    assert policy_a_adapter.model is not None
    assert policy_a_adapter.checkpoint_metadata["policy"] == "POLICY_A_RETRAINED"
    assert policy_a_adapter.checkpoint_metadata["best_seed"] in [42, 43, 44, 45, 46]
    assert policy_a_adapter.checkpoint_metadata["best_val_rmse"] > 0.0

    assert policy_b_adapter.model is not None
    assert policy_b_adapter.checkpoint_metadata["policy"] == "POLICY_B_DECOMPOSED"
    assert policy_b_adapter.checkpoint_metadata["best_seed"] in [42, 43, 44, 45, 46]
    assert policy_b_adapter.checkpoint_metadata["best_val_rmse"] > 0.0


def test_normal_pair_inference(policy_a_adapter):
    adapter = policy_a_adapter
    cv_comps = [
        {"skill_id": "python", "display_name": "Python", "proficiency": "Expert"},
        {"skill_id": "docker", "display_name": "Docker", "proficiency": "Intermediate"},
    ]
    jd_comps = [
        {"skill_id": "python", "display_name": "Python", "proficiency": "Required"},
        {"skill_id": "kubernetes", "display_name": "Kubernetes", "proficiency": "Preferred"},
    ]
    res = adapter.infer_competencies(cv_comps, jd_comps)
    assert "raw_score" in res
    assert 0.0 <= res["bounded_score"] <= 1.0
    assert res["fit_category"] in [f.value for f in FitCategory]
    assert res["graph_metadata"]["num_shared_skills"] == 1
    assert res["embedding_contract_version"] == "phase_j_v1_canonical_display"


def test_zero_shared_skills(policy_a_adapter):
    adapter = policy_a_adapter
    cv_comps = [
        {"skill_id": "python", "display_name": "Python", "proficiency": "Expert"},
        {"skill_id": "django", "display_name": "Django", "proficiency": "Intermediate"},
    ]
    jd_comps = [
        {"skill_id": "java", "display_name": "Java", "proficiency": "Required"},
        {"skill_id": "spring-boot", "display_name": "Spring Boot", "proficiency": "Required"},
    ]
    res = adapter.infer_competencies(cv_comps, jd_comps)
    assert 0.0 <= res["bounded_score"] <= 1.0
    assert res["graph_metadata"]["num_shared_skills"] == 0


def test_empty_skill_set(policy_a_adapter):
    adapter = policy_a_adapter
    # Edge case: 0 skills total
    builder = PaperAlignedGraphBuilder(config=PaperAlignedGraphConfig(random_seed=42))
    g_data, _ = builder.build_graph_from_items([], [], pair_id="empty_test")
    pyg, _, _ = builder.export_to_pyg(g_data)

    res = adapter.infer_graph(pyg)
    assert 0.0 <= res["bounded_score"] <= 1.0
    assert res["graph_metadata"]["total_skill_nodes"] == 0


def test_unanchored_implicit_skill_quarantine(policy_a_adapter):
    adapter = policy_a_adapter
    cv_comps = [
        {"skill_id": "python", "display_name": "Python", "proficiency": "Expert"},
        {
            "skill_id": "leadership",
            "display_name": "Leadership",
            "extraction_type": "implicit",
            "evidence_sentences": ["Led cross-functional teams of engineers."],
        },
    ]
    jd_comps = [
        {"skill_id": "python", "display_name": "Python", "proficiency": "Required"},
    ]
    # cv_text does not contain "Led cross-functional teams" -> must be quarantined
    cv_text = "Experienced backend developer specializing in high performance computing."
    res = adapter.infer_competencies(cv_comps, jd_comps, cv_text=cv_text)

    report = res["data_integrity_report"]
    assert report["cv_input_count"] == 2
    assert report["cv_admitted_count"] == 1  # Leadership was quarantined!
    assert res["graph_metadata"]["num_resume_skills"] == 1


def test_high_skill_count(policy_a_adapter):
    adapter = policy_a_adapter
    cv_comps = [{"skill_id": f"skill_{i}", "display_name": f"Skill {i}"} for i in range(60)]
    jd_comps = [{"skill_id": f"skill_{i}", "display_name": f"Skill {i}"} for i in range(20, 80)]
    res = adapter.infer_competencies(cv_comps, jd_comps)
    assert 0.0 <= res["bounded_score"] <= 1.0
    assert res["graph_metadata"]["num_shared_skills"] == 40
    assert res["graph_metadata"]["total_skill_nodes"] == 80


def test_missing_proficiency_ratings(policy_a_adapter):
    adapter = policy_a_adapter
    cv_comps = [
        {"skill_id": "python", "display_name": "Python", "proficiency": None},
    ]
    jd_comps = [
        {"skill_id": "python", "display_name": "Python", "proficiency": None},
    ]
    res = adapter.infer_competencies(cv_comps, jd_comps)
    assert 0.0 <= res["bounded_score"] <= 1.0
    assert not math.isnan(res["raw_score"])


def test_policy_b_adapter_inference(policy_b_adapter):
    adapter = policy_b_adapter
    cv_comps = [
        {"skill_id": "python", "display_name": "Python", "proficiency": "Expert"},
        {"skill_id": "spring-boot", "display_name": "Spring Boot", "proficiency": "Intermediate"},
    ]
    jd_comps = [
        {"skill_id": "python", "display_name": "Python", "proficiency": "Required"},
        {"skill_id": "spring-boot", "display_name": "Spring Boot", "proficiency": "Required"},
    ]
    res = adapter.infer_competencies(cv_comps, jd_comps)
    assert 0.0 <= res["bounded_score"] <= 1.0
    assert res["graph_policy_version"] == "POLICY_B_DECOMPOSED"
    assert res["embedding_contract_version"] == "phase_j_v1_canonical_display"
    assert res["graph_metadata"]["num_shared_skills"] == 2
