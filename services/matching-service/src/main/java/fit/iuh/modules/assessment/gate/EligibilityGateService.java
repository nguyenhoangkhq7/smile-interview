package fit.iuh.modules.assessment.gate;

import com.fasterxml.jackson.annotation.JsonIgnoreProperties;
import com.fasterxml.jackson.annotation.JsonProperty;
import com.fasterxml.jackson.databind.ObjectMapper;
import fit.iuh.config.AppProperties;
import fit.iuh.dto.chat.LlmChatRequest;
import fit.iuh.dto.chat.LlmChatResponse;
import fit.iuh.modules.assessment.dto.AssessmentResponseDto;
import fit.iuh.modules.assessment.entity.EligibilityStatus;
import fit.iuh.modules.assessment.entity.Importance;
import fit.iuh.modules.assessment.prompt.AssessmentPrompts;
import lombok.Data;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;
import org.springframework.web.reactive.function.client.WebClient;
import org.springframework.web.reactive.function.client.WebClientResponseException;

import java.time.Duration;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;

@Slf4j
@Service
@RequiredArgsConstructor
public class EligibilityGateService {

    private static final Map<String, String> JSON_RESPONSE_FORMAT = Map.of("type", "json_object");

    private final List<GateEvaluator> gateEvaluators;
    private final WebClient llmWebClient;
    private final ObjectMapper objectMapper;
    private final AppProperties appProperties;

    @com.fasterxml.jackson.annotation.JsonIgnoreProperties(ignoreUnknown = true)
    public record EligibilityEvaluationResult(
            EligibilityStatus status,
            List<AssessmentResponseDto.EvidenceItem> gateItems
    ) {}

    @Data
    @JsonIgnoreProperties(ignoreUnknown = true)
    public static class GateExtractionDto {
        @JsonProperty("gate_requirements")
        private List<GateCheckDto> gateRequirements;
    }

    @Data
    @JsonIgnoreProperties(ignoreUnknown = true)
    public static class GateCheckDto {
        @JsonProperty("criteria_name") private String criteriaName;
        @JsonProperty("importance") private String importance;
        @JsonProperty("required_value") private String requiredValue;
        @JsonProperty("actual_value") private String actualValue;
        @JsonProperty("status") private String status;
    }

    public EligibilityEvaluationResult evaluateEligibility(String jdContent, String cvContent) {
        return evaluateEligibilityWithRawGates(null, jdContent, cvContent);
    }

    public EligibilityEvaluationResult evaluateEligibilityWithRawGates(
            List<GateCheckDto> preExtractedGates, String jdContent, String cvContent) {

        log.info("[EligibilityGateService] Evaluating GATE requirements...");
        List<GateCheckDto> rawGates = (preExtractedGates != null && !preExtractedGates.isEmpty())
                ? preExtractedGates
                : null;

        if (rawGates == null) {
            try {
                rawGates = extractGateFromJd(jdContent);
            } catch (Exception e) {
                log.error("[EligibilityGateService] Gate extraction exception: {}", e.getMessage());
            }
        }

        if (rawGates == null || rawGates.isEmpty()) {
            return new EligibilityEvaluationResult(EligibilityStatus.PARTIAL, List.of());
        }

        boolean failedRequired = false;
        List<AssessmentResponseDto.EvidenceItem> gateItems = new ArrayList<>();

        for (GateCheckDto dto : rawGates) {
            String name = dto.getCriteriaName();
            Importance imp = parseImportance(dto.getImportance());
            String reqVal = dto.getRequiredValue();

            GateEvaluator evaluator = findEvaluator(name);
            GateEvaluationResult evalResult;

            if (evaluator != null) {
                evalResult = evaluator.evaluate(name, reqVal, cvContent);
                if (evalResult.evaluated() && !evalResult.passed() && imp == Importance.REQUIRED) {
                    failedRequired = true;
                }
            } else {
                // Cannot auto-evaluate this gate with simple heuristics.
                // Default to passed=true to avoid unfair rejection, but flag for manual review.
                evalResult = new GateEvaluationResult(
                        false,
                        true,
                        "Manual verification required",
                        "System heuristics currently only auto-evaluate recognized gates. Please manually verify this requirement."
                );
            }

            gateItems.add(new AssessmentResponseDto.EvidenceItem(
                    null,
                    (name != null && !"Certification".equalsIgnoreCase(name)) ? name : (reqVal != null && reqVal.length() <= 30 ? reqVal : name),
                    "GATE",
                    reqVal,
                    evalResult.cvEvidence(),
                    null,
                    evalResult.evaluated() ? (evalResult.passed() ? "PASSED" : "NOT_PASSED") : "NOT_EVALUATED",
                    evalResult.reasoning(),
                    null, null, null, null, null, null, null
            ));
        }

        EligibilityStatus finalStatus = failedRequired ? EligibilityStatus.NOT_ELIGIBILITY : EligibilityStatus.ELIGIBILITY;
        return new EligibilityEvaluationResult(finalStatus, gateItems);
    }

