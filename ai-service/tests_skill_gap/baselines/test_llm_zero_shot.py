import os
import shutil
import tempfile
from typing import List, Optional, Type
import pytest

from skill_gap.domain.enums import SemanticAlignment, SkillType
from skill_gap.domain.models import ExtractedCVSkill, ExtractedJDSkill, MatchResult
from skill_gap.adapters.config import AppConfig
from skill_gap.adapters.llm_client import LLMClient
from skill_gap.baselines.base import BaselineInput, BaselineOutputField
from skill_gap.baselines.llm.parser import validate_quote_in_text
from skill_gap.baselines.llm.prompts import build_augmented_prompt, build_text_only_prompt
from skill_gap.baselines.llm.schemas import (
    LLMSkillAssessment,
    LLMZeroShotResponse,
)
from skill_gap.baselines.llm.zero_shot import (
    LLMAugmentedBaseline,
    LLMTextOnlyBaseline,
)


class FakeLLMClient(LLMClient):
    """
    Fake LLM client simulating structured outputs without any real network or API calls.
    Tracks invocation count and prompts received.
    """

    def __init__(self, response_generator=None, model: str = "qwen/qwen3.7-flash") -> None:
        self.response_generator = response_generator
        self.model = model
        self.call_count = 0
        self.prompts_received: List[str] = []

    def complete(self, prompt: str, schema: Type[LLMZeroShotResponse]) -> LLMZeroShotResponse:
        self.call_count += 1
        self.prompts_received.append(prompt)
        if callable(self.response_generator):
            return self.response_generator(prompt, schema, self.call_count)
        elif self.response_generator is not None:
            return self.response_generator
        raise RuntimeError("No response generator configured for FakeLLMClient.")


@pytest.fixture
def mock_baseline_input() -> BaselineInput:
    """Fixture cung cấp đầu vào chuẩn với CV, JD và Module 1 data."""
    cv_text = (
        "Alice Smith - Cloud Engineer\n"
        "Experience:\n"
        "- Designed Kubernetes production clusters at FinTech Corp.\n"
        "- Basic familiarity with Terraform for AWS provisioning."
    )
    jd_text = (
        "Required:\n"
        "- Kubernetes: 4+ years\n"
        "- Terraform: Infrastructure as Code"
    )
    cv_skills = [
        ExtractedCVSkill(
            skill_id="kubernetes",
            type=SkillType.EXPLICIT,
            confidence=0.98,
            evidence_spans=["Designed Kubernetes production clusters at FinTech Corp."],
        ),
        ExtractedCVSkill(
            skill_id="terraform",
            type=SkillType.EXPLICIT,
            confidence=0.85,
            evidence_spans=["Basic familiarity with Terraform for AWS provisioning."],
        ),
    ]
    jd_skills = [
        ExtractedJDSkill(
            skill_id="kubernetes",
            type=SkillType.EXPLICIT,
            confidence=0.99,
            evidence_spans=["Kubernetes: 4+ years"],
        ),
        ExtractedJDSkill(
            skill_id="terraform",
            type=SkillType.EXPLICIT,
            confidence=0.95,
            evidence_spans=["Terraform: Infrastructure as Code"],
        ),
    ]
    match_results = [
        MatchResult(jd_skill_id="kubernetes", w_j=0.40, matched_cv_skill_id="kubernetes", soft_match=0.95),
        MatchResult(jd_skill_id="terraform", w_j=0.30, matched_cv_skill_id="terraform", soft_match=0.80),
    ]
    return BaselineInput(
        cv_text=cv_text,
        jd_text=jd_text,
        cv_skills=cv_skills,
        jd_skills=jd_skills,
        match_results=match_results,
    )


# ==============================================================================
# 1. Test phản hồi hợp lệ -> Parse đúng kết quả
# ==============================================================================

