from dataclasses import dataclass, field
from typing import List, Optional, Tuple


@dataclass
class SkillNode:
    """Biểu diễn một nút kỹ năng (Skill Entity) trong Đồ thị phụ thuộc JD."""
    skill_id: int
    name: str
    is_mandatory: bool
    jd_context: str
    cv_evidence: Optional[str] = None
    sbert_similarity: float = 0.0
    gnn_aggregated_score: float = 0.0
    match_status: str = "missing"  # matched | partial | weak | missing


@dataclass
class DependencyEdge:
    """Biểu diễn cạnh phụ thuộc có hướng (source_skill -> target_skill) trong JD."""
    source_skill: str
    target_skill: str
    relation_weight: float = 1.0


@dataclass
class SkillGraphMatchResult:
    """Output của Đóng góp 1: Độ đo tương đồng kết hợp Sentence-BERT và GNN."""
    nodes: List[SkillNode] = field(default_factory=list)
    edges: List[DependencyEdge] = field(default_factory=list)
    sbert_mean_score: float = 0.0
    gnn_structural_score: float = 0.0
    hybrid_similarity_score: float = 0.0


@dataclass
class SkillGapResult:
    """Output của Đóng góp 2: Khoảng trống năng lực (Skill-Gap) và Điểm nghi vấn."""
    skill_name: str
    gap_type: str  # CRITICAL_MISSING | WEAK_PREREQUISITE | UNVERIFIED_CLAIM
    severity: float
    prerequisite_chain: Tuple[str, ...] = field(default_factory=tuple)
    explanation: str = ""
    actionable_recommendation: str = ""


@dataclass
class AdaptiveQuestionItem:
    """Output của Đóng góp 3: Câu hỏi phỏng vấn thích ứng từ Prompt-Chaining."""
    item_id: str
    question_type: str
    difficulty: str
    topic: str
    question_text: str
    follow_up_questions: List[str]
    evaluation_criteria: str
    rationale: str
    hints: List[str]
    components_to_cover: List[str]
