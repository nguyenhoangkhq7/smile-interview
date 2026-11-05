from fastapi import APIRouter
from app.schemas.cv_jd_schema import CvJdMatchRequest, AssessmentResponseSchema
from app.research.sbert_gnn_matcher import SbertGnnMatcher
from app.research.skill_gap_detector import SkillGapDetector
from app.adapters.system_dto_adapter import SystemDtoAdapter

router = APIRouter(prefix="/api/ai/cv-jd", tags=["CV-JD Matching & Skill-Gap"])

matcher = SbertGnnMatcher()
gap_detector = SkillGapDetector()


@router.post("/match", response_model=AssessmentResponseSchema)
async def match_cv_jd(payload: CvJdMatchRequest) -> AssessmentResponseSchema:
    """
    Endpoint tích hợp:
    1. [Đóng góp 1]: Khớp nối ngữ nghĩa CV-JD với Sentence-BERT + GNN (Skill Dependency Graph).
    2. [Đóng góp 2]: Thuật toán phát hiện Khoảng trống năng lực (Skill-Gap Detection).
    3. [ACL Adapter]: Chuyển đổi kết quả nghiên cứu sang DTO chuẩn của Spring Boot Backend.
    """
    graph_result = matcher.match(cv_text=payload.cvText or "", jd_text=payload.jdText or "")
    gaps = gap_detector.detect_gaps(graph_result)
    return SystemDtoAdapter.to_assessment_response(payload, graph_result, gaps)
