package fit.iuh.modules.evaluation.service;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import fit.iuh.common.exception.LlmInferenceException;
import fit.iuh.common.util.JsonSanitizer;
import fit.iuh.grpc.inference.FinalReportRequest;
import fit.iuh.grpc.inference.InferenceRequest;
import fit.iuh.grpc.inference.QAContext;
import fit.iuh.modules.evaluation.client.OpenRouterClient;
import fit.iuh.modules.evaluation.model.EvaluationResult;
import fit.iuh.modules.evaluation.model.FinalReportResult;
import fit.iuh.modules.evaluation.prompt.PromptBuilder;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Service;

import java.util.Arrays;
import java.util.HashSet;
import java.util.List;
import java.util.Set;

/**
 * Orchestrates the AI evaluation workflow for interview sessions on Virtual Threads.
 * Enforces business constraints, sanitizes outputs, and manages retries/fallbacks.
 */
@Service
public class EvaluationServiceImpl implements EvaluationService {

    private static final Logger log = LoggerFactory.getLogger(EvaluationServiceImpl.class);

    private final OpenRouterClient openRouterClient;
    private final ObjectMapper objectMapper;
    private final PromptBuilder promptBuilder;

    public EvaluationServiceImpl(
            OpenRouterClient openRouterClient,
            ObjectMapper objectMapper,
            PromptBuilder promptBuilder) {
        this.openRouterClient = openRouterClient;
        this.objectMapper = objectMapper;
        this.promptBuilder = promptBuilder;
    }

    // ─────────────────────────────────────────────────────────────────────────
    // Per-turn evaluation
    // ─────────────────────────────────────────────────────────────────────────

