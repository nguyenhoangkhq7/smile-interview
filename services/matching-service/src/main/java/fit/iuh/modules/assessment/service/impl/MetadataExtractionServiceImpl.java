package fit.iuh.modules.assessment.service.impl;

import com.fasterxml.jackson.annotation.JsonIgnoreProperties;
import com.fasterxml.jackson.annotation.JsonProperty;
import com.fasterxml.jackson.databind.ObjectMapper;
import fit.iuh.config.AppProperties;
import fit.iuh.dto.chat.LlmChatRequest;
import fit.iuh.dto.chat.LlmChatResponse;
import fit.iuh.exception.LlmApiException;
import fit.iuh.modules.assessment.entity.JobCategory;
import fit.iuh.modules.assessment.entity.SeniorityLevel;
import fit.iuh.modules.assessment.prompt.AssessmentPrompts;
import fit.iuh.modules.assessment.service.MetadataExtractionService;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Qualifier;
import org.springframework.stereotype.Service;
import org.springframework.web.reactive.function.client.WebClient;
import org.springframework.web.reactive.function.client.WebClientResponseException;

import java.time.Duration;
import java.util.List;
import java.util.Map;

@Slf4j
@Service
public class MetadataExtractionServiceImpl implements MetadataExtractionService {

    private static final Map<String, String> JSON_RESPONSE_FORMAT = Map.of("type", "json_object");
    private static final int METADATA_MAX_TOKENS = 1024;

    private final AppProperties appProperties;
    private final WebClient llmWebClient;
    private final ObjectMapper objectMapper;

    public MetadataExtractionServiceImpl(
            AppProperties appProperties,
            @Qualifier("llmWebClient") WebClient llmWebClient,
            ObjectMapper objectMapper) {
        this.appProperties = appProperties;
        this.llmWebClient = llmWebClient;
        this.objectMapper = objectMapper;
    }

    @Override
    public ExtractionResult extract(String jdMarkdown) {
        log.info("[MetadataExtraction] Extracting job category and seniority level from JD Markdown...");

        String truncatedJd = jdMarkdown;
        if (jdMarkdown != null && jdMarkdown.length() > 600) {
            truncatedJd = jdMarkdown.substring(0, 600) + "\n...[TRUNCATED]";
        }

        LlmChatRequest request = LlmChatRequest.builder()
                .model(appProperties.getLlm().getModel())
                .maxTokens(METADATA_MAX_TOKENS)
                .temperature(0.1)
                .stream(false)
                .responseFormat(JSON_RESPONSE_FORMAT)
                .messages(List.of(
                        LlmChatRequest.Message.system(AssessmentPrompts.SYSTEM_PROMPT_METADATA_EXTRACTION),
                        LlmChatRequest.Message.user(truncatedJd)
                ))
                .build();

        Duration timeout = Duration.ofSeconds(appProperties.getLlm().getTimeoutSeconds());
        int maxAttempts = 2;

        for (int attempt = 1; attempt <= maxAttempts; attempt++) {
            try {
                String responseBody = llmWebClient.post()
                        .uri(appProperties.getLlm().getChatPath())
                        .bodyValue(request)
                        .retrieve()
                        .bodyToMono(String.class)
                        .timeout(timeout,
                                reactor.core.publisher.Mono.error(new LlmApiException(
                                        "Metadata extraction timed out after " + timeout.toSeconds() + "s")))
                        .block();

                if (responseBody == null || responseBody.isBlank()) {
                    throw new LlmApiException("LLM API returned empty HTTP body.");
                }

                log.debug("[MetadataExtraction] Raw HTTP response body: {}", responseBody);

                if (responseBody.contains("\"error\"") && (responseBody.contains("\"message\"") || responseBody.contains("\"code\""))) {
                    throw new LlmApiException("LLM API returned error JSON: " + responseBody);
                }

                LlmChatResponse response = objectMapper.readValue(responseBody, LlmChatResponse.class);

                if (response == null || response.getFirstChoiceContent() == null) {
                    throw new LlmApiException("LLM returned empty choices or null content. Response: " + responseBody);
                }

                String rawJson = response.getFirstChoiceContent().strip();
                log.info("[MetadataExtraction] Extracted raw content: {}", rawJson);
                return parseAndMapToEnums(rawJson);

            } catch (WebClientResponseException e) {
                if (e.getStatusCode().value() == 400 && request.getResponseFormat() != null) {
                    log.warn("[MetadataExtraction] Model '{}' rejected response_format (400 Bad Request). Retrying without response_format...", appProperties.getLlm().getModel());
                    request = LlmChatRequest.builder()
                            .model(appProperties.getLlm().getModel())
                            .maxTokens(METADATA_MAX_TOKENS)
                            .temperature(0.1)
                            .stream(false)
                            .messages(request.getMessages())
                            .build();
                    continue;
                }
                if (e.getStatusCode().value() == 429 && attempt < maxAttempts) {
                    log.warn("[MetadataExtraction] Rate limit (429) — retrying in 15s...");
                    sleepQuietly(15_000);
                    continue;
                }
                log.error("[MetadataExtraction] LLM HTTP error {}: {}", e.getStatusCode(), e.getResponseBodyAsString());
                return fallbackResult();
            } catch (Exception e) {
                log.error("[MetadataExtraction] Unexpected error (attempt {}/{}): {}", attempt, maxAttempts, e.getMessage());
                if (attempt >= maxAttempts) {
                    return fallbackResult();
                }
            }
        }
        return fallbackResult();
    }

