"""
Declarative 3-Layer Structured Prompt Templates (Step 2A), Reflective Metamorphic
PBA Judge Prompt Templates (Step 2B), and DSPy Signatures (Khattab et al., 2023)
following Gheartha et al. (2026), Hashimoto et al. (2024), and Stuart et al. (2026).
"""

import json
from typing import List, Optional, Tuple

import dspy

from adaptive_questioning.config import CENTROIDS, MAX_SUB_SLOTS, RUBRIC_LEVELS
from adaptive_questioning.schemas.api_models import (
    ProposedSubSlot,
    Step2AQuestionOutput,
    Step2BJudgeOutput,
)
from adaptive_questioning.schemas.state import (
    ContextAnchor,
    MetamorphicTag,
    SkillBeliefState,
    TurnLog,
)


STRATEGY_GUIDELINES = {
    "PROBE_DEPTH": (
        "PROBE_DEPTH: Ứng viên đã từng sử dụng kỹ năng này nhưng mức độ thành thạo trên CV (s_cv) thấp hơn "
        "yêu cầu JD (s_jd). Hãy đào sâu vào cách giải quyết tình huống thực tế (troubleshooting/execution), "
        "các quyết định đánh đổi chuyên môn (domain trade-offs), hoặc vận hành ở quy mô thực chiến để xác minh độ sâu thực sự."
    ),
    "COMPARE_SUBSTITUTE": (
        "COMPARE_SUBSTITUTE: Ứng viên có kỹ năng tương đương/thay thế (substituted skill). Hãy bắc cầu từ "
        "kỹ năng ứng viên đã biết sang kỹ năng mục tiêu của JD, hỏi về sự khác biệt cốt lõi trong nguyên lý vận hành "
        "và cách ứng viên chuyển đổi tư duy nghiệp vụ khi áp dụng vào bài toán thực tế."
    ),
    "LEARNING_AGILITY": (
        "LEARNING_AGILITY: Kỹ năng còn thiếu hoặc chỉ mới tiếp xúc bề nổi. Hãy đặt tình huống nghiệp vụ cụ thể "
        "liên quan đến kinh nghiệm hiện tại của ứng viên để kiểm tra khả năng suy luận nguyên lý gốc (first-principles) "
        "và tốc độ thích ứng chuyên môn."
    ),
}


# ---------------------------------------------------------------------------
# Domain-Agnostic Difficulty Rubric Anchors (Stuart et al., 2026; Gheartha et al., 2026)
# ---------------------------------------------------------------------------

