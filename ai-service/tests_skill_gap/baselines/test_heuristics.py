import math
from typing import List
import pytest

from skill_gap.domain.enums import SemanticAlignment, SkillType
from skill_gap.domain.models import (
    ExtractedCVSkill,
    ExtractedJDSkill,
    MatchResult,
)
from skill_gap.adapters.config import AppConfig
from skill_gap.services.gap_detector import GapDetector
from skill_gap.baselines.base import (
    BaselineInput,
    BaselineOutputField,
)
from skill_gap.baselines.heuristics.binary_exact import BinaryExactBaseline
from skill_gap.baselines.heuristics.jdw import JDWBaseline
from skill_gap.baselines.heuristics.random_baseline import RandomBaseline
from skill_gap.baselines.heuristics.sim_gap import SimGapBaseline
from skill_gap.baselines.registry import baseline_registry


class MockLLMClient:
    def complete(self, prompt: str, schema):
        return None


@pytest.fixture
def demo_baseline_input() -> BaselineInput:
    """
    Fixture tạo dữ liệu mẫu chuẩn từ demo.py (5 kỹ năng: kubernetes, terraform, linux, gcp, ui_ux).
    """
    cv_skills = [
        ExtractedCVSkill(
            skill_id="kubernetes",
            type=SkillType.EXPLICIT,
            confidence=0.98,
            evidence_spans=["Thiết kế hạ tầng Kubernetes cho 50+ microservices."],
        ),
        ExtractedCVSkill(
            skill_id="terraform",
            type=SkillType.EXPLICIT,
            confidence=0.95,
            evidence_spans=["Viết Terraform để provision hạ tầng AWS."],
        ),
        ExtractedCVSkill(
            skill_id="linux",
            type=SkillType.EXPLICIT,
            confidence=0.85,
            evidence_spans=["Hỗ trợ quản trị server Linux cơ bản."],
        ),
        ExtractedCVSkill(
            skill_id="gcp",
            type=SkillType.EXPLICIT,
            confidence=0.70,
            evidence_spans=["Kỹ năng khác: Python, Bash, Ansible, GCP, Photoshop."],
        ),
        ExtractedCVSkill(
            skill_id="photoshop",
            type=SkillType.EXPLICIT,
            confidence=0.75,
            evidence_spans=["Kỹ năng khác: Python, Bash, Ansible, GCP, Photoshop."],
        ),
    ]

    jd_skills = [
        ExtractedJDSkill(
            skill_id="kubernetes",
            type=SkillType.EXPLICIT,
            confidence=0.99,
            evidence_spans=["Tối thiểu 4 năm kinh nghiệm vận hành Kubernetes."],
        ),
        ExtractedJDSkill(
            skill_id="terraform",
            type=SkillType.EXPLICIT,
            confidence=0.95,
            evidence_spans=["Thành thạo Terraform."],
        ),
        ExtractedJDSkill(
            skill_id="linux",
            type=SkillType.EXPLICIT,
            confidence=0.95,
            evidence_spans=["Vững vàng quản trị hệ thống Linux."],
        ),
        ExtractedJDSkill(
            skill_id="gcp",
            type=SkillType.EXPLICIT,
            confidence=0.85,
            evidence_spans=["Có kinh nghiệm với GCP là một lợi thế."],
        ),
        ExtractedJDSkill(
            skill_id="ui_ux",
            type=SkillType.EXPLICIT,
            confidence=0.80,
            evidence_spans=["Có kỹ năng thiết kế UI/UX cơ bản."],
        ),
    ]

    match_results = [
        MatchResult(jd_skill_id="kubernetes", w_j=0.30, matched_cv_skill_id="kubernetes", soft_match=1.0),
        MatchResult(jd_skill_id="terraform", w_j=0.25, matched_cv_skill_id="terraform", soft_match=1.0),
        MatchResult(jd_skill_id="linux", w_j=0.25, matched_cv_skill_id="linux", soft_match=1.0),
        MatchResult(jd_skill_id="gcp", w_j=0.10, matched_cv_skill_id="gcp", soft_match=1.0),
        # ui_ux matched with photoshop, low soft_match 0.25
        MatchResult(jd_skill_id="ui_ux", w_j=0.10, matched_cv_skill_id="photoshop", soft_match=0.25),
    ]

    return BaselineInput(
        cv_text="Jane Smith DevOps CV text",
        jd_text="DevOps Engineer JD text",
        cv_skills=cv_skills,
        jd_skills=jd_skills,
        match_results=match_results,
    )


# ==============================================================================
# 1. B-SimGap Tests
# ==============================================================================

