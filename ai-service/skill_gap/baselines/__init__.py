"""
Module baselines: Kiến trúc đối chuẩn và đánh giá so sánh cho Module Skill Gap Detection.
Cung cấp hợp đồng dữ liệu chuẩn, interface chuẩn cho các phương pháp đối chuẩn,
chính sách tính priority, và registry quản lý.
"""

from skill_gap.baselines.base import (
    BaselineInput,
    BaselineMethod,
    BaselineOutputField,
    BaselineSkillResult,
)
from skill_gap.baselines.module_adapter import (
    ProposedModuleBaseline,
    SkillGapModuleAdapter,
)
from skill_gap.baselines.llm.zero_shot import (
    LLMAugmentedBaseline,
    LLMTextOnlyBaseline,
)
from skill_gap.baselines.priority_policies import (
    DepthScaledPriorityPolicy,
    PriorityPolicy,
    WeightTimesGapPolicy,
)
from skill_gap.baselines.proficiency.raw_duration import (
    RawDurationBaseline,
    RawDurationEstimator,
)
from skill_gap.baselines.registry import (
    BaselineRegistry,
    baseline_registry,
)

from skill_gap.baselines.registrations import register_standard_factories

__all__ = [
    "BaselineInput",
    "BaselineMethod",
    "BaselineOutputField",
    "BaselineSkillResult",
    "PriorityPolicy",
    "WeightTimesGapPolicy",
    "DepthScaledPriorityPolicy",
    "BaselineRegistry",
    "baseline_registry",
    "register_standard_factories",
    "SkillGapModuleAdapter",
    "ProposedModuleBaseline",
    "RawDurationEstimator",
    "RawDurationBaseline",
    "LLMAugmentedBaseline",
    "LLMTextOnlyBaseline",
]
