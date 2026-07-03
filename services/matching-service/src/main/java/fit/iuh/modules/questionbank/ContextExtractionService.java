package fit.iuh.modules.questionbank;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import fit.iuh.config.AppProperties;
import fit.iuh.config.PromptTemplateConfig;
import fit.iuh.dto.chat.LlmChatRequest;
import fit.iuh.dto.chat.LlmChatResponse;
import fit.iuh.modules.questionbank.CandidateContextDto;
import fit.iuh.exception.LlmApiException;
import fit.iuh.exception.QuestionBankException;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Qualifier;
import org.springframework.stereotype.Service;
import org.springframework.web.reactive.function.client.WebClient;
import org.springframework.web.reactive.function.client.WebClientResponseException;

import java.time.Duration;
import java.util.List;
import java.util.Map;

/**
 * Service to call LLM and extract structured candidate profile and context
 * from CV, JD, and assessment result.
 */
@Slf4j
@Service
public class ContextExtractionService {

    private static final String CHAT_COMPLETIONS_PATH = "/openai/v1/chat/completions";
    private static final Map<String, String> JSON_RESPONSE_FORMAT = Map.of("type", "json_object");

    private final WebClient llmWebClient;
    private final AppProperties props;
    private final ObjectMapper objectMapper;

    public ContextExtractionService(
            @Qualifier("llmWebClient") WebClient llmWebClient,
            AppProperties props,
            ObjectMapper objectMapper) {
        this.llmWebClient = llmWebClient;
        this.props = props;
        this.objectMapper = objectMapper;
    }

    /**
     * Calls LLM to extract context information.
     *
     * @param cvMarkdown ATS optimized CV markdown
     * @param jdMarkdown Structured JD markdown
     * @param assessmentJson Assessment results in JSON format
     * @return candidate context DTO
     */
    public CandidateContextDto extractContext(String cvMarkdown, String jdMarkdown, String assessmentJson) {
        log.info("[ContextExtraction] Extracting candidate context via LLM...");

        String userPrompt = PromptTemplateConfig.buildContextExtractionUserPrompt(cvMarkdown, jdMarkdown, assessmentJson);

        LlmChatRequest request = LlmChatRequest.builder()
                .model(props.getLlm().getModel())
                .maxTokens(props.getLlm().getMaxTokens())
                .temperature(0.1) // Lower temperature for factual extraction
                .stream(false)
                .responseFormat(JSON_RESPONSE_FORMAT)
                .messages(List.of(
                        LlmChatRequest.Message.system(PromptTemplateConfig.SYSTEM_PROMPT_CONTEXT_EXTRACTION),
                        LlmChatRequest.Message.user(userPrompt)
                ))
                .build();

        Duration timeout = Duration.ofSeconds(props.getLlm().getTimeoutSeconds());

        int attempts = 0;
        int maxAttempts = 3;

        while (attempts < maxAttempts) {
            attempts++;
            try {
                LlmChatResponse response = llmWebClient.post()
                        .uri(CHAT_COMPLETIONS_PATH)
                        .bodyValue(request)
                        .retrieve()
                        .bodyToMono(LlmChatResponse.class)
                        .timeout(
                                timeout,
                                reactor.core.publisher.Mono.error(new LlmApiException(
                                        "Context extraction LLM API call timed out after " + timeout.toSeconds() + "s"))
                        )
                        .block();

                if (response == null || response.getFirstChoiceContent() == null) {
                    throw new QuestionBankException("LLM returned an empty context extraction response.");
                }

                String rawJson = response.getFirstChoiceContent().strip();
                return parseContextDto(rawJson);

            } catch (WebClientResponseException e) {
                if (e.getStatusCode().value() == 429 && attempts < maxAttempts) {
                    log.warn("[ContextExtraction] Rate limit hit (429). Sleeping for 15 seconds before attempt {}/{}", attempts + 1, maxAttempts);
                    try {
                        Thread.sleep(15000);
                    } catch (InterruptedException ie) {
                        Thread.currentThread().interrupt();
                        throw new QuestionBankException("Context extraction interrupted during backoff", ie);
                    }
                    continue;
                }
                throw new LlmApiException("LLM API HTTP " + e.getStatusCode() + " while extracting context: " + e.getResponseBodyAsString(), e);
            } catch (Exception e) {
                if (attempts >= maxAttempts) {
                    if (e instanceof QuestionBankException || e instanceof LlmApiException) {
                        throw e;
                    }
                    throw new QuestionBankException("Unexpected error during context extraction: " + e.getMessage(), e);
                }
            }
        }
        throw new QuestionBankException("Failed to extract context after " + maxAttempts + " attempts due to rate limiting or timeouts.");
    }

    private CandidateContextDto parseContextDto(String rawJson) {
        String cleanJson = rawJson
                .replaceAll("(?s)^```json\\s*", "")
                .replaceAll("(?s)\\s*```$", "")
                .strip();

        log.debug("[ContextExtraction] Cleaned JSON: {}", cleanJson);

        try {
            CandidateContextDto dto = objectMapper.readValue(cleanJson, CandidateContextDto.class);

            // Simple validation of required fields
            if (dto.getCandidateLevel() == null) {
                dto.setCandidateLevel("mid");
            }
            if (dto.getOverallMatch() == null) {
                dto.setOverallMatch("medium");
            }
            
            // Normalize values
            dto.setCandidateLevel(dto.getCandidateLevel().toLowerCase().strip());
            dto.setOverallMatch(dto.getOverallMatch().toLowerCase().strip());

            return dto;
        } catch (JsonProcessingException e) {
            log.error("[ContextExtraction] Failed to parse LLM JSON: {}", cleanJson, e);
            throw new QuestionBankException("LLM returned invalid context JSON: " + e.getMessage(), e);
        }
    }
}
