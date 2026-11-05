from typing import List
from app.research.models import (
    SkillGraphMatchResult,
    SkillGapResult,
    AdaptiveQuestionItem,
    SkillNode,
)
from app.schemas.cv_jd_schema import (
    CvJdMatchRequest,
    AssessmentResponseSchema,
    EvidenceItemDto,
    ScoreBreakdownDto,
    ImprovementItemDto,
)
from app.schemas.question_schema import QuestionDtoSchema

VALID_JOB_CATEGORIES = {
    "SOFTWARE_ENGINEERING",
    "BACKEND",
    "FRONTEND",
    "FULLSTACK",
    "DEVOPS",
    "DATA_ENGINEERING",
    "AI_ML",
    "MOBILE",
    "QA_TESTING",
    "OTHER",
}

VALID_SENIORITY_LEVELS = {
    "INTERN",
    "FRESHER",
    "JUNIOR",
    "MID",
    "SENIOR",
    "LEAD",
}


class SystemDtoAdapter:
    """
    Anti-Corruption Layer (ACL) / Adapter:
    Chuyển đổi kết quả từ mô hình Nghiên cứu Khoa học (SBERT + GNN + Skill-Gap + Prompt-Chaining)
    sang đúng định dạng DTO của hệ thống Spring Boot & Next.js.
    """

    @classmethod
    def to_assessment_response(
        cls,
        request: CvJdMatchRequest,
        graph_result: SkillGraphMatchResult,
        gaps: List[SkillGapResult],
    ) -> AssessmentResponseSchema:
        must_have_nodes = [n for n in graph_result.nodes if n.is_mandatory]
        prefer_nodes = [n for n in graph_result.nodes if not n.is_mandatory]

        must_have_items = [cls._to_evidence_dto(n, "REQUIRED") for n in must_have_nodes]
        prefer_items = [cls._to_evidence_dto(n, "PREFERRED") for n in prefer_nodes]

        must_score = cls._compute_group_score(must_have_nodes, graph_result.hybrid_similarity_score)
        prefer_score = cls._compute_group_score(prefer_nodes, graph_result.hybrid_similarity_score)
        final_score = int(round(0.8 * must_score + 0.2 * prefer_score))

        quick_wins, skill_gaps = cls._map_improvements(gaps)
        job_cat = cls._normalize_job_category(request.jobCategory, request.roleTitle)
        sen_level = cls._normalize_seniority(request.seniorityLevel)
        eligibility = "ELIGIBILITY" if final_score >= 45 else "PARTIAL"

        return AssessmentResponseSchema(
            session_id=request.sessionId,
            job_category=job_cat,
            seniority_level=sen_level,
            overall_match_score=final_score,
            eligibility=eligibility,
            gate_evidence_items=[],
            must_have_evidence_items=must_have_items,
            prefer_to_have_evidence_items=prefer_items,
            score_breakdown=ScoreBreakdownDto(
                raw_must_have_score=must_score,
                must_have_weight_ratio=0.8,
                raw_prefer_to_have_score=prefer_score,
                prefer_to_have_weight_ratio=0.2,
                final_score=final_score,
            ),
            quick_wins=quick_wins,
            skill_gaps=skill_gaps,
            cached=False,
        )

    @classmethod
    def to_question_dto(cls, item: AdaptiveQuestionItem) -> QuestionDtoSchema:
        return QuestionDtoSchema(
            id=item.item_id,
            type=item.question_type,
            difficulty=item.difficulty,
            topic=item.topic,
            question=item.question_text,
            follow_up_questions=item.follow_up_questions,
            evaluation_criteria=item.evaluation_criteria,
            expected_competency=item.item_id,
            rationale=item.rationale,
            star_prompt="Trình bày theo cấu trúc Bối cảnh (Situation) - Giải pháp (Action) - Kết quả (Result)",
            hints=item.hints,
            components_to_cover=item.components_to_cover,
        )

    @staticmethod
    def _to_evidence_dto(node: SkillNode, importance: str) -> EvidenceItemDto:
        cv_ev = node.cv_evidence or "Chưa tìm thấy minh chứng cụ thể trong CV."
        reasoning = (
            f"[SBERT={int(node.sbert_similarity * 100)}% | GNN={int(node.gnn_aggregated_score * 100)}%] "
            f"Đánh giá khớp nối ngữ nghĩa và phụ thuộc đồ thị kỹ năng cho '{node.name}'."
        )
        return EvidenceItemDto(
            criteria_id=node.skill_id,
            criteria_name=node.name,
            importance=importance,
            jd_requirement=node.jd_context,
            cv_evidence=cv_ev,
            status=node.match_status,
            reasoning=reasoning,
        )

    @staticmethod
    def _compute_group_score(nodes: List[SkillNode], fallback_ratio: float) -> int:
        if not nodes:
            return int(round(fallback_ratio * 100))
        avg = sum(n.gnn_aggregated_score for n in nodes) / len(nodes)
        return max(0, min(100, int(round(avg * 100))))

    @staticmethod
    def _map_improvements(
        gaps: List[SkillGapResult],
    ) -> tuple[List[ImprovementItemDto], List[ImprovementItemDto]]:
        quick_wins: List[ImprovementItemDto] = []
        skill_gaps: List[ImprovementItemDto] = []

        for idx, gap in enumerate(gaps, start=1):
            dto = ImprovementItemDto(
                criteria_name=gap.skill_name,
                actionable_advice=f"{gap.explanation} {gap.actionable_recommendation}".strip(),
                priority=str(idx),
            )
            if gap.gap_type in ("UNVERIFIED_CLAIM", "WEAK_PREREQUISITE"):
                quick_wins.append(dto)
            else:
                skill_gaps.append(dto)

        return quick_wins, skill_gaps

    @staticmethod
    def _normalize_job_category(raw_cat: str | None, role_title: str | None) -> str:
        combined = f"{raw_cat or ''} {role_title or ''}".upper()
        if raw_cat and raw_cat.upper() in VALID_JOB_CATEGORIES:
            return raw_cat.upper()
        if "FRONT" in combined or "REACT" in combined:
            return "FRONTEND"
        if "FULL" in combined:
            return "FULLSTACK"
        if "DEVOPS" in combined or "CLOUD" in combined:
            return "DEVOPS"
        if "AI" in combined or "ML" in combined:
            return "AI_ML"
        if "DATA" in combined:
            return "DATA_ENGINEERING"
        return "BACKEND"

    @staticmethod
    def _normalize_seniority(raw_level: str | None) -> str:
        if not raw_level:
            return "MID"
        upper = raw_level.upper().strip()
        if upper in VALID_SENIORITY_LEVELS:
            return upper
        if "MIDDLE" in upper or "MID" in upper:
            return "MID"
        if "JUNIOR" in upper or "JR" in upper:
            return "JUNIOR"
        if "SENIOR" in upper or "SR" in upper:
            return "SENIOR"
        if "INTERN" in upper:
            return "INTERN"
        if "FRESH" in upper:
            return "FRESHER"
        if "LEAD" in upper or "PRINCIPAL" in upper:
            return "LEAD"
        return "MID"
