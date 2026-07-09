package fit.iuh.modules.evaluation;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;
import org.springframework.web.reactive.function.client.WebClient;
import org.springframework.web.reactive.function.client.WebClientResponseException;
import reactor.core.publisher.Mono;

import java.util.List;
import java.util.Map;

/**
 * HTTP client wrapper for the OpenRouter API (OpenAI-compatible REST interface).
 * Calls POST /chat/completions and extracts choices[0].message.content.
 */
@Service
public class OpenRouterClient {

    private static final Logger log = LoggerFactory.getLogger(OpenRouterClient.class);

    private final WebClient webClient;
    private final ObjectMapper objectMapper;
    private final String evalModel;
    private final String finalReportModel;

    public OpenRouterClient(
            @Value("${openrouter.api-key}") String apiKey,
            @Value("${openrouter.base-url:https://openrouter.ai/api/v1}") String baseUrl,
            @Value("${openrouter.model.evaluation:google/gemini-2.5-flash}") String evalModel,
            @Value("${openrouter.model.final-report:google/gemini-2.5-flash}") String finalReportModel,
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
    }

    /**
     * Calls OpenRouter with the per-turn evaluation model.
     *
     * @param systemPrompt the system message
     * @param userPrompt   the user message
     * @return Mono of the raw JSON string from choices[0].message.content
     */
    public Mono<String> evaluationCompletion(String systemPrompt, String userPrompt) {
        return chatCompletion(evalModel, systemPrompt, userPrompt, 0.3);
    }

    /**
     * Calls OpenRouter with the final-report model (may be a stronger/slower model).
     *
     * @param systemPrompt the system message
     * @param userPrompt   the user message
     * @return Mono of the raw JSON string from choices[0].message.content
     */
    public Mono<String> finalReportCompletion(String systemPrompt, String userPrompt) {
        return chatCompletion(finalReportModel, systemPrompt, userPrompt, 0.4);
    }

    // ─────────────────────────────────────────────────────────────────────────

    private Mono<String> chatCompletion(String model, String systemPrompt, String userPrompt, double temperature) {
        Map<String, Object> body = Map.of(
                "model", model,
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
                .map(this::extractContent)
                .doOnError(WebClientResponseException.class,
                        e -> log.error("OpenRouter HTTP error {}: {}", e.getStatusCode(), e.getResponseBodyAsString()));
    }

    /**
     * Extracts the text content from choices[0].message.content in the OpenRouter response.
     */
    private String extractContent(String rawResponse) {
        try {
            JsonNode root = objectMapper.readTree(rawResponse);
            return root.path("choices").path(0).path("message").path("content").asText();
        } catch (Exception e) {
            log.error("Failed to parse OpenRouter response envelope: {}", rawResponse, e);
            throw new RuntimeException("Failed to parse OpenRouter response", e);
        }
    }
}
