package fit.iuh.modules.evaluation;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import fit.iuh.grpc.inference.FinalReportRequest;
import fit.iuh.grpc.inference.QAContext;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;

import fit.iuh.grpc.inference.InferenceRequest;

import java.util.List;
import java.util.concurrent.CompletableFuture;
import java.util.concurrent.TimeUnit;

@Service
public class InterviewEvaluationService {

    private static final Logger log = LoggerFactory.getLogger(InterviewEvaluationService.class);

    private final OpenRouterClient openRouterClient;
    private final ObjectMapper objectMapper;
    private final int timeoutSeconds;
    private final int finalReportTimeoutSeconds;

    public InterviewEvaluationService(
            OpenRouterClient openRouterClient,
            ObjectMapper objectMapper,
            @Value("${llm.timeout-seconds:20}") int timeoutSeconds,
            @Value("${llm.final-report-timeout-seconds:60}") int finalReportTimeoutSeconds) {
        this.openRouterClient = openRouterClient;
        this.objectMapper = objectMapper;
        this.timeoutSeconds = timeoutSeconds;
        this.finalReportTimeoutSeconds = finalReportTimeoutSeconds;
    }

    // ─────────────────────────────────────────────────────────────────────────
    // Per-turn evaluation
    // ─────────────────────────────────────────────────────────────────────────

    public EvaluationResult evaluate(InferenceRequest request) {
        boolean fastMode = request.getFastMode();
        String systemPrompt;
        if (fastMode) {
            systemPrompt = buildEvalSystemPromptFast(
                    request.getTargetJobTitle(),
                    request.getInterviewDomain(),
                    request.getCvText());
        } else {
            systemPrompt = buildEvalSystemPrompt(
                    request.getTargetJobTitle(),
                    request.getInterviewDomain(),
                    request.getCvText(),
                    request.getGoodAnswerSignalsList());
        }
        String userPrompt = buildEvalUserPrompt(request);

        try {
            return CompletableFuture.supplyAsync(() ->
                    callAndParse(systemPrompt, userPrompt, true)
            ).get(timeoutSeconds, TimeUnit.SECONDS);
        } catch (Exception e) {
            log.error("[EvaluateResponse] Inference failed or timed out. Falling back to NEXT_TOPIC.", e);
            return buildFallbackResult();
        }
    }

    // ─────────────────────────────────────────────────────────────────────────
    // Final synthesis
    // ─────────────────────────────────────────────────────────────────────────

    public FinalReportResult generateFinalReport(FinalReportRequest request) {
        String systemPrompt = buildFinalReportSystemPrompt(request.getTargetJobTitle());
        String userPrompt = buildFinalReportUserPrompt(request);

        try {
            return CompletableFuture.supplyAsync(() ->
                    callFinalReportAndParse(systemPrompt, userPrompt)
            ).get(finalReportTimeoutSeconds, TimeUnit.SECONDS);
        } catch (Exception e) {
            log.error("[GenerateFinalReport] Final report generation failed or timed out.", e);
            return FinalReportResult.builder()
                    .overallScore(0)
                    .overallSummary("Không thể tổng hợp báo cáo do lỗi hệ thống.")
                    .strengths(List.of())
                    .weaknesses(List.of())
                    .recommendations(List.of())
                    .hiringRecommendation("No Hire")
                    .build();
        }
    }

    // ─────────────────────────────────────────────────────────────────────────
    // System prompts
    // ─────────────────────────────────────────────────────────────────────────

