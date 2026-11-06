import pytest
from src.domain.enums import SemanticAlignment, QuestionStrategy
from src.domain.models import JDRequirement, ProficiencyResult, MatchResult
from src.adapters.config import AppConfig
from src.services.gap_detector import GapDetector

class MockLLMClient:
    def complete(self, prompt: str, schema):
        return None

def test_gap_detector_layers():
    config = AppConfig()
    llm = MockLLMClient()
    detector = GapDetector(llm_client=llm, config=config)
    
    # 1. Semantic alignment test
    assert detector.compute_semantic_alignment(0.9) == SemanticAlignment.MATCH
    assert detector.compute_semantic_alignment(0.6) == SemanticAlignment.PARTIAL
    assert detector.compute_semantic_alignment(0.2) == SemanticAlignment.MISSING
    
    # 2. Substitution factor test (công thức mới: dùng soft_match trực tiếp trong PARTIAL)
    assert detector.compute_substitution_factor(0.85) == 1.0   # MATCH → full credit
    assert detector.compute_substitution_factor(0.40) == pytest.approx(0.40, 1e-9)  # floor PARTIAL → s = soft_match (không còn = 0)
    assert detector.compute_substitution_factor(0.60) == pytest.approx(0.60, 1e-9)  # mid PARTIAL → s = soft_match
    assert detector.compute_substitution_factor(0.95) == 1.0   # above identity → clipped to 1.0
    assert detector.compute_substitution_factor(0.20) == 0.0   # MISSING → no credit
    
    # 3. Gap magnitude test (normalized over 4.0 scale width)
    # P_JD = 4.0, P_CV = 3.0, s = 1.0 -> d = 1.0 -> gap = 1.0 / 4.0 = 0.25
    gap = detector.compute_gap_magnitude(
        required_level=4.0,
        candidate_proficiency=3.0,
        substitution_factor=1.0,
        alignment=SemanticAlignment.MATCH
    )
    assert gap == 0.25
    
    # 4. Deterministic Priority test (Priority = Severity = w_j * (P_JD/5.0) * gap)
    severity, priority = detector.compute_priorities(
        w_j=0.5,
        gap_magnitude=0.25,
        required_level=4.0
    )
    assert severity == pytest.approx(0.5 * (4.0 / 5.0) * 0.25, 1e-6)
    assert priority == severity
    
    # 5. End-to-End detection
    reqs = [
        JDRequirement(jd_skill_id="java", required_level=4.0, reasoning="Senior Java"),
        JDRequirement(jd_skill_id="rabbitmq", required_level=3.0, reasoning="Mid RMQ")
    ]
    profs = [
        ProficiencyResult(
            skill_id="java",
            proficiency=3.0,
            c_evidence=0.9,
            effective_months=18.0
        ),
        ProficiencyResult(
            skill_id="kafka",
            proficiency=3.5,
            c_evidence=0.8,
            effective_months=24.0
        )
    ]
    matches = [
        MatchResult(jd_skill_id="java", w_j=0.6, matched_cv_skill_id="java", soft_match=1.0),
        MatchResult(jd_skill_id="rabbitmq", w_j=0.4, matched_cv_skill_id="kafka", soft_match=0.8)
    ]
    
    results = detector.detect(reqs, profs, matches)
    r_java = next(r for r in results if r.jd_skill_id == "java")
    assert r_java.semantic_alignment == SemanticAlignment.MATCH
    assert r_java.gap_magnitude == 0.25
    # Severity = w_j * (P_JD/5.0) * gap = 0.6 * (4.0/5.0) * 0.25 = 0.12
    assert r_java.severity == pytest.approx(0.6 * (4.0 / 5.0) * 0.25, 1e-6)
    assert r_java.suggested_strategy == QuestionStrategy.PROBE_DEPTH
    
    r_rmq = next(r for r in results if r.jd_skill_id == "rabbitmq")
    assert r_rmq.semantic_alignment == SemanticAlignment.PARTIAL
    assert r_rmq.is_substituted is True
    assert r_rmq.suggested_strategy == QuestionStrategy.COMPARE_SUBSTITUTE


def test_strategy_at_floor_boundary():
    """
    Regression test cho 2 bug liên tiếp được sửa:

    Bug 1 (đã sửa): strategy sai tại boundary PARTIAL.
    - Điều kiện cũ '0.0 < s < 1.0' không thoả khi s=0 → strategy = PROBE_DEPTH (sai).
    - Fix: dùng alignment label: PARTIAL → COMPARE_SUBSTITUTE.

    Bug 2 (đang sửa): substitution_factor sai tại soft_match = floor_threshold.
    - Công thức cũ: s = (0.40 - 0.40) / (0.85 - 0.40) = 0.0 → không tín dụng.
    - Công thức mới: s = soft_match = 0.40 → Vue nhận 40% tín dụng cho React.
    - Gap mới: (3.0 - 0.40 * 3.111) / 4.0 = (3.0 - 1.244) / 4.0 ≈ 0.439 (thay vì 0.75).
    """
    config = AppConfig()
    llm = MockLLMClient()
    detector = GapDetector(llm_client=llm, config=config)

    # Xác nhận floor_threshold = 0.40 từ config
    assert config.thresholds.floor_threshold == pytest.approx(0.40, 1e-9)

    # soft_match chính xác tại floor → s = 0.40 (công thức mới), alignment = PARTIAL
    s = detector.compute_substitution_factor(0.40)
    alignment = detector.compute_semantic_alignment(0.40)
    assert s == pytest.approx(0.40, 1e-9)   # không còn = 0.0
    assert alignment == SemanticAlignment.PARTIAL

    # strategy vẫn phải là COMPARE_SUBSTITUTE
    strategy = detector.classify_question_strategy(
        alignment=alignment,
        substitution_factor=s,
        gap_magnitude=0.439  # gap nhỏ hơn trước vì s > 0
    )
    assert strategy == QuestionStrategy.COMPARE_SUBSTITUTE

    # Verify end-to-end qua detect()
    # gap = (3.0 - 0.40 * 3.111) / 4.0 = (3.0 - 1.244) / 4.0 = 0.439
    reqs = [JDRequirement(jd_skill_id="react", required_level=3.0, reasoning="Mid React")]
    profs = [ProficiencyResult(skill_id="vue", proficiency=3.111, c_evidence=1.0, effective_months=20.0)]
    matches = [MatchResult(jd_skill_id="react", w_j=0.20, matched_cv_skill_id="vue", soft_match=0.40)]

    results = detector.detect(reqs, profs, matches)
    assert len(results) == 1
    r = results[0]
    assert r.semantic_alignment == SemanticAlignment.PARTIAL
    assert r.is_substituted is True
    assert r.suggested_strategy == QuestionStrategy.COMPARE_SUBSTITUTE
    # s=0.40: effective = 0.40 * 3.111 = 1.244 → gap = (3.0 - 1.244) / 4.0 ≈ 0.439
    assert r.gap_magnitude == pytest.approx(0.439, abs=1e-3)
