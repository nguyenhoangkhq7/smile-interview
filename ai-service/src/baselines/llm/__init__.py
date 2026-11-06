"""
Subpackage llm: Chứa các baseline Chain-of-Thought sử dụng mô hình ngôn ngữ lớn (LLM):
- LLMAugmentedBaseline: Biến thể chính (kèm tín hiệu từ Module 1)
- LLMTextOnlyBaseline: Biến thể tham khảo (chỉ dùng văn bản thô)
"""

from src.baselines.llm.schemas import (
    LLMSkillAssessment,
    LLMZeroShotResponse,
    RunAuditRecord,
)
from src.baselines.llm.zero_shot import (
    BaseLLMZeroShotBaseline,
    LLMAugmentedBaseline,
    LLMTextOnlyBaseline,
)

__all__ = [
    "LLMAugmentedBaseline",
    "LLMTextOnlyBaseline",
    "BaseLLMZeroShotBaseline",
    "LLMSkillAssessment",
    "LLMZeroShotResponse",
    "RunAuditRecord",
]
