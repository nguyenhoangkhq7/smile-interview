package fit.iuh.modules.assessment.service;

import com.fasterxml.jackson.annotation.JsonIgnoreProperties;
import com.fasterxml.jackson.annotation.JsonProperty;
import com.fasterxml.jackson.databind.ObjectMapper;
import fit.iuh.config.AppProperties;
import fit.iuh.dto.chat.LlmChatRequest;
import fit.iuh.dto.chat.LlmChatResponse;
import fit.iuh.modules.assessment.entity.JobCategory;
import fit.iuh.modules.assessment.entity.SeniorityLevel;
import fit.iuh.modules.assessment.prompt.AssessmentPrompts;
import fit.iuh.modules.assessment.util.TextSanitizationUtil;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;
import org.springframework.web.reactive.function.client.WebClient;
import org.springframework.web.reactive.function.client.WebClientResponseException;

import java.time.Duration;
import java.util.ArrayList;
import java.util.List;
import java.util.Locale;
import java.util.Map;

@Slf4j
@Service
@RequiredArgsConstructor
public class JdMetadataExtractor {

    private static final Map<String, String> JSON_RESPONSE_FORMAT = Map.of("type", "json_object");
    private static final int METADATA_MAX_TOKENS = 1024;

    private final AppProperties appProperties;
    private final WebClient llmWebClient;
    private final ObjectMapper objectMapper;

    public record MetadataResult(JobCategory category, SeniorityLevel level) {}
    public record JdRawMetadata(JobCategory category, List<SeniorityLevel> acceptedLevels) {}

    @JsonIgnoreProperties(ignoreUnknown = true)
    private record RawMetadataDto(
            @JsonProperty("category") String category,
            @JsonProperty("accepted_levels") List<String> acceptedLevels,
            @JsonProperty("level") String level
    ) {}

    public MetadataResult extractMetadata(String jdMarkdown, String cvMarkdown) {
        log.info("[JdMetadataExtractor] Calling LLM to extract Metadata...");
        var taskConfig = appProperties.getLlm().getTasks().getMetadataExtraction();
        List<String> models = appProperties.getLlm().resolveModels(taskConfig);
        String model = models.isEmpty() ? appProperties.getLlm().resolveModel(taskConfig) : models.get(0);
        int maxTokens = appProperties.getLlm().resolveMaxTokens(taskConfig);
        Duration timeout = Duration.ofSeconds(appProperties.getLlm().resolveTimeoutSeconds(taskConfig));

        String systemPrompt = AssessmentPrompts.SYSTEM_PROMPT_METADATA_EXTRACTION;
        String userPrompt = AssessmentPrompts.buildMetadataUserPrompt(jdMarkdown);

        LlmChatRequest request = LlmChatRequest.builder()
                .model(model)
                .models(models)
                .maxTokens(maxTokens)
                .temperature(0.1)
                .stream(false)
                .responseFormat(JSON_RESPONSE_FORMAT)
                .messages(List.of(
                        LlmChatRequest.Message.system(systemPrompt),
                        LlmChatRequest.Message.user(userPrompt)
                ))
                .build();

        for (int attempt = 1; attempt <= 2; attempt++) {
            long startTime = System.currentTimeMillis();
            try {
                String responseBody = llmWebClient.post()
                        .uri(appProperties.getLlm().getChatPath())
                        .bodyValue(request)
                        .retrieve()
                        .bodyToMono(String.class)
                        .timeout(timeout)
                        .block();

                long durationMs = System.currentTimeMillis() - startTime;

                if (responseBody != null) {
                    LlmChatResponse res = objectMapper.readValue(responseBody, LlmChatResponse.class);
                    if (res != null && res.getFirstChoiceContent() != null) {
                        var usage = res.getUsage();
                        if (usage != null) {
                            log.info("[LLM METRICS] Task: MetadataExtraction | Model: {} | Duration: {} ms ({} s) | Prompt Tokens: {} | Completion Tokens: {} | Total Tokens: {}",
                                    res.getModel() != null ? res.getModel() : model,
                                    durationMs,
                                    String.format("%.2f", durationMs / 1000.0),
                                    usage.getPromptTokens(),
                                    usage.getCompletionTokens(),
                                    usage.getTotalTokens());
                        } else {
                            log.info("[LLM METRICS] Task: MetadataExtraction | Model: {} | Duration: {} ms ({} s) | Usage: N/A",
                                    res.getModel() != null ? res.getModel() : model,
                                    durationMs,
                                    String.format("%.2f", durationMs / 1000.0));
                        }
                        return parseAndMapToEnums(res.getFirstChoiceContent(), cvMarkdown);
                    }
                }
            } catch (WebClientResponseException e) {
                log.warn("[JdMetadataExtractor] OpenRouter HTTP {} Error: {}", e.getStatusCode(), e.getResponseBodyAsString());
                if (e.getStatusCode().value() == 400 && request.getResponseFormat() != null) {
                    request = LlmChatRequest.builder()
                            .model(model)
                            .models(models)
                            .maxTokens(METADATA_MAX_TOKENS)
                            .temperature(0.1)
                            .stream(false)
                            .messages(request.getMessages())
                            .build();
                    continue;
                }
                break;
            } catch (Exception e) {
                log.warn("[JdMetadataExtractor] Error calling LLM: {}", e.getMessage());
                break;
            }
        }
        return fallbackMetadataResult();
    }

