package fit.iuh.modules.assessment.service;

import com.fasterxml.jackson.databind.ObjectMapper;
import fit.iuh.config.AppProperties;
import fit.iuh.dto.chat.LlmChatRequest;
import fit.iuh.dto.chat.LlmChatResponse;
import fit.iuh.exception.LlmApiException;
import fit.iuh.modules.admin.repository.SystemSettingRepository;
import fit.iuh.modules.assessment.dto.AssessmentResponseDto;
import fit.iuh.modules.assessment.dto.ClassifiedCriteriaBundle;
import fit.iuh.modules.assessment.prompt.AssessmentPrompts;
import fit.iuh.modules.assessment.util.TextSanitizationUtil;

import fit.iuh.modules.rulengine.repository.JobCriteriaRepository.CriteriaWeightProjection;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.beans.factory.annotation.Qualifier;
import org.springframework.stereotype.Service;
import org.springframework.web.reactive.function.client.WebClient;
import org.springframework.web.reactive.function.client.WebClientResponseException;

import java.time.Duration;
import java.util.*;
import java.util.concurrent.CompletableFuture;
import java.util.concurrent.Semaphore;
import java.util.concurrent.TimeUnit;
import java.util.stream.Collectors;

/**
 * High-cohesion service responsible for LLM execution:
 * 1. Low-level LLM calls with global concurrency semaphore & retry logic
 * 2. Parsing & sanitizing LLM JSON responses
 * 3. Batched criteria assessment execution & evidence grounding
 */
@Slf4j
@Service
public class AssessmentLlmRunner {

    private static final Map<String, String> JSON_RESPONSE_FORMAT = Map.of("type", "json_object");

    private static final int DEFAULT_BATCH_SIZE = 10;
    private static final double DEFAULT_GROUNDING_THRESHOLD = 0.75;
    private static final int DEFAULT_BATCH_CONCURRENCY = 3;


    private final AppProperties appProperties;
    private final WebClient llmWebClient;
    private final ObjectMapper objectMapper;
    private final Semaphore globalLlmSemaphore;
    private final SystemSettingRepository systemSettingRepository;
    private final EvidenceGroundingValidator evidenceGroundingValidator;
    private final java.util.concurrent.Executor assessmentTaskExecutor;

    @Autowired
    public AssessmentLlmRunner(
            AppProperties appProperties,
            @Qualifier("llmWebClient") WebClient llmWebClient,
            ObjectMapper objectMapper,
            SystemSettingRepository systemSettingRepository,
            EvidenceGroundingValidator evidenceGroundingValidator,
            @Qualifier("assessmentTaskExecutor") java.util.concurrent.Executor assessmentTaskExecutor) {
        this.appProperties = appProperties;
        this.llmWebClient = llmWebClient;
        this.objectMapper = objectMapper;
        this.systemSettingRepository = systemSettingRepository;
        this.evidenceGroundingValidator = evidenceGroundingValidator;
        this.assessmentTaskExecutor = assessmentTaskExecutor;

        int concurrency = appProperties.getLlm().getGlobalConcurrency() > 0
                ? appProperties.getLlm().getGlobalConcurrency() : 10;
        this.globalLlmSemaphore = new Semaphore(concurrency, true);
    }


    // =========================================================================
    // 1. LLM CALLING WITH CONCURRENCY PERMITS
    // =========================================================================

    public String callLlmBlockingWithSemaphore(String systemPrompt, String userPrompt) {
        return callLlmBlockingWithSemaphore((AppProperties.TaskConfig) null, systemPrompt, userPrompt);
    }

    public String callLlmBlockingWithSemaphore(AppProperties.TaskConfig taskConfig, String systemPrompt, String userPrompt) {
        boolean acquired = false;
        long timeoutSeconds = appProperties.getLlm().getConcurrencyTimeoutSeconds() > 0
                ? appProperties.getLlm().getConcurrencyTimeoutSeconds() : 180;
        try {
            acquired = globalLlmSemaphore.tryAcquire(timeoutSeconds, TimeUnit.SECONDS);
            if (!acquired) {
                throw new LlmApiException("System LLM concurrency limit reached. Please try again later.");
            }
            return callLlmBlocking(taskConfig, systemPrompt, userPrompt);
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
            throw new LlmApiException("Interrupted while waiting for LLM semaphore permit", e);
        } finally {
            if (acquired) {
                globalLlmSemaphore.release();
            }
        }
    }

