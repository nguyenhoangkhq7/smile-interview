package fit.iuh.modules.evaluation.client;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import fit.iuh.common.exception.LlmInferenceException;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.HttpStatusCode;
import org.springframework.http.MediaType;
import org.springframework.http.client.JdkClientHttpRequestFactory;
import org.springframework.stereotype.Component;
import org.springframework.web.client.RestClient;
import org.springframework.web.client.RestClientResponseException;

import java.time.Duration;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.List;
import java.util.Map;
import java.util.stream.Collectors;

/**
 * Modern synchronous HTTP client wrapper for the OpenRouter API (OpenAI-compatible REST interface).
 * Leverages Spring 6 RestClient running on Java 21 Virtual Threads.
 */
@Component
public class OpenRouterClient {

    private static final Logger log = LoggerFactory.getLogger(OpenRouterClient.class);

    private final RestClient evalRestClient;
    private final RestClient finalReportRestClient;
    private final ObjectMapper objectMapper;
    private final String evalModel;
    private final String finalReportModel;
    private final List<String> fallbackModels;
    private final int maxRetries;
    private final long retryBackoffMs;

    public OpenRouterClient(
            @Value("${openrouter.api-key}") String apiKey,
            @Value("${openrouter.base-url:https://openrouter.ai/api/v1}") String baseUrl,
            @Value("${openrouter.fallback-models:poolside/laguna-xs-2.1:free,poolside/laguna-xs-2.1}") String fallbackModelsStr,
            @Value("${openrouter.model.evaluation:google/gemini-2.0-flash-001}") String evalModel,
            @Value("${openrouter.model.final-report:google/gemini-2.0-flash-001}") String finalReportModel,
            @Value("${llm.timeout-seconds:60}") int timeoutSeconds,
            @Value("${llm.final-report-timeout-seconds:180}") int finalReportTimeoutSeconds,
            @Value("${llm.max-retries:2}") int maxRetries,
            @Value("${llm.retry-backoff-ms:1000}") long retryBackoffMs,
            ObjectMapper objectMapper) {

        this.objectMapper = objectMapper;
        this.evalModel = evalModel;
        this.finalReportModel = finalReportModel;
        this.fallbackModels = parseModelsStr(fallbackModelsStr);
        this.maxRetries = Math.max(0, maxRetries);
        this.retryBackoffMs = Math.max(100, retryBackoffMs);

        // Build RestClient with custom timeout factories
        this.evalRestClient = buildRestClient(baseUrl, apiKey, Duration.ofSeconds(timeoutSeconds));
        this.finalReportRestClient = buildRestClient(baseUrl, apiKey, Duration.ofSeconds(finalReportTimeoutSeconds));
    }

    private static RestClient buildRestClient(String baseUrl, String apiKey, Duration timeout) {
        JdkClientHttpRequestFactory requestFactory = new JdkClientHttpRequestFactory();
        requestFactory.setReadTimeout(timeout);

        return RestClient.builder()
                .baseUrl(baseUrl)
                .requestFactory(requestFactory)
                .defaultHeader("Authorization", "Bearer " + apiKey)
                .defaultHeader("Content-Type", MediaType.APPLICATION_JSON_VALUE)
                .defaultHeader("HTTP-Referer", "https://github.com/nguyenhoangkhq7/smile-interview")
                .defaultHeader("X-Title", "Smile Interview App")
                .build();
    }

    private static List<String> parseModelsStr(String modelsStr) {
        if (modelsStr == null || modelsStr.isBlank()) {
            return List.of();
        }
        return Arrays.stream(modelsStr.split(","))
                .map(String::trim)
                .filter(s -> !s.isEmpty())
                .collect(Collectors.toList());
    }

    /**
     * Calls OpenRouter with the per-turn evaluation model.
     *
     * @param systemPrompt the system message
     * @param userPrompt   the user message
     * @return the raw content string from {@code choices[0].message.content}
     */
    public String evaluationCompletion(String systemPrompt, String userPrompt) {
        return executeWithRetry(evalRestClient, evalModel, systemPrompt, userPrompt, 0.3);
    }

    /**
     * Calls OpenRouter with the final-report model.
     *
     * @param systemPrompt the system message
     * @param userPrompt   the user message
     * @return the raw content string from {@code choices[0].message.content}
     */
    public String finalReportCompletion(String systemPrompt, String userPrompt) {
        return executeWithRetry(finalReportRestClient, finalReportModel, systemPrompt, userPrompt, 0.4);
    }

    // ─────────────────────────────────────────────────────────────────────────

    private String executeWithRetry(RestClient client, String model, String systemPrompt,
                                    String userPrompt, double temperature) {
        List<String> modelsList = new ArrayList<>();
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

        int attempts = 0;
        long startTime = System.currentTimeMillis();

        while (true) {
            attempts++;
            try {
                String rawResponse = client.post()
                        .uri("/chat/completions")
                        .body(body)
                        .retrieve()
                        .body(String.class);

                long duration = System.currentTimeMillis() - startTime;
                return extractContentAndLog(rawResponse, duration);
            } catch (RestClientResponseException ex) {
                HttpStatusCode status = ex.getStatusCode();
                boolean isRetryable = status.value() == 429 || status.is5xxServerError();
                log.error("[OpenRouter] HTTP error {} (attempt {}/{}): {}",
                        status, attempts, maxRetries + 1, ex.getResponseBodyAsString());

                if (isRetryable && attempts <= maxRetries) {
                    sleepBackoff(attempts);
                    continue;
                }
                throw new LlmInferenceException("OpenRouter API call failed with HTTP " + status + ": " + ex.getMessage(), ex);
            } catch (Exception ex) {
                log.error("[OpenRouter] Request failed (attempt {}/{}): {}", attempts, maxRetries + 1, ex.getMessage());
                if (attempts <= maxRetries) {
                    sleepBackoff(attempts);
                    continue;
                }
                throw new LlmInferenceException("OpenRouter request failed after " + attempts + " attempts: " + ex.getMessage(), ex);
            }
        }
    }

    private void sleepBackoff(int attempt) {
        try {
            long sleepTime = retryBackoffMs * attempt;
            log.info("[OpenRouter] Retrying in {}ms...", sleepTime);
            Thread.sleep(sleepTime);
        } catch (InterruptedException ie) {
            Thread.currentThread().interrupt();
            throw new LlmInferenceException("Retry interrupted", ie);
        }
    }

    /**
     * Extracts text content from {@code choices[0].message.content} and logs usage metadata.
     */
    private String extractContentAndLog(String rawResponse, long durationMs) {
        try {
            JsonNode root = objectMapper.readTree(rawResponse);
            String content = root.path("choices").path(0).path("message").path("content").asText();

            String modelUsed = root.path("model").asText("unknown");
            JsonNode usage = root.path("usage");
            int promptTokens = usage.path("prompt_tokens").asInt(0);
            int completionTokens = usage.path("completion_tokens").asInt(0);
            int totalTokens = usage.path("total_tokens").asInt(0);

            log.info("[OpenRouter] Call finished in {}ms. Model: {}, Tokens: [prompt={}, completion={}, total={}]",
                    durationMs, modelUsed, promptTokens, completionTokens, totalTokens);

            if (content == null || content.isBlank()) {
                throw new LlmInferenceException("Empty content received in OpenRouter choices[0]");
            }
            return content;
        } catch (LlmInferenceException e) {
            throw e;
        } catch (Exception e) {
            log.error("Failed to parse OpenRouter response envelope: {}", rawResponse, e);
            throw new LlmInferenceException("Failed to parse OpenRouter response envelope", e);
        }
    }
}
