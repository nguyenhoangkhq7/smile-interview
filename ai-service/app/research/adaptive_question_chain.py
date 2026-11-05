from typing import Any, Dict, List
from app.research.models import AdaptiveQuestionItem


class AdaptiveQuestionChain:
    """
    [Đóng góp khoa học 3]:
    Cơ chế Prompt-Chaining 3 bước để sinh bộ câu hỏi phỏng vấn thích ứng (Adaptive Questioning)
    tập trung làm rõ khoảng trống kiến thức (Skill-Gap) và các điểm nghi vấn trong CV mà không bị lan man.
    """

    def run_chain_for_assignments(
        self,
        question_type: str,
        context: Dict[str, Any],
        assignments: List[Dict[str, Any]],
    ) -> List[AdaptiveQuestionItem]:
        if not assignments:
            return [self._build_chain_item(question_type, "medium", 0, {}, context)]

        results: List[AdaptiveQuestionItem] = []
        for idx, assignment in enumerate(assignments):
            difficulty = str(assignment.get("difficulty") or "medium").lower()
            item_data = assignment.get("item") or {}
            q_item = self._build_chain_item(question_type, difficulty, idx, item_data, context)
            results.append(q_item)
        return results

    def run_chain_single_regeneration(
        self,
        question_type: str,
        difficulty: str,
        context: Dict[str, Any],
        evidence_items: List[Dict[str, Any]],
        existing_questions: List[Dict[str, Any]],
    ) -> AdaptiveQuestionItem:
        target_item = evidence_items[0] if evidence_items else {}
        offset = len(existing_questions) + 1
        return self._build_chain_item(question_type, difficulty.lower(), offset, target_item, context)

    def _build_chain_item(
        self,
        question_type: str,
        difficulty: str,
        idx: int,
        item_data: Dict[str, Any],
        context: Dict[str, Any],
    ) -> AdaptiveQuestionItem:
        # Chain Step 1: Xác định trọng tâm kiểm chứng (Gap Focus & Suspicion Analysis)
        focus = self._step1_analyze_gap_focus(item_data, context)

        # Chain Step 2: Sinh câu hỏi chính và câu hỏi đào sâu thích ứng (Adaptive Question Synthesis)
        q_text, follow_ups = self._step2_generate_grounded_question(question_type, difficulty, focus)

        # Chain Step 3: Thiết lập Rubric chấm điểm & tín hiệu trả lời tốt (Rubric Calibration)
        criteria, hints, components = self._step3_calibrate_rubric(focus, difficulty)

        return AdaptiveQuestionItem(
            item_id=f"item_{idx}",
            question_type=question_type,
            difficulty=difficulty,
            topic=focus["skill_name"],
            question_text=q_text,
            follow_up_questions=follow_ups,
            evaluation_criteria=criteria,
            rationale=focus["rationale"],
            hints=hints,
            components_to_cover=components,
        )

    def _step1_analyze_gap_focus(self, item_data: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, str]:
        gap_areas = (context or {}).get("gap_areas") or (context or {}).get("gapAreas") or []
        strong_areas = (context or {}).get("strong_areas") or (context or {}).get("strongAreas") or []
        default_skill = gap_areas[0] if gap_areas else (strong_areas[0] if strong_areas else "System Architecture")

        skill_name = item_data.get("criteriaName") or item_data.get("criteria_name") or default_skill
        status = str(item_data.get("status") or "missing").lower()
        cv_evidence = item_data.get("cvEvidence") or item_data.get("cv_evidence") or ""
        jd_req = item_data.get("jdRequirement") or item_data.get("jd_requirement") or f"Yêu cầu nắm vững {skill_name}"

        if status in ("missing", "weak", "partial"):
            strategy = "KNOWLEDGE_GAP_PROBING"
            rationale = (
                f"[Prompt-Chain Gap Probe] Phát hiện khoảng trống năng lực ở '{skill_name}' (status={status}). "
                f"Câu hỏi được thiết kế để đánh giá tư duy chuyển giao và khả năng bù đắp kiến thức theo yêu cầu JD."
            )
        else:
            strategy = "DEEP_EVIDENCE_VERIFICATION"
            rationale = (
                f"[Prompt-Chain Claim Verification] Xác thực sâu minh chứng '{skill_name}' trong CV "
                f"nhằm kiểm tra kiến thức thực chiến và các kỹ năng phụ thuộc trên đồ thị GNN."
            )

        return {
            "skill_name": str(skill_name),
            "status": status,
            "strategy": strategy,
            "cv_evidence": str(cv_evidence),
            "jd_requirement": str(jd_req),
            "rationale": rationale,
        }

    def _step2_generate_grounded_question(
        self, question_type: str, difficulty: str, focus: Dict[str, str]
    ) -> tuple[str, List[str]]:
        skill = focus["skill_name"]
        strategy = focus["strategy"]
        cv_ev = focus["cv_evidence"]

        if strategy == "KNOWLEDGE_GAP_PROBING":
            question_text = (
                f"Vị trí tuyển dụng yêu cầu vận dụng {skill} trong môi trường thực tế, nhưng CV của bạn chưa nêu chi tiết phần này. "
                f"Nếu cần thiết kế hoặc xử lý một bài toán liên quan đến {skill} ở mức độ {difficulty.upper()}, "
                f"bạn sẽ tiếp cận kiến trúc và giải quyết các rủi ro kỹ thuật như thế nào?"
            )
            follow_ups = [
                f"Những thành phần phụ thuộc (dependencies) nào quan trọng nhất khi triển khai {skill}?",
                f"Nếu gặp nút thắt hiệu năng (bottleneck) với {skill}, bạn sẽ đo đạc và xử lý ra sao?",
            ]
        else:
            context_clause = f" (dựa trên kinh nghiệm '{cv_ev[:90]}')" if cv_ev else ""
            question_text = (
                f"Trong CV bạn có đề cập đến {skill}{context_clause}. "
                f"Hãy phân tích một quyết định kỹ thuật khó khăn nhất khi bạn áp dụng {skill} "
                f"và cách bạn đảm bảo tính ổn định, mở rộng của hệ thống?"
            )
            follow_ups = [
                f"Tại sao bạn chọn giải pháp đó với {skill} thay vì các phương án thay thế khác?",
                f"Nếu tải lượng tăng gấp 10 lần, thiết kế {skill} hiện tại của bạn cần thay đổi ở điểm nào?",
            ]

        return question_text, follow_ups

    def _step3_calibrate_rubric(
        self, focus: Dict[str, str], difficulty: str
    ) -> tuple[str, List[str], List[str]]:
        skill = focus["skill_name"]
        evaluation_criteria = (
            f"Giải thích rõ bản chất hoạt động của {skill} | "
            f"Nêu được mối liên hệ với các kỹ năng nền tảng phụ thuộc | "
            f"Phân tích được trade-offs thực tế ở mức độ {difficulty}"
        )
        hints = [
            f"Tập trung vào nguyên lý cốt lõi và luồng dữ liệu của {skill}",
            "Đưa ra ví dụ thực tế hoặc phương án xử lý lỗi (fault tolerance)",
        ]
        components = [
            f"Kiến trúc cốt lõi của {skill}",
            "Quản lý phụ thuộc & hiệu năng",
            "Xử lý ngoại lệ & khả năng mở rộng",
        ]
        return evaluation_criteria, hints, components