    public String callLlmBlocking(AppProperties.TaskConfig taskConfig, String systemPrompt, String userPrompt) {
        List<String> targetModels = appProperties.getLlm().resolveModels(taskConfig);
        String targetModel = targetModels.isEmpty() ? appProperties.getLlm().resolveModel(taskConfig) : targetModels.get(0);
        int maxTokens = appProperties.getLlm().resolveMaxTokens(taskConfig);
        double temperature = appProperties.getLlm().resolveTemperature(taskConfig);
        int timeoutSec = Math.max(180, appProperties.getLlm().resolveTimeoutSeconds(taskConfig));

        List<LlmChatRequest.Message> messagesList = new ArrayList<>();
        if (systemPrompt != null && !systemPrompt.isBlank()) {
            messagesList.add(LlmChatRequest.Message.system(systemPrompt));
        }
        if (userPrompt != null && !userPrompt.isBlank()) {
            messagesList.add(LlmChatRequest.Message.user(userPrompt));
        }

        LlmChatRequest request = LlmChatRequest.builder()
                .model(targetModel)
                .models(targetModels)
                .maxTokens(maxTokens)
                .temperature(temperature)
                .stream(false)
                .responseFormat(JSON_RESPONSE_FORMAT)
                .messages(messagesList)
                .build();

        int maxRetries = appProperties.getLlm().getMaxRetries() > 0
                ? appProperties.getLlm().getMaxRetries() : 3;
        long rateLimitSleepMs = appProperties.getLlm().getRateLimitSleepMs() > 0
                ? appProperties.getLlm().getRateLimitSleepMs() : 35000;

        for (int i = 0; i <= maxRetries; i++) {
            long startTime = System.currentTimeMillis();
            try {
                String responseBody = llmWebClient.post()
                        .uri(appProperties.getLlm().getChatPath())
                        .bodyValue(request)
                        .retrieve()
                        .bodyToMono(String.class)
                        .timeout(Duration.ofSeconds(timeoutSec))
                        .block();

                long durationMs = System.currentTimeMillis() - startTime;

                if (responseBody == null || responseBody.isBlank()) {
                    throw new LlmApiException("LLM API returned empty HTTP body during assessment.");
                }

                if (responseBody.contains("\"error\"") && (responseBody.contains("\"message\"") || responseBody.contains("\"code\""))) {
                    throw new LlmApiException("LLM API returned error JSON during assessment: " + responseBody);
                }

                LlmChatResponse response = objectMapper.readValue(responseBody, LlmChatResponse.class);
                if (response.getFirstChoiceContent() == null) {
                    throw new LlmApiException("LLM API returned empty assessment response.");
                }

                var usage = response.getUsage();
                if (usage != null) {
                    log.info("[LLM METRICS] Model: {} | Duration: {} ms ({} s) | Prompt Tokens: {} | Completion Tokens: {} | Total Tokens: {}",
                            response.getModel() != null ? response.getModel() : targetModel,
                            durationMs,
                            String.format("%.2f", durationMs / 1000.0),
                            usage.getPromptTokens(),
                            usage.getCompletionTokens(),
                            usage.getTotalTokens());
                } else {
                    log.info("[LLM METRICS] Model: {} | Duration: {} ms ({} s) | Usage: N/A",
                            response.getModel() != null ? response.getModel() : targetModel,
                            durationMs,
                            String.format("%.2f", durationMs / 1000.0));
                }

                return response.getFirstChoiceContent().strip();

            } catch (WebClientResponseException e) {
                log.warn("[LlmRunner] OpenRouter HTTP {} Error: {}", e.getStatusCode(), e.getResponseBodyAsString());
                if (e.getStatusCode().value() == 400 && request.getResponseFormat() != null) {
                    log.warn("[LlmRunner] Model '{}' rejected response_format (400 Bad Request). Retrying without response_format...", targetModel);
                    request = LlmChatRequest.builder()
                            .model(targetModel)
                            .models(targetModels)
                            .maxTokens(maxTokens)
                            .temperature(temperature)
                            .stream(false)
                            .messages(request.getMessages())
                            .build();
                    continue;
                }
                if (e.getStatusCode().value() == 429 && i < maxRetries) {
                    log.warn("[LlmRunner] LLM 429 Rate Limit — retrying after {}ms...", rateLimitSleepMs);
                    sleepQuietly(rateLimitSleepMs);
                    continue;
                }
                throw new LlmApiException("LLM HTTP " + e.getStatusCode() + ": " + e.getResponseBodyAsString(), e);
            } catch (LlmApiException e) {
                throw e;
            } catch (Exception e) {
                if (i >= maxRetries) {
                    throw new LlmApiException("LLM call failed after " + (maxRetries + 1) + " attempts: " + e.getMessage(), e);
                }
                sleepQuietly(2000);
            }
        }
        throw new LlmApiException("LLM call failed unexpectedly.");
    }