def get_difficulty_rubric_anchor(r_target: float) -> str:
    """
    Ánh xạ r_target (s_jd) sang mô tả độ khó phi miền chuẩn theo Rubric 3 tầng
    (Stuart et al., 2026; Gheartha et al., 2026; Bloom's Taxonomy).
    Áp dụng đồng nhất cho mọi ngành nghề (Kỹ thuật, Tài chính, Y tế, Marketing, Quản trị...).
    """
    if r_target < 2.5:
        return (
            f"MỤC TIÊU ĐỘ KHÓ: LOW ({r_target:.1f}/5.0) - NỀN TẢNG & QUY TRÌNH MẪU (Centroid c = 1.5)\n"
            "  * Trọng tâm đánh giá: Khả năng nắm vững khái niệm, thuật ngữ nền tảng và thực thi các quy trình/thao tác chuẩn theo mẫu hoặc hướng dẫn có sẵn.\n"
            "  * RÀNG BUỘC CẤM (Overkill Prevention): Tuyệt đối KHÔNG hỏi về xử lý sự cố/khủng hoảng nghiêm trọng, tối ưu hóa quy mô lớn/tác động cao, "
            "thiết kế chiến lược vĩ mô hay các tình huống quy chuẩn bị phá vỡ."
        )
    elif r_target < 3.8:
        return (
            f"MỤC TIÊU ĐỘ KHÓ: MEDIUM ({r_target:.1f}/5.0) - TỰ CHỦ & THỰC THI NGHIỆP VỤ (Centroid c = 3.0)\n"
            "  * Trọng tâm đánh giá: Khả năng làm việc độc lập trong công việc hàng ngày mà không cần hướng dẫn từng bước; "
            "giải quyết các tình huống nghiệp vụ thực tế; phát hiện và khắc phục các sai lệch, lỗi hoặc tình huống ngoại lệ phổ biến trong phạm vi phụ trách.\n"
            "  * RÀNG BUỘC CẤM: Tránh hỏi các bài toán tái cấu trúc quy mô lớn, quản trị rủi ro sống còn của tổ chức hay các quyết định chiến lược phức tạp liên phòng ban."
        )
    else:
        return (
            f"MỤC TIÊU ĐỘ KHÓ: HIGH ({r_target:.1f}/5.0) - LÀM CHỦ CHUYÊN SÂU & QUYẾT ĐỊNH ĐÁNH ĐỔI (Centroid c = 4.5)\n"
            "  * Trọng tâm đánh giá: Năng lực giải quyết các sự cố/khủng hoảng nghiêm trọng ở quy mô lớn hoặc tác động cao (high-impact); "
            "chẩn đoán nguyên nhân gốc rễ (root-cause diagnosis); đưa ra các quyết định đánh đổi (Trade-offs) phức tạp giữa chi phí, thời gian, chất lượng, tài nguyên và rủi ro.\n"
            "  * RÀNG BUỘC CẤM: Bỏ qua các câu hỏi định nghĩa lý thuyết sách vở, câu hỏi thuộc lòng hoặc các quy trình mẫu nhập môn."
        )


# ---------------------------------------------------------------------------
# Declarative DSPy Signatures (Khattab et al., 2023)
# ---------------------------------------------------------------------------

class Step2AAbductiveQuestionSignature(dspy.Signature):
    """
    3-Layer Adaptive Question Generator with Abductive Chain-of-Thought (C -> A).
    Enforces Relevance Theory & Domain-Agnostic Rubric constraints:
    1. One-Question-One-Answer: Ask exactly ONE clear, concrete question in Vietnamese.
    2. Show, Don't Tell: Ask for concrete real-world execution, troubleshooting steps, or domain trade-offs.
    3. Contextual Bridging: Connect naturally to Context Anchors A_ctx or previous utterance (Zero Topic Drift).
    4. Difficulty Calibration: Calibrate difficulty strictly according to the Target Rubric Anchor (Low/Med/High).
    """

    reference_layer_context: str = dspy.InputField(
        desc="Layer 1 Reference Context: skill metadata, CV evidence spans, context_job, Context Anchors A_ctx, dialogue history, and active slot state"
    )
    main_layer_directives: str = dspy.InputField(
        desc="Layer 2 Main Directives: Dynamic Persona, suggested_strategy, target difficulty rubric anchor r_target = s_jd, and Abductive CoT (C -> A) instructions"
    )

    surprising_fact_C: str = dspy.OutputField(
        desc="Observed Surprising Fact C_0 (at k=1) or C_{t-1} (at k>=2) from CV/dialogue discrepancy"
    )
    hypothesis_A: str = dspy.OutputField(
        desc="Inferred Abductive Hypothesis A_0 or A_{t-1} explaining the hidden cause of C"
    )
    new_sub_slot: Optional[ProposedSubSlot] = dspy.OutputField(
        desc="Optional temporary Probing Sub-slot (None at k=1; at most 1 at k in {2,3} if active sub-slots < 2)"
    )
    target_slot_id: str = dspy.OutputField(
        desc="ID of the active primary slot or sub-slot targeted by this question"
    )
    question: str = dspy.OutputField(
        desc="Single concrete Vietnamese question adhering to One-Question-One-Answer, Show-Don't-Tell, and Difficulty Anchor"
    )


