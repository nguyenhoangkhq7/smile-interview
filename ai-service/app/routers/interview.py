from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional, List, Dict, Any

router = APIRouter(prefix="/api/ai/interview", tags=["Interview Evaluation"])

class TurnItem(BaseModel):
    question: str
    answer: str
    score: Optional[int] = 0
    is_deep_dive: Optional[bool] = False
    is_warmup: Optional[bool] = False

class InterviewEvaluationRequest(BaseModel):
    role_title: str
    interview_type: str
    total_base_questions: int
    turns: List[TurnItem]

@router.post("/evaluate")
async def evaluate_interview(request: InterviewEvaluationRequest):
    """
    Placeholder endpoint for LLM-based holistic session evaluation.
    Replace with your Python LangChain / LlamaIndex / Agentic evaluation code.
    """
    total_turns = len(request.turns)
    evaluated_turns = []
    total_score = 0
    for idx, t in enumerate(request.turns):
        t_score = 80 if len(t.answer.strip()) > 10 else 30
        total_score += t_score
        evaluated_turns.append({
            "questionNumber": idx + 1,
            "question": t.question,
            "score": t_score,
            "strengths": "Trả lời có trọng tâm, diễn đạt rành mạch",
            "improvements": "Nên cung cấp thêm ví dụ thực tế trong dự án",
            "suggestedAnswer": "Ví dụ tham khảo chuẩn cho vị trí " + request.role_title
        })

    avg_score = round(total_score / max(total_turns, 1))

    return {
        "overallScore": avg_score,
        "overallFeedback": f"Ứng viên thể hiện năng lực tốt ở vị trí {request.role_title}. Cần trau dồi thêm các tình huống tối ưu thực tế.",
        "strongAreas": [
            "Tư duy giải quyết vấn đề mạch lạc",
            "Kiến thức nền tảng vững vàng"
        ],
        "gapAreas": [
            "Cần đào sâu hơn về tối ưu hoá tài nguyên và xử lý ngoại lệ"
        ],
        "actionableSuggestions": [
            "Thực hành thêm các bài toán mở rộng quy mô hệ thống (Scalability)",
            "Tự tin hơn khi giải thích quyết định kiến trúc"
        ],
        "evaluatedQuestions": evaluated_turns
    }