def test_simgap_hand_calculated(demo_baseline_input: BaselineInput) -> None:
    """
    Kiểm thử B-SimGap với giá trị TÍNH TAY:
    Công thức: gap = clamp(1.0 - soft_match, 0.0, 1.0)
               priority = w_j * gap
    - kubernetes: soft_match=1.0 -> gap=0.0, priority = 0.30 * 0.0 = 0.0
    - terraform:  soft_match=1.0 -> gap=0.0, priority = 0.25 * 0.0 = 0.0
    - linux:      soft_match=1.0 -> gap=0.0, priority = 0.25 * 0.0 = 0.0
    - gcp:        soft_match=1.0 -> gap=0.0, priority = 0.10 * 0.0 = 0.0
    - ui_ux:      soft_match=0.25 -> gap = 1.0 - 0.25 = 0.75, priority = 0.10 * 0.75 = 0.075
    """
    baseline = SimGapBaseline()
    results = baseline.run(demo_baseline_input)

    res_map = {r.jd_skill_id: r for r in results}

    assert res_map["kubernetes"].gap_magnitude == pytest.approx(0.0, abs=1e-9)
    assert res_map["kubernetes"].priority == pytest.approx(0.0, abs=1e-9)

    assert res_map["terraform"].gap_magnitude == pytest.approx(0.0, abs=1e-9)
    assert res_map["terraform"].priority == pytest.approx(0.0, abs=1e-9)

    assert res_map["linux"].gap_magnitude == pytest.approx(0.0, abs=1e-9)
    assert res_map["linux"].priority == pytest.approx(0.0, abs=1e-9)

    assert res_map["gcp"].gap_magnitude == pytest.approx(0.0, abs=1e-9)
    assert res_map["gcp"].priority == pytest.approx(0.0, abs=1e-9)

    # ui_ux: w_j = 0.10, soft_match = 0.25 -> gap = 0.75, priority = 0.075
    assert res_map["ui_ux"].gap_magnitude == pytest.approx(0.75, abs=1e-9)
    assert res_map["ui_ux"].priority == pytest.approx(0.075, abs=1e-9)


def test_simgap_with_injected_alignment_fn(demo_baseline_input: BaselineInput) -> None:
    """
    Kiểm thử B-SimGap tái sử dụng logic tính semantic_alignment từ GapDetector qua injection.
    """
    detector = GapDetector(llm_client=MockLLMClient(), config=AppConfig())
    baseline = SimGapBaseline(alignment_fn=detector.compute_semantic_alignment)

    assert BaselineOutputField.ALIGNMENT in baseline.produces

    results = baseline.run(demo_baseline_input)
    res_map = {r.jd_skill_id: r for r in results}

    # soft_match = 1.0 >= 0.85 -> MATCH
    assert res_map["kubernetes"].semantic_alignment == SemanticAlignment.MATCH
    # soft_match = 0.25 < 0.40 -> MISSING
    assert res_map["ui_ux"].semantic_alignment == SemanticAlignment.MISSING


# ==============================================================================
# 2. B-Binary Tests
# ==============================================================================

def test_binary_exact_hand_calculated(demo_baseline_input: BaselineInput) -> None:
    """
    Kiểm thử B-Binary (exact-match heuristic) với giá trị TÍNH TAY:
    Tập cv_skill_ids = {"kubernetes", "terraform", "linux", "gcp", "photoshop"}
    - kubernetes, terraform, linux, gcp: có trong CV -> gap = 0.0, priority = 0.0, alignment = MATCH
    - ui_ux: KHÔNG có trong CV -> gap = 1.0, w_j = 0.10 -> priority = 0.10 * 1.0 = 0.10, alignment = MISSING
    """
    baseline = BinaryExactBaseline()
    results = baseline.run(demo_baseline_input)

    res_map = {r.jd_skill_id: r for r in results}

    for skill in ["kubernetes", "terraform", "linux", "gcp"]:
        assert res_map[skill].gap_magnitude == 0.0
        assert res_map[skill].priority == 0.0
        assert res_map[skill].semantic_alignment == SemanticAlignment.MATCH

    assert res_map["ui_ux"].gap_magnitude == 1.0
    assert res_map["ui_ux"].priority == pytest.approx(0.10, abs=1e-9)
    assert res_map["ui_ux"].semantic_alignment == SemanticAlignment.MISSING


# ==============================================================================
# 3. B-JDW Tests
# ==============================================================================