class Step2BReflectivePBAJudgeSignature(dspy.Signature):
    """
    Reflective Two-Step Previous Belief Aware (PBA) Metamorphic LLM-as-a-Judge.
    Step 2B.1: Extract specific technical evidence into the active slot and formulate a concise 1-2 sentence
    reflective_insight evaluating candidate_response against Rubric centroids [1.5, 3.0, 4.5] BEFORE assigning probabilities.
    Step 2B.2: Classify candidate_response into EXACTLY ONE of the 4 Metamorphic Relations:
      - INVARIANT (delta_max = 0.00): ONLY when the answer is empty buzzwords without substance, off-topic/irrelevant, or verbatim repetition of the CV. Never use INVARIANT for a valid technical answer!
      - MINOR_SHIFT (delta_max = 0.12): Indirect evidence, basic/partial answer, or legitimate external constraint (Context Invalidation).
      - MODERATE_SHIFT (delta_max = 0.25): Valid practical example, or moderate Scope/Rigour Downgrade.
      - DECISIVE_SHIFT (delta_max = 0.45): Deep production mastery at level s_jd (High = 4.5), OR explicit admission of lacking the skill (Low = 1.5).
    Then propose raw posterior probabilities [P(Low), P(Med), P(High)] summing to 1.0.
    """

    reference_layer_rubric: str = dspy.InputField(
        desc="Layer 1 Reference Context: Skill metadata, s_jd, s_cv, CV evidence, Rubric Ordinal Levels L=[Low(1.5), Med(3.0), High(4.5)], and Previous Belief P_{t-1}"
    )
    question_and_slot: str = dspy.InputField(
        desc="Target slot ID and the technical question asked to the candidate"
    )
    candidate_response: str = dspy.InputField(
        desc="Candidate response x_t to evaluate"
    )

    extracted_slot_value: Optional[str] = dspy.OutputField(
        desc="Specific technical evidence extracted from candidate_response x_t to fill the active slot"
    )
    reflective_insight: str = dspy.OutputField(
        desc="Concise 1-2 sentence Vietnamese evaluation against Rubric centroids [1.5, 3.0, 4.5] BEFORE assigning probabilities"
    )
    metamorphic_tag: MetamorphicTag = dspy.OutputField(
        desc="Metamorphic Relation classification: DECISIVE_SHIFT (deep production mastery or explicit lack of skill), MODERATE_SHIFT (valid practical example), MINOR_SHIFT (basic/indirect evidence), or INVARIANT (ONLY buzzwords/off-topic/verbatim CV)"
    )
    raw_posterior_probs: List[float] = dspy.OutputField(
        desc="Normalized raw posterior probability vector [P(Low), P(Med), P(High)] of length 3 summing to 1.0"
    )
    consolidated_summary: str = dspy.OutputField(
        desc="Concise 1-sentence Vietnamese summary of verified competency for A_ctx memory consolidation"
    )


# ---------------------------------------------------------------------------
# 3-Layer Prompt Formatting Helpers
# ---------------------------------------------------------------------------

def format_context_anchors(anchors: List[ContextAnchor]) -> str:
    """Format Context Anchors A_ctx for Reference Layer injection."""
    if not anchors:
        return "Không có Context Anchors ban đầu."

    lines = []
    for idx, anchor in enumerate(anchors, start=1):
        job_info = f" tại [{anchor.context_job}]" if anchor.context_job else ""
        if anchor.consolidated_summary:
            lines.append(
                f"  {idx}. [VERIFIED MEMORY] Kỹ năng '{anchor.jd_skill_id}' (Proficiency={anchor.candidate_proficiency:.2f}{job_info}): "
                f"{anchor.consolidated_summary}"
            )
        else:
            lines.append(
                f"  {idx}. [STRONG ANCHOR] Kỹ năng '{anchor.jd_skill_id}' (s_cv={anchor.candidate_proficiency:.2f}{job_info}) - Đã đạt yêu cầu JD."
            )
    return "\n".join(lines)