    // =========================================================================
    // 2. RESPONSE PARSING & SANITIZATION
    // =========================================================================

    public AssessmentResponseDto parseAssessmentDto(String sessionId, String llmJsonResponse) {
        String cleanJson = TextSanitizationUtil.extractCleanJson(llmJsonResponse);
        try {
            AssessmentResponseDto rawDto = objectMapper.readValue(cleanJson, AssessmentResponseDto.class);

            List<AssessmentResponseDto.EvidenceItem> sanitizedEvidence = rawDto.mustHaveEvidenceItems() != null
                    ? rawDto.mustHaveEvidenceItems().stream()
                    .filter(Objects::nonNull)
                    .map(item -> new AssessmentResponseDto.EvidenceItem(
                            item.criteriaId(),
                            TextSanitizationUtil.sanitizeCyrillicScript(item.criteriaName()),
                            item.importance(),
                            TextSanitizationUtil.sanitizeLanguageText(item.jdRequirement()),
                            TextSanitizationUtil.sanitizeLanguageText(item.cvEvidence()),
                            TextSanitizationUtil.sanitizeLanguageText(item.cvQuote()),
                            item.status(),
                            TextSanitizationUtil.sanitizeLanguageText(item.reasoning()),
                            item.weightUsed(),
                            item.scoreContribution(),
                            item.groundingScore(),
                            item.confidenceVotes(),
                            item.lowConfidence(),
                            item.needsManualReview(),
                            item.matchMetadata()
                    ))
                    .collect(Collectors.toList())
                    : List.of();

            List<AssessmentResponseDto.AdHocEvidenceItem> preferToHave = rawDto.preferToHaveEvidenceItems() != null
                    ? rawDto.preferToHaveEvidenceItems() : List.of();
            List<AssessmentResponseDto.AdHocEvidenceItem> sanitizedAdHoc = preferToHave.stream()
                    .filter(Objects::nonNull)
                    .map(item -> new AssessmentResponseDto.AdHocEvidenceItem(
                            item.criteriaId(),
                            TextSanitizationUtil.sanitizeCyrillicScript(item.criteriaName()),
                            item.importance(),
                            TextSanitizationUtil.sanitizeLanguageText(item.jdRequirement()),
                            TextSanitizationUtil.sanitizeLanguageText(item.cvEvidence()),
                            TextSanitizationUtil.sanitizeLanguageText(item.cvQuote()),
                            item.status(),
                            TextSanitizationUtil.sanitizeLanguageText(item.reasoning()),
                            item.matchMetadata()
                    ))
                    .collect(Collectors.toList());

            return new AssessmentResponseDto(sanitizedEvidence, sanitizedAdHoc);

        } catch (Exception e) {
            log.error("[AssessmentLlmRunner] JSON parse error for session {}: {}", sessionId, e.getMessage());
            throw new RuntimeException("Failed to parse LLM assessment JSON response", e);
        }
    }

    // =========================================================================
    // 3. BATCHED ASSESSMENT EXECUTION
    // =========================================================================

    /**
     * A single criterion item assembled for LLM prompt injection.
     *
     * @param sourceDepth  0 = leaf / most-specific category → [SPECIFIC_SKILLS] tag;
     *                     ≥1 = ancestor category → [CORE_SKILLS] tag.
     *                     Null means depth is unknown (treated as specific).
     */
    public record CriteriaInstructionItem(Long criteriaId, String name, String label, String promptInstruction, Integer sourceDepth) implements java.io.Serializable {
        @java.io.Serial
        private static final long serialVersionUID = 1L;
    }

    public record BatchResult(
            List<AssessmentResponseDto.EvidenceItem> evidenceItems,
            List<AssessmentResponseDto.AdHocEvidenceItem> preferToHaveEvidenceItems
    ) {}