    private ExtractionResult parseAndMapToEnums(String rawJson) {
        String json = rawJson
                .replaceAll("(?s)^```json\\s*", "")
                .replaceAll("(?s)\\s*```$", "")
                .strip();

        try {
            RawMetadataDto raw = objectMapper.readValue(json, RawMetadataDto.class);

            JobCategory category = parseJobCategory(raw.category());
            SeniorityLevel level = parseSeniorityLevel(raw.level());

            log.info("[MetadataExtraction] Extracted: category={}, level={}", category, level);
            return new ExtractionResult(category, level);

        } catch (Exception e) {
            log.warn("[MetadataExtraction] Failed to parse metadata JSON '{}': {}. Using fallback.", json, e.getMessage());
            return fallbackResult();
        }
    }

    private JobCategory parseJobCategory(String value) {
        if (value == null) return JobCategory.OTHER;
        try {
            return JobCategory.valueOf(value.toUpperCase().strip().replace(" ", "_").replace("-", "_"));
        } catch (IllegalArgumentException e) {
            log.warn("[MetadataExtraction] Unknown JobCategory '{}' — defaulting to OTHER", value);
            return JobCategory.OTHER;
        }
    }

    private SeniorityLevel parseSeniorityLevel(String value) {
        if (value == null) return SeniorityLevel.MID;
        try {
            return SeniorityLevel.valueOf(value.toUpperCase().strip());
        } catch (IllegalArgumentException e) {
            log.warn("[MetadataExtraction] Unknown SeniorityLevel '{}' — defaulting to MID", value);
            return SeniorityLevel.MID;
        }
    }

    private ExtractionResult fallbackResult() {
        log.warn("[MetadataExtraction] Using fallback defaults: category=OTHER, level=MID");
        return new ExtractionResult(JobCategory.OTHER, SeniorityLevel.MID);
    }

    private void sleepQuietly(long ms) {
        try {
            Thread.sleep(ms);
        } catch (InterruptedException ie) {
            Thread.currentThread().interrupt();
        }
    }

    @JsonIgnoreProperties(ignoreUnknown = true)
    private record RawMetadataDto(
            @JsonProperty("category") String category,
            @JsonProperty("level") String level
    ) {}
}