    private String buildEvalSystemPrompt(String targetJobTitle, String interviewDomain, String cvText, List<String> goodAnswerSignals) {
        String domain = (interviewDomain == null || interviewDomain.isBlank()) ? "IT" : interviewDomain;
        String jobTitle = (targetJobTitle == null || targetJobTitle.isBlank()) ? "Software Engineer" : targetJobTitle;

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

        if (goodAnswerSignals != null && !goodAnswerSignals.isEmpty()) {
            sb.append("\n## Bước 1.5 — So sánh với Tín hiệu trả lời tốt (Good Answer Signals)\n");
            sb.append("Hãy đối chiếu câu trả lời của ứng viên với các tín hiệu/từ khóa kỹ thuật mong đợi sau:\n");
            for (String signal : goodAnswerSignals) {
                sb.append("- ").append(signal).append("\n");
            }
            sb.append("Chấm điểm dựa trên tỷ lệ bao phủ của các tín hiệu này.\n");
        }

        if (cvText != null && !cvText.isBlank()) {
            sb.append("\n## Bước 1.6 — Tham chiếu CV của ứng viên để đặt câu hỏi phụ (Cá nhân hóa)\n");
            sb.append("Khi sinh câu hỏi phụ (follow_up_question), hãy tìm kiếm các dự án hoặc công nghệ liên quan trong CV dưới đây để đặt câu hỏi liên hệ thực tế của ứng viên đó:\n");
            sb.append("=== CV CỦA ỨNG VIÊN ===\n");
            sb.append(cvText).append("\n");
            sb.append("=======================\n");
        }

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

    private String buildEvalSystemPromptFast(String targetJobTitle, String interviewDomain, String cvText) {
        String domain = (interviewDomain == null || interviewDomain.isBlank()) ? "IT" : interviewDomain;
        String jobTitle = (targetJobTitle == null || targetJobTitle.isBlank()) ? "Software Engineer" : targetJobTitle;

        StringBuilder sb = new StringBuilder();
        sb.append(String.format("""
                Bạn là một chuyên gia phỏng vấn tuyển dụng cấp cao cho vị trí "%s"
                thuộc lĩnh vực "%s". Nhiệm vụ của bạn là đưa ra quyết định đi tiếp hay hỏi câu hỏi phụ đối với câu trả lời vừa rồi của ứng viên.

                ## Quyết định đi tiếp (decision):
                - FOLLOW_UP: câu trả lời chưa trọn vẹn, còn khía cạnh cụ thể đáng để hỏi sâu thêm VÀ current_follow_up_count < max_follow_up_count.
                - NEXT_TOPIC: câu trả lời đạt yêu cầu xuất sắc, HOẶC ứng viên nói không biết, HOẶC đã đạt max_follow_up_count, HOẶC câu trả lời quá kém.
                """, jobTitle, domain));

        if (cvText != null && !cvText.isBlank()) {
            sb.append("\n## Tham chiếu CV của ứng viên để đặt câu hỏi phụ (Cá nhân hóa)\n");
            sb.append("Khi sinh câu hỏi phụ (follow_up_question), hãy tìm kiếm các dự án hoặc công nghệ liên quan trong CV dưới đây để đặt câu hỏi liên hệ thực tế của ứng viên đó:\n");
            sb.append("=== CV CỦA ỨNG VIÊN ===\n");
            sb.append(cvText).append("\n");
            sb.append("=======================\n");
        }

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

    private String buildFinalReportSystemPrompt(String targetJobTitle) {
        String jobTitle = (targetJobTitle == null || targetJobTitle.isBlank()) ? "Software Engineer" : targetJobTitle;
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

    private String buildEvalUserPrompt(InferenceRequest request) {
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

        List<QAContext> thread = request.getConversationThreadList();
        if (thread != null && !thread.isEmpty()) {
            sb.append("\nNhánh hội thoại của chủ đề này (các lượt trước):\n");
            for (int i = 0; i < thread.size(); i++) {
                QAContext ctx = thread.get(i);
                sb.append(i + 1).append(". ")
                  .append(ctx.getWasFollowUp() ? "[Follow-up] " : "[Main] ")
                  .append("Q: ").append(ctx.getQuestion()).append("\n")
                  .append("   A: ").append(ctx.getAnswer()).append("\n");
            }
        }

        return sb.toString();
    }

    private String buildFinalReportUserPrompt(FinalReportRequest request) {
        StringBuilder sb = new StringBuilder();
        sb.append("Target Job Title: ").append(request.getTargetJobTitle()).append("\n\n");

        sb.append("=== TRANSCRIPT ===\n");
        List<fit.iuh.grpc.inference.TurnRecord> turns = request.getTurnsList();
        for (int i = 0; i < turns.size(); i++) {
            fit.iuh.grpc.inference.TurnRecord turn = turns.get(i);
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
    // LLM call + JSON parse (with 1 retry)
    // ─────────────────────────────────────────────────────────────────────────

    private EvaluationResult callAndParse(String systemPrompt, String userPrompt, boolean allowRetry) {
        String rawJson = openRouterClient.evaluationCompletion(systemPrompt, userPrompt).block();
        try {
            return objectMapper.readValue(rawJson, EvaluationResult.class);
        } catch (JsonProcessingException e) {
            log.warn("[EvaluateResponse] JSON parse failed (retry={}): {}", allowRetry, e.getMessage());
            if (allowRetry) {
                String retryUserPrompt = userPrompt + "\n\n[SYSTEM] Output trước không đúng JSON schema." +
                        " Hãy trả lại ĐÚNG schema JSON đã được chỉ định, không thêm text ngoài JSON.";
                return callAndParse(systemPrompt, retryUserPrompt, false);
            }
            log.error("[EvaluateResponse] JSON parse failed after retry. Falling back.", e);
            return buildFallbackResult();
        }
    }

    private FinalReportResult callFinalReportAndParse(String systemPrompt, String userPrompt) {
        String rawJson = openRouterClient.finalReportCompletion(systemPrompt, userPrompt).block();
        try {
            return objectMapper.readValue(rawJson, FinalReportResult.class);
        } catch (JsonProcessingException e) {
            log.error("[GenerateFinalReport] JSON parse failed: {}", e.getMessage());
            throw new RuntimeException("Failed to parse final report response", e);
        }
    }

    // ─────────────────────────────────────────────────────────────────────────
    // Fallback
    // ─────────────────────────────────────────────────────────────────────────

    private EvaluationResult buildFallbackResult() {
        return EvaluationResult.builder()
                .decision("NEXT_TOPIC")
                .followUpQuestion("")
                .reasoning("Hệ thống gặp sự cố kỹ thuật khi đánh giá, tự động chuyển câu hỏi tiếp theo.")
                .score(null)
                .evaluation(null)
                .isFallback(true)
                .excludedFromScoring(true)
                .build();
    }
}
