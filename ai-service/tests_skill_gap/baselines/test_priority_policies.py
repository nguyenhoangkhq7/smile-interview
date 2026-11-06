import pytest

from src.baselines.priority_policies import (
    DepthScaledPriorityPolicy,
    WeightTimesGapPolicy,
)


def test_weight_times_gap_policy_hand_calculated() -> None:
    """
    Kiểm thử WeightTimesGapPolicy với các giá trị TÍNH TAY:
    Công thức: priority = w_j * gap_magnitude
    """
    policy = WeightTimesGapPolicy()

    # Trường hợp 1:
    # w_j = 0.40, gap_magnitude = 0.50
    # Tính tay: 0.40 * 0.50 = 0.20
    p1 = policy.compute_priority(w_j=0.40, gap_magnitude=0.50)
    assert p1 == pytest.approx(0.20, abs=1e-9)

    # Trường hợp 2:
    # w_j = 0.25, gap_magnitude = 0.80
    # Tính tay: 0.25 * 0.80 = 0.20
    p2 = policy.compute_priority(w_j=0.25, gap_magnitude=0.80)
    assert p2 == pytest.approx(0.20, abs=1e-9)

    # Trường hợp 3: Không có gap (gap = 0.0)
    # w_j = 0.35, gap_magnitude = 0.0
    # Tính tay: 0.35 * 0.0 = 0.0
    p3 = policy.compute_priority(w_j=0.35, gap_magnitude=0.0)
    assert p3 == pytest.approx(0.0, abs=1e-9)

    # Trường hợp 4: Gap tối đa (gap = 1.0)
    # w_j = 0.50, gap_magnitude = 1.0
    # Tính tay: 0.50 * 1.0 = 0.50
    p4 = policy.compute_priority(w_j=0.50, gap_magnitude=1.0)
    assert p4 == pytest.approx(0.50, abs=1e-9)

    # Trường hợp 5: Baseline không sinh ra gap (gap is None)
    # Quy tắc: baseline không tính gap thì priority = None
    p_none = policy.compute_priority(w_j=0.50, gap_magnitude=None)
    assert p_none is None


def test_depth_scaled_priority_policy_hand_calculated() -> None:
    """
    Kiểm thử DepthScaledPriorityPolicy với các giá trị TÍNH TAY:
    Công thức: depth_factor = min(1.0, max(0.0, P_JD / 5.0))
               priority = w_j * depth_factor * gap_magnitude
    """
    policy = DepthScaledPriorityPolicy()

    # Trường hợp 1:
    # w_j = 0.50, P_JD = 4.0, gap_magnitude = 0.25
    # Tính tay:
    # depth_factor = 4.0 / 5.0 = 0.80
    # priority = 0.50 * 0.80 * 0.25 = 0.10
    p1 = policy.compute_priority(w_j=0.50, gap_magnitude=0.25, p_jd=4.0)
    assert p1 == pytest.approx(0.10, abs=1e-9)

    # Trường hợp 2: Kỹ năng chuyên gia (P_JD = 5.0), gap = 1.0, w_j = 0.30
    # Tính tay:
    # depth_factor = 5.0 / 5.0 = 1.00
    # priority = 0.30 * 1.00 * 1.00 = 0.30
    p2 = policy.compute_priority(w_j=0.30, gap_magnitude=1.00, p_jd=5.0)
    assert p2 == pytest.approx(0.30, abs=1e-9)

    # Trường hợp 3: Kỹ năng sơ cấp (P_JD = 1.5), gap = 1.0, w_j = 0.30
    # Tính tay:
    # depth_factor = 1.5 / 5.0 = 0.30
    # priority = 0.30 * 0.30 * 1.00 = 0.09
    p3 = policy.compute_priority(w_j=0.30, gap_magnitude=1.00, p_jd=1.5)
    assert p3 == pytest.approx(0.09, abs=1e-9)

    # Tỷ lệ phân hóa giữa Lead (5.0) và Intern (1.5) cùng gap = 1.0 và cùng w_j:
    # 0.30 / 0.09 = 3.333333333... (chính xác tỷ lệ 3.33x nêu trong walkthrough.md:11)
    ratio = p2 / p3
    assert ratio == pytest.approx(5.0 / 1.5, abs=1e-9)

    # Trường hợp 4: P_JD không truyền vào (mặc định là 5.0 -> depth_factor = 1.0)
    # w_j = 0.20, gap_magnitude = 0.50
    # Tính tay: 0.20 * 1.0 * 0.50 = 0.10
    p4 = policy.compute_priority(w_j=0.20, gap_magnitude=0.50, p_jd=None)
    assert p4 == pytest.approx(0.10, abs=1e-9)

    # Trường hợp 5: gap_magnitude is None
    p_none = policy.compute_priority(w_j=0.50, gap_magnitude=None, p_jd=4.0)
    assert p_none is None