def format_recent_dialogue(turn_history: List[TurnLog], limit: int = 3) -> str:
    """Format recent dialogue turns for Reference Layer."""
    if not turn_history:
        return "Chưa có lượt hội thoại nào trước đó (Cold-start Turn t=1)."

    recent = turn_history[-limit:]
    blocks = []
    for log in recent:
        blocks.append(
            f"- [Turn t={log.turn}, k={log.local_turn}, Skill='{log.skill_id}', Slot='{log.target_slot_id}']\n"
            f"  + Câu hỏi: {log.question}\n"
            f"  + Trả lời (x_t): {log.candidate_response or ''}\n"
            f"  + Judge Insight: {log.reflective_insight or ''} (Tag={log.metamorphic_tag.value if log.metamorphic_tag else 'N/A'})"
        )
    return "\n".join(blocks)


def build_step2a_layers(
    skill: SkillBeliefState,
    context_anchors: List[ContextAnchor],
    turn_history: List[TurnLog],
    next_local_turn_k: int,
) -> Tuple[str, str]:
    """
    Build (reference_layer_context, main_layer_directives) for Step 2A DSPy Signature.
    """
    evidence_text = (
        "; ".join(f'"{span}"' for span in skill.cv_evidence_spans)
        if skill.cv_evidence_spans
        else "Không có đoạn trích dẫn trực tiếp trong CV."
    )
    can_create_sub_slot = (next_local_turn_k >= 2) and (len(skill.active_sub_slots) < MAX_SUB_SLOTS)

    if next_local_turn_k == 1:
        active_slot_desc = f"Primary Competency Slot: '{skill.jd_skill_id}:primary'"
        abductive_instruction = (
            "Tại lượt mở đầu của kỹ năng (local turn k = 1):\n"
            "  1. Quan sát Sự kiện Đáng ngạc nhiên C_0 (Surprising Fact): Sự chênh lệch cấu trúc giữa "
            f"năng lực CV hiện tại (s_cv = {skill.candidate_proficiency:.2f}, bằng chứng: {evidence_text} "
            f"tại '{skill.context_job or 'N/A'}') so với mức độ yêu cầu của JD (s_jd = {skill.required_proficiency:.2f}) "
            "và vai trò hiện tại của ứng viên trong Context Anchors A_ctx.\n"
            "  2. Suy diễn Giả thuyết A_0 (Abductive Hypothesis C_0 -> A_0): Đưa ra giả thuyết hợp lý giải thích C_0 "
            "(ví dụ: ứng viên chỉ dùng các dịch vụ managed/abstraction bậc cao hoặc chưa ghi chi tiết kinh nghiệm xử lý sự cố vào CV).\n"
            "  3. KHÔNG tạo Probing Sub-slot mới ở k = 1 (`new_sub_slot` = null). Đặt `target_slot_id` = "
            f"'{skill.jd_skill_id}:primary'."
        )
    else:
        last_skill_turns = [t for t in turn_history if t.skill_id == skill.jd_skill_id]
        last_turn = last_skill_turns[-1] if last_skill_turns else None
        prev_ans = last_turn.candidate_response if last_turn else "N/A"
        prev_insight = last_turn.reflective_insight if last_turn else "N/A"
        active_slot_desc = (
            f"Existing Sub-slots ({len(skill.active_sub_slots)}/{MAX_SUB_SLOTS}): "
            + json.dumps([s.model_dump() for s in skill.active_sub_slots], ensure_ascii=False)
        )
        abductive_instruction = (
            f"Tại lượt hỏi xoáy tiếp theo (local turn k = {next_local_turn_k}):\n"
            f"  1. Quan sát Sự kiện Đáng ngạc nhiên C_{{t-1}} từ câu trả lời trước của ứng viên ('{prev_ans}') "
            f"và nhận định của Judge ('{prev_insight}').\n"
            "  2. Suy diễn Giả thuyết A_{t-1} (Abductive Hypothesis C_{t-1} -> A_{t-1}) về nguyên nhân ẩn đằng sau "
            "lỗ hổng hoặc điểm chưa rõ trong câu trả lời vừa rồi.\n"
            f"  3. Quản lý Probing Sub-slot (Giới hạn cứng tối đa {MAX_SUB_SLOTS} sub-slots cho mỗi kỹ năng): "
            + (
                "Bạn ĐƯỢC PHÉP sinh tối đa 1 `new_sub_slot` (gồm `slot_name`, `description`) để đào sâu vào giả thuyết A_{t-1}, "
                f"và đặt `target_slot_id` = '{skill.jd_skill_id}:sub_{len(skill.active_sub_slots) + 1}'."
                if can_create_sub_slot
                else f"Đã đạt giới hạn {MAX_SUB_SLOTS} sub-slots; KHÔNG sinh thêm `new_sub_slot` (`new_sub_slot` = null), "
                f"hãy dùng slot hiện hành."
            )
        )

    strategy_instruction = STRATEGY_GUIDELINES.get(
        skill.suggested_strategy, STRATEGY_GUIDELINES["PROBE_DEPTH"]
    )

    difficulty_guideline = get_difficulty_rubric_anchor(skill.required_proficiency)
    job_title = skill.context_job or "vị trí chuyên môn ứng tuyển"
    persona_str = f"Chuyên gia phỏng vấn / Trưởng bộ phận chuyên môn cao cấp trong lĩnh vực '{job_title}', phỏng vấn bằng tiếng Việt chuyên nghiệp."

    reference_layer = (
        f"- Kỹ năng mục tiêu (Primary Skill d*): `{skill.jd_skill_id}` (Matched CV Skill: `{skill.matched_cv_skill_id or 'None'}`)\n"
        f"- Độ sâu năng lực yêu cầu từ JD (Target Difficulty Anchor r_target = s_jd): {skill.required_proficiency:.2f} / 5.0\n"
        f"- Điểm năng lực ước lượng ban đầu từ CV (s_cv): {skill.candidate_proficiency:.2f} / 5.0\n"
        f"- Phân phối niềm tin hiện tại P_{{t-1}} [Low(1.5), Med(3.0), High(4.5)]: {[round(p, 4) for p in skill.current_belief]}\n"
        f"- Bằng chứng nguyên văn từ CV (`cv_evidence_spans`): {evidence_text}\n"
        f"- Ngữ cảnh công việc (`context_job`): {skill.context_job or 'Không rõ'}\n"
        f"- Trạng thái Slot hiện hành: {active_slot_desc}\n"
        f"- Context Anchors bắc cầu & Bộ nhớ hợp nhất ($A_{{ctx}}$):\n{format_context_anchors(context_anchors)}\n"
        f"- Lịch sử hội thoại gần nhất:\n{format_recent_dialogue(turn_history)}"
    )

    main_layer = (
        f"- Persona: {persona_str}\n"
        f"- Chiến lược phỏng vấn (`suggested_strategy`): {strategy_instruction}\n"
        f"- Khung Độ khó Mục tiêu (Target Difficulty Rubric Anchor):\n{difficulty_guideline}\n"
        f"- Suy luận Abductive Chain-of-Thought (C -> A):\n{abductive_instruction}\n"
        "- Ràng buộc Relevance Theory (BẮT BUỘC):\n"
        "  1. One-Question-One-Answer: Chỉ hỏi ĐÚNG MỘT câu hỏi rõ ràng, cụ thể trong lượt này.\n"
        "  2. Show, Don't Tell: Yêu cầu ứng viên trình bày tình huống thực tế, các bước chẩn đoán/xử lý vấn đề cụ thể (practical execution & troubleshooting), "
        "hoặc các quyết định đánh đổi nghiệp vụ (domain trade-offs) thay vì chỉ nêu định nghĩa lý thuyết suông.\n"
        "  3. Contextual Bridging: Dẫn dắt mượt mà từ Context Anchors ($A_{ctx}$) hoặc câu trả lời liền trước (Zero Topic Drift).\n"
    )

    return reference_layer, main_layer


