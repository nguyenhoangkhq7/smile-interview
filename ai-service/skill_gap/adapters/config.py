import os
from datetime import date
from pathlib import Path
import yaml
from typing import Dict, Optional
from pydantic import BaseModel, Field

class ThresholdsConfig(BaseModel):
    identity_threshold: float = Field(
        default=0.85,
        description="Ngưỡng soft_match tối thiểu để xác nhận là MATCH hoàn toàn"
    )
    floor_threshold: float = Field(
        default=0.40,
        description="Ngưỡng soft_match tối thiểu để xác nhận kỹ năng có thể thay thế (PARTIAL)"
    )

class SeniorityWeightsConfig(BaseModel):
    # Nhóm Có hướng dẫn (Supervised / Entry)
    Intern: float = 0.8
    Junior: float = 0.8
    # Nhóm Độc lập / Dẫn dắt (Autonomous / Core)
    Mid: float = 1.0
    Senior: float = 1.0
    Lead: float = 1.0
    Unknown: float = 1.0

class ContextWeightsConfig(BaseModel):
    rich_context: float = 1.0
    list_only: float = 0.3
    ambiguous: float = 0.5

class NormalizationConfig(BaseModel):
    mode: str = "absolute"
    milestones_months: Dict[int, float] = Field(
        default_factory=lambda: {
            0: 1.0,
            6: 2.0,
            18: 3.0,
            36: 4.0,
            60: 5.0
        },
        description="Bảng ánh xạ số tháng kinh nghiệm tích lũy sang mức năng lực 1.0 - 5.0"
    )

class Phase3Config(BaseModel):
    evidence_fuzzy_threshold: float = Field(
        default=0.85,
        description="Ngưỡng fuzzy string matching để kiểm tra trích dẫn nguyên văn trong CV"
    )
    max_llm_retries: int = Field(
        default=3,
        description="Số lần thử lại tối đa trước khi gắn cờ degraded"
    )

class LLMConfig(BaseModel):
    model: str = "qwen/qwen3.7-flash"
    temperature: float = 0.0
    seed: int = 42
    n_consistency: int = 1

class AppConfig(BaseModel):
    reference_date: str = Field(
        default_factory=lambda: date.today().isoformat(),
        description="Ngày tham chiếu cố định (ISO YYYY-MM-DD) đảm bảo tính tái lập 100%"
    )
    recency_years_threshold: float = Field(
        default=3.0,
        description="Số năm tối đa tính từ lần cuối sử dụng kỹ năng trước khi kích hoạt Recency Flag"
    )

    thresholds: ThresholdsConfig = ThresholdsConfig()
    seniority_weights: SeniorityWeightsConfig = SeniorityWeightsConfig()
    context_weights: ContextWeightsConfig = ContextWeightsConfig()
    normalization: NormalizationConfig = NormalizationConfig()
    phase3: Phase3Config = Phase3Config()
    llm: LLMConfig = LLMConfig()

    def get_reference_date(self) -> str:
        return self.reference_date

def load_config(config_path: Optional[str] = None) -> AppConfig:
    if not config_path:
        config_path = os.environ.get(
            "SKILL_GAP_CONFIG",
            str(Path(__file__).resolve().parent.parent / "config" / "settings.yaml"),
        )
    
    if os.path.exists(config_path):
        with open(config_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
            return AppConfig(**(data or {}))
    return AppConfig()

settings = load_config()
