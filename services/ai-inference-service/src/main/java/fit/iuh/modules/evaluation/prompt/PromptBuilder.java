package fit.iuh.modules.evaluation.prompt;

import fit.iuh.grpc.inference.FinalReportRequest;
import fit.iuh.grpc.inference.InferenceRequest;
import fit.iuh.grpc.inference.QAContext;
import fit.iuh.grpc.inference.TurnRecord;
import org.springframework.stereotype.Component;

import java.util.List;

/**
 * Responsible exclusively for constructing LLM prompts (system + user messages).
 * <p>
 * Prompt construction is a distinct concern from business orchestration; isolating it here
 * keeps {@link fit.iuh.modules.evaluation.service.EvaluationServiceImpl} focused on
 * timeouts, retries, and fallback decisions, and makes prompt text easy to locate and tune.
 */
@Component
public class PromptBuilder {

    // ─────────────────────────────────────────────────────────────────────────
    // Evaluation system prompts
    // ─────────────────────────────────────────────────────────────────────────

    /**
     * Full-scoring system prompt (non-fast mode).
     * Includes 3-criteria rubric, good-answer-signal comparison, and CV personalisation.
     */
    public String buildEvalSystemPrompt(String targetJobTitle, String interviewDomain,
                                        String cvText, List<String> goodAnswerSignals) {
        String domain = normalise(interviewDomain, "IT");
        String jobTitle = normalise(targetJobTitle, "Software Engineer");

        StringBuilder sb = new StringBuilder();
        sb.append(String.format("""
                Bạn là một chuyên gia phỏng vấn tuyển dụng cấp cao cho vị trí "%s"
                thuộc lĩnh vực "%s". Nhiệm vụ của bạn là đóng vai LLM-as-a-judge để
                đánh giá MỘT câu trả lời của ứng viên trong ngữ cảnh cuộc phỏng vấn đang diễn ra.

                ## Bước 1 — Phân tích theo 3 tiêu chí (bắt buộc)
                1. Độ chính xác & chiều sâu: Nội dung có đúng không? Có thể hiện hiểu biết thực chất
                   hay chỉ định nghĩa bề nổi?
                2. Độ liên quan & bao phủ: Trả lời có đúng trọng tâm câu hỏi? Có bao quát các
                   khía cạnh kỹ thuật quan trọng không?
                3. Ứng dụng thực tế: Có ví dụ/tình huống/kết quả cụ thể (STAR) không, hay chỉ lý thuyết?
                """, jobTitle, domain));

        appendGoodAnswerSignals(sb, goodAnswerSignals);
        appendCvContext(sb, cvText,
                "## Bước 1.6 — Tham chiếu CV của ứng viên để đặt câu hỏi phụ (Cá nhân hóa)",
                "Khi sinh câu hỏi phụ (follow_up_question), hãy tìm kiếm các dự án hoặc công nghệ liên quan trong CV dưới đây để đặt câu hỏi liên hệ thực tế của ứng viên đó:");

        sb.append("""

                ## Bước 2 — Chấm điểm (rubric bắt buộc)
                - 9-10: Trả lời đầy đủ, chính xác, có ví dụ thực tế cụ thể, thể hiện chiều sâu chuyên môn rõ ràng.
                - 7-8 : Trả lời đúng trọng tâm, có ví dụ nhưng chưa thật sâu hoặc thiếu 1 khía cạnh nhỏ.
                - 5-6 : Trả lời đúng hướng nhưng chung chung, thiếu ví dụ cụ thể hoặc bỏ sót ý quan trọng.
                - 3-4 : Trả lời một phần, có hiểu sai hoặc rất sơ sài.
                - 1-2 : Trả lời sai trọng tâm, hoặc gần như không liên quan.
                - 0   : CHỈ dùng khi ứng viên chủ động nói không biết ("tôi không biết", "chưa tìm hiểu", "I don't know"...).

                ## Bước 3 — Ra quyết định
                - FOLLOW_UP : câu trả lời ở mức 3-8 điểm VÀ current_follow_up_count < max_follow_up_count
                              VÀ còn khía cạnh cụ thể đáng để hỏi sâu thêm.
                - NEXT_TOPIC : câu trả lời đạt 9-10 điểm, HOẶC ứng viên nói không biết (score=0),
                               HOẶC đã đạt max_follow_up_count, HOẶC câu trả lời quá kém (0-2 điểm).

                ## Bước 4 — Nếu FOLLOW_UP: sinh follow_up_question
                Câu hỏi phụ phải:
                - Nhắm thẳng vào phần cụ thể còn thiếu/sai/chưa rõ trong câu trả lời vừa rồi.
                - Không lặp lại ý đã có trong conversation_thread.
                - Ngắn gọn, tự nhiên như một người phỏng vấn thật đang hỏi tiếp.

                ## Output — CHỈ trả JSON đúng schema, không thêm text ngoài JSON:
                {
                  "decision": "FOLLOW_UP" hoặc "NEXT_TOPIC",
                  "follow_up_question": "..." (chuỗi rỗng nếu NEXT_TOPIC),
                  "reasoning": "1 câu ngắn gọn giải thích vì sao chọn decision này",
                  "score": <số nguyên 0-10>,
                  "evaluation": "Điểm mạnh: ...\\nĐiểm yếu / Hạn chế: ...\\nGợi ý bổ sung: ..."
                }
                """);

        return sb.toString();
    }

