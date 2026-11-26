import pytest
from typing import List

from skill_gap.domain.enums import RichnessLabel, SemanticAlignment, SeniorityLevel, SkillType
from skill_gap.domain.models import (
    ExtractedCVSkill,
    ExtractedJDSkill,
    JobBlock,
    MatchResult,
    SpanMapping,
    SpanRichness,
    JDRequirement,
    JDParserOutput,
)
from skill_gap.adapters.config import AppConfig
from skill_gap.services.proficiency_estimator import (
    ProficiencyEstimator,
    SpanAnalysisList,
)
from skill_gap.services.resume_segmenter import (
    JobBlockExtraction,
    SpanMappingExtraction,
)
from skill_gap.pipeline.orchestrator import SkillGapOrchestrator
from skill_gap.baselines.base import BaselineInput, BaselineOutputField
from skill_gap.baselines.proficiency.raw_duration import (
    RawDurationBaseline,
    RawDurationEstimator,
)


class MockFixedLLM:
    """Mock LLM deterministic cho các bài test proficiency."""

    def complete(self, prompt: str, schema):
        name = schema.__name__
        if name == "SpanAnalysisList":
            # Luôn trả về RICH_CONTEXT
            return SpanAnalysisList(
                analyses=[
                    SpanRichness(span="Rich Span", richness_label=RichnessLabel.RICH_CONTEXT),
                    SpanRichness(span="List Span", richness_label=RichnessLabel.LIST_ONLY),
                ]
            )
        elif name == "JobBlockExtraction":
            return JobBlockExtraction(job_blocks=[])
        elif name == "SpanMappingExtraction":
            return SpanMappingExtraction(span_mappings=[])
        elif name == "JDParserOutput":
            return JDParserOutput(requirements=[])
        raise ValueError(f"Unexpected schema: {name}")


# ==============================================================================
# 1. Test việc làm chồng chéo (Overlapping Jobs)
# ==============================================================================

def test_raw_duration_overlapping_jobs_double_counts() -> None:
    """
    Kiểm thử hai việc làm chồng chéo 12 tháng:
    - Job 1: 2022-01 đến 2022-12 (12 tháng).
    - Job 2: 2022-06 đến 2023-05 (12 tháng).
    Tính tay:
    - Estimator thô (RawDurationEstimator): cộng dồn độc lập = 12 + 12 = 24.0 tháng.
    - Estimator gốc (ProficiencyEstimator): Interval Union từ 2022-01 đến 2023-05 = 17 tháng.
      (Với Seniority MID 1.0 và Rich 1.0 -> 17.0 tháng).
    Chứng minh: Estimator thô cho tháng = tổng (24.0), estimator gốc cho tháng nhỏ hơn (17.0).
    """
    config = AppConfig(reference_date="2024-06-01")

    job1 = JobBlock(
        job_id="job1",
        title="Software Engineer A",
        seniority_level=SeniorityLevel.MID,
        start_date="2022-01",
        end_date="2022-12",
        raw_text="Worked on Python A",
    )
    job2 = JobBlock(
        job_id="job2",
        title="Software Engineer B",
        seniority_level=SeniorityLevel.MID,
        start_date="2022-06",
        end_date="2023-05",
        raw_text="Worked on Python B",
    )

    skill = ExtractedCVSkill(
        skill_id="python",
        type=SkillType.EXPLICIT,
        confidence=1.0,
        evidence_spans=["Python span 1", "Python span 2"],
    )

    mappings = [
        SpanMapping(span="Python span 1", job_id="job1"),
        SpanMapping(span="Python span 2", job_id="job2"),
    ]

    # 1. Chạy với RawDurationEstimator
    raw_estimator = RawDurationEstimator(config=config)
    raw_res = raw_estimator.estimate(skill=skill, mappings=mappings, job_blocks=[job1, job2])

    # Tính tay: 12 + 12 = 24 tháng thô
    assert raw_res.effective_months == pytest.approx(24.0, abs=1e-9)

    # 2. Chạy với ProficiencyEstimator gốc (có Interval Union)
    class RichOnlyLLM:
        def complete(self, prompt, schema):
            return SpanAnalysisList(
                analyses=[
                    SpanRichness(span="Python span 1", richness_label=RichnessLabel.RICH_CONTEXT),
                    SpanRichness(span="Python span 2", richness_label=RichnessLabel.RICH_CONTEXT),
                ]
            )

    orig_estimator = ProficiencyEstimator(llm_client=RichOnlyLLM(), config=config)
    orig_res = orig_estimator.estimate(skill=skill, mappings=mappings, job_blocks=[job1, job2])

    # Tính tay Interval Union: từ 2022-01 đến 2023-05 = 17 tháng
    assert orig_res.effective_months == pytest.approx(17.0, abs=1e-9)

    # Khẳng định sự khác biệt đúng trọng tâm
    assert raw_res.effective_months > orig_res.effective_months


