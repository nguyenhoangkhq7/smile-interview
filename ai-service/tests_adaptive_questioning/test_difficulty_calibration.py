"""
Tests for Domain-Agnostic Difficulty Calibration and Dynamic Persona Adaptation
(Stuart et al., 2026; Gheartha et al., 2026; Bloom's Taxonomy).
"""

import pytest
from adaptive_questioning.core.prompts import (
    build_step2a_layers,
    get_difficulty_rubric_anchor,
)
from adaptive_questioning.schemas.state import SkillBeliefState


class TestDifficultyCalibration:
    """Test suite verifying universal domain-agnostic difficulty calibration."""

    @pytest.mark.parametrize("r_target", [1.0, 1.5, 2.0, 2.4, 2.49])
    def test_low_difficulty_anchor_thresholds(self, r_target: float) -> None:
        anchor = get_difficulty_rubric_anchor(r_target)
        assert "MỤC TIÊU ĐỘ KHÓ: LOW" in anchor
        assert "Centroid c = 1.5" in anchor
        assert "RÀNG BUỘC CẤM (Overkill Prevention)" in anchor
        assert "Tuyệt đối KHÔNG hỏi về xử lý sự cố/khủng hoảng nghiêm trọng" in anchor

    @pytest.mark.parametrize("r_target", [2.5, 3.0, 3.5, 3.7, 3.79])
    def test_medium_difficulty_anchor_thresholds(self, r_target: float) -> None:
        anchor = get_difficulty_rubric_anchor(r_target)
        assert "MỤC TIÊU ĐỘ KHÓ: MEDIUM" in anchor
        assert "Centroid c = 3.0" in anchor
        assert "TỰ CHỦ & THỰC THI NGHIỆP VỤ" in anchor
        assert "Tránh hỏi các bài toán tái cấu trúc quy mô lớn" in anchor

    @pytest.mark.parametrize("r_target", [3.8, 4.0, 4.5, 5.0])
    def test_high_difficulty_anchor_thresholds(self, r_target: float) -> None:
        anchor = get_difficulty_rubric_anchor(r_target)
        assert "MỤC TIÊU ĐỘ KHÓ: HIGH" in anchor
        assert "Centroid c = 4.5" in anchor
        assert "LÀM CHỦ CHUYÊN SÂU & QUYẾT ĐỊNH ĐÁNH ĐỔI" in anchor
        assert "Bỏ qua các câu hỏi định nghĩa lý thuyết sách vở" in anchor

    @pytest.mark.parametrize(
        "job_title",
        [
            "Kế toán trưởng",
            "Marketing Growth Lead",
            "Bác sĩ Chẩn đoán hình ảnh",
            "Kỹ sư Cầu đường",
            "Chuyên viên Nhân sự C&B",
        ],
    )
    def test_dynamic_domain_persona_adaptation(self, job_title: str) -> None:
        skill = SkillBeliefState(
            jd_skill_id="domain_specific_skill",
            required_proficiency=3.5,
            candidate_proficiency=2.0,
            prior_belief=[0.33, 0.33, 0.34],
            current_belief=[0.33, 0.33, 0.34],
            cv_evidence_spans=["Kinh nghiệm thực hành."],
            context_job=job_title,
        )
        _, main_layer = build_step2a_layers(
            skill=skill,
            context_anchors=[],
            turn_history=[],
            next_local_turn_k=1,
        )
        assert f"trong lĩnh vực '{job_title}'" in main_layer
        assert "phỏng vấn bằng tiếng Việt chuyên nghiệp" in main_layer

    def test_step2a_layers_difficulty_injection(self) -> None:
        # 1. Low target (Junior level)
        skill_low = SkillBeliefState(
            jd_skill_id="financial_accounting",
            required_proficiency=2.0,
            candidate_proficiency=1.5,
            prior_belief=[0.6, 0.3, 0.1],
            current_belief=[0.6, 0.3, 0.1],
            cv_evidence_spans=["Nhập liệu hóa đơn."],
            context_job="Nhân viên Kế toán",
        )
        _, main_low = build_step2a_layers(
            skill=skill_low,
            context_anchors=[],
            turn_history=[],
            next_local_turn_k=1,
        )
        assert "MỤC TIÊU ĐỘ KHÓ: LOW (2.0/5.0)" in main_low
        assert "Centroid c = 1.5" in main_low

        # 2. High target (Senior / Lead level)
        skill_high = SkillBeliefState(
            jd_skill_id="financial_accounting",
            required_proficiency=4.5,
            candidate_proficiency=2.5,
            prior_belief=[0.1, 0.3, 0.6],
            current_belief=[0.1, 0.3, 0.6],
            cv_evidence_spans=["Lập báo cáo tài chính."],
            context_job="Giám đốc Tài chính (CFO)",
        )
        _, main_high = build_step2a_layers(
            skill=skill_high,
            context_anchors=[],
            turn_history=[],
            next_local_turn_k=1,
        )
        assert "MỤC TIÊU ĐỘ KHÓ: HIGH (4.5/5.0)" in main_high
        assert "Centroid c = 4.5" in main_high
        assert "practical execution & troubleshooting" in main_low
        assert "domain trade-offs" in main_high