def test_jdw_hand_calculated(demo_baseline_input: BaselineInput) -> None:
    """
    Kiểm thử B-JDW với giá trị TÍNH TAY:
    priority = w_j của từng kỹ năng:
    - kubernetes: 0.30
    - terraform:  0.25
    - linux:      0.25
    - gcp:        0.10
    - ui_ux:      0.10
    gap_magnitude = None (B-JDW không tính gap).
    """
    baseline = JDWBaseline()
    results = baseline.run(demo_baseline_input)

    assert baseline.produces == frozenset({BaselineOutputField.PRIORITY})

    res_map = {r.jd_skill_id: r for r in results}

    assert res_map["kubernetes"].priority == pytest.approx(0.30, abs=1e-9)
    assert res_map["terraform"].priority == pytest.approx(0.25, abs=1e-9)
    assert res_map["linux"].priority == pytest.approx(0.25, abs=1e-9)
    assert res_map["gcp"].priority == pytest.approx(0.10, abs=1e-9)
    assert res_map["ui_ux"].priority == pytest.approx(0.10, abs=1e-9)

    for r in results:
        assert r.gap_magnitude is None
        assert r.semantic_alignment is None
        assert r.required_proficiency is None
        assert r.candidate_proficiency is None


# ==============================================================================
# 4. B-Random Tests
# ==============================================================================

def test_random_seed_determinism_and_ranges(demo_baseline_input: BaselineInput) -> None:
    """
    Kiểm thử B-Random:
    - Cùng seed -> cùng kết quả (tính tất định).
    - Khác seed -> khác kết quả.
    - Tất cả giá trị số nằm trong khoảng hợp lệ [0, 1] và [1, 5].
    """
    b_seed42_a = RandomBaseline(seed=42)
    b_seed42_b = RandomBaseline(seed=42)
    b_seed999 = RandomBaseline(seed=999)

    res_a = b_seed42_a.run(demo_baseline_input)
    res_b = b_seed42_b.run(demo_baseline_input)
    res_other = b_seed999.run(demo_baseline_input)

    # 1. Cùng seed -> cùng kết quả 100%
    assert len(res_a) == len(res_b)
    for r_a, r_b in zip(res_a, res_b):
        assert r_a.jd_skill_id == r_b.jd_skill_id
        assert r_a.gap_magnitude == r_b.gap_magnitude
        assert r_a.priority == r_b.priority
        assert r_a.required_proficiency == r_b.required_proficiency
        assert r_a.candidate_proficiency == r_b.candidate_proficiency
        assert r_a.semantic_alignment == r_b.semantic_alignment

    # 2. Khác seed -> kết quả khác nhau
    differences = [
        r_a.gap_magnitude != r_o.gap_magnitude
        for r_a, r_o in zip(res_a, res_other)
    ]
    assert any(differences)

    # 3. Kiểm tra khoảng giá trị
    for r in res_a:
        assert 0.0 <= r.gap_magnitude <= 1.0
        assert 0.0 <= r.priority <= 1.0
        assert 1.0 <= r.required_proficiency <= 5.0
        assert 1.0 <= r.candidate_proficiency <= 5.0
        assert r.semantic_alignment in {
            SemanticAlignment.MATCH,
            SemanticAlignment.PARTIAL,
            SemanticAlignment.MISSING,
        }


# ==============================================================================
# 5. General Contract across ALL baselines
# ==============================================================================

@pytest.mark.parametrize("baseline_cls", [SimGapBaseline, BinaryExactBaseline, JDWBaseline, RandomBaseline])
def test_all_baselines_contract(baseline_cls, demo_baseline_input: BaselineInput) -> None:
    """
    Kiểm tra hợp đồng chung cho mọi baseline:
    - Số kết quả == số jd_skills.
    - Thứ tự kết quả khớp chính xác thứ tự jd_skills.
    - gap trong [0, 1] (nếu không None).
    - Không có giá trị NaN nào.
    """
    baseline = baseline_cls()
    results = baseline.run(demo_baseline_input)

    assert len(results) == len(demo_baseline_input.jd_skills)

    expected_ids = [s.skill_id for s in demo_baseline_input.jd_skills]
    actual_ids = [r.jd_skill_id for r in results]
    assert actual_ids == expected_ids

    for r in results:
        if r.gap_magnitude is not None:
            assert 0.0 <= r.gap_magnitude <= 1.0
            assert not math.isnan(r.gap_magnitude)
        if r.priority is not None:
            assert 0.0 <= r.priority <= 1.0
            assert not math.isnan(r.priority)
        if r.required_proficiency is not None:
            assert not math.isnan(r.required_proficiency)
        if r.candidate_proficiency is not None:
            assert not math.isnan(r.candidate_proficiency)


# ==============================================================================
# 6. Edge Cases
# ==============================================================================

