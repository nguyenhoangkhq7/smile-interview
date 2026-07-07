package fit.iuh.modules.assessment;

import com.fasterxml.jackson.annotation.JsonIgnoreProperties;
import com.fasterxml.jackson.annotation.JsonProperty;
import com.fasterxml.jackson.databind.ObjectMapper;
import fit.iuh.config.AppProperties;
import fit.iuh.config.PromptTemplateConfig;
import fit.iuh.dto.chat.LlmChatRequest;
import fit.iuh.dto.chat.LlmChatResponse;
import fit.iuh.exception.LlmApiException;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Qualifier;
import org.springframework.stereotype.Service;
import org.springframework.web.reactive.function.client.WebClient;
import org.springframework.web.reactive.function.client.WebClientResponseException;

import java.time.Duration;
import java.util.List;
import java.util.Map;

/**
 * Performs a lightweight LLM call to extract two key metadata fields from the
 * Job Description Markdown: {@link JobCategory} and {@link SeniorityLevel}.
 *
 * <h2>Design Philosophy</h2>
 * <ul>
 *   <li>This is the <strong>only</strong> LLM call that determines job routing.</li>
 *   <li>The output is immediately mapped to typed Java ENUMs — string variance
 *       ({@code "backend"}, {@code "BACK_END"}, {@code "Back End"}) is eliminated at
 *       this boundary, enforcing type safety across the entire pipeline.</li>
 *   <li>Uses {@code temperature=0.0} for maximum determinism.</li>
 *   <li>Token budget is minimal (max 128 tokens) — only 2 fields are returned.</li>
 * </ul>
 *
 * <h2>Fallback Strategy</h2>
 * If the LLM returns an unrecognised value, the service falls back to
 * {@code JobCategory.OTHER} and {@code SeniorityLevel.MID} rather than throwing,
 * ensuring the pipeline never hard-fails on metadata extraction.
 */
@Slf4j
@Service
public class MetadataExtractionService {

    /** Force JSON mode for deterministic output. */
    private static final Map<String, String> JSON_RESPONSE_FORMAT = Map.of("type", "json_object");

    /** Minimal token budget — we expect only 2 fields in the response. */
    private static final int METADATA_MAX_TOKENS = 128;

    private final AppProperties appProperties;
    private final WebClient llmWebClient;
    private final ObjectMapper objectMapper;

    public MetadataExtractionService(
            AppProperties appProperties,
            @Qualifier("llmWebClient") WebClient llmWebClient,
            ObjectMapper objectMapper) {
        this.appProperties = appProperties;
        this.llmWebClient = llmWebClient;
        this.objectMapper = objectMapper;
    }

    /**
     * Extracts {@link JobCategory} and {@link SeniorityLevel} from the JD Markdown.
     *
     * @param jdMarkdown the full, standardized JD Markdown from Step 1
     * @return an {@link ExtractionResult} containing the ENUM-mapped values
     */
    public ExtractionResult extract(String jdMarkdown) {
        log.info("[MetadataExtraction] Extracting job category and seniority level from JD Markdown...");
        
        // Cắt ngắn JD chỉ lấy 600 ký tự đầu (phần Header/Position Overview).
        // Việc này ép mô hình 30B không bị phân tâm bởi các yêu cầu rải rác bên dưới.
        String truncatedJd = jdMarkdown;
        if (jdMarkdown != null && jdMarkdown.length() > 600) {
            truncatedJd = jdMarkdown.substring(0, 600) + "\n...[TRUNCATED]";
        }

        LlmChatRequest request = LlmChatRequest.builder()
                .model(appProperties.getLlm().getModel())
                .maxTokens(METADATA_MAX_TOKENS)
                .temperature(0.0)
                .stream(false)
                .responseFormat(JSON_RESPONSE_FORMAT)
                .messages(List.of(
                        LlmChatRequest.Message.system(PromptTemplateConfig.SYSTEM_PROMPT_METADATA_EXTRACTION),
                        LlmChatRequest.Message.user(truncatedJd)
                ))
                .build();

        Duration timeout = Duration.ofSeconds(appProperties.getLlm().getTimeoutSeconds());
        int maxAttempts = 2;

        for (int attempt = 1; attempt <= maxAttempts; attempt++) {
            try {
                LlmChatResponse response = llmWebClient.post()
                        .uri(appProperties.getLlm().getChatPath())
                        .bodyValue(request)
                        .retrieve()
                        .bodyToMono(LlmChatResponse.class)
                        .timeout(timeout,
                                reactor.core.publisher.Mono.error(new LlmApiException(
                                        "Metadata extraction timed out after " + timeout.toSeconds() + "s")))
                        .block();

                if (response == null || response.getFirstChoiceContent() == null) {
                    throw new LlmApiException("LLM returned empty response during metadata extraction.");
                }

                String rawJson = response.getFirstChoiceContent().strip();
                log.debug("[MetadataExtraction] Raw LLM response: {}", rawJson);
                return parseAndMapToEnums(rawJson);

            } catch (WebClientResponseException e) {
                if (e.getStatusCode().value() == 429 && attempt < maxAttempts) {
                    log.warn("[MetadataExtraction] Rate limit (429) — retrying in 15s...");
                    sleepQuietly(15_000);
                    continue;
                }
                log.error("[MetadataExtraction] LLM HTTP error {}: {}", e.getStatusCode(), e.getResponseBodyAsString());
                // Fallback: do not crash the pipeline, return safe defaults
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

    // -------------------------------------------------------------------------
    // Private — Parsing & ENUM mapping
    // -------------------------------------------------------------------------

    /**
     * Parses the raw LLM JSON and maps the string values to typed Java ENUMs.
     * Invalid ENUM values are caught and replaced with safe fallbacks
     * ({@code OTHER} / {@code MID}) rather than throwing.
     */
    private ExtractionResult parseAndMapToEnums(String rawJson) {
        // Strip Markdown code fences as a safety fallback
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

    // -------------------------------------------------------------------------
    // Public result type & internal DTO
    // -------------------------------------------------------------------------

    /**
     * Immutable result of the metadata extraction step.
     * Passed directly to the rule engine (Step 3) and persisted on the entity.
     */
    public record ExtractionResult(JobCategory category, SeniorityLevel level) {}

    /**
     * Internal DTO for deserializing the LLM JSON output.
     * Fields intentionally kept as nullable Strings to handle LLM variance
     * before ENUM parsing with fallback.
     */
    @JsonIgnoreProperties(ignoreUnknown = true)
    private record RawMetadataDto(
            @JsonProperty("category") String category,
            @JsonProperty("level")    String level
    ) {}
}
