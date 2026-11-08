from pydantic import BaseModel, Field
from typing import List, Optional, Literal
from .enums import SkillType, SemanticAlignment, SeniorityLevel, RichnessLabel, QuestionStrategy

UNASSIGNED_JOB_ID = "UNASSIGNED"

# --- Module 1 Inputs (SBERT + GNN Contracts) ---

class ExtractedCVSkill(BaseModel):
    skill_id: str
    type: SkillType
    confidence: float = Field(ge=0.0, le=1.0)
    evidence_spans: List[str]

class ExtractedJDSkill(BaseModel):
    skill_id: str
    type: SkillType
    confidence: float = Field(ge=0.0, le=1.0)
    evidence_spans: List[str]

class MatchResult(BaseModel):
    jd_skill_id: str
    w_j: float = Field(ge=0.0, le=1.0, description="Trọng số tầm quan trọng của kỹ năng trong JD (từ GNN)")
    matched_cv_skill_id: str
    soft_match: float = Field(ge=0.0, le=1.0, description="Độ tương đồng ngữ nghĩa (từ SBERT)")

# --- Step A Models (Resume Segmenter) ---

class JobBlock(BaseModel):
    job_id: str
    title: str
    seniority_level: SeniorityLevel
    start_date: Optional[str] = Field(default=None, description="ISO YYYY-MM")
    end_date: Optional[str] = Field(default=None, description="ISO YYYY-MM hoặc None nếu là công việc hiện tại")
    raw_text: str
    raw_start_date: Optional[str] = Field(default=None, description="Legacy optional field")
    raw_end_date: Optional[str] = Field(default=None, description="Legacy optional field")
    raw_quote: Optional[str] = Field(default=None, description="Legacy optional field")

    @classmethod
    def model_json_schema(cls, *args, **kwargs):
        schema = super().model_json_schema(*args, **kwargs)
        props = schema.get("properties", {})
        for legacy_key in ("raw_start_date", "raw_end_date", "raw_quote"):
            props.pop(legacy_key, None)
            if "required" in schema and legacy_key in schema["required"]:
                schema["required"].remove(legacy_key)
        return schema

class SpanMapping(BaseModel):
    span: str
    job_id: str = Field(description="ID của JobBlock tương ứng hoặc 'UNASSIGNED'")

class SegmenterOutput(BaseModel):
    job_blocks: List[JobBlock]
    span_mappings: List[SpanMapping]
    degraded: bool = Field(default=False, description="True nếu quá trình trích xuất bị lỗi/fallback")
    flags: List[str] = Field(default_factory=list, description="Cờ cảnh báo kiểm toán")

# --- Step B Models (JD Requirement Parser) ---

class JobTask(BaseModel):
    task_id: str = ""
    description: str
    evidence_spans: List[str] = Field(default_factory=list)
    required_level: float = Field(ge=1.0, le=5.0)
    requirement_kind: Literal["REQUIRED", "OPTIONAL", "UNSPECIFIED"] = "UNSPECIFIED"
    level_basis: Literal["EXPLICIT", "INFERRED", "FALLBACK"] = "INFERRED"


class JDRequirement(BaseModel):
    jd_skill_id: str
    required_level: float = Field(ge=1.0, le=5.0, description="Độ sâu năng lực yêu cầu P_JD trên thang chuẩn hóa 1.0 - 5.0")
    reasoning: str
    tasks: List[JobTask] = Field(default_factory=list)

class JDParserOutput(BaseModel):
    requirements: List[JDRequirement]
    degraded: bool = Field(default=False, description="True nếu parser phải chạy ở chế độ fallback")
    flags: List[str] = Field(default_factory=list, description="Cờ cảnh báo kiểm toán")

# --- Step C Models (Proficiency Estimator) ---

class SpanRichness(BaseModel):
    span: str
    richness_label: RichnessLabel
    modifier_score: Optional[float] = Field(
        default=None,
        description="Trường tùy chọn tương thích ngược (không yêu cầu LLM sinh ra để tránh tính trùng trọng số)",
    )

    @classmethod
    def model_json_schema(cls, *args, **kwargs):
        schema = super().model_json_schema(*args, **kwargs)
        props = schema.get("properties", {})
        props.pop("modifier_score", None)
        if "required" in schema and "modifier_score" in schema["required"]:
            schema["required"].remove("modifier_score")
        return schema

class ProficiencyResult(BaseModel):
    skill_id: str
    proficiency: float = Field(ge=1.0, le=5.0, description="Điểm năng lực ước lượng của ứng viên P_CV")
    c_evidence: float = Field(default=0.0, ge=0.0, le=1.0, description="Tỷ lệ bằng chứng giàu ngữ cảnh thực tế (RICH_CONTEXT)")
    effective_months: float = Field(default=0.0, ge=0.0, description="Tổng số tháng kinh nghiệm hiệu dụng sau khi nhân trọng số")
    recency_flag: bool = Field(default=False, description="True nếu kỹ năng không được thực hành trong vòng 3 năm gần đây")
    degraded: bool = Field(default=False, description="Cờ cảnh báo tính toán bị suy giảm")
    flags: List[str] = Field(default_factory=list, description="Danh sách cờ chẩn đoán")

# --- Step D Models (Skill Gap Detector) ---

class SkillGapResult(BaseModel):
    jd_skill_id: str
    semantic_alignment: SemanticAlignment
    matched_cv_skill_id: Optional[str]
    is_substituted: bool = Field(description="True nếu kỹ năng được bù đắp bởi kỹ năng tương đương (PARTIAL)")
    gap_magnitude: float = Field(ge=0.0, le=1.0, description="Độ thiếu hụt năng lực chuẩn hóa trên độ rộng thang đo 4.0")
    severity: float = Field(ge=0.0, le=1.0, description="Mức độ nghiêm trọng của thiếu hụt (w_j * gap_magnitude)")
    priority: float = Field(ge=0.0, le=1.0, description="Mức độ ưu tiên phỏng vấn tất định (w_j * gap_magnitude)")

    # --- Rich Context cho Module 3 (Adaptive Question Generation) ---
    required_proficiency: float = Field(description="P_JD từ Bước B")
    candidate_proficiency: float = Field(description="P_CV từ Bước C")
    cv_evidence_spans: List[str] = Field(default_factory=list, description="Các đoạn trích dẫn bằng chứng từ CV")
    context_job: Optional[str] = Field(default=None, description="Tóm tắt công việc, chức danh và mốc thời gian")
    suggested_strategy: QuestionStrategy = Field(description="Chiến lược phỏng vấn thích ứng khuyến nghị")

    degraded: bool = Field(default=False)
    flags: List[str] = Field(default_factory=list)
    importance_weight: float = Field(default=0.0, ge=0.0, le=1.0)
    jd_reasoning: str = ""
    jd_evidence_spans: List[str] = Field(default_factory=list)
    job_tasks: List[JobTask] = Field(default_factory=list)
    c_evidence: float = Field(default=0.0, ge=0.0, le=1.0)
    recency_flag: bool = False
