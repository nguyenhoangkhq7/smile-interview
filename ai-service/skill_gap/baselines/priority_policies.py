from abc import ABC, abstractmethod
from typing import Optional


class PriorityPolicy(ABC):
    """
    Focused interface for computing interview priority for a skill gap.
    Allows swappable and fair priority policies across baselines.
    """

    @abstractmethod
    def compute_priority(
        self,
        w_j: float,
        gap_magnitude: Optional[float],
        p_jd: Optional[float] = None
    ) -> Optional[float]:
        """
        Compute interview priority given skill weight w_j, gap_magnitude, and optional P_JD.
        Returns None if gap_magnitude is None (i.e. baseline did not produce a gap).
        """
        pass


class WeightTimesGapPolicy(PriorityPolicy):
    """
    Standard linear priority policy for fair baseline comparison:
        Priority = w_j * gap_magnitude

    Mathematical formulation:
        Priority = w_j * gap_magnitude if gap_magnitude is not None else None

    Clamped to range [0.0, 1.0].
    """

    def compute_priority(
        self,
        w_j: float,
        gap_magnitude: Optional[float],
        p_jd: Optional[float] = None
    ) -> Optional[float]:
        if gap_magnitude is None:
            return None
        raw_val = w_j * gap_magnitude
        return min(1.0, max(0.0, float(raw_val)))


class DepthScaledPriorityPolicy(PriorityPolicy):
    """
    Proposed system priority policy incorporating requirement depth P_JD:
        Priority = w_j * (P_JD / 5.0) * gap_magnitude

    Mathematical formulation (from skill_gap/services/gap_detector.py:85-87):
        depth_factor = min(1.0, max(0.0, P_JD / 5.0))
        Priority = w_j * depth_factor * gap_magnitude

    Clamped to range [0.0, 1.0].
    """

    def compute_priority(
        self,
        w_j: float,
        gap_magnitude: Optional[float],
        p_jd: Optional[float] = None
    ) -> Optional[float]:
        if gap_magnitude is None:
            return None
        depth = 5.0 if p_jd is None else p_jd
        depth_factor = min(1.0, max(0.0, depth / 5.0))
        raw_val = w_j * depth_factor * gap_magnitude
        return min(1.0, max(0.0, float(raw_val)))
