from typing import List
from fastapi import APIRouter
from app.schemas.question_schema import (
    QuestionGenerationRequest,
    SingleQuestionRegenerateRequest,
    QuestionDtoSchema,
)
from app.research.adaptive_question_chain import AdaptiveQuestionChain
from app.adapters.system_dto_adapter import SystemDtoAdapter

router = APIRouter(prefix="/api/ai/questions", tags=["Adaptive Question Generation"])

question_chain = AdaptiveQuestionChain()


@router.post("/generate", response_model=List[QuestionDtoSchema])
async def generate_questions(payload: QuestionGenerationRequest) -> List[QuestionDtoSchema]:
    """
    [Đóng góp 3]: Sinh bộ câu hỏi phỏng vấn thích ứng qua cơ chế Prompt-Chaining
    tập trung làm rõ Skill-Gap và các điểm nghi vấn trong CV.
    """
    adaptive_items = question_chain.run_chain_for_assignments(
        question_type=payload.type,
        context=payload.context or {},
        assignments=payload.assignments or [],
    )
    return [SystemDtoAdapter.to_question_dto(item) for item in adaptive_items]


@router.post("/regenerate-single", response_model=QuestionDtoSchema)
async def regenerate_single_question(payload: SingleQuestionRegenerateRequest) -> QuestionDtoSchema:
    """
    Sinh lại một câu hỏi đơn lẻ bằng cơ chế Prompt-Chaining dựa trên Skill-Gap.
    """
    item = question_chain.run_chain_single_regeneration(
        question_type=payload.type,
        difficulty=payload.difficulty,
        context=payload.context or {},
        evidence_items=payload.allEvidenceItems or [],
        existing_questions=payload.existingQuestions or [],
    )
    return SystemDtoAdapter.to_question_dto(item)