    /**
     * Lightweight system prompt (fast mode) — skips full rubric scoring,
     * returns only decision + follow-up question + reasoning.
     */
    public String buildEvalSystemPromptFast(String targetJobTitle, String interviewDomain, String cvText) {
        String domain = normalise(interviewDomain, "IT");
        String jobTitle = normalise(targetJobTitle, "Software Engineer");

        StringBuilder sb = new StringBuilder();
        sb.append(String.format("""
                Bạn là một chuyên gia phỏng vấn tuyển dụng cấp cao cho vị trí "%s"
                thuộc lĩnh vực "%s". Nhiệm vụ của bạn là đưa ra quyết định đi tiếp hay hỏi câu hỏi phụ đối với câu trả lời vừa rồi của ứng viên.

                ## Quyết định đi tiếp (decision):
                - FOLLOW_UP: câu trả lời chưa trọn vẹn, còn khía cạnh cụ thể đáng để hỏi sâu thêm VÀ current_follow_up_count < max_follow_up_count.
                - NEXT_TOPIC: câu trả lời đạt yêu cầu xuất sắc, HOẶC ứng viên nói không biết, HOẶC đã đạt max_follow_up_count, HOẶC câu trả lời quá kém.
                """, jobTitle, domain));

        appendCvContext(sb, cvText,
                "## Tham chiếu CV của ứng viên để đặt câu hỏi phụ (Cá nhân hóa)",
                "Khi sinh câu hỏi phụ (follow_up_question), hãy tìm kiếm các dự án hoặc công nghệ liên quan trong CV dưới đây để đặt câu hỏi liên hệ thực tế của ứng viên đó:");

        sb.append("""

                ## Sinh câu hỏi phụ (follow_up_question):
                - Nếu chọn FOLLOW_UP: sinh 1 câu hỏi đào sâu ngắn gọn, nhắm thẳng vào phần chưa rõ hoặc thiếu trong câu trả lời của ứng viên.
                - Nếu chọn NEXT_TOPIC: để chuỗi rỗng "".

                ## Output — CHỈ trả JSON đúng schema, không thêm bất kỳ văn bản nào khác ngoài JSON:
                {
                  "decision": "FOLLOW_UP" hoặc "NEXT_TOPIC",
                  "follow_up_question": "...",
                  "reasoning": "1 câu ngắn gọn giải thích vì sao chọn decision này"
                }
                """);

        return sb.toString();
    }