    public AssessmentResponseDto runBatchedAssessment(
            String sessionId,
            String fullCvMarkdown,
            String fullJdMarkdown,
            ClassifiedCriteriaBundle bundle) {

        List<ClassifiedCriteriaBundle.ClassifiedCriteria> dbCriteria = bundle.activeDbCriteria();
        List<ClassifiedCriteriaBundle.JdExtraCriteria> jdExtras = bundle.jdExtras();

        List<CriteriaInstructionItem> allItems = new ArrayList<>();
        for (var c : dbCriteria) {
            String label = switch (c.importance().toLowerCase(Locale.ROOT)) {
                case "required" -> "[REQUIRED]";
                case "preferred" -> "[PREFERRED]";
                case "not_in_jd" -> "[NOT_IN_JD]";
                default -> "[REQUIRED]";
            };
            // JD-classified criteria: depth not applicable (null → treated as [SPECIFIC_SKILLS] by convention)
            allItems.add(new CriteriaInstructionItem(c.criteriaId(), c.criteriaName(), label, c.promptInstruction(), null));
        }
        for (var extra : jdExtras) {
            String label = "preferred".equalsIgnoreCase(extra.importance()) ? "[PREFERRED]" : "[REQUIRED]";
            allItems.add(new CriteriaInstructionItem(null, extra.name(), label, extra.promptInstruction(), null));
        }

        return executeBatchedAssessment(sessionId, fullCvMarkdown, allItems);
    }

    public AssessmentResponseDto runBatchedCriteriaAssessment(
            String sessionId,
            String fullCvMarkdown,
            String fullJdMarkdown,
            List<CriteriaWeightProjection> criteriaList) {

        List<CriteriaInstructionItem> allItems = new ArrayList<>();
        if (criteriaList != null) {
            for (CriteriaWeightProjection c : criteriaList) {
                String promptInst = (c.getLevelPromptInstruction() != null && !c.getLevelPromptInstruction().isBlank())
                        ? c.getLevelPromptInstruction() : c.getPromptInstruction();
                // sourceDepth: 0 = leaf/specific category, ≥1 = ancestor/inherited
                Integer depth = c.getSourceDepth();
                allItems.add(new CriteriaInstructionItem(c.getCriteriaId(), c.getCriteriaName(), "[REQUIRED]", promptInst, depth));
            }
        }
        return executeBatchedAssessment(sessionId, fullCvMarkdown, allItems);
    }

    private AssessmentResponseDto executeBatchedAssessment(
            String sessionId,
            String fullCvMarkdown,
            List<CriteriaInstructionItem> allItems) {

        int maxBatchSize = getSystemSettingInt("CRITERIA_BATCH_SIZE", DEFAULT_BATCH_SIZE);
        if (maxBatchSize < 1) maxBatchSize = 1;
        double groundingThreshold = getSystemSettingDouble("EVIDENCE_GROUNDING_THRESHOLD", DEFAULT_GROUNDING_THRESHOLD);
        int batchConcurrency = getSystemSettingInt("CRITERIA_BATCH_CONCURRENCY", DEFAULT_BATCH_CONCURRENCY);

        Semaphore batchSemaphore = new Semaphore(batchConcurrency, true);
        List<List<CriteriaInstructionItem>> batches = partitionInstructionItems(allItems, maxBatchSize);

        List<CompletableFuture<BatchResult>> batchFutures = new ArrayList<>();
        for (List<CriteriaInstructionItem> batchItems : batches) {
            CompletableFuture<BatchResult> batchFuture = CompletableFuture.supplyAsync(() -> {
                boolean acquired = false;
                try {
                    acquired = batchSemaphore.tryAcquire(240, TimeUnit.SECONDS);
                    if (!acquired) {
                        throw new LlmApiException("Batch concurrency limit reached waiting for permit.");
                    }
                    return processBatchInstructionItems(
                            sessionId, fullCvMarkdown, batchItems, groundingThreshold
                    );
                } catch (InterruptedException e) {
                    Thread.currentThread().interrupt();
                    throw new LlmApiException("Interrupted waiting for batch concurrency semaphore.", e);
                } finally {
                    if (acquired) batchSemaphore.release();
                }
            }, assessmentTaskExecutor);
            batchFutures.add(batchFuture);
        }

        List<AssessmentResponseDto.EvidenceItem> aggregatedEvidenceItems = new ArrayList<>();
        List<AssessmentResponseDto.AdHocEvidenceItem> aggregatedAdHocItems = new ArrayList<>();

        for (CompletableFuture<BatchResult> future : batchFutures) {
            try {
                BatchResult res = future.join();
                if (res.evidenceItems() != null) aggregatedEvidenceItems.addAll(res.evidenceItems());
                if (res.preferToHaveEvidenceItems() != null) aggregatedAdHocItems.addAll(res.preferToHaveEvidenceItems());
            } catch (Exception e) {
                log.error("[AssessmentLlmRunner] Batch execution failed for session {}: {}", sessionId, e.getMessage());
            }
        }

        List<AssessmentResponseDto.EvidenceItem> deduplicatedEvidenceItems = deduplicateEvidenceItems(aggregatedEvidenceItems);
        return new AssessmentResponseDto(deduplicatedEvidenceItems, aggregatedAdHocItems);
    }