def test_valid_llm_response_parsing(mock_baseline_input: BaselineInput) -> None:
    """
    Kiểm thử câu trả lời hợp lệ từ FakeLLMClient được parse chính xác thành BaselineSkillResult.
    """
    fake_response = LLMZeroShotResponse(
        skills=[
            LLMSkillAssessment(
                jd_skill_id="kubernetes",
                reasoning="Candidate has production K8s cluster design experience.",
                evidence_quote="Designed Kubernetes production clusters at FinTech Corp.",
                semantic_alignment=SemanticAlignment.MATCH,
                candidate_proficiency=4.0,
                required_proficiency=4.5,
                gap_magnitude=0.125,
                priority=0.20,
            ),
            LLMSkillAssessment(
                jd_skill_id="terraform",
                reasoning="Candidate only has basic familiarity with Terraform.",
                evidence_quote="Basic familiarity with Terraform for AWS provisioning.",
                semantic_alignment=SemanticAlignment.MATCH,
                candidate_proficiency=2.0,
                required_proficiency=3.5,
                gap_magnitude=0.375,
                priority=0.45,
            ),
        ]
    )

    llm = FakeLLMClient(response_generator=fake_response)
    baseline = LLMAugmentedBaseline(llm_client=llm)

    results = baseline.run(mock_baseline_input)
    assert len(results) == 2

    k8s = next(r for r in results if r.jd_skill_id == "kubernetes")
    assert k8s.semantic_alignment == SemanticAlignment.MATCH
    assert k8s.candidate_proficiency == 4.0
    assert k8s.required_proficiency == 4.5
    assert k8s.gap_magnitude == 0.125
    assert k8s.priority == 0.20
    assert k8s.metadata["evidence_unverified"] is False
    assert "production K8s cluster" in k8s.metadata["reasoning"]

    tf = next(r for r in results if r.jd_skill_id == "terraform")
    assert tf.gap_magnitude == 0.375
    assert tf.priority == 0.45


# ==============================================================================
# 2. Test JSON hỏng / thiếu kỹ năng -> Retry rồi báo FAILED
# ==============================================================================

def test_missing_skills_triggers_retry_and_fails(mock_baseline_input: BaselineInput) -> None:
    """
    Kiểm thử: LLM trả về thiếu kỹ năng (chỉ trả về kubernetes, thiếu terraform).
    Hệ thống phải thử lại đủ max_retries lần và cuối cùng đánh dấu FAILED rõ ràng,
    tuyệt đối không điền số mặc định giả mạo.
    """
    # Response thiếu kỹ năng terraform
    incomplete_response = LLMZeroShotResponse(
        skills=[
            LLMSkillAssessment(
                jd_skill_id="kubernetes",
                reasoning="Analysis for k8s only.",
                evidence_quote="Designed Kubernetes production clusters",
                semantic_alignment=SemanticAlignment.MATCH,
                candidate_proficiency=4.0,
                required_proficiency=4.0,
                gap_magnitude=0.0,
                priority=0.0,
            )
        ]
    )

    llm = FakeLLMClient(response_generator=incomplete_response)
    baseline = LLMAugmentedBaseline(llm_client=llm, max_retries=3)

    results = baseline.run(mock_baseline_input)
    # Phải gọi đúng 3 lần (attempt 1, 2, 3)
    assert llm.call_count == 3

    # Kết quả trả về phải được đánh dấu FAILED cho toàn bộ kỹ năng
    assert len(results) == 2
    for r in results:
        assert r.metadata["status"] == "FAILED"
        assert "Exhausted 3 retries" in r.metadata["failure_reason"]
        # Mọi trường số phải là None, không điền giá trị giả
        assert r.gap_magnitude is None
        assert r.priority is None
        assert r.candidate_proficiency is None
        assert r.required_proficiency is None
        assert r.semantic_alignment is None


# ==============================================================================
# 3. Test trích dẫn bịa (Hallucinated quote) -> Cờ unverified bật
# ==============================================================================