    /**
     * System prompt for the final holistic report (GenerateFinalReport RPC).
     */
    public String buildFinalReportSystemPrompt(String targetJobTitle) {
        String jobTitle = normalise(targetJobTitle, "Software Engineer");
        return """
                Bạn là một chuyên gia HR/Talent Acquisition cấp cao. Nhiệm vụ của bạn là
                tổng hợp toàn bộ buổi phỏng vấn cho vị trí "%s" và đưa ra đánh giá cuối cùng.

                ## Bước 1 — Đọc toàn bộ transcript
                Đọc kỹ từng cặp câu hỏi / câu trả lời, điểm số và nhận xét đánh giá từng lượt.
                Phân biệt câu hỏi chính (main question) và câu hỏi đào sâu (follow-up).

                ## Bước 2 — Tính overall_score
                Không lấy trung bình cộng đơn thuần. Hãy cân nhắc:
                - Câu hỏi chính (was_follow_up = false) có trọng số cao hơn follow-up.
                - Xu hướng cải thiện hay thụt lùi qua các chủ đề.
                - Mức độ đồng đều về kiến thức (ứng viên giỏi 1 mảng nhưng yếu hẳn mảng khác
                  sẽ bị đánh giá thấp hơn ứng viên đồng đều).
                Kết quả overall_score là số nguyên 0-10.

                ## Bước 3 — Đối chiếu với hồ sơ ứng viên (nếu có resume/JD)
                So sánh những gì ứng viên nói trong phỏng vấn với nội dung resume và JD được cung cấp.
                Chỉ ra nếu có điểm mâu thuẫn, phóng đại, hoặc không nhất quán giữa lời nói và CV.
                Nếu không phát hiện mâu thuẫn nào, không cần đề cập.
                Các mâu thuẫn phát hiện được (nếu có) phải được đưa vào mảng "weaknesses".

                ## Bước 4 — Đưa ra hiring_recommendation
                - "Strong Hire"    : overall_score >= 9, thể hiện rõ năng lực vượt yêu cầu.
                - "Hire"           : overall_score 7-8, đủ năng lực cho vị trí.
                - "No Hire"        : overall_score 4-6, tiềm năng nhưng chưa đủ.
                - "Strong No Hire" : overall_score <= 3, thiếu kiến thức nền tảng nghiêm trọng.

                ## Output — CHỈ trả JSON đúng schema, không thêm text ngoài JSON:
                {
                  "overall_score": <số nguyên 0-10>,
                  "overall_summary": "Tổng quan ngắn gọn về năng lực ứng viên",
                  "strengths": ["điểm mạnh 1", "điểm mạnh 2", ...],
                  "weaknesses": ["điểm yếu 1", "điểm yếu 2", ...],
                  "recommendations": ["gợi ý 1", "gợi ý 2", ...],
                  "hiring_recommendation": "Strong Hire" | "Hire" | "No Hire" | "Strong No Hire"
                }
                """.formatted(jobTitle);
    }

    // ─────────────────────────────────────────────────────────────────────────
    // User prompts
    // ─────────────────────────────────────────────────────────────────────────

    /**
     * Builds the user-turn prompt for per-turn evaluation.
     * Includes current Q&A context, follow-up depth counters, and conversation thread.
     */
    public String buildEvalUserPrompt(InferenceRequest request) {
        StringBuilder sb = new StringBuilder();
        sb.append("Target Job Title: ").append(request.getTargetJobTitle()).append("\n");
        sb.append("Interview Domain: ").append(request.getInterviewDomain()).append("\n");
        sb.append("Current Question: ").append(request.getCurrentQuestion()).append("\n");
        sb.append("Candidate Answer: ").append(request.getCandidateAnswer()).append("\n");
        sb.append("Follow-up depth: ").append(request.getCurrentFollowUpCount())
          .append(" / ").append(request.getMaxFollowUpCount()).append("\n");

        if (request.getMaxFollowUpCount() > 0
                && request.getCurrentFollowUpCount() >= request.getMaxFollowUpCount()) {
            sb.append("[RULE] Đã đạt giới hạn đào sâu. Bắt buộc trả NEXT_TOPIC bất kể chất lượng câu trả lời.\n");
        }

        appendConversationThread(sb, request.getConversationThreadList());

        return sb.toString();
    }

