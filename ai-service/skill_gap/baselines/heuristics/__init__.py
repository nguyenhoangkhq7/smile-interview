"""
Package chứa các baseline heuristic và đối chuẩn tham chiếu:
- B-SimGap: Semantic Similarity-as-Gap baseline
- B-Binary: Exact-match heuristic baseline
- B-JDW: Job Description Weight Only baseline
- B-Random: Pseudo-random uniform baseline
"""

from skill_gap.baselines.heuristics.binary_exact import BinaryExactBaseline
from skill_gap.baselines.heuristics.jdw import JDWBaseline
from skill_gap.baselines.heuristics.random_baseline import RandomBaseline
from skill_gap.baselines.heuristics.sim_gap import SimGapBaseline
from skill_gap.baselines.registry import BaselineRegistry, baseline_registry


def register_heuristic_baselines(registry: BaselineRegistry = baseline_registry) -> None:
    """
    Registers the 4 heuristic baselines into the specified registry.
    Idempotent: skips baselines whose names are already registered.
    """
    available = set(registry.list_available())
    baselines = [
        SimGapBaseline(),
        BinaryExactBaseline(),
        JDWBaseline(),
        RandomBaseline(seed=42),
    ]
    for b in baselines:
        if b.name not in available:
            registry.register(b)


# Tự động đăng ký các heuristic baseline vào global registry khi import package
register_heuristic_baselines(baseline_registry)

__all__ = [
    "SimGapBaseline",
    "BinaryExactBaseline",
    "JDWBaseline",
    "RandomBaseline",
    "register_heuristic_baselines",
]
