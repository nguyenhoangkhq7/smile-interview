package fit.iuh.modules.evaluation.service;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import fit.iuh.common.exception.LlmInferenceException;
import fit.iuh.grpc.inference.FinalReportRequest;
import fit.iuh.grpc.inference.InferenceRequest;
import fit.iuh.modules.evaluation.client.OpenRouterClient;
import fit.iuh.modules.evaluation.model.EvaluationResult;
import fit.iuh.modules.evaluation.model.FinalReportResult;
import fit.iuh.modules.evaluation.prompt.PromptBuilder;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;

import java.util.List;
import java.util.concurrent.CompletableFuture;
import java.util.concurrent.TimeUnit;

/**
 * Orchestrates the AI evaluation workflow for interview sessions.
 * <p>
 * Responsibilities (and only these):
 * <ol>
 *   <li>Select the appropriate prompt mode (fast vs. full scoring).</li>
 *   <li>Delegate prompt construction to {@link PromptBuilder}.</li>
 *   <li>Call the LLM via {@link OpenRouterClient} within a timeout boundary.</li>
 *   <li>Parse the JSON response and handle retries / fallbacks.</li>
 * </ol>
 */
@Service
public class EvaluationServiceImpl implements EvaluationService {

    private static final Logger log = LoggerFactory.getLogger(EvaluationServiceImpl.class);

    private final OpenRouterClient openRouterClient;
    private final ObjectMapper objectMapper;
    private final PromptBuilder promptBuilder;
    private final int timeoutSeconds;
    private final int finalReportTimeoutSeconds;

    public EvaluationServiceImpl(
            OpenRouterClient openRouterClient,
            ObjectMapper objectMapper,
            PromptBuilder promptBuilder,
            @Value("${llm.timeout-seconds:20}") int timeoutSeconds,
            @Value("${llm.final-report-timeout-seconds:60}") int finalReportTimeoutSeconds) {
        this.openRouterClient = openRouterClient;
        this.objectMapper = objectMapper;
        this.promptBuilder = promptBuilder;
        this.timeoutSeconds = timeoutSeconds;
        this.finalReportTimeoutSeconds = finalReportTimeoutSeconds;
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

        try {
            return CompletableFuture.supplyAsync(() ->
                    callAndParseEvaluation(systemPrompt, userPrompt, true)
            ).get(timeoutSeconds, TimeUnit.SECONDS);
        } catch (Exception e) {
            log.error("[EvaluateResponse] Inference failed or timed out. Falling back to NEXT_TOPIC.", e);
            return buildFallbackResult();
        }
    }

    // ─────────────────────────────────────────────────────────────────────────
    // Final synthesis
    // ─────────────────────────────────────────────────────────────────────────

    @Override
    public FinalReportResult generateFinalReport(FinalReportRequest request) {
        String systemPrompt = promptBuilder.buildFinalReportSystemPrompt(request.getTargetJobTitle());
        String userPrompt = promptBuilder.buildFinalReportUserPrompt(request);

        try {
            return CompletableFuture.supplyAsync(() ->
                    callAndParseFinalReport(systemPrompt, userPrompt)
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
    // LLM call + JSON parse helpers
    // ─────────────────────────────────────────────────────────────────────────

    /**
     * Calls the evaluation model and parses its JSON response.
     * Retries once with an explicit schema reminder if the initial response is malformed.
     */
    private EvaluationResult callAndParseEvaluation(String systemPrompt, String userPrompt, boolean allowRetry) {
        String rawJson = openRouterClient.evaluationCompletion(systemPrompt, userPrompt).block();
        try {
            return objectMapper.readValue(rawJson, EvaluationResult.class);
        } catch (JsonProcessingException e) {
            log.warn("[EvaluateResponse] JSON parse failed (retry={}): {}", allowRetry, e.getMessage());
            if (allowRetry) {
                String retryUserPrompt = userPrompt
                        + "\n\n[SYSTEM] Output trước không đúng JSON schema."
                        + " Hãy trả lại ĐÚNG schema JSON đã được chỉ định, không thêm text ngoài JSON.";
                return callAndParseEvaluation(systemPrompt, retryUserPrompt, false);
            }
            log.error("[EvaluateResponse] JSON parse failed after retry. Falling back.", e);
            return buildFallbackResult();
        }
    }

    /**
     * Calls the final-report model and parses its JSON response.
     * Throws {@link LlmInferenceException} on parse failure — no fallback,
     * since a malformed final report cannot be silently ignored.
     */
    private FinalReportResult callAndParseFinalReport(String systemPrompt, String userPrompt) {
        String rawJson = openRouterClient.finalReportCompletion(systemPrompt, userPrompt).block();
        try {
            return objectMapper.readValue(rawJson, FinalReportResult.class);
        } catch (JsonProcessingException e) {
            log.error("[GenerateFinalReport] JSON parse failed: {}", e.getMessage());
            throw new LlmInferenceException("Failed to parse final report response", e);
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
