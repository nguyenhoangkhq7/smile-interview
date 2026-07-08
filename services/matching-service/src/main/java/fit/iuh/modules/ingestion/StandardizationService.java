package fit.iuh.modules.ingestion;

import fit.iuh.config.AppProperties;
import fit.iuh.config.PromptTemplateConfig;
import fit.iuh.dto.chat.LlmChatRequest;
import fit.iuh.dto.chat.LlmChatResponse;
import fit.iuh.exception.LlmApiException;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Qualifier;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;
import org.springframework.web.reactive.function.client.WebClient;
import org.springframework.web.reactive.function.client.WebClientResponseException;
import reactor.core.publisher.Mono;

import java.time.Duration;
import java.util.List;

@Slf4j
@Service
public class StandardizationService {

    private final AppProperties appProperties;

    /**
     * Pre-configured LLM WebClient (currently pointing to Groq).
     * Injected by qualifier to avoid ambiguity with the embedding WebClient.
     */
    private final WebClient llmWebClient;

    public StandardizationService(
            AppProperties appProperties,
            @Qualifier("llmWebClient") WebClient llmWebClient) {
        this.appProperties = appProperties;
        this.llmWebClient = llmWebClient;
    }

    // -------------------------------------------------------------------------
    // Public API
    // -------------------------------------------------------------------------

    /**
     * Transforms raw CV text into an ATS-optimized Markdown document.
     *
     * <p>Sends the raw text to the configured LLM with
     * {@link PromptTemplateConfig#SYSTEM_PROMPT_CV} as the system instruction.
     *
     * @param rawCvText plain text extracted from the uploaded CV PDF
     * @return structured Markdown representation of the CV
     * @throws LlmApiException if the LLM API call fails or returns empty content
     */
    public String standardizeCv(String rawCvText) {
        log.info("Standardizing CV ({} chars) via LLM API...", rawCvText.length());
        return callLlmApi(PromptTemplateConfig.SYSTEM_PROMPT_CV, rawCvText, "CV");
    }

    /**
     * Transforms raw Job Description text into a structured Markdown document.
     *
     * <p>Sends the raw text to the configured LLM with
     * {@link PromptTemplateConfig#SYSTEM_PROMPT_JD} as the system instruction.
     *
     * @param rawJdText plain text from the JD PDF or free-form string input
     * @return structured Markdown representation of the JD
     * @throws LlmApiException if the LLM API call fails or returns empty content
     */
    public String standardizeJd(String rawJdText) {
        log.info("Standardizing JD ({} chars) via LLM API...", rawJdText.length());
        return callLlmApi(PromptTemplateConfig.SYSTEM_PROMPT_JD, rawJdText, "JD");
    }

    // -------------------------------------------------------------------------
    // Private implementation
    // -------------------------------------------------------------------------

    /**
     * Builds a {@link LlmChatRequest} and calls the configured LLM API via WebClient.
     *
     * <p>Error handling covers:
     * <ul>
     *   <li>HTTP 401 → invalid API key</li>
     *   <li>HTTP 429 → rate limit exceeded</li>
     *   <li>HTTP 5xx → provider server error</li>
     *   <li>Timeout → configurable via {@code app.groq.timeout-seconds}</li>
     *   <li>Null / blank response → empty LLM output</li>
     * </ul>
     *
     * @param systemPrompt the ATS system prompt (CV optimizer or JD analyzer)
     * @param userContent  the raw document text from the uploaded PDF
     * @param documentLabel short label for log messages: {@code "CV"} or {@code "JD"}
     * @return the LLM-generated Markdown string (never null, never blank)
     * @throws LlmApiException on any API or parsing failure
     */
    private String callLlmApi(String systemPrompt, String userContent, String documentLabel) {

        LlmChatRequest request = LlmChatRequest.builder()
                .model(appProperties.getLlm().getModel())
                .maxTokens(appProperties.getLlm().getMaxTokens())
                .temperature(0.1) // Changed from 0.0 to 0.1 to prevent Groq Llama 3 empty response bug
                .messages(List.of(
                        LlmChatRequest.Message.system(systemPrompt),
                        LlmChatRequest.Message.user(userContent)
                ))
                .build();

        Duration timeout = Duration.ofSeconds(appProperties.getLlm().getTimeoutSeconds());

        int maxRetries = 2;
        int attempt = 0;

        while (true) {
            try {
                LlmChatResponse response = llmWebClient.post()
                        .uri(appProperties.getLlm().getChatPath())
                        .bodyValue(request)
                        .retrieve()
                        .bodyToMono(LlmChatResponse.class)
                        .timeout(
                                timeout,
                                Mono.error(new LlmApiException(
                                        "LLM API call timed out after " +
                                        appProperties.getLlm().getTimeoutSeconds() +
                                        "s while standardizing " + documentLabel + "."))
                        )
                        .block(); // Convert reactive to blocking for the service layer

                if (response == null) {
                    throw new LlmApiException("LLM API returned a null response for " + documentLabel + ".");
                }

                String content = response.getFirstChoiceContent();
                if (content == null || content.isBlank()) {
                    log.error("LLM returned empty content. Raw response: {}", response);
                    throw new LlmApiException(
                            "LLM API returned empty content for " + documentLabel + ". " +
                            "Check that the system prompt is not malformed. Raw response was logged.");
                }

                log.info("LLM standardization OK for {}: {} chars generated (tokens={})",
                        documentLabel,
                        content.length(),
                        response.getUsage() != null ? response.getUsage().getTotalTokens() : "N/A");

                return content.strip();

            } catch (LlmApiException | WebClientResponseException e) {
                if (attempt >= maxRetries) {
                    if (e instanceof WebClientResponseException wce) {
                        throw new LlmApiException(
                                "LLM API HTTP " + wce.getStatusCode() + " for " + documentLabel +
                                ": " + wce.getResponseBodyAsString(), wce);
                    }
                    throw e; // re-throw LlmApiException
                }
                attempt++;
                log.warn("Transient error calling LLM API for {} (attempt {}/{}). Retrying... Error: {}",
                        documentLabel, attempt, maxRetries, e.getMessage());
                try {
                    Thread.sleep(1000 * attempt); // simple backoff
                } catch (InterruptedException ie) {
                    Thread.currentThread().interrupt();
                    throw new LlmApiException("Interrupted during retry backoff", ie);
                }
            } catch (Exception e) {
                throw new LlmApiException(
                        "Unexpected error calling LLM API for " + documentLabel +
                        ": " + e.getMessage(), e);
            }
        }
    }
}