    public List<GateCheckDto> extractGateFromJd(String jdContent) {
        if (jdContent == null || jdContent.isBlank()) return List.of();

        String targetJd = jdContent.length() > 8000 ? jdContent.substring(0, 8000) + "\n...[TRUNCATED]" : jdContent;

        var taskConfig = appProperties.getLlm().getTasks().getGateExtraction();
        List<String> models = appProperties.getLlm().resolveModels(taskConfig);
        String model = models.isEmpty() ? appProperties.getLlm().resolveModel(taskConfig) : models.get(0);
        int maxTokens = 500;
        Duration timeout = Duration.ofSeconds(30);

        LlmChatRequest request = LlmChatRequest.builder()
                .model(model)
                .models(models)
                .maxTokens(maxTokens)
                .temperature(0.1)
                .stream(false)
                .responseFormat(JSON_RESPONSE_FORMAT)
                .messages(List.of(
                        LlmChatRequest.Message.system(AssessmentPrompts.SYSTEM_PROMPT_GATE_EXTRACTION),
                        LlmChatRequest.Message.user("Job Description:\n" + targetJd)
                ))
                .build();

        for (int attempt = 1; attempt <= 2; attempt++) {
            try {
                String responseBody = llmWebClient.post()
                        .uri(appProperties.getLlm().getChatPath())
                        .bodyValue(request)
                        .retrieve()
                        .bodyToMono(String.class)
                        .timeout(timeout)
                        .block();

                if (responseBody != null) {
                    LlmChatResponse res = objectMapper.readValue(responseBody, LlmChatResponse.class);
                    if (res != null && res.getFirstChoiceContent() != null) {
                        GateExtractionDto dto = objectMapper.readValue(res.getFirstChoiceContent(), GateExtractionDto.class);
                        return (dto != null && dto.getGateRequirements() != null) ? dto.getGateRequirements() : List.of();
                    }
                }
            } catch (WebClientResponseException e) {
                log.warn("[EligibilityGateService] Gate extraction OpenRouter HTTP {} Error: {}", e.getStatusCode(), e.getResponseBodyAsString());
                if (e.getStatusCode().value() == 400 && request.getResponseFormat() != null) {
                    log.warn("[EligibilityGateService] Retrying gate extraction without response_format...");
                    request = LlmChatRequest.builder()
                            .model(model)
                            .models(models)
                            .maxTokens(maxTokens)
                            .temperature(0.1)
                            .stream(false)
                            .messages(request.getMessages())
                            .build();
                    continue;
                }
                break;
            } catch (Exception e) {
                log.warn("[EligibilityGateService] Failed to extract gates: {}", e.getMessage());
                break;
            }
        }
        return List.of();
    }

    private GateEvaluator findEvaluator(String criteriaName) {
        if (gateEvaluators == null || criteriaName == null) return null;
        for (GateEvaluator evaluator : gateEvaluators) {
            if (evaluator.supports(criteriaName)) {
                return evaluator;
            }
        }
        return null;
    }

    private Importance parseImportance(String imp) {
        if (imp == null) return Importance.REQUIRED;
        try {
            return Importance.valueOf(imp.toUpperCase());
        } catch (Exception e) {
            return Importance.REQUIRED;
        }
    }
}