def test_hallucinated_quote_triggers_unverified_flag(mock_baseline_input: BaselineInput) -> None:
    """
    Kiểm thử: LLM bịa ra câu trích dẫn không hề có trong CV text.
    Hệ thống phải bật cờ evidence_unverified = True mà không tự sửa số liệu.
    """
    fake_response = LLMZeroShotResponse(
        skills=[
            LLMSkillAssessment(
                jd_skill_id="kubernetes",
                reasoning="Candidate claims to be the core author of Kubernetes.",
                evidence_quote="I invented Kubernetes cluster architecture at Google in 2014.",  # Bịa
                semantic_alignment=SemanticAlignment.MATCH,
                candidate_proficiency=5.0,
                required_proficiency=4.0,
                gap_magnitude=0.0,
                priority=0.0,
            ),
            LLMSkillAssessment(
                jd_skill_id="terraform",
                reasoning="Verbatim match.",
                evidence_quote="Basic familiarity with Terraform for AWS provisioning.",  # Thật
                semantic_alignment=SemanticAlignment.MATCH,
                candidate_proficiency=2.0,
                required_proficiency=3.0,
                gap_magnitude=0.25,
                priority=0.10,
            ),
        ]
    )

    llm = FakeLLMClient(response_generator=fake_response)
    baseline = LLMAugmentedBaseline(llm_client=llm)

    results = baseline.run(mock_baseline_input)
    k8s = next(r for r in results if r.jd_skill_id == "kubernetes")
    tf = next(r for r in results if r.jd_skill_id == "terraform")

    # K8s có trích dẫn bịa -> cờ unverified = True
    assert k8s.metadata["evidence_unverified"] is True
    # TF có trích dẫn thật -> cờ unverified = False
    assert tf.metadata["evidence_unverified"] is False
    # Điểm số giữ nguyên không bị can thiệp
    assert k8s.candidate_proficiency == 5.0


# ==============================================================================
# 4. Test Prompt: Augmented có soft_match/w_j, TextOnly KHÔNG có
# ==============================================================================

def test_prompts_contain_expected_signals(mock_baseline_input: BaselineInput) -> None:
    """
    Kiểm thử:
    - Prompt của biến thể Augmented PHẢI chứa w_j và soft_match từ Module 1.
    - Prompt của biến thể TextOnly KHÔNG ĐƯỢC chứa w_j hay soft_match.
    """
    prompt_aug = build_augmented_prompt(
        cv_text=mock_baseline_input.cv_text,
        jd_text=mock_baseline_input.jd_text,
        cv_skills=mock_baseline_input.cv_skills,
        jd_skills=mock_baseline_input.jd_skills,
        match_results=mock_baseline_input.match_results,
    )
    prompt_text = build_text_only_prompt(
        cv_text=mock_baseline_input.cv_text,
        jd_text=mock_baseline_input.jd_text,
        jd_skills=mock_baseline_input.jd_skills,
    )

    # Augmented: chứa tín hiệu Module 1
    assert "soft_match from SBERT" in prompt_aug
    assert "w_j from GNN" in prompt_aug
    assert "0.950" in prompt_aug  # soft_match của k8s

    # TextOnly: không chứa tín hiệu Module 1
    assert "soft_match from SBERT" not in prompt_text
    assert "w_j from GNN" not in prompt_text
    assert "0.950" not in prompt_text


# ==============================================================================
# 5. Test chống rò rỉ thiết kế: Prompt không chứa hằng số/công thức module
# ==============================================================================

def test_prompt_does_not_leak_module_constants(mock_baseline_input: BaselineInput) -> None:
    """
    Grep test: Kiểm tra prompt không chứa các hằng số và bảng mốc nội bộ của module
    (tránh hiện tượng data leakage khiến LLM học vẹt công thức của chính module).
    """
    prompt_aug = build_augmented_prompt(
        cv_text=mock_baseline_input.cv_text,
        jd_text=mock_baseline_input.jd_text,
        cv_skills=mock_baseline_input.cv_skills,
        jd_skills=mock_baseline_input.jd_skills,
        match_results=mock_baseline_input.match_results,
    )

    forbidden_patterns = [
        "identity_threshold",
        "floor_threshold",
        "milestones_months",
        "month_weight_map",
        "IntervalUnion",
        "depth_factor",
        "P_JD / 5.0",
        "P_JD - s",
        "shortfall / 4.0",
        "list_only",
        "seniority_weights",
        "context_weights",
        "substitution_factor",
    ]

    for pattern in forbidden_patterns:
        assert pattern not in prompt_aug, f"Rò rỉ hằng số/công thức nội bộ '{pattern}' trong prompt!"