# ==============================================================================
# 2. Test không phạt ngữ cảnh (LIST_ONLY vs RICH_CONTEXT)
# ==============================================================================

def test_raw_duration_ignores_context_density() -> None:
    """
    Kiểm thử: Kỹ năng chỉ liệt kê từ khóa (LIST_ONLY) có số tháng BẰNG HỆT
    kỹ năng có ngữ cảnh dự án phong phú (RICH_CONTEXT) khi dùng RawDurationEstimator.
    - Cùng thời lượng: 12 tháng (2022-01 đến 2022-12).
    - RawDurationEstimator: cả hai đều = 12.0 tháng (không phạt 0.3).
    - So sánh với Estimator gốc: LIST_ONLY bị phạt xuống 12 * 0.3 = 3.6 tháng.
    """
    config = AppConfig(reference_date="2024-06-01")
    job = JobBlock(
        job_id="job1",
        title="Developer",
        seniority_level=SeniorityLevel.MID,
        start_date="2022-01",
        end_date="2022-12",
        raw_text="Job details",
    )

    skill_list = ExtractedCVSkill(
        skill_id="docker",
        type=SkillType.EXPLICIT,
        confidence=0.9,
        evidence_spans=["Skills: Docker, K8s"],
    )
    skill_rich = ExtractedCVSkill(
        skill_id="kubernetes",
        type=SkillType.EXPLICIT,
        confidence=0.9,
        evidence_spans=["Triển khai kiến trúc microservices Kubernetes production"],
    )

    mapping_list = [SpanMapping(span="Skills: Docker, K8s", job_id="job1")]
    mapping_rich = [SpanMapping(span="Triển khai kiến trúc microservices Kubernetes production", job_id="job1")]

    raw_estimator = RawDurationEstimator(config=config)
    res_list = raw_estimator.estimate(skill_list, mapping_list, [job])
    res_rich = raw_estimator.estimate(skill_rich, mapping_rich, [job])

    # Cả hai đều đạt trọn vẹn 12 tháng thô
    assert res_list.effective_months == pytest.approx(12.0, abs=1e-9)
    assert res_rich.effective_months == pytest.approx(12.0, abs=1e-9)
    assert res_list.effective_months == res_rich.effective_months

    # So sánh với estimator gốc:
    class ContextMockLLM:
        def complete(self, prompt, schema):
            return SpanAnalysisList(
                analyses=[
                    SpanRichness(span="Skills: Docker, K8s", richness_label=RichnessLabel.LIST_ONLY),
                    SpanRichness(span="Triển khai kiến trúc microservices Kubernetes production", richness_label=RichnessLabel.RICH_CONTEXT),
                ]
            )

    orig_estimator = ProficiencyEstimator(llm_client=ContextMockLLM(), config=config)
    orig_list = orig_estimator.estimate(skill_list, mapping_list, [job])
    orig_rich = orig_estimator.estimate(skill_rich, mapping_rich, [job])

    # Estimator gốc phạt LIST_ONLY: 12 * 0.3 = 3.6 tháng vs 12 * 1.0 = 12.0 tháng
    assert orig_list.effective_months == pytest.approx(3.6, abs=1e-9)
    assert orig_rich.effective_months == pytest.approx(12.0, abs=1e-9)


# ==============================================================================
# 3. Test bảng nội suy P_CV tại các mốc và điểm trung gian
# ==============================================================================

