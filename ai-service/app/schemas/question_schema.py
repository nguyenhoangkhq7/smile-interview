from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any


class QuestionGenerationRequest(BaseModel):
    type: str
    context: Optional[Dict[str, Any]] = None
    assignments: Optional[List[Dict[str, Any]]] = Field(default_factory=list)
    config: Optional[Dict[str, Any]] = None


class SingleQuestionRegenerateRequest(BaseModel):
    type: str
    difficulty: str
    context: Optional[Dict[str, Any]] = None
    allEvidenceItems: Optional[List[Dict[str, Any]]] = Field(default_factory=list)
    existingQuestions: Optional[List[Dict[str, Any]]] = Field(default_factory=list)


class QuestionDtoSchema(BaseModel):
    id: str
    type: str
    difficulty: str
    topic: str
    question: str
    follow_up_questions: List[str] = Field(default_factory=list)
    evaluation_criteria: str
    expected_competency: str
    rationale: Optional[str] = None
    star_prompt: Optional[str] = None
    hints: List[str] = Field(default_factory=list)
    components_to_cover: List[str] = Field(default_factory=list)