# ==============================================================================
# 6. Test n_runs: tạo đúng số bản ghi với run_id khác nhau
# ==============================================================================

def test_n_runs_creates_distinct_records(mock_baseline_input: BaselineInput) -> None:
    """
    Kiểm thử: n_runs tạo ra đúng số lượt chạy độc lập, mỗi lượt có run_id phân biệt.
    """
    fake_response = LLMZeroShotResponse(
        skills=[
            LLMSkillAssessment(
                jd_skill_id="kubernetes",
                reasoning="Reasoning k8s.",
                evidence_quote="Designed Kubernetes production clusters",
                semantic_alignment=SemanticAlignment.MATCH,
                candidate_proficiency=4.0,
                required_proficiency=4.0,
                gap_magnitude=0.0,
                priority=0.0,
            ),
            LLMSkillAssessment(
                jd_skill_id="terraform",
                reasoning="Reasoning tf.",
                evidence_quote="Basic familiarity with Terraform",
                semantic_alignment=SemanticAlignment.MATCH,
                candidate_proficiency=2.0,
                required_proficiency=3.0,
                gap_magnitude=0.25,
                priority=0.10,
            ),
        ]
    )

    llm = FakeLLMClient(response_generator=fake_response)
    baseline = LLMAugmentedBaseline(llm_client=llm, run_id="master_experiment")

    runs = baseline.run_multiple(mock_baseline_input, n_runs=3)

    assert len(runs) == 3
    run_ids = [run[0].metadata["run_id"] for run in runs]

    # Kiểm tra tính độc nhất của các run_id
    assert len(set(run_ids)) == 3
    assert all("master_experiment" in rid for rid in run_ids)


# ==============================================================================
# 7. Test Caching: không gọi lại LLM khi hash(prompt+model+run_id) trùng
# ==============================================================================

def test_caching_mechanism_prevents_duplicate_calls(mock_baseline_input: BaselineInput) -> None:
    """
    Kiểm thử cơ chế cache theo SHA256(prompt + model + run_id).
    Khi cache đã có, không gọi lại FakeLLMClient.
    """
    temp_cache_dir = tempfile.mkdtemp()
    try:
        fake_response = LLMZeroShotResponse(
            skills=[
                LLMSkillAssessment(
                    jd_skill_id="kubernetes",
                    reasoning="Cached k8s.",
                    evidence_quote="Designed Kubernetes",
                    semantic_alignment=SemanticAlignment.MATCH,
                    candidate_proficiency=4.0,
                    required_proficiency=4.0,
                    gap_magnitude=0.0,
                    priority=0.0,
                ),
                LLMSkillAssessment(
                    jd_skill_id="terraform",
                    reasoning="Cached tf.",
                    evidence_quote="Terraform",
                    semantic_alignment=SemanticAlignment.MATCH,
                    candidate_proficiency=2.0,
                    required_proficiency=3.0,
                    gap_magnitude=0.25,
                    priority=0.10,
                ),
            ]
        )

        llm = FakeLLMClient(response_generator=fake_response)
        baseline = LLMAugmentedBaseline(
            llm_client=llm,
            cache_dir=temp_cache_dir,
            run_id="static_run_123",
        )

        # Lần 1: Gọi LLM (call_count = 1)
        res1 = baseline.run(mock_baseline_input)
        assert llm.call_count == 1
        assert len(res1) == 2

        # Lần 2: Đọc từ cache (call_count vẫn = 1)
        res2 = baseline.run(mock_baseline_input)
        assert llm.call_count == 1
        assert len(res2) == 2
        assert res1[0].candidate_proficiency == res2[0].candidate_proficiency
    finally:
        shutil.rmtree(temp_cache_dir)