@pytest.mark.parametrize("baseline_cls", [SimGapBaseline, BinaryExactBaseline, JDWBaseline, RandomBaseline])
def test_edge_case_empty_jd_skills(baseline_cls) -> None:
    """Trường hợp biên 1: jd_skills rỗng -> trả về [] an toàn."""
    baseline = baseline_cls()
    empty_input = BaselineInput(
        cv_text="",
        jd_text="",
        cv_skills=[],
        jd_skills=[],
        match_results=[],
    )
    results = baseline.run(empty_input)
    assert results == []


def test_edge_case_skill_in_match_results_but_not_in_cv_skills() -> None:
    """
    Trường hợp biên 2: Skill có trong match_results nhưng thí sinh không có trong cv_skills.
    - Binary: kiểm tra cv_skills trực tiếp -> gap = 1.0
    - SimGap: kiểm tra match_results -> đọc soft_match
    """
    inp = BaselineInput(
        cv_text="CV trống",
        jd_text="JD cần Docker",
        cv_skills=[],  # cv_skills rỗng
        jd_skills=[
            ExtractedJDSkill(skill_id="docker", type=SkillType.EXPLICIT, confidence=0.9, evidence_spans=[])
        ],
        match_results=[
            MatchResult(jd_skill_id="docker", w_j=0.4, matched_cv_skill_id="podman", soft_match=0.8)
        ],
    )

    # Binary: không có trong cv_skills -> gap = 1.0, priority = 0.4 * 1.0 = 0.4
    binary = BinaryExactBaseline()
    b_res = binary.run(inp)
    assert b_res[0].gap_magnitude == 1.0
    assert b_res[0].priority == pytest.approx(0.4, abs=1e-9)

    # SimGap: dùng soft_match 0.8 -> gap = 1.0 - 0.8 = 0.2, priority = 0.4 * 0.2 = 0.08
    simgap = SimGapBaseline()
    s_res = simgap.run(inp)
    assert s_res[0].gap_magnitude == pytest.approx(0.2, abs=1e-9)
    assert s_res[0].priority == pytest.approx(0.08, abs=1e-9)


def test_edge_case_skill_missing_in_match_results() -> None:
    """
    Trường hợp biên 3: Skill trong jd_skills bị khuyết thiếu trong match_results.
    Phải fallback an toàn, không crash:
    - SimGap: soft_match = 0.0 -> gap = 1.0, w_j = 0.0 -> priority = 0.0
    - Binary: w_j = 0.0 -> priority = 0.0
    - JDW: w_j = 0.0 -> priority = 0.0
    """
    inp = BaselineInput(
        cv_text="CV",
        jd_text="JD",
        cv_skills=[],
        jd_skills=[
            ExtractedJDSkill(skill_id="unmatched_skill", type=SkillType.EXPLICIT, confidence=0.9, evidence_spans=[])
        ],
        match_results=[],  # Trống
    )

    simgap_res = SimGapBaseline().run(inp)
    assert simgap_res[0].gap_magnitude == 1.0
    assert simgap_res[0].priority == 0.0

    binary_res = BinaryExactBaseline().run(inp)
    assert binary_res[0].gap_magnitude == 1.0
    assert binary_res[0].priority == 0.0

    jdw_res = JDWBaseline().run(inp)
    assert jdw_res[0].gap_magnitude is None
    assert jdw_res[0].priority == 0.0


def test_edge_case_zero_weight() -> None:
    """Trường hợp biên 4: Trọng số w_j = 0.0 -> priority phải luôn bằng 0.0."""
    inp = BaselineInput(
        cv_text="CV",
        jd_text="JD",
        cv_skills=[],
        jd_skills=[
            ExtractedJDSkill(skill_id="skill_zero", type=SkillType.EXPLICIT, confidence=0.9, evidence_spans=[])
        ],
        match_results=[
            MatchResult(jd_skill_id="skill_zero", w_j=0.0, matched_cv_skill_id="none", soft_match=0.0)
        ],
    )

    for baseline in [SimGapBaseline(), BinaryExactBaseline(), JDWBaseline()]:
        res = baseline.run(inp)
        assert res[0].priority == 0.0


# ==============================================================================
# 7. Registry Verification
# ==============================================================================

def test_heuristic_baselines_registered() -> None:
    """Kiểm tra 4 baseline đã được đăng ký đầy đủ trong global registry."""
    available = baseline_registry.list_available()
    assert "B-SimGap" in available
    assert "B-Binary" in available
    assert "B-JDW" in available
    assert "B-Random" in available

    assert isinstance(baseline_registry.get("B-SimGap"), SimGapBaseline)
    assert isinstance(baseline_registry.get("B-Binary"), BinaryExactBaseline)
    assert isinstance(baseline_registry.get("B-JDW"), JDWBaseline)
    assert isinstance(baseline_registry.get("B-Random"), RandomBaseline)