    private BatchResult processBatchInstructionItems(
            String sessionId,
            String fullCvMarkdown,
            List<CriteriaInstructionItem> batchItems,
            double groundingThreshold) {

        StringBuilder sb = new StringBuilder();
        for (CriteriaInstructionItem item : batchItems) {
            sb.append("- ").append(item.label());
            if (item.criteriaId() != null) {
                sb.append(" [ID: ").append(item.criteriaId()).append("]");
            }
            // Inheritance tag: depth=0 (or unknown) → specific skill; depth≥1 → inherited core skill
            boolean isInherited = item.sourceDepth() != null && item.sourceDepth() > 0;
            sb.append(isInherited ? " [CORE_SKILLS]" : " [SPECIFIC_SKILLS]");
            sb.append(" ").append(item.name()).append(": ")
                    .append(item.promptInstruction() != null ? item.promptInstruction() : "")
                    .append("\n");
        }
        String criteriaInstructions = sb.toString().strip();

        String systemPrompt = AssessmentPrompts.buildAssessmentSystemPrompt();
        String userPrompt = AssessmentPrompts.buildAssessmentUserPrompt(fullCvMarkdown, criteriaInstructions);

        var taskConfig = appProperties.getLlm().getTasks().getAssessment();

        String llmResponse = callLlmBlockingWithSemaphore(taskConfig, systemPrompt, userPrompt);
        AssessmentResponseDto dto = parseAssessmentDto(sessionId, llmResponse);
        if (dto == null) {
            throw new LlmApiException("Failed to parse LLM assessment response for session " + sessionId);
        }

        Map<Long, String> labelMap = new HashMap<>();
        Map<String, Long> nameToIdMap = new HashMap<>();

        for (CriteriaInstructionItem item : batchItems) {
            if (item.criteriaId() != null) {
                labelMap.put(item.criteriaId(), item.label());
                if (item.name() != null && !item.name().isBlank()) {
                    nameToIdMap.put(item.name().trim().toLowerCase(Locale.ROOT), item.criteriaId());
                }
            }
        }

        Map<Long, AssessmentResponseDto.EvidenceItem> evaluatedItemsMap = new LinkedHashMap<>();

        if (dto.mustHaveEvidenceItems() != null) {
            for (AssessmentResponseDto.EvidenceItem item : dto.mustHaveEvidenceItems()) {
                Long cid = item.criteriaId();
                if (cid == null && item.criteriaName() != null) {
                    cid = nameToIdMap.get(item.criteriaName().trim().toLowerCase(Locale.ROOT));
                }
                if (cid != null) {
                    String rawLabel = labelMap.getOrDefault(cid, "[REQUIRED]");
                    String importance = parseLabelToImportance(rawLabel);
                    AssessmentResponseDto.EvidenceItem resolved = new AssessmentResponseDto.EvidenceItem(
                            cid, item.criteriaName(), importance, item.jdRequirement(),
                            item.cvEvidence(), item.cvQuote(), item.status(), item.reasoning(),
                            item.weightUsed(), item.scoreContribution(), item.groundingScore(),
                            null, false, false, item.matchMetadata()
                    );
                    evaluatedItemsMap.put(cid, resolved);
                }
            }
        }

        if (dto.preferToHaveEvidenceItems() != null) {
            for (AssessmentResponseDto.AdHocEvidenceItem item : dto.preferToHaveEvidenceItems()) {
                Long cid = item.criteriaId();
                if (cid == null && item.criteriaName() != null) {
                    cid = nameToIdMap.get(item.criteriaName().trim().toLowerCase(Locale.ROOT));
                }
                if (cid != null && !evaluatedItemsMap.containsKey(cid)) {
                    String rawLabel = labelMap.getOrDefault(cid, "[PREFERRED]");
                    String importance = parseLabelToImportance(rawLabel);
                    AssessmentResponseDto.EvidenceItem converted = new AssessmentResponseDto.EvidenceItem(
                            cid,
                            item.criteriaName(),
                            importance,
                            item.jdRequirement(),
                            item.cvEvidence(),
                            item.cvQuote(),
                            item.status(),
                            item.reasoning(),
                            null, null, null, null, false, false, null
                    );
                    evaluatedItemsMap.put(cid, converted);
                }
            }
        }

        // Fallback for any DB criteria in this batch that LLM missed or returned without matching ID
        for (CriteriaInstructionItem item : batchItems) {
            if (item.criteriaId() != null && !evaluatedItemsMap.containsKey(item.criteriaId())) {
                log.warn("[AssessmentLlmRunner] Fallback: criterion id {} ('{}') was omitted by LLM. Inserting default missing item.",
                        item.criteriaId(), item.name());
                AssessmentResponseDto.EvidenceItem fallbackItem = new AssessmentResponseDto.EvidenceItem(
                        item.criteriaId(),
                        item.name(),
                        parseLabelToImportance(item.label()),
                        item.name(),
                        null,
                        null,
                        "missing",
                        "Criterion evaluated as missing (not directly addressed in CV)",
                        null, null, null, null, false, false, null
                );
                evaluatedItemsMap.put(item.criteriaId(), fallbackItem);
            }
        }

        List<AssessmentResponseDto.EvidenceItem> evidenceItems = new ArrayList<>();
        for (AssessmentResponseDto.EvidenceItem item : evaluatedItemsMap.values()) {
            AssessmentResponseDto.EvidenceItem validated = item;
            if (evidenceGroundingValidator != null) {
                validated = evidenceGroundingValidator.validateAndApply(validated, fullCvMarkdown, groundingThreshold);
            }
            evidenceItems.add(validated);
        }

        List<AssessmentResponseDto.AdHocEvidenceItem> preferToHaveItems = new ArrayList<>();
        if (dto.preferToHaveEvidenceItems() != null) {
            for (AssessmentResponseDto.AdHocEvidenceItem item : dto.preferToHaveEvidenceItems()) {
                if (item != null && item.criteriaId() == null && item.criteriaName() != null && !item.criteriaName().isBlank()) {
                    // Ensure it's not a DB criterion name
                    String normName = item.criteriaName().trim().toLowerCase(Locale.ROOT);
                    if (!nameToIdMap.containsKey(normName)) {
                        preferToHaveItems.add(item);
                    }
                }
            }
        }

        Map<String, AssessmentResponseDto.AdHocEvidenceItem> deduplicatedAdHoc = new LinkedHashMap<>();
        for (AssessmentResponseDto.AdHocEvidenceItem item : preferToHaveItems) {
            deduplicatedAdHoc.putIfAbsent(item.criteriaName().trim().toLowerCase(Locale.ROOT), item);
        }

        return new BatchResult(evidenceItems, new ArrayList<>(deduplicatedAdHoc.values()));
    }

