package fit.iuh.modules.evaluation.client;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import fit.iuh.common.exception.LlmInferenceException;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;
import org.springframework.web.reactive.function.client.WebClient;
import org.springframework.web.reactive.function.client.WebClientResponseException;
import reactor.core.publisher.Mono;

import java.time.Duration;
import java.util.List;
import java.util.Map;

/**
 * HTTP client wrapper for the OpenRouter API (OpenAI-compatible REST interface).
 * <p>
 * Calls {@code POST /chat/completions} and extracts {@code choices[0].message.content}.
 * A Reactor-level {@code .timeout()} is applied directly on the reactive chain to
 * ensure threads are released promptly on slow responses, in addition to the
 * {@code CompletableFuture} timeout enforced upstream in {@code EvaluationServiceImpl}.
 */
@Component
public class OpenRouterClient {

    private static final Logger log = LoggerFactory.getLogger(OpenRouterClient.class);

    private final WebClient webClient;
    private final ObjectMapper objectMapper;
    private final String evalModel;
    private final String finalReportModel;
    private final List<String> fallbackModels;
    private final Duration evalTimeout;
    private final Duration finalReportTimeout;

    public OpenRouterClient(
            @Value("${openrouter.api-key}") String apiKey,
            @Value("${openrouter.base-url:https://openrouter.ai/api/v1}") String baseUrl,
            @Value("${openrouter.fallback-models:poolside/laguna-xs-2.1:free,poolside/laguna-xs-2.1}") String fallbackModelsStr,
            @Value("${openrouter.model.evaluation:google/gemini-2.5-flash}") String evalModel,
            @Value("${openrouter.model.final-report:google/gemini-2.5-flash}") String finalReportModel,
            @Value("${llm.timeout-seconds:20}") int timeoutSeconds,
            @Value("${llm.final-report-timeout-seconds:60}") int finalReportTimeoutSeconds,
            ObjectMapper objectMapper) {
        this.webClient = WebClient.builder()
                .baseUrl(baseUrl)
                .defaultHeader("Authorization", "Bearer " + apiKey)
                .defaultHeader("Content-Type", "application/json")
                .defaultHeader("HTTP-Referer", "https://github.com/nguyenhoangkhq7/smile-interview")
                .defaultHeader("X-Title", "Smile Interview App")
                .build();
        this.objectMapper = objectMapper;
        this.evalModel = evalModel;
        this.finalReportModel = finalReportModel;
        this.fallbackModels = parseModelsStr(fallbackModelsStr);
        this.evalTimeout = Duration.ofSeconds(timeoutSeconds);
        this.finalReportTimeout = Duration.ofSeconds(finalReportTimeoutSeconds);
    }

    private static List<String> parseModelsStr(String modelsStr) {
        if (modelsStr == null || modelsStr.isBlank()) {
            return List.of();
        }
        return java.util.Arrays.stream(modelsStr.split(","))
                .map(String::trim)
                .filter(s -> !s.isEmpty())
                .collect(java.util.stream.Collectors.toList());
    }

    /**
     * Calls OpenRouter with the per-turn evaluation model.
     *
     * @param systemPrompt the system message
     * @param userPrompt   the user message
     * @return {@code Mono} of the raw JSON string from {@code choices[0].message.content}
     */
    public Mono<String> evaluationCompletion(String systemPrompt, String userPrompt) {
        return chatCompletion(evalModel, systemPrompt, userPrompt, 0.3, evalTimeout);
    }

    /**
     * Calls OpenRouter with the final-report model (may be a stronger / slower model).
     *
     * @param systemPrompt the system message
     * @param userPrompt   the user message
     * @return {@code Mono} of the raw JSON string from {@code choices[0].message.content}
     */
    public Mono<String> finalReportCompletion(String systemPrompt, String userPrompt) {
        return chatCompletion(finalReportModel, systemPrompt, userPrompt, 0.4, finalReportTimeout);
    }

    // ─────────────────────────────────────────────────────────────────────────

    private Mono<String> chatCompletion(String model, String systemPrompt, String userPrompt,
                                        double temperature, Duration timeout) {
        List<String> modelsList = new java.util.ArrayList<>();
        if (model != null && !model.isBlank()) {
            modelsList.add(model);
        }
        for (String fm : fallbackModels) {
            if (!modelsList.contains(fm)) {
                modelsList.add(fm);
            }
        }

        Map<String, Object> body = Map.of(
                "models", modelsList,
                "messages", List.of(
                        Map.of("role", "system", "content", systemPrompt),
                        Map.of("role", "user", "content", userPrompt)
                ),
                "response_format", Map.of("type", "json_object"),
                "temperature", temperature
        );

        return webClient.post()
                .uri("/chat/completions")
                .bodyValue(body)
                .retrieve()
                .bodyToMono(String.class)
                .timeout(timeout)
                .map(this::extractContent)
                .doOnError(WebClientResponseException.class,
                        e -> log.error("OpenRouter HTTP error {}: {}", e.getStatusCode(), e.getResponseBodyAsString()))
                .doOnError(java.util.concurrent.TimeoutException.class,
                        e -> log.error("OpenRouter request timed out after {}", timeout));
    }

    /**
     * Extracts the text content from {@code choices[0].message.content} in the OpenRouter response.
     */
    private String extractContent(String rawResponse) {
        try {
            JsonNode root = objectMapper.readTree(rawResponse);
            return root.path("choices").path(0).path("message").path("content").asText();
        } catch (Exception e) {
            log.error("Failed to parse OpenRouter response envelope: {}", rawResponse, e);
            throw new LlmInferenceException("Failed to parse OpenRouter response envelope", e);
        }
    }
}
