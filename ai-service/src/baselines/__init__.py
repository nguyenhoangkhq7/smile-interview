"""
Module baselines: Kiến trúc đối chuẩn và đánh giá so sánh cho Module Skill Gap Detection.
Cung cấp hợp đồng dữ liệu chuẩn, interface chuẩn cho các phương pháp đối chuẩn,
chính sách tính priority, và registry quản lý.
"""

from src.baselines.base import (
    BaselineInput,
    BaselineMethod,
    BaselineOutputField,
    BaselineSkillResult,
)
from src.baselines.module_adapter import (
    ProposedModuleBaseline,
    SkillGapModuleAdapter,
)
from src.baselines.llm.zero_shot import (
    LLMAugmentedBaseline,
    LLMTextOnlyBaseline,
)
from src.baselines.priority_policies import (
    DepthScaledPriorityPolicy,
    PriorityPolicy,
    WeightTimesGapPolicy,
)
from src.baselines.proficiency.raw_duration import (
    RawDurationBaseline,
    RawDurationEstimator,
)
from src.baselines.registry import (
    BaselineRegistry,
    baseline_registry,
)

from src.baselines.registrations import register_standard_factories

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