def build_step2a_question_prompt(
    skill: SkillBeliefState,
    context_anchors: List[ContextAnchor],
    turn_history: List[TurnLog],
    next_local_turn_k: int,
) -> str:
    """
    Construct the full 3-Layer Structured Prompt (Reference, Main, Output Layers)
    for Step 2A: Abductive CoT & Adaptive Question Generator.
    """
    reference_layer, main_layer = build_step2a_layers(
        skill, context_anchors, turn_history, next_local_turn_k
    )
    output_schema_str = json.dumps(Step2AQuestionOutput.model_json_schema(), ensure_ascii=False)

    return (
        "# 3-LAYER STRUCTURED PROMPT: ADAPTIVE QUESTION GENERATOR (STEP 2A)\n\n"
        f"## [LAYER 1: REFERENCE LAYER (GROUNDING & MEMORY CONTEXT)]\n{reference_layer}\n\n"
        f"## [LAYER 2: MAIN LAYER (PERSONA, ABDUCTIVE CoT & RELEVANCE CONSTRAINTS)]\n{main_layer}\n\n"
        "## [LAYER 3: OUTPUT LAYER (DECLARATIVE DSPy SIGNATURE)]\n"
        "Trả về duy nhất một đối tượng JSON hợp lệ tuân thủ tuyệt đối JSON Schema dưới đây (trường `question` viết bằng tiếng Việt):\n"
        f"{output_schema_str}\n"
    )


