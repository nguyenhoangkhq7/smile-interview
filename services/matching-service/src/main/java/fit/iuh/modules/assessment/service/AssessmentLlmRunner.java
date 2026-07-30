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
 * 3. Batched execution & self-consistency voting algorithm
 */
@Slf4j
@Service
public class AssessmentLlmRunner {

    private static final Map<String, String> JSON_RESPONSE_FORMAT = Map.of("type", "json_object");

    private static final int DEFAULT_BATCH_SIZE = 10;
    private static final int DEFAULT_SELF_CONSISTENCY_RUNS = 1;
    private static final double DEFAULT_GROUNDING_THRESHOLD = 0.75;
    private static final int DEFAULT_BATCH_CONCURRENCY = 3;


    private final AppProperties appProperties;
    private final WebClient llmWebClient;
    private final ObjectMapper objectMapper;
    private final Semaphore globalLlmSemaphore;
    private final SystemSettingRepository systemSettingRepository;
    private final EvidenceGroundingValidator evidenceGroundingValidator;

    @Autowired
    public AssessmentLlmRunner(
            AppProperties appProperties,
            @Qualifier("llmWebClient") WebClient llmWebClient,
            ObjectMapper objectMapper,
            SystemSettingRepository systemSettingRepository,
            EvidenceGroundingValidator evidenceGroundingValidator) {
        this.appProperties = appProperties;
        this.llmWebClient = llmWebClient;
        this.objectMapper = objectMapper;
        this.systemSettingRepository = systemSettingRepository;
        this.evidenceGroundingValidator = evidenceGroundingValidator;

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
        String targetModel = appProperties.getLlm().resolveModel(taskConfig);
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
            try {
                String responseBody = llmWebClient.post()
                        .uri(appProperties.getLlm().getChatPath())
                        .bodyValue(request)
                        .retrieve()
                        .bodyToMono(String.class)
                        .timeout(Duration.ofSeconds(timeoutSec))
                        .block();

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
                return response.getFirstChoiceContent().strip();

            } catch (WebClientResponseException e) {
                log.warn("[LlmRunner] OpenRouter HTTP {} Error: {}", e.getStatusCode(), e.getResponseBodyAsString());
                if (e.getStatusCode().value() == 400 && request.getResponseFormat() != null) {
                    log.warn("[LlmRunner] Model '{}' rejected response_format (400 Bad Request). Retrying without response_format...", targetModel);
                    request = LlmChatRequest.builder()
                            .model(targetModel)
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
                            item.needsManualReview()
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
                            TextSanitizationUtil.sanitizeLanguageText(item.reasoning())
                    ))
                    .collect(Collectors.toList());

            return new AssessmentResponseDto(sanitizedEvidence, sanitizedAdHoc);

        } catch (Exception e) {
            log.error("[AssessmentLlmRunner] JSON parse error for session {}: {}", sessionId, e.getMessage());
            throw new RuntimeException("Failed to parse LLM assessment JSON response", e);
        }
    }

    // =========================================================================
    // 3. BATCHED ASSESSMENT EXECUTION & SELF-CONSISTENCY VOTING
    // =========================================================================

    public record CriteriaInstructionItem(Long criteriaId, String name, String label, String promptInstruction) {}
    public record BatchResult(
            List<AssessmentResponseDto.EvidenceItem> evidenceItems,
            List<AssessmentResponseDto.AdHocEvidenceItem> preferToHaveEvidenceItems
    ) {}

    public AssessmentResponseDto runBatchedAssessmentWithSelfConsistencyClassified(
            String sessionId,
            String fullCvMarkdown,
            String fullJdMarkdown,
            ClassifiedCriteriaBundle bundle,
            boolean comprehensiveMode) {

        List<ClassifiedCriteriaBundle.ClassifiedCriteria> dbCriteria = bundle.dbCriteriaForMode(comprehensiveMode);
        List<ClassifiedCriteriaBundle.JdExtraCriteria> jdExtras = bundle.jdExtras();

        List<CriteriaInstructionItem> allItems = new ArrayList<>();
        for (var c : dbCriteria) {
            String label = switch (c.importance().toLowerCase(Locale.ROOT)) {
                case "required" -> "[REQUIRED]";
                case "preferred" -> "[PREFERRED]";
                case "not_in_jd" -> "[NOT_IN_JD]";
                default -> "[REQUIRED]";
            };
            allItems.add(new CriteriaInstructionItem(c.criteriaId(), c.criteriaName(), label, c.promptInstruction()));
        }
        for (var extra : jdExtras) {
            String label = "preferred".equalsIgnoreCase(extra.importance()) ? "[PREFERRED]" : "[REQUIRED]";
            allItems.add(new CriteriaInstructionItem(null, extra.name(), label, extra.promptInstruction()));
        }

        return executeBatchedSelfConsistency(sessionId, fullCvMarkdown, allItems);
    }

    public AssessmentResponseDto runBatchedAssessmentWithSelfConsistency(
            String sessionId,
            String fullCvMarkdown,
            String fullJdMarkdown,
            List<CriteriaWeightProjection> criteriaList) {

        List<CriteriaInstructionItem> allItems = new ArrayList<>();
        if (criteriaList != null) {
            for (CriteriaWeightProjection c : criteriaList) {
                String promptInst = (c.getLevelPromptInstruction() != null && !c.getLevelPromptInstruction().isBlank())
                        ? c.getLevelPromptInstruction() : c.getPromptInstruction();
                allItems.add(new CriteriaInstructionItem(c.getCriteriaId(), c.getCriteriaName(), "[REQUIRED]", promptInst));
            }
        }
        return executeBatchedSelfConsistency(sessionId, fullCvMarkdown, allItems);
    }

    private AssessmentResponseDto executeBatchedSelfConsistency(
            String sessionId,
            String fullCvMarkdown,
            List<CriteriaInstructionItem> allItems) {

        int maxBatchSize = getSystemSettingInt("CRITERIA_BATCH_SIZE", DEFAULT_BATCH_SIZE);
        if (maxBatchSize < 1) maxBatchSize = 1;
        int selfConsistencyRuns = getSystemSettingInt("SELF_CONSISTENCY_RUNS", DEFAULT_SELF_CONSISTENCY_RUNS);
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
                    return processBatchInstructionItemsWithSelfConsistency(
                            sessionId, fullCvMarkdown, batchItems, selfConsistencyRuns, groundingThreshold
                    );
                } catch (InterruptedException e) {
                    Thread.currentThread().interrupt();
                    throw new LlmApiException("Interrupted waiting for batch concurrency semaphore.", e);
                } finally {
                    if (acquired) batchSemaphore.release();
                }
            });
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

    private BatchResult processBatchInstructionItemsWithSelfConsistency(
            String sessionId,
            String fullCvMarkdown,
            List<CriteriaInstructionItem> batchItems,
            int selfConsistencyRuns,
            double groundingThreshold) {

        StringBuilder sb = new StringBuilder();
        for (CriteriaInstructionItem item : batchItems) {
            sb.append("- ").append(item.label());
            if (item.criteriaId() != null) {
                sb.append(" [ID: ").append(item.criteriaId()).append("]");
            }
            sb.append(" ").append(item.name()).append(": ")
                    .append(item.promptInstruction() != null ? item.promptInstruction() : "")
                    .append("\n");
        }
        String criteriaInstructions = sb.toString().strip();

        String cvToSupply = fullCvMarkdown;

        String systemPrompt = AssessmentPrompts.buildAssessmentSystemPrompt();
        String userPrompt = AssessmentPrompts.buildAssessmentUserPrompt(cvToSupply, criteriaInstructions);

        var taskConfig = appProperties.getLlm().getTasks().getAssessment();
        int totalRuns = Math.max(1, selfConsistencyRuns);

        List<AssessmentResponseDto> runDtos = new ArrayList<>();
        for (int run = 1; run <= totalRuns; run++) {
            try {
                String llmResponse = callLlmBlockingWithSemaphore(taskConfig, systemPrompt, userPrompt);
                AssessmentResponseDto dto = parseAssessmentDto(sessionId, llmResponse);
                if (dto != null) runDtos.add(dto);
            } catch (Exception e) {
                log.error("[AssessmentLlmRunner] Run {}/{} failed for batch: {}", run, totalRuns, e.getMessage());
            }
        }

        if (runDtos.isEmpty()) {
            throw new LlmApiException("All self-consistency runs failed for session " + sessionId);
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

        List<AssessmentResponseDto.EvidenceItem> votedEvidenceItems = new ArrayList<>();
        Map<Long, List<AssessmentResponseDto.EvidenceItem>> groupedById = new LinkedHashMap<>();

        for (AssessmentResponseDto dto : runDtos) {
            if (dto.mustHaveEvidenceItems() != null) {
                for (AssessmentResponseDto.EvidenceItem item : dto.mustHaveEvidenceItems()) {
                    Long cid = item.criteriaId();
                    if (cid == null && item.criteriaName() != null) {
                        cid = nameToIdMap.get(item.criteriaName().trim().toLowerCase(Locale.ROOT));
                    }
                    if (cid != null) {
                        AssessmentResponseDto.EvidenceItem resolved = new AssessmentResponseDto.EvidenceItem(
                                cid, item.criteriaName(), item.importance(), item.jdRequirement(),
                                item.cvEvidence(), item.cvQuote(), item.status(), item.reasoning(),
                                item.weightUsed(), item.scoreContribution(), item.groundingScore(),
                                item.confidenceVotes(), item.lowConfidence(), item.needsManualReview()
                        );
                        groupedById.computeIfAbsent(cid, k -> new ArrayList<>()).add(resolved);
                    }
                }
            }
            if (dto.preferToHaveEvidenceItems() != null) {
                for (AssessmentResponseDto.AdHocEvidenceItem item : dto.preferToHaveEvidenceItems()) {
                    Long cid = item.criteriaId();
                    if (cid == null && item.criteriaName() != null) {
                        cid = nameToIdMap.get(item.criteriaName().trim().toLowerCase(Locale.ROOT));
                    }
                    if (cid != null) {
                        AssessmentResponseDto.EvidenceItem converted = new AssessmentResponseDto.EvidenceItem(
                                cid,
                                item.criteriaName(),
                                item.importance() != null ? item.importance() : "PREFERRED",
                                item.jdRequirement(),
                                item.cvEvidence(),
                                item.cvQuote(),
                                item.status(),
                                item.reasoning(),
                                null, null, null, null, null, null
                        );
                        groupedById.computeIfAbsent(cid, k -> new ArrayList<>()).add(converted);
                    }
                }
            }
        }

        // Fallback for any DB criteria in this batch that LLM missed or returned without matching ID
        for (CriteriaInstructionItem item : batchItems) {
            if (item.criteriaId() != null && !groupedById.containsKey(item.criteriaId())) {
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
                        null, null, null, null, false, false
                );
                groupedById.put(item.criteriaId(), List.of(fallbackItem));
            }
        }

        for (Map.Entry<Long, List<AssessmentResponseDto.EvidenceItem>> entry : groupedById.entrySet()) {
            Long criteriaId = entry.getKey();
            List<AssessmentResponseDto.EvidenceItem> votes = entry.getValue();

            Map<String, Long> statusCounts = votes.stream()
                    .collect(Collectors.groupingBy(i -> i.status() != null ? i.status().toLowerCase() : "missing", Collectors.counting()));

            String winningStatus = statusCounts.entrySet().stream()
                    .max(Map.Entry.comparingByValue())
                    .map(Map.Entry::getKey)
                    .orElse("missing");

            long winningVotes = statusCounts.getOrDefault(winningStatus, 0L);
            int confidenceCount = (int) winningVotes;
            boolean lowConfidence = totalRuns > 1 && confidenceCount <= (totalRuns / 2);
            boolean needsManualReview = lowConfidence;

            AssessmentResponseDto.EvidenceItem sample = votes.stream()
                    .filter(i -> i.status() != null && i.status().equalsIgnoreCase(winningStatus))
                    .findFirst()
                    .orElse(votes.get(0));

            String rawLabel = labelMap.getOrDefault(criteriaId, "[REQUIRED]");
            String importance = parseLabelToImportance(rawLabel);

            Map<String, Integer> confidenceVotesMap = statusCounts.entrySet().stream()
                    .collect(Collectors.toMap(Map.Entry::getKey, e -> e.getValue().intValue()));

            AssessmentResponseDto.EvidenceItem aggregated = new AssessmentResponseDto.EvidenceItem(
                    criteriaId,
                    sample.criteriaName(),
                    importance,
                    sample.jdRequirement(),
                    sample.cvEvidence(),
                    sample.cvQuote(),
                    winningStatus,
                    sample.reasoning(),
                    sample.weightUsed(),
                    sample.scoreContribution(),
                    sample.groundingScore(),
                    confidenceVotesMap,
                    lowConfidence,
                    needsManualReview
            );

            if (evidenceGroundingValidator != null) {
                aggregated = evidenceGroundingValidator.validateAndApply(aggregated, fullCvMarkdown, groundingThreshold);
            }
            votedEvidenceItems.add(aggregated);
        }

        List<AssessmentResponseDto.AdHocEvidenceItem> preferToHaveItems = new ArrayList<>();
        for (AssessmentResponseDto dto : runDtos) {
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
        }

        Map<String, AssessmentResponseDto.AdHocEvidenceItem> deduplicatedAdHoc = new LinkedHashMap<>();
        for (AssessmentResponseDto.AdHocEvidenceItem item : preferToHaveItems) {
            deduplicatedAdHoc.putIfAbsent(item.criteriaName().trim().toLowerCase(), item);
        }

        return new BatchResult(votedEvidenceItems, new ArrayList<>(deduplicatedAdHoc.values()));
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