def test_raw_duration_interpolation_milestones() -> None:
    """
    Kiểm thử hàm nội suy P_CV từ số tháng:
    Bảng mốc chuẩn từ config:
      0 tháng -> 1.0
      6 tháng -> 2.0
      18 tháng -> 3.0
      36 tháng -> 4.0
      60 tháng -> 5.0
    Các mốc trung gian tính tay:
      3 tháng: 1.0 + (3 - 0) * (2.0 - 1.0) / 6 = 1.50
      12 tháng: 2.0 + (12 - 6) * (3.0 - 2.0) / 12 = 2.50
      27 tháng: 3.0 + (27 - 18) * (4.0 - 3.0) / 18 = 3.50
      48 tháng: 4.0 + (48 - 36) * (5.0 - 4.0) / 24 = 4.50
      80 tháng: vượt 60 -> chặn trên 5.0
    """
    config = AppConfig()
    estimator = RawDurationEstimator(config=config)

    # 1. Các mốc chính xác
    assert estimator._map_experience_to_proficiency(0.0) == pytest.approx(1.0, abs=1e-9)
    assert estimator._map_experience_to_proficiency(6.0) == pytest.approx(2.0, abs=1e-9)
    assert estimator._map_experience_to_proficiency(18.0) == pytest.approx(3.0, abs=1e-9)
    assert estimator._map_experience_to_proficiency(36.0) == pytest.approx(4.0, abs=1e-9)
    assert estimator._map_experience_to_proficiency(60.0) == pytest.approx(5.0, abs=1e-9)

    # 2. Các điểm nội suy trung gian tính tay
    assert estimator._map_experience_to_proficiency(3.0) == pytest.approx(1.50, abs=1e-9)
    assert estimator._map_experience_to_proficiency(12.0) == pytest.approx(2.50, abs=1e-9)
    assert estimator._map_experience_to_proficiency(27.0) == pytest.approx(3.50, abs=1e-9)
    assert estimator._map_experience_to_proficiency(48.0) == pytest.approx(4.50, abs=1e-9)

    # 3. Chặn biên
    assert estimator._map_experience_to_proficiency(80.0) == pytest.approx(5.0, abs=1e-9)


# ==============================================================================
# 4. Test hồi quy (Regression Test): Module gốc không đổi sau refactor
# ==============================================================================

def test_orchestrator_regression_unchanged_behavior() -> None:
    """
    Kiểm thử hồi quy: SkillGapOrchestrator khi KHÔNG truyền estimator (dùng mặc định)
    phải cho ra output hoàn toàn trùng khớp với hành vi gốc trước refactoring.
    """
    config = AppConfig()

    class FullMockLLM:
        def complete(self, prompt: str, schema):
            name = schema.__name__
            if name == "JobBlockExtraction":
                return JobBlockExtraction(
                    job_blocks=[
                        JobBlock(
                            job_id="job_1",
                            title="Senior Engineer",
                            seniority_level=SeniorityLevel.SENIOR,
                            start_date="2022-01",
                            end_date="2024-01",
                            raw_text="Dev",
                        )
                    ]
                )
            elif name == "SpanMappingExtraction":
                return SpanMappingExtraction(
                    span_mappings=[
                        SpanMapping(span="Span K8s", job_id="job_1"),
                    ]
                )
            elif name == "JDParserOutput":
                return JDParserOutput(
                    requirements=[
                        JDRequirement(jd_skill_id="k8s", required_level=4.0, reasoning="Senior"),
                    ]
                )
            elif name == "SpanAnalysisList":
                return SpanAnalysisList(
                    analyses=[
                        SpanRichness(span="Span K8s", richness_label=RichnessLabel.RICH_CONTEXT),
                    ]
                )
            raise ValueError(f"Unknown schema: {name}")

    llm = FullMockLLM()
    # Khởi tạo không truyền estimator -> phải dùng ProficiencyEstimator gốc
    orchestrator = SkillGapOrchestrator(llm_client=llm, config=config)

    cv_skills = [
        ExtractedCVSkill(skill_id="k8s", type=SkillType.EXPLICIT, confidence=0.9, evidence_spans=["Span K8s"])
    ]
    jd_skills = [
        ExtractedJDSkill(skill_id="k8s", type=SkillType.EXPLICIT, confidence=0.9, evidence_spans=["Req K8s"])
    ]
    matches = [
        MatchResult(jd_skill_id="k8s", w_j=0.4, matched_cv_skill_id="k8s", soft_match=1.0)
    ]

    results = orchestrator.run_pipeline(
        cv_text="CV",
        jd_text="JD",
        cv_skills=cv_skills,
        jd_skills=jd_skills,
        match_results=matches,
    )

    assert len(results) == 1
    r = results[0]
    assert r.jd_skill_id == "k8s"
    assert r.semantic_alignment == SemanticAlignment.MATCH
    assert r.is_substituted is False
    assert r.required_proficiency == 4.0
    # 25 tháng (2022-01 đến 2024-01 inclusive), Senior 1.0, Rich 1.0 -> 25 tháng -> P_CV = 3.389
    assert r.candidate_proficiency == pytest.approx(3.389, abs=1e-2)
    # gap = max(0, 4.0 - 1.0 * 3.389) / 4.0 = (4.0 - 3.389) / 4.0 = 0.611 / 4.0 = 0.1527
    expected_gap = (4.0 - r.candidate_proficiency) / 4.0
    assert r.gap_magnitude == pytest.approx(expected_gap, abs=1e-4)