def build_step2b_layers(
    skill: SkillBeliefState,
    question: str,
    target_slot_id: str,
) -> Tuple[str, str]:
    """
    Build (reference_layer_rubric, question_and_slot) for Step 2B DSPy Judge Signature.
    """
    evidence_text = (
        "; ".join(f'"{span}"' for span in skill.cv_evidence_spans)
        if skill.cv_evidence_spans
        else "Không có đoạn trích dẫn trực tiếp trong CV."
    )
    reference_layer_rubric = (
        f"- Kỹ năng đang đánh giá (d*): `{skill.jd_skill_id}`\n"
        f"- Mức năng lực yêu cầu từ JD (s_jd): {skill.required_proficiency:.2f} / 5.0\n"
        f"- Mức năng lực ước lượng từ CV (s_cv): {skill.candidate_proficiency:.2f} / 5.0\n"
        f"- Bằng chứng trong CV (`cv_evidence_spans`): {evidence_text}\n"
        f"- Hệ quy chiếu Rubric Ordinal Levels L = {list(RUBRIC_LEVELS)} với tâm cụm c = {list(CENTROIDS)} trên thang 5.0:\n"
        "  * Low (c = 1.5): Chỉ nắm khái niệm cơ bản, thao tác theo hướng dẫn có sẵn, chưa hiểu cơ chế bên dưới.\n"
        "  * Med (c = 3.0): Vận hành độc lập trong môi trường thực tế, xử lý lỗi phổ biến ở mức độ vừa phải.\n"
        "  * High (c = 4.5): Làm chủ chuyên sâu ở quy mô production, hiểu rõ kiến trúc nội tại và giải quyết sự cố phức tạp.\n"
        f"- Phân phối niềm tin liền trước (Previous Belief P_{{t-1}}): {[round(p, 4) for p in skill.current_belief]}"
    )
    question_and_slot = (
        f"- Slot mục tiêu đang điền (`target_slot_id`): `{target_slot_id}`\n"
        f'- Câu hỏi đã đặt cho ứng viên: "{question}"'
    )
    return reference_layer_rubric, question_and_slot


