from typing import List
from unittest.mock import MagicMock

from src.domain.enums import QuestionStrategy, SemanticAlignment, SkillType
from src.domain.models import (
    ExtractedCVSkill,
    ExtractedJDSkill,
    MatchResult,
    SkillGapResult,
)
from src.baselines.base import (
    BaselineInput,
    BaselineOutputField,
    BaselineSkillResult,
)
from src.baselines.module_adapter import (
    ProposedModuleBaseline,
    SkillGapModuleAdapter,
)


def test_skill_gap_module_adapter_preserves_values() -> None:
    """
    Kiểm tra SkillGapModuleAdapter chuyển đổi SkillGapResult sang BaselineSkillResult
    mà KHÔNG làm thay đổi bất kỳ giá trị nào của các trường output.
    """
    original = SkillGapResult(
        jd_skill_id="kubernetes",
        semantic_alignment=SemanticAlignment.MATCH,
        matched_cv_skill_id="kubernetes",
        is_substituted=False,
        gap_magnitude=0.25,
        severity=0.10,
        priority=0.10,
        required_proficiency=4.0,
        candidate_proficiency=3.0,
        cv_evidence_spans=["Quản lý k8s cluster 2 năm"],
        context_job="DevOps Engineer (2020-2022)",
        suggested_strategy=QuestionStrategy.PROBE_DEPTH,
        degraded=False,
        flags=["audit_verified"],
    )

    adapted = SkillGapModuleAdapter.adapt(original, baseline_name="proposed_module")

    assert isinstance(adapted, BaselineSkillResult)
    # Kiểm tra bảo toàn các giá trị cốt lõi
    assert adapted.jd_skill_id == "kubernetes"
    assert adapted.semantic_alignment == SemanticAlignment.MATCH
    assert adapted.required_proficiency == 4.0
    assert adapted.candidate_proficiency == 3.0
    assert adapted.gap_magnitude == 0.25
    assert adapted.priority == 0.10

    # Kiểm tra metadata phong phú được bảo toàn
    assert adapted.metadata["baseline_name"] == "proposed_module"
    assert adapted.metadata["matched_cv_skill_id"] == "kubernetes"
    assert adapted.metadata["is_substituted"] is False
    assert adapted.metadata["severity"] == 0.10
    assert adapted.metadata["suggested_strategy"] == "PROBE_DEPTH"
    assert adapted.metadata["cv_evidence_spans"] == ["Quản lý k8s cluster 2 năm"]
    assert adapted.metadata["context_job"] == "DevOps Engineer (2020-2022)"
    assert adapted.metadata["degraded"] is False
    assert adapted.metadata["flags"] == ["audit_verified"]


def test_skill_gap_module_adapter_adapt_all() -> None:
    """Kiểm tra phương thức adapt_all trên danh sách kết quả."""
    results = [
        SkillGapResult(
            jd_skill_id="k8s",
            semantic_alignment=SemanticAlignment.MATCH,
            matched_cv_skill_id="k8s",
            is_substituted=False,
            gap_magnitude=0.0,
            severity=0.0,
            priority=0.0,
            required_proficiency=3.0,
            candidate_proficiency=3.0,
            suggested_strategy=QuestionStrategy.NONE,
        ),
        SkillGapResult(
            jd_skill_id="aws",
            semantic_alignment=SemanticAlignment.MISSING,
            matched_cv_skill_id=None,
            is_substituted=False,
            gap_magnitude=1.0,
            severity=0.3,
            priority=0.3,
            required_proficiency=5.0,
            candidate_proficiency=1.0,
            suggested_strategy=QuestionStrategy.LEARNING_AGILITY,
        ),
    ]

    adapted_list = SkillGapModuleAdapter.adapt_all(results, baseline_name="test_run")
    assert len(adapted_list) == 2
    assert adapted_list[0].jd_skill_id == "k8s"
    assert adapted_list[0].gap_magnitude == 0.0
    assert adapted_list[1].jd_skill_id == "aws"
    assert adapted_list[1].gap_magnitude == 1.0
    assert adapted_list[1].semantic_alignment == SemanticAlignment.MISSING


def test_proposed_module_baseline_wrapper() -> None:
    """
    Kiểm tra ProposedModuleBaseline đóng gói Orchestrator dưới interface BaselineMethod
    mà không cần gọi LLM thật (sử dụng Fake/Mock orchestrator).
    """
    # Tạo fake orchestrator trả về kết quả giả định đã biết trước
    fake_orchestrator = MagicMock()
    mock_gap_result = SkillGapResult(
        jd_skill_id="python",
        semantic_alignment=SemanticAlignment.MATCH,
        matched_cv_skill_id="python",
        is_substituted=False,
        gap_magnitude=0.125,
        severity=0.05,
        priority=0.05,
        required_proficiency=4.0,
        candidate_proficiency=3.5,
        suggested_strategy=QuestionStrategy.PROBE_DEPTH,
    )
    fake_orchestrator.run_pipeline.return_value = [mock_gap_result]

    baseline = ProposedModuleBaseline(orchestrator=fake_orchestrator, name="proposed_module")

    # Kiểm tra thuộc tính
    assert baseline.name == "proposed_module"
    expected_produces = frozenset(
        {
            BaselineOutputField.ALIGNMENT,
            BaselineOutputField.P_JD,
            BaselineOutputField.P_CV,
            BaselineOutputField.GAP_MAGNITUDE,
            BaselineOutputField.PRIORITY,
        }
    )
    assert baseline.produces == expected_produces

    # Tạo input chuẩn
    inp = BaselineInput(
        cv_text="CV Python developer",
        jd_text="JD cần Python 4 năm",
        cv_skills=[
            ExtractedCVSkill(
                skill_id="python",
                type=SkillType.EXPLICIT,
                confidence=0.95,
                evidence_spans=["Lập trình Python 3 năm"],
            )
        ],
        jd_skills=[
            ExtractedJDSkill(
                skill_id="python",
                type=SkillType.EXPLICIT,
                confidence=0.95,
                evidence_spans=["Python 4 năm kinh nghiệm"],
            )
        ],
        match_results=[
            MatchResult(
                jd_skill_id="python",
                w_j=0.25,
                matched_cv_skill_id="python",
                soft_match=1.0,
            )
        ],
    )

    # Chạy baseline
    output = baseline.run(inp)

    # Kiểm tra tương tác với Orchestrator
    fake_orchestrator.run_pipeline.assert_called_once_with(
        cv_text=inp.cv_text,
        jd_text=inp.jd_text,
        cv_skills=inp.cv_skills,
        jd_skills=inp.jd_skills,
        match_results=inp.match_results,
    )

    # Kiểm tra kết quả chuyển đổi
    assert len(output) == 1
    assert output[0].jd_skill_id == "python"
    assert output[0].gap_magnitude == 0.125
    assert output[0].priority == 0.05
    assert output[0].metadata["baseline_name"] == "proposed_module"