# ==============================================================================
# 5. Test đóng gói RawDurationBaseline (BaselineMethod)
# ==============================================================================

def test_raw_duration_baseline_wrapper() -> None:
    """
    Kiểm thử RawDurationBaseline:
    - Thuộc tính produces có đủ 5 fields.
    - Phương thức run trả về danh sách BaselineSkillResult được chuyển đổi đúng.
    """
    config = AppConfig()

    class BaselineMockLLM:
        def complete(self, prompt: str, schema):
            name = schema.__name__
            if name == "JobBlockExtraction":
                return JobBlockExtraction(
                    job_blocks=[
                        JobBlock(
                            job_id="j1",
                            title="Junior Dev",
                            seniority_level=SeniorityLevel.JUNIOR,
                            start_date="2023-01",
                            end_date="2023-06",
                            raw_text="Junior",
                        )
                    ]
                )
            elif name == "SpanMappingExtraction":
                return SpanMappingExtraction(
                    span_mappings=[
                        SpanMapping(span="Java work", job_id="j1"),
                    ]
                )
            elif name == "JDParserOutput":
                return JDParserOutput(
                    requirements=[
                        JDRequirement(jd_skill_id="java", required_level=3.0, reasoning="Mid Java"),
                    ]
                )
            raise ValueError(f"Unknown schema: {name}")

    llm = BaselineMockLLM()
    baseline = RawDurationBaseline(llm_client=llm, config=config, name="B-RawDuration")

    assert baseline.name == "B-RawDuration"
    assert baseline.produces == frozenset(
        {
            BaselineOutputField.ALIGNMENT,
            BaselineOutputField.P_JD,
            BaselineOutputField.P_CV,
            BaselineOutputField.GAP_MAGNITUDE,
            BaselineOutputField.PRIORITY,
        }
    )

    inp = BaselineInput(
        cv_text="CV",
        jd_text="JD",
        cv_skills=[
            ExtractedCVSkill(skill_id="java", type=SkillType.EXPLICIT, confidence=0.9, evidence_spans=["Java work"])
        ],
        jd_skills=[
            ExtractedJDSkill(skill_id="java", type=SkillType.EXPLICIT, confidence=0.9, evidence_spans=["Java req"])
        ],
        match_results=[
            MatchResult(jd_skill_id="java", w_j=0.3, matched_cv_skill_id="java", soft_match=1.0)
        ],
    )

    results = baseline.run(inp)
    assert len(results) == 1
    res = results[0]
    assert res.jd_skill_id == "java"
    assert res.semantic_alignment == SemanticAlignment.MATCH
    assert res.required_proficiency == 3.0
    # 6 tháng (2023-01 đến 2023-06 inclusive) không nhân trọng số Junior 0.8 -> 6 tháng thô -> P_CV = 2.0
    assert res.candidate_proficiency == pytest.approx(2.0, abs=1e-9)
    # gap = (3.0 - 2.0) / 4.0 = 0.25
    assert res.gap_magnitude == pytest.approx(0.25, abs=1e-9)
    # priority = w_j * (P_JD / 5.0) * gap = 0.3 * (3.0 / 5.0) * 0.25 = 0.3 * 0.6 * 0.25 = 0.045
    assert res.priority == pytest.approx(0.045, abs=1e-9)
    assert res.metadata["baseline_name"] == "B-RawDuration"


def test_raw_duration_baseline_registry_integration() -> None:
    """Kiểm tra RawDurationBaseline đăng ký và tra cứu thành công trong BaselineRegistry."""
    from skill_gap.baselines.registry import BaselineRegistry
    registry = BaselineRegistry()
    baseline = RawDurationBaseline(llm_client=MockFixedLLM(), name="B-RawDuration")
    registry.register(baseline)

    assert "B-RawDuration" in registry.list_available()
    assert registry.get("B-RawDuration") is baseline