def build_step2b_judge_prompt(
    skill: SkillBeliefState,
    question: str,
    target_slot_id: str,
    candidate_response: str,
) -> str:
    """
    Construct the Reflective Two-Step Metamorphic PBA Judge Prompt (Step 2B).
    """
    output_schema_str = json.dumps(Step2BJudgeOutput.model_json_schema(), ensure_ascii=False)
    ref_rubric, question_and_slot = build_step2b_layers(skill, question, target_slot_id)

    prompt = f"""# REFLECTIVE METAMORPHIC PBA LLM-AS-A-JUDGE (STEP 2B)

## [LAYER 1: REFERENCE LAYER (RUBRIC & PREVIOUS BELIEF ANCHOR)]
{ref_rubric}
{question_and_slot}
- Câu trả lời của ứng viên ($x_t$): "{candidate_response}"

## [LAYER 2: MAIN LAYER (TWO-STEP REFLECTIVE EVALUATION & METAMORPHIC TAGGING)]
Thực hiện đánh giá hai bước nghiêm ngặt:
1. **Step 2B.1 — Slot-Filling & Reflective Insight**:
   - Trích xuất bằng chứng kỹ thuật cụ thể từ $x_t$ vào `extracted_slot_value` (nếu ứng viên né tránh hoặc không có thông tin thực chất, ghi tóm tắt trạng thái thiếu bằng chứng).
   - Viết `reflective_insight` (1-2 câu ngắn gọn bằng tiếng Việt) đối chiếu trực tiếp câu trả lời $x_t$ với 3 tâm cụm Rubric c = [1.5, 3.0, 4.5] TRƯỚC KHI gán xác suất.
2. **Step 2B.2 — Metamorphic Tagging ($\\delta_{{\\max}}$ Bound)**:
   Phân loại $x_t$ vào ĐÚNG MỘT trong 4 quan hệ Metamorphic:
   - `INVARIANT` ($\\delta_{{\\max}} = 0.00$): Nói phô trương dùng từ khóa sáo rỗng (buzzwords without substance), lạc đề/không liên quan, hoặc chỉ lặp lại nguyên văn câu chữ đã có trong CV.
   - `MINOR_SHIFT` ($\\delta_{{\\max}} = 0.12$): Bằng chứng gián tiếp hoặc có rào cản khách quan hợp lý (Context Invalidation - ví dụ: do phân quyền tổ chức/hạ tầng khóa quyền nên chỉ tiếp cận một phần).
   - `MODERATE_SHIFT` ($\\delta_{{\\max}} = 0.25$): Đưa ra được ví dụ thực tế hợp lệ, hoặc bộc lộ giới hạn phạm vi/độ sâu ở mức trung bình (Scope/Rigour Downgrade).
   - `DECISIVE_SHIFT` ($\\delta_{{\\max}} = 0.45$): Thể hiện trình độ làm chủ chuyên sâu ở mức production đạt yêu cầu $s_{{jd}}$, HOẶC thừa nhận trực tiếp/rõ ràng việc không biết/thiếu kỹ năng này.
3. **Đề xuất Raw Posterior ($P_t^{{\\text{{raw}}}}$) & Tóm tắt hợp nhất**:
   - Đề xuất `raw_posterior_probs` = [P(Low), P(Med), P(High)] có tổng bằng 1.0 phản ánh đánh giá của bạn (hệ thống toán học sẽ tự động nội suy lồi với $P_{{t-1}}$ theo $\\delta_{{\\max}}$).
   - Viết `consolidated_summary` (đúng 1 câu tiếng Việt ngắn gọn tổng kết năng lực thực tế đã xác minh của ứng viên đối với kỹ năng `{skill.jd_skill_id}` để lưu vào bộ nhớ $A_{{ctx}}$).

## [LAYER 3: OUTPUT LAYER (DECLARATIVE DSPy SIGNATURE)]
Trả về duy nhất một đối tượng JSON hợp lệ tuân thủ tuyệt đối JSON Schema dưới đây:
{output_schema_str}
"""
    return prompt
