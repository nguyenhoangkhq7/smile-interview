from pydantic import BaseModel, Field, SerializerFunctionWrapHandler, model_serializer
from typing import List, Optional, Literal
from matching_cv.app.eligibility.models import EligibilityReport
from .enums import SkillType, SemanticAlignment, SeniorityLevel, RichnessLabel

UNASSIGNED_JOB_ID = "UNASSIGNED"

# --- Module 1 Inputs (SBERT + GNN Contracts) ---

class ExtractedCVSkill(BaseModel):
    skill_id: str
    skill_name: Optional[str] = None
    type: SkillType
    confidence: float = Field(ge=0.0, le=1.0)
    evidence_spans: List[str]

class ExtractedJDSkill(BaseModel):
    skill_id: str
    skill_name: Optional[str] = None
    type: SkillType
    confidence: float = Field(ge=0.0, le=1.0)
    evidence_spans: List[str]

class MatchResult(BaseModel):
    jd_skill_id: str
    w_j: float = Field(ge=0.0, le=1.0, description="Trọng số tầm quan trọng của kỹ năng trong JD (từ Module 1 JSI)")
    matched_cv_skill_id: str
    soft_match: float = Field(ge=0.0, le=1.0, description="Độ tương đồng ngữ nghĩa định hướng (từ Module 1 SBERT + DAG)")

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

class SkillGapSummary(BaseModel):
    jd_skill_id: str
    jd_skill_name: Optional[str] = None
    matched_cv_skill_name: Optional[str] = None
    semantic_alignment: SemanticAlignment
    matched_cv_skill_id: Optional[str]
    priority: float = Field(ge=0.0, le=1.0, description="Mức độ ưu tiên (w_j * required_proficiency / 5 * gap_magnitude)")
    required_proficiency: float = Field(description="P_JD từ Bước B")
    cv_evidence_spans: List[str] = Field(default_factory=list, description="Các đoạn trích dẫn bằng chứng từ CV")
    context_job: Optional[str] = Field(default=None, description="Tóm tắt công việc, chức danh và mốc thời gian")
    importance_weight: float = Field(default=0.0, ge=0.0, le=1.0)
    job_tasks: List[JobTask] = Field(default_factory=list)
    jd_evidence_spans: List[str] = Field(default_factory=list, description="Trích dẫn JD khi chưa có nhiệm vụ cụ thể")

    @model_serializer(mode="wrap")
    def serialize_skill(self, handler: SerializerFunctionWrapHandler):
        data = handler(self)
        if self.job_tasks or not self.jd_evidence_spans:
            data.pop("jd_evidence_spans", None)
        return data


class SkillGapResult(SkillGapSummary):
    """Internal pipeline result with proficiency/gap diagnostics."""

    is_substituted: bool = Field(description="True nếu kỹ năng được bù đắp bởi kỹ năng tương đương (PARTIAL)")
    gap_magnitude: float = Field(ge=0.0, le=1.0, description="Độ thiếu hụt năng lực chuẩn hóa trên độ rộng thang đo 4.0")
    candidate_proficiency: float = Field(description="P_CV từ Bước C")
    degraded: bool = False
    flags: List[str] = Field(default_factory=list)


class SkillGapReportSummary(BaseModel):
    eligibility: EligibilityReport | None = None

    cv_skills: List[ExtractedCVSkill] = Field(default_factory=list)
    matching_score: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Module 1 semantic & dependency GNN CV-JD match score (S_semantic) on a 0-1 scale",
    )
    degraded: bool = False

    @model_serializer(mode="wrap")
    def serialize_report(self, handler: SerializerFunctionWrapHandler):
        data = handler(self)
        if self.eligibility is None:
            data.pop("eligibility", None)
        return data