    @Override
    public EvaluationResult evaluate(InferenceRequest request) {
        String systemPrompt = request.getFastMode()
                ? promptBuilder.buildEvalSystemPromptFast(
                        request.getTargetJobTitle(), request.getInterviewDomain(), request.getCvText())
                : promptBuilder.buildEvalSystemPrompt(
                        request.getTargetJobTitle(), request.getInterviewDomain(),
                        request.getCvText(), request.getGoodAnswerSignalsList());

        String userPrompt = promptBuilder.buildEvalUserPrompt(request);

        EvaluationResult result;
        try {
            result = callAndParseEvaluation(systemPrompt, userPrompt, true);
        } catch (Exception e) {
            log.error("[EvaluateResponse] Inference failed for session {}. Falling back to NEXT_TOPIC.",
                    request.getSessionId(), e);
            return buildFallbackResult();
        }

        // Programmatic enforcement:
        // 1. If follow-up quota is reached, force NEXT_TOPIC
        boolean limitReached = request.getMaxFollowUpCount() > 0
                && request.getCurrentFollowUpCount() >= request.getMaxFollowUpCount();

        if (limitReached && !"NEXT_TOPIC".equalsIgnoreCase(result.getDecision())) {
            log.info("[EvaluateResponse] Follow-up quota reached ({}/{}). Enforcing NEXT_TOPIC.",
                    request.getCurrentFollowUpCount(), request.getMaxFollowUpCount());
            result = EvaluationResult.builder()
                    .decision("NEXT_TOPIC")
                    .followUpQuestion("")
                    .reasoning((result.getReasoning() != null && !result.getReasoning().isBlank())
                            ? result.getReasoning()
                            : "Đã đạt giới hạn đào sâu của chủ đề này, chuyển sang câu hỏi tiếp theo.")
                    .score(result.getScore())
                    .evaluation(result.getEvaluation())
                    .isFallback(result.isFallback())
                    .excludedFromScoring(result.isExcludedFromScoring())
                    .build();
        } else if (result.getScore() != null && result.getScore() >= 8 && !"NEXT_TOPIC".equalsIgnoreCase(result.getDecision())) {
            // 2. If candidate scored high (>= 8), force NEXT_TOPIC to prevent redundant probes
            log.info("[EvaluateResponse] Candidate scored {} >= 8. Overriding decision to NEXT_TOPIC.", result.getScore());
            result = EvaluationResult.builder()
                    .decision("NEXT_TOPIC")
                    .followUpQuestion("")
                    .reasoning((result.getReasoning() != null && !result.getReasoning().isBlank())
                            ? result.getReasoning()
                            : "Câu trả lời đạt chất lượng tốt (" + result.getScore() + "/10), chuyển sang câu hỏi tiếp theo.")
                    .score(result.getScore())
                    .evaluation(result.getEvaluation())
                    .isFallback(result.isFallback())
                    .excludedFromScoring(result.isExcludedFromScoring())
                    .build();
        } else if (result.getScore() != null && result.getScore() <= 2 && !"NEXT_TOPIC".equalsIgnoreCase(result.getDecision())) {
            // 3. If candidate scored <= 2 (doesn't know or completely off-topic), force NEXT_TOPIC
            log.info("[EvaluateResponse] Candidate scored {} <= 2. Overriding decision to NEXT_TOPIC.", result.getScore());
            result = EvaluationResult.builder()
                    .decision("NEXT_TOPIC")
                    .followUpQuestion("")
                    .reasoning((result.getReasoning() != null && !result.getReasoning().isBlank())
                            ? result.getReasoning()
                            : "Câu trả lời chưa đúng trọng tâm hoặc ứng viên chưa nắm kiến thức, chuyển sang câu hỏi tiếp theo.")
                    .score(result.getScore())
                    .evaluation(result.getEvaluation())
                    .isFallback(result.isFallback())
                    .excludedFromScoring(result.isExcludedFromScoring())
                    .build();
        } else if ("FOLLOW_UP".equalsIgnoreCase(result.getDecision())
                && result.getFollowUpQuestion() != null
                && !result.getFollowUpQuestion().isBlank()) {
            // 4. Programmatic duplicate / repetition check against current and historical questions
            String newQ = result.getFollowUpQuestion();
            if (isRepetitiveQuestion(newQ, request.getCurrentQuestion(), request.getConversationThreadList())) {
                log.warn("[EvaluateResponse] Detected repetitive follow-up question for session {}: '{}'. Forcing NEXT_TOPIC.",
                        request.getSessionId(), newQ);
                result = EvaluationResult.builder()
                        .decision("NEXT_TOPIC")
                        .followUpQuestion("")
                        .reasoning("Ứng viên đã trả lời các khía cạnh trọng tâm của chủ đề này, chuyển sang câu hỏi tiếp theo.")
                        .score(result.getScore())
                        .evaluation(result.getEvaluation())
                        .isFallback(result.isFallback())
                        .excludedFromScoring(result.isExcludedFromScoring())
                        .build();
            }
        }

        return result;
    }

    // ─────────────────────────────────────────────────────────────────────────
    // Final synthesis
    // ─────────────────────────────────────────────────────────────────────────

    @Override
    public FinalReportResult generateFinalReport(FinalReportRequest request) {
        String systemPrompt = promptBuilder.buildFinalReportSystemPrompt(request.getTargetJobTitle());
        String userPrompt = promptBuilder.buildFinalReportUserPrompt(request);

        try {
            return callAndParseFinalReport(systemPrompt, userPrompt, true);
        } catch (Exception e) {
            log.error("[GenerateFinalReport] Final report generation failed for session {}: {}",
                    request.getSessionId(), e.getMessage(), e);
            throw new LlmInferenceException("Failed to generate final report: " + e.getMessage(), e);
        }
    }

    // ─────────────────────────────────────────────────────────────────────────
    // LLM call + JSON parse helpers
    // ─────────────────────────────────────────────────────────────────────────