    private MetadataResult parseAndMapToEnums(String rawJson, String cvMarkdown) {
        String cleanJson = TextSanitizationUtil.extractCleanJson(rawJson);
        try {
            RawMetadataDto dto = objectMapper.readValue(cleanJson, RawMetadataDto.class);
            JobCategory category = parseJobCategory(dto.category());

            List<SeniorityLevel> jdLevels = new ArrayList<>();
            if (dto.acceptedLevels() != null && !dto.acceptedLevels().isEmpty()) {
                for (String l : dto.acceptedLevels()) {
                    jdLevels.add(parseSeniorityLevel(l));
                }
            } else if (dto.level() != null) {
                jdLevels.add(parseSeniorityLevel(dto.level()));
            }

            if (jdLevels.isEmpty()) {
                jdLevels.add(SeniorityLevel.MID);
            }

            SeniorityLevel finalLevel;
            if (jdLevels.size() == 1) {
                finalLevel = jdLevels.get(0);
            } else if (cvMarkdown != null && !cvMarkdown.isBlank()) {
                SeniorityLevel cvLevel = extractCvSeniorityLevel(cvMarkdown);
                finalLevel = resolveTargetSeniorityLevel(jdLevels, cvLevel);
            } else {
                finalLevel = jdLevels.get(0);
            }

            return new MetadataResult(category, finalLevel);
        } catch (Exception e) {
            log.warn("[JdMetadataExtractor] Parse error for: {}, using fallback", cleanJson);
            return fallbackMetadataResult();
        }
    }

    public JdRawMetadata extractJdRawMetadata(String jdMarkdown) {
        MetadataResult res = extractMetadata(jdMarkdown, "");
        return new JdRawMetadata(res.category(), List.of(res.level()));
    }

    public SeniorityLevel extractCvSeniorityLevel(String cvMarkdown) {
        if (cvMarkdown == null || cvMarkdown.isBlank()) return SeniorityLevel.MID;
        double yoe = fit.iuh.modules.assessment.util.ResumeHeuristicsUtil.calculateCandidateYoe(cvMarkdown);
        String cvLower = cvMarkdown.toLowerCase(Locale.ROOT);
        boolean hasInternKeywords = cvLower.contains("intern") || cvLower.contains("thực tập")
                || cvLower.contains("trainee") || cvLower.contains("thực tập sinh");
        if (yoe == 0.0 && hasInternKeywords) return SeniorityLevel.INTERN;
        if (yoe < 1.0) return SeniorityLevel.FRESHER;
        if (yoe < 3.0) return SeniorityLevel.JUNIOR;
        if (yoe < 5.0) return SeniorityLevel.MID;
        if (yoe < 8.0) return SeniorityLevel.SENIOR;
        return SeniorityLevel.LEAD;
    }

    public SeniorityLevel resolveTargetSeniorityLevel(List<SeniorityLevel> jdLevels, SeniorityLevel cvLevel) {
        if (jdLevels == null || jdLevels.isEmpty()) return SeniorityLevel.MID;
        if (cvLevel != null && jdLevels.contains(cvLevel)) return cvLevel;
        return jdLevels.get(0);
    }

    public JobCategory parseJobCategory(String value) {
        if (value == null || value.isBlank()) return JobCategory.SOFTWARE_ENGINEERING;
        String clean = value.toUpperCase(Locale.ROOT).trim();
        for (JobCategory cat : JobCategory.values()) {
            if (cat.name().equalsIgnoreCase(clean)) return cat;
        }
        return JobCategory.SOFTWARE_ENGINEERING;
    }

    public SeniorityLevel parseSeniorityLevel(String value) {
        if (value == null || value.isBlank()) return SeniorityLevel.MID;
        String clean = value.toUpperCase(Locale.ROOT).trim();
        for (SeniorityLevel lvl : SeniorityLevel.values()) {
            if (lvl.name().equalsIgnoreCase(clean)) return lvl;
        }
        return SeniorityLevel.MID;
    }

    private MetadataResult fallbackMetadataResult() {
        return new MetadataResult(JobCategory.SOFTWARE_ENGINEERING, SeniorityLevel.MID);
    }
}