    /**
     * Builds the user-turn prompt for final report synthesis.
     * Includes the full interview transcript, optional resume, and optional JD.
     */
    public String buildFinalReportUserPrompt(FinalReportRequest request) {
        StringBuilder sb = new StringBuilder();
        sb.append("Target Job Title: ").append(request.getTargetJobTitle()).append("\n\n");

        sb.append("=== TRANSCRIPT ===\n");
        List<TurnRecord> turns = request.getTurnsList();
        for (int i = 0; i < turns.size(); i++) {
            TurnRecord turn = turns.get(i);
            sb.append("--- Turn ").append(i + 1)
              .append(turn.getWasFollowUp() ? " [Follow-up]" : " [Main]")
              .append(" ---\n");
            sb.append("Q: ").append(turn.getQuestion()).append("\n");
            sb.append("A: ").append(turn.getAnswer()).append("\n");
            sb.append("Score: ").append(turn.getScore()).append("/10\n");
            if (turn.getEvaluation() != null && !turn.getEvaluation().isBlank()) {
                sb.append("Evaluation: ").append(turn.getEvaluation()).append("\n");
            }
            sb.append("\n");
        }

        if (request.getResumeText() != null && !request.getResumeText().isBlank()) {
            sb.append("=== RESUME ===\n").append(request.getResumeText()).append("\n\n");
        }
        if (request.getJdText() != null && !request.getJdText().isBlank()) {
            sb.append("=== JOB DESCRIPTION ===\n").append(request.getJdText()).append("\n");
        }

        return sb.toString();
    }

    // ─────────────────────────────────────────────────────────────────────────
    // Private helpers
    // ─────────────────────────────────────────────────────────────────────────

    private String normalise(String value, String fallback) {
        return (value == null || value.isBlank()) ? fallback : value;
    }

    private void appendGoodAnswerSignals(StringBuilder sb, List<String> signals) {
        if (signals == null || signals.isEmpty()) return;
        sb.append("\n## Bước 1.5 — So sánh với Tín hiệu trả lời tốt (Good Answer Signals)\n");
        sb.append("Hãy đối chiếu câu trả lời của ứng viên với các tín hiệu/từ khóa kỹ thuật mong đợi sau:\n");
        for (String signal : signals) {
            sb.append("- ").append(signal).append("\n");
        }
        sb.append("Chấm điểm dựa trên tỷ lệ bao phủ của các tín hiệu này.\n");
    }

    private void appendCvContext(StringBuilder sb, String cvText, String header, String description) {
        if (cvText == null || cvText.isBlank()) return;
        sb.append("\n").append(header).append("\n");
        sb.append(description).append("\n");
        sb.append("=== CV CỦA ỨNG VIÊN ===\n");
        sb.append(cvText).append("\n");
        sb.append("=======================\n");
    }

    private void appendConversationThread(StringBuilder sb, List<QAContext> thread) {
        if (thread == null || thread.isEmpty()) return;
        sb.append("\nNhánh hội thoại của chủ đề này (các lượt trước):\n");
        for (int i = 0; i < thread.size(); i++) {
            QAContext ctx = thread.get(i);
            sb.append(i + 1).append(". ")
              .append(ctx.getWasFollowUp() ? "[Follow-up] " : "[Main] ")
              .append("Q: ").append(ctx.getQuestion()).append("\n")
              .append("   A: ").append(ctx.getAnswer()).append("\n");
        }
    }
}