    /**
     * Calls the evaluation model and parses its JSON response with markdown sanitization and retry.
     */
    private EvaluationResult callAndParseEvaluation(String systemPrompt, String userPrompt, boolean allowRetry) {
        String rawContent = openRouterClient.evaluationCompletion(systemPrompt, userPrompt);
        String cleanJson = JsonSanitizer.sanitize(rawContent);

        try {
            return objectMapper.readValue(cleanJson, EvaluationResult.class);
        } catch (JsonProcessingException e) {
            log.warn("[EvaluateResponse] JSON parse failed (retryAllowed={}): {}", allowRetry, e.getMessage());
            if (allowRetry) {
                String retryUserPrompt = userPrompt
                        + "\n\n[SYSTEM NOTICE] Output trước không đúng định dạng JSON chuẩn."
                        + " Hãy trả lời CHỈ bằng JSON đúng schema đã cung cấp, không thêm bất kỳ văn bản giải thích nào.";
                return callAndParseEvaluation(systemPrompt, retryUserPrompt, false);
            }
            log.error("[EvaluateResponse] JSON parse failed after retry. Raw: {}", rawContent, e);
            return buildFallbackResult();
        }
    }

    /**
     * Calls the final-report model and parses its JSON response with markdown sanitization and retry.
     */
    private FinalReportResult callAndParseFinalReport(String systemPrompt, String userPrompt, boolean allowRetry) {
        String rawContent = openRouterClient.finalReportCompletion(systemPrompt, userPrompt);
        String cleanJson = JsonSanitizer.sanitize(rawContent);

        try {
            return objectMapper.readValue(cleanJson, FinalReportResult.class);
        } catch (JsonProcessingException e) {
            log.warn("[GenerateFinalReport] JSON parse failed (retryAllowed={}): {}", allowRetry, e.getMessage());
            if (allowRetry) {
                String retryUserPrompt = userPrompt
                        + "\n\n[SYSTEM NOTICE] Output trước không đúng định dạng JSON chuẩn."
                        + " Hãy trả lời CHỈ bằng JSON đúng schema, không thêm text ngoài JSON.";
                return callAndParseFinalReport(systemPrompt, retryUserPrompt, false);
            }
            log.error("[GenerateFinalReport] JSON parse failed after retry. Raw: {}", rawContent, e);
            throw new LlmInferenceException("Failed to parse final report response from LLM", e);
        }
    }

    // ─────────────────────────────────────────────────────────────────────────
    // Repetition and duplicate question detection helpers
    // ─────────────────────────────────────────────────────────────────────────

    private boolean isRepetitiveQuestion(String newQ, String currentQ, List<QAContext> thread) {
        if (newQ == null || newQ.isBlank()) return false;
        if (isSimilar(newQ, currentQ)) return true;
        if (thread != null) {
            for (QAContext ctx : thread) {
                if (isSimilar(newQ, ctx.getQuestion())) {
                    return true;
                }
            }
        }
        return false;
    }

    private boolean isSimilar(String q1, String q2) {
        if (q1 == null || q2 == null) return false;
        String s1 = sanitizeText(q1);
        String s2 = sanitizeText(q2);
        if (s1.isBlank() || s2.isBlank()) return false;
        if (s1.equals(s2)) return true;

        Set<String> words1 = new HashSet<>(Arrays.asList(s1.split("\\s+")));
        Set<String> words2 = new HashSet<>(Arrays.asList(s2.split("\\s+")));

        // Remove short stopwords
        words1.removeIf(w -> w.length() <= 2);
        words2.removeIf(w -> w.length() <= 2);

        if (words1.isEmpty() || words2.isEmpty()) return false;

        Set<String> intersection = new HashSet<>(words1);
        intersection.retainAll(words2);

        double similarity = (double) intersection.size() / Math.min(words1.size(), words2.size());
        return similarity >= 0.55;
    }

    private String sanitizeText(String text) {
        return text.toLowerCase()
                .replaceAll("[^a-z0-9àáảãạăắằẳẵặâấầẩẫậèéẻẽẹêếềểễệìíỉĩịòóỏõọôốồổỗộơớờởỡợùúủũụưứừửữựỳýỷỹỵđ\\s]", " ")
                .replaceAll("\\s+", " ")
                .trim();
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