    private String parseLabelToImportance(String label) {
        if (label == null) return "REQUIRED";
        return switch (label.toUpperCase()) {
            case "[PREFERRED]" -> "PREFERRED";
            case "[NOT_IN_JD]" -> "NOT_APPLICABLE";
            default -> "REQUIRED";
        };
    }

    private List<AssessmentResponseDto.EvidenceItem> deduplicateEvidenceItems(List<AssessmentResponseDto.EvidenceItem> items) {
        if (items == null || items.isEmpty()) return List.of();
        Map<Long, AssessmentResponseDto.EvidenceItem> map = new LinkedHashMap<>();
        for (AssessmentResponseDto.EvidenceItem item : items) {
            if (item.criteriaId() != null) {
                map.put(item.criteriaId(), item);
            }
        }
        return new ArrayList<>(map.values());
    }

    private List<List<CriteriaInstructionItem>> partitionInstructionItems(List<CriteriaInstructionItem> list, int size) {
        List<List<CriteriaInstructionItem>> partitions = new ArrayList<>();
        for (int i = 0; i < list.size(); i += size) {
            partitions.add(list.subList(i, Math.min(i + size, list.size())));
        }
        return partitions;
    }

    private int getSystemSettingInt(String key, int defaultValue) {
        return systemSettingRepository != null ? systemSettingRepository.getInt(key, defaultValue) : defaultValue;
    }

    private double getSystemSettingDouble(String key, double defaultValue) {
        return systemSettingRepository != null ? systemSettingRepository.getDouble(key, defaultValue) : defaultValue;
    }

    private void sleepQuietly(long ms) {
        try { Thread.sleep(ms); } catch (InterruptedException e) { Thread.currentThread().interrupt(); }
    }
}
