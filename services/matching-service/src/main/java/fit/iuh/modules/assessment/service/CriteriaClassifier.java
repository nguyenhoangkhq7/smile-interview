package fit.iuh.modules.assessment.service;

import com.fasterxml.jackson.databind.ObjectMapper;
import fit.iuh.config.AppProperties;
import fit.iuh.dto.chat.LlmChatRequest;
import fit.iuh.dto.chat.LlmChatResponse;
import fit.iuh.modules.assessment.dto.ClassifiedCriteriaBundle;
import fit.iuh.modules.assessment.dto.ClassifiedCriteriaBundle.ClassifiedCriteria;
import fit.iuh.modules.assessment.dto.ClassifiedCriteriaBundle.JdExtraCriteria;
import fit.iuh.modules.assessment.entity.JobCategory;
import fit.iuh.modules.assessment.entity.SeniorityLevel;
import fit.iuh.modules.assessment.prompt.AssessmentPrompts;
import fit.iuh.modules.assessment.util.TextSanitizationUtil;
import fit.iuh.modules.rulengine.repository.JobCriteriaRepository;
import fit.iuh.modules.rulengine.repository.JobCriteriaRepository.CriteriaWeightProjection;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;
import org.springframework.web.reactive.function.client.WebClient;
import org.springframework.web.reactive.function.client.WebClientResponseException;

import java.time.Duration;
import java.util.*;
import java.util.concurrent.CompletableFuture;
import java.util.concurrent.Executor;
import java.util.stream.Collectors;

@Slf4j
@Service
@RequiredArgsConstructor
public class CriteriaClassifier {

    private static final Map<String, String> JSON_RESPONSE_FORMAT = Map.of("type", "json_object");
    private static final int MAX_CLASSIFIER_BATCH_SIZE = 15;

    private final AppProperties appProperties;
    private final WebClient llmWebClient;
    private final ObjectMapper objectMapper;
    private final JobCriteriaRepository jobCriteriaRepository;
    private final Executor assessmentTaskExecutor;

    public record CriteriaFilterDebugDetail(
            Long criteriaId,
            String criteriaName,
            boolean isMatched,
            String reason
    ) {}

    public record ConsolidatedPhase1Output(
            fit.iuh.modules.assessment.entity.JobCategory category,
            List<fit.iuh.modules.assessment.entity.SeniorityLevel> acceptedLevels,
            List<fit.iuh.modules.assessment.gate.EligibilityGateService.GateCheckDto> gateRequirements,
            ClassifiedCriteriaBundle criteriaBundle
    ) {}

    public List<CriteriaWeightProjection> loadAndFilterCriteria(
            String categoryName,
            String seniorityLevelName,
            String sessionId,
            String jdText,
            boolean isJdTextExtracted) {

        List<CriteriaWeightProjection> allCriteria = loadCriteriaWithFallback(categoryName, seniorityLevelName);
        if (jdText == null || jdText.isBlank()) {
            return allCriteria;
        }

        List<CriteriaWeightProjection> filtered = preFilterCriteriaForJd(sessionId, jdText, allCriteria);
        log.info("[CriteriaClassifier] Pre-filtered criteria: {}/{} kept for category='{}', level='{}'",
                filtered.size(), allCriteria.size(), categoryName, seniorityLevelName);
        return filtered;
    }

    public List<CriteriaWeightProjection> loadCriteriaWithFallback(String categoryName, String seniorityLevelName) {
        List<CriteriaWeightProjection> exact = jobCriteriaRepository.findCriteriaTreeByCategory(categoryName, seniorityLevelName);
        if (!exact.isEmpty()) {
            return deduplicateCriteria(exact);
        }

        log.warn("[CriteriaClassifier] No criteria found for category='{}', level='{}'. Falling back to MID level.",
                categoryName, seniorityLevelName);
        List<CriteriaWeightProjection> midFallback = jobCriteriaRepository.findCriteriaTreeByCategory(categoryName, "MID");
        if (!midFallback.isEmpty()) {
            return deduplicateCriteria(midFallback);
        }

        log.warn("[CriteriaClassifier] No criteria found for category='{}' at MID level. Falling back to default SOFTWARE_ENGINEERING category.", categoryName);
        List<CriteriaWeightProjection> defaultCat = jobCriteriaRepository.findCriteriaTreeByCategory("SOFTWARE_ENGINEERING", seniorityLevelName);
        return deduplicateCriteria(defaultCat);
    }

    private List<CriteriaWeightProjection> deduplicateCriteria(List<CriteriaWeightProjection> list) {
        if (list == null || list.isEmpty()) return List.of();
        Map<Long, CriteriaWeightProjection> map = new LinkedHashMap<>();
        for (CriteriaWeightProjection c : list) {
            map.putIfAbsent(c.getCriteriaId(), c);
        }
        return new ArrayList<>(map.values());
    }

    private List<CriteriaWeightProjection> preFilterCriteriaForJd(String sessionId, String jdText, List<CriteriaWeightProjection> allCriteria) {
        if (allCriteria == null || allCriteria.isEmpty()) return List.of();
        try {
            List<CriteriaFilterDebugDetail> debugList = executeLlmCriteriaPreFiltering(jdText, allCriteria);
            Set<Long> matchedIds = debugList.stream()
                    .filter(CriteriaFilterDebugDetail::isMatched)
                    .map(CriteriaFilterDebugDetail::criteriaId)
                    .collect(Collectors.toSet());

            List<CriteriaWeightProjection> result = allCriteria.stream()
                    .filter(c -> matchedIds.contains(c.getCriteriaId()))
                    .collect(Collectors.toList());

            return result.isEmpty() ? allCriteria : result;
        } catch (Exception e) {
            log.warn("[CriteriaClassifier] Pre-filtering failed, retaining all criteria: {}", e.getMessage());
            return allCriteria;
        }
    }

    public List<CriteriaFilterDebugDetail> debugFilterCriteriaDetails(
            String categoryName, String seniorityLevelName, String jdText, double threshold) {
        List<CriteriaWeightProjection> allCriteria = loadCriteriaWithFallback(categoryName, seniorityLevelName);
        return executeLlmCriteriaPreFiltering(jdText, allCriteria);
    }

    private List<CriteriaFilterDebugDetail> executeLlmCriteriaPreFiltering(String jdMarkdown, List<CriteriaWeightProjection> allCriteria) {
        if (allCriteria == null || allCriteria.isEmpty()) return List.of();

        var taskConfig = appProperties.getLlm().getTasks().getCriteriaClassification();
        List<String> models = appProperties.getLlm().resolveModels(taskConfig);
        String model = models.isEmpty() ? appProperties.getLlm().resolveModel(taskConfig) : models.get(0);
        int maxTokens = appProperties.getLlm().resolveMaxTokens(taskConfig);
        Duration timeout = Duration.ofSeconds(appProperties.getLlm().resolveTimeoutSeconds(taskConfig));

        StringBuilder criteriaListPrompt = new StringBuilder();
        for (CriteriaWeightProjection c : allCriteria) {
            criteriaListPrompt.append(String.format("- [ID: %d] %s: %s\n",
                    c.getCriteriaId(), c.getCriteriaName(), resolveEffectivePromptInstruction(c)));
        }

        String sysPrompt = AssessmentPrompts.SYSTEM_PROMPT_PRE_FILTER_CRITERIA;
        String userPrompt = AssessmentPrompts.buildCriteriaPreFilterUserPrompt(jdMarkdown, criteriaListPrompt.toString());

        LlmChatRequest request = LlmChatRequest.builder()
                .model(model)
                .models(models)
                .maxTokens(maxTokens)
                .temperature(0.1)
                .stream(false)
                .responseFormat(JSON_RESPONSE_FORMAT)
                .messages(List.of(
                        LlmChatRequest.Message.system(sysPrompt),
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
                            log.info("[LLM METRICS] Task: PreFilterCriteria | Model: {} | Duration: {} ms ({} s) | Prompt Tokens: {} | Completion Tokens: {} | Total Tokens: {}",
                                    res.getModel() != null ? res.getModel() : model,
                                    durationMs,
                                    String.format("%.2f", durationMs / 1000.0),
                                    usage.getPromptTokens(),
                                    usage.getCompletionTokens(),
                                    usage.getTotalTokens());
                        } else {
                            log.info("[LLM METRICS] Task: PreFilterCriteria | Model: {} | Duration: {} ms ({} s) | Usage: N/A",
                                    res.getModel() != null ? res.getModel() : model,
                                    durationMs,
                                    String.format("%.2f", durationMs / 1000.0));
                        }
                        return parseLlmFilterJson(res.getFirstChoiceContent(), allCriteria);
                    }
                }
            } catch (WebClientResponseException e) {
                log.warn("[CriteriaClassifier] OpenRouter HTTP {} Error: {}", e.getStatusCode(), e.getResponseBodyAsString());
                if (e.getStatusCode().value() == 400 && request.getResponseFormat() != null) {
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
                log.warn("[CriteriaClassifier] Pre-filtering LLM call error: {}", e.getMessage());
                break;
            }
        }

        return allCriteria.stream()
                .map(c -> new CriteriaFilterDebugDetail(c.getCriteriaId(), c.getCriteriaName(), true, "Fallback: Pre-filtering failed"))
                .collect(Collectors.toList());
    }

    private List<CriteriaFilterDebugDetail> parseLlmFilterJson(String rawJson, List<CriteriaWeightProjection> allCriteria) {
        String cleanJson = TextSanitizationUtil.extractCleanJson(rawJson);
        Map<Long, CriteriaFilterDebugDetail> resultMap = new HashMap<>();

        try {
            var node = objectMapper.readTree(cleanJson);
            if (node.has("evaluations") && node.get("evaluations").isArray()) {
                for (var item : node.get("evaluations")) {
                    Long id = item.has("criteria_id") ? item.get("criteria_id").asLong() : null;
                    boolean isMatched = (item.has("matched") && item.get("matched").asBoolean()) ||
                            (item.has("is_matched") && item.get("is_matched").asBoolean());
                    String reason = item.has("reason") ? item.get("reason").asText() : "";
                    if (id != null) {
                        resultMap.put(id, new CriteriaFilterDebugDetail(id, "", isMatched, reason));
                    }
                }
            }
        } catch (Exception e) {
            log.warn("[CriteriaClassifier] JSON parse error for pre-filter response: {}", e.getMessage());
        }

        List<CriteriaFilterDebugDetail> finalDetails = new ArrayList<>();
        for (CriteriaWeightProjection c : allCriteria) {
            Long id = c.getCriteriaId();
            if (resultMap.containsKey(id)) {
                CriteriaFilterDebugDetail d = resultMap.get(id);
                finalDetails.add(new CriteriaFilterDebugDetail(id, c.getCriteriaName(), d.isMatched(), d.reason()));
            } else {
                finalDetails.add(new CriteriaFilterDebugDetail(id, c.getCriteriaName(), true, "Fallback: Default included"));
            }
        }
        return finalDetails;
    }

    public ClassifiedCriteriaBundle classifyCriteria(String jdMarkdown, List<CriteriaWeightProjection> dbCriteria, String seniorityLevel) {
        if (dbCriteria == null || dbCriteria.isEmpty()) {
            return new ClassifiedCriteriaBundle(List.of(), List.of());
        }

        List<List<CriteriaWeightProjection>> batches = partitionList(dbCriteria, MAX_CLASSIFIER_BATCH_SIZE);
        List<ClassifiedCriteria> allClassified = Collections.synchronizedList(new ArrayList<>());
        List<JdExtraCriteria> allExtras = Collections.synchronizedList(new ArrayList<>());

        List<CompletableFuture<Void>> futures = new ArrayList<>();
        for (int i = 0; i < batches.size(); i++) {
            final List<CriteriaWeightProjection> batch = batches.get(i);
            final int batchIndex = i + 1;
            final int totalBatches = batches.size();

            futures.add(CompletableFuture.runAsync(() ->
                    classifyBatch(batch, batchIndex, totalBatches, jdMarkdown, seniorityLevel, allClassified, allExtras),
                    assessmentTaskExecutor
            ));
        }

        CompletableFuture.allOf(futures.toArray(new CompletableFuture[0])).join();

        Set<String> activeDbNamesLower = allClassified.stream()
                .filter(c -> !"not_applicable".equalsIgnoreCase(c.importance()))
                .map(c -> c.criteriaName().toLowerCase().trim())
                .collect(Collectors.toSet());

        List<JdExtraCriteria> filteredExtras = filterAndDeduplicateJdExtras(allExtras, activeDbNamesLower);
        return new ClassifiedCriteriaBundle(new ArrayList<>(allClassified), filteredExtras);
    }

    private List<JdExtraCriteria> filterAndDeduplicateJdExtras(List<JdExtraCriteria> allExtras, Set<String> activeDbNamesLower) {
        if (allExtras == null || allExtras.isEmpty()) return List.of();
        Map<String, JdExtraCriteria> uniqueExtras = new LinkedHashMap<>();

        for (JdExtraCriteria extra : allExtras) {
            if (extra == null || extra.name() == null || extra.name().isBlank()) continue;
            String extraNameLower = extra.name().trim().toLowerCase();

            if (isOverlappingWithDbCriteria(extraNameLower, activeDbNamesLower)) {
                log.info("[CriteriaClassifier] Dropping JD Extra '{}' due to overlap with active DB criteria.", extra.name());
                continue;
            }

            if (!uniqueExtras.containsKey(extraNameLower)) {
                uniqueExtras.put(extraNameLower, extra);
            } else {
                JdExtraCriteria existing = uniqueExtras.get(extraNameLower);
                if ("required".equalsIgnoreCase(extra.importance()) && !"required".equalsIgnoreCase(existing.importance())) {
                    uniqueExtras.put(extraNameLower, extra);
                }
            }
        }
        return new ArrayList<>(uniqueExtras.values());
    }

    private boolean isOverlappingWithDbCriteria(String extraNameLower, Set<String> activeDbNamesLower) {
        if (activeDbNamesLower.contains(extraNameLower)) return true;
        for (String dbName : activeDbNamesLower) {
            if (extraNameLower.contains(dbName) || dbName.contains(extraNameLower)) {
                return true;
            }
            if (isSemanticDuplicate(extraNameLower, dbName)) {
                return true;
            }
        }
        return false;
    }

    private boolean isSemanticDuplicate(String nameA, String nameB) {
        if (nameA.contains("cloud") && nameB.contains("cloud")) return true;
        if (nameA.contains("database") && (nameB.contains("database") || nameB.contains("sql") || nameB.contains("nosql"))) return true;
        if (nameB.contains("database") && (nameA.contains("database") || nameA.contains("sql") || nameA.contains("nosql"))) return true;
        return false;
    }

    private String resolveEffectivePromptInstruction(CriteriaWeightProjection c) {
        String levelInst = c.getLevelPromptInstruction();
        return (levelInst != null && !levelInst.isBlank()) ? levelInst : c.getPromptInstruction();
    }

    private void classifyBatch(
            List<CriteriaWeightProjection> batch,
            int batchIndex,
            int totalBatches,
            String jdMarkdown,
            String seniorityLevel,
            List<ClassifiedCriteria> classifiedResults,
            List<JdExtraCriteria> extraResults) {

        var taskConfig = appProperties.getLlm().getTasks().getCriteriaClassification();
        List<String> models = appProperties.getLlm().resolveModels(taskConfig);
        String model = models.isEmpty() ? appProperties.getLlm().resolveModel(taskConfig) : models.get(0);
        int maxTokens = appProperties.getLlm().resolveMaxTokens(taskConfig);
        Duration timeout = Duration.ofSeconds(appProperties.getLlm().resolveTimeoutSeconds(taskConfig));

        StringBuilder criteriaBlock = new StringBuilder();
        Map<Long, CriteriaWeightProjection> batchMap = new HashMap<>();
        for (CriteriaWeightProjection c : batch) {
            criteriaBlock.append(String.format("- [ID: %d] %s: %s\n",
                    c.getCriteriaId(), c.getCriteriaName(), resolveEffectivePromptInstruction(c)));
            batchMap.put(c.getCriteriaId(), c);
        }

        String sysPrompt = AssessmentPrompts.SYSTEM_PROMPT_CRITERIA_CLASSIFICATION;
        String userPrompt = AssessmentPrompts.buildClassifierUserPrompt(jdMarkdown, criteriaBlock.toString(), seniorityLevel);

        LlmChatRequest request = LlmChatRequest.builder()
                .model(model)
                .models(models)
                .maxTokens(maxTokens)
                .temperature(0.1)
                .stream(false)
                .responseFormat(JSON_RESPONSE_FORMAT)
                .messages(List.of(
                        LlmChatRequest.Message.system(sysPrompt),
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
                            log.info("[LLM METRICS] Task: ClassifyBatch ({}/{}) | Model: {} | Duration: {} ms ({} s) | Prompt Tokens: {} | Completion Tokens: {} | Total Tokens: {}",
                                    batchIndex, totalBatches,
                                    res.getModel() != null ? res.getModel() : model,
                                    durationMs,
                                    String.format("%.2f", durationMs / 1000.0),
                                    usage.getPromptTokens(),
                                    usage.getCompletionTokens(),
                                    usage.getTotalTokens());
                        } else {
                            log.info("[LLM METRICS] Task: ClassifyBatch ({}/{}) | Model: {} | Duration: {} ms ({} s) | Usage: N/A",
                                    batchIndex, totalBatches,
                                    res.getModel() != null ? res.getModel() : model,
                                    durationMs,
                                    String.format("%.2f", durationMs / 1000.0));
                        }
                        boolean parsed = parseClassifierJson(res.getFirstChoiceContent(), batchMap, classifiedResults, extraResults);
                        if (parsed) return;
                    }
                }
            } catch (WebClientResponseException e) {
                log.warn("[CriteriaClassifier] OpenRouter HTTP {} Error: {}", e.getStatusCode(), e.getResponseBodyAsString());
                if (e.getStatusCode().value() == 400 && request.getResponseFormat() != null) {
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
                log.warn("[CriteriaClassifier] Error classifying batch {}/{}: {}", batchIndex, totalBatches, e.getMessage());
                break;
            }
        }

        // Fallback for batch
        for (CriteriaWeightProjection c : batch) {
            classifiedResults.add(new ClassifiedCriteria(
                    c.getCriteriaId(), c.getCriteriaName(), resolveEffectivePromptInstruction(c), c.getWeightPercentage(), "preferred"
            ));
        }
    }

    private boolean parseClassifierJson(
            String rawJson,
            Map<Long, CriteriaWeightProjection> batchMap,
            List<ClassifiedCriteria> classifiedResults,
            List<JdExtraCriteria> extraResults) {

        String cleanJson = TextSanitizationUtil.extractCleanJson(rawJson);
        try {
            var node = objectMapper.readTree(cleanJson);
            if (node.has("classified") && node.get("classified").isArray()) {
                Set<Long> processedIds = new HashSet<>();
                for (var item : node.get("classified")) {
                    Long id = item.has("criteria_id") ? item.get("criteria_id").asLong() : null;
                    String importance = item.has("importance") ? item.get("importance").asText() : "preferred";
                    if (id != null && batchMap.containsKey(id)) {
                        CriteriaWeightProjection c = batchMap.get(id);
                        classifiedResults.add(new ClassifiedCriteria(
                                c.getCriteriaId(), c.getCriteriaName(), resolveEffectivePromptInstruction(c), c.getWeightPercentage(), importance
                        ));
                        processedIds.add(id);
                    }
                }
                for (CriteriaWeightProjection c : batchMap.values()) {
                    if (!processedIds.contains(c.getCriteriaId())) {
                        classifiedResults.add(new ClassifiedCriteria(
                                c.getCriteriaId(), c.getCriteriaName(), resolveEffectivePromptInstruction(c), c.getWeightPercentage(), "preferred"
                        ));
                    }
                }
            } else {
                log.warn("[CriteriaClassifier] Missing 'classified' array in: {}", cleanJson);
                return false;
            }

            if (extraResults != null && node.has("jd_extras") && node.get("jd_extras").isArray()) {
                for (var extra : node.get("jd_extras")) {
                    String name = extra.has("name") ? extra.get("name").asText() : "";
                    String imp = extra.has("importance") ? extra.get("importance").asText() : "preferred";
                    String promptInst = extra.has("prompt_instruction") ? extra.get("prompt_instruction").asText() : "";
                    if (!name.isBlank()) {
                        extraResults.add(new JdExtraCriteria(name, imp, promptInst));
                    }
                }
            }
            return true;
        } catch (Exception e) {
            log.warn("[CriteriaClassifier] Parse error: {}", e.getMessage());
            return false;
        }
    }

    public ConsolidatedPhase1Output classifyConsolidatedSinglePass(String jdMarkdown, List<CriteriaWeightProjection> dbCriteria) {
        if (dbCriteria == null || dbCriteria.isEmpty()) {
            dbCriteria = loadCriteriaWithFallback("SOFTWARE_ENGINEERING", "MID");
        }

        var taskConfig = appProperties.getLlm().getTasks().getCriteriaClassification();
        List<String> models = appProperties.getLlm().resolveModels(taskConfig);
        String model = models.isEmpty() ? appProperties.getLlm().resolveModel(taskConfig) : models.get(0);
        int maxTokens = appProperties.getLlm().resolveMaxTokens(taskConfig);
        Duration timeout = Duration.ofSeconds(appProperties.getLlm().resolveTimeoutSeconds(taskConfig));

        StringBuilder criteriaBlock = new StringBuilder();
        Map<Long, CriteriaWeightProjection> criteriaMap = new HashMap<>();
        for (CriteriaWeightProjection c : dbCriteria) {
            criteriaBlock.append(String.format("- [ID: %d] %s: %s\n",
                    c.getCriteriaId(), c.getCriteriaName(), resolveEffectivePromptInstruction(c)));
            criteriaMap.put(c.getCriteriaId(), c);
        }

        String sysPrompt = AssessmentPrompts.SYSTEM_PROMPT_CONSOLIDATED_JD_PREPARATION;
        String userPrompt = AssessmentPrompts.buildConsolidatedJdPreparationPrompt(jdMarkdown, criteriaBlock.toString());

        LlmChatRequest request = LlmChatRequest.builder()
                .model(model)
                .models(models)
                .maxTokens(maxTokens)
                .temperature(0.1)
                .stream(false)
                .responseFormat(JSON_RESPONSE_FORMAT)
                .messages(List.of(
                        LlmChatRequest.Message.system(sysPrompt),
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
                            log.info("[LLM METRICS] Task: ConsolidatedPhase1Preparation | Model: {} | Duration: {} ms ({} s) | Prompt Tokens: {} | Completion Tokens: {} | Total Tokens: {}",
                                    res.getModel() != null ? res.getModel() : model,
                                    durationMs,
                                    String.format("%.2f", durationMs / 1000.0),
                                    usage.getPromptTokens(),
                                    usage.getCompletionTokens(),
                                    usage.getTotalTokens());
                        } else {
                            log.info("[LLM METRICS] Task: ConsolidatedPhase1Preparation | Model: {} | Duration: {} ms ({} s) | Usage: N/A",
                                    res.getModel() != null ? res.getModel() : model,
                                    durationMs,
                                    String.format("%.2f", durationMs / 1000.0));
                        }
                        ConsolidatedPhase1Output parsed = parseConsolidatedJson(res.getFirstChoiceContent(), criteriaMap);
                        if (parsed != null) {
                            return parsed;
                        }
                    }
                }
            } catch (WebClientResponseException e) {
                log.warn("[CriteriaClassifier] OpenRouter HTTP {} Error in consolidated single-pass: {}", e.getStatusCode(), e.getResponseBodyAsString());
                if (e.getStatusCode().value() == 400 && request.getResponseFormat() != null) {
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
                log.warn("[CriteriaClassifier] Consolidated single-pass attempt {} failed: {}", attempt, e.getMessage());
                break;
            }
        }

        return null;
    }

    private ConsolidatedPhase1Output parseConsolidatedJson(String rawJson, Map<Long, CriteriaWeightProjection> criteriaMap) {
        String cleanJson = TextSanitizationUtil.extractCleanJson(rawJson);
        try {
            var node = objectMapper.readTree(cleanJson);

            // 1. Category
            String catStr = node.has("category") ? node.get("category").asText() : "SOFTWARE_ENGINEERING";
            fit.iuh.modules.assessment.entity.JobCategory category = parseJobCategoryEnum(catStr);

            // 2. Levels
            List<fit.iuh.modules.assessment.entity.SeniorityLevel> levels = new ArrayList<>();
            if (node.has("accepted_levels") && node.get("accepted_levels").isArray()) {
                for (var lNode : node.get("accepted_levels")) {
                    levels.add(parseSeniorityLevelEnum(lNode.asText()));
                }
            }
            if (levels.isEmpty()) {
                levels.add(fit.iuh.modules.assessment.entity.SeniorityLevel.MID);
            }

            // 3. Gate Requirements
            List<fit.iuh.modules.assessment.gate.EligibilityGateService.GateCheckDto> gates = new ArrayList<>();
            if (node.has("gate_requirements") && node.get("gate_requirements").isArray()) {
                for (var gNode : node.get("gate_requirements")) {
                    var gateDto = new fit.iuh.modules.assessment.gate.EligibilityGateService.GateCheckDto();
                    gateDto.setCriteriaName(gNode.has("criteria_name") ? gNode.get("criteria_name").asText() : "");
                    gateDto.setImportance(gNode.has("importance") ? gNode.get("importance").asText() : "REQUIRED");
                    gateDto.setRequiredValue(gNode.has("required_value") ? gNode.get("required_value").asText() : "");
                    gateDto.setActualValue(gNode.has("actual_value") ? gNode.get("actual_value").asText() : null);
                    gateDto.setStatus(gNode.has("status") ? gNode.get("status").asText() : null);
                    gates.add(gateDto);
                }
            }

            // 4. Classified Criteria
            List<ClassifiedCriteria> classifiedList = new ArrayList<>();
            Set<Long> processedIds = new HashSet<>();
            if (node.has("classified") && node.get("classified").isArray()) {
                for (var cNode : node.get("classified")) {
                    Long cid = cNode.has("criteria_id") ? cNode.get("criteria_id").asLong() : null;
                    String importance = cNode.has("importance") ? cNode.get("importance").asText() : "preferred";
                    if (cid != null && criteriaMap.containsKey(cid)) {
                        CriteriaWeightProjection c = criteriaMap.get(cid);
                        classifiedList.add(new ClassifiedCriteria(
                                c.getCriteriaId(), c.getCriteriaName(), resolveEffectivePromptInstruction(c), c.getWeightPercentage(), importance
                        ));
                        processedIds.add(cid);
                    }
                }
            }
            for (CriteriaWeightProjection c : criteriaMap.values()) {
                if (!processedIds.contains(c.getCriteriaId())) {
                    classifiedList.add(new ClassifiedCriteria(
                            c.getCriteriaId(), c.getCriteriaName(), resolveEffectivePromptInstruction(c), c.getWeightPercentage(), "preferred"
                    ));
                }
            }

            // 5. Extras
            List<JdExtraCriteria> extraList = new ArrayList<>();
            if (node.has("jd_extras") && node.get("jd_extras").isArray()) {
                for (var eNode : node.get("jd_extras")) {
                    String name = eNode.has("name") ? eNode.get("name").asText() : "";
                    String imp = eNode.has("importance") ? eNode.get("importance").asText() : "preferred";
                    String promptInst = eNode.has("prompt_instruction") ? eNode.get("prompt_instruction").asText() : "";
                    if (!name.isBlank()) {
                        extraList.add(new JdExtraCriteria(name, imp, promptInst));
                    }
                }
            }

            Set<String> activeDbNamesLower = classifiedList.stream()
                    .filter(c -> !"not_applicable".equalsIgnoreCase(c.importance()))
                    .map(c -> c.criteriaName().toLowerCase(Locale.ROOT).trim())
                    .collect(Collectors.toSet());
            List<JdExtraCriteria> filteredExtras = filterAndDeduplicateJdExtras(extraList, activeDbNamesLower);

            return new ConsolidatedPhase1Output(category, levels, gates, new ClassifiedCriteriaBundle(classifiedList, filteredExtras));
        } catch (Exception e) {
            log.warn("[CriteriaClassifier] Failed to parse consolidated JSON: {}", e.getMessage());
            return null;
        }
    }

    private JobCategory parseJobCategoryEnum(String value) {
        if (value == null || value.isBlank()) return JobCategory.SOFTWARE_ENGINEERING;
        try {
            return JobCategory.valueOf(value.toUpperCase(Locale.ROOT).trim());
        } catch (IllegalArgumentException e) {
            return JobCategory.SOFTWARE_ENGINEERING;
        }
    }

    private SeniorityLevel parseSeniorityLevelEnum(String value) {
        if (value == null || value.isBlank()) return SeniorityLevel.MID;
        try {
            return SeniorityLevel.valueOf(value.toUpperCase(Locale.ROOT).trim());
        } catch (IllegalArgumentException e) {
            return SeniorityLevel.MID;
        }
    }

    private static final Set<String> STOPWORDS_CLASSIFIER = Set.of(
            "the", "and", "for", "with", "evaluate", "understanding", "experience", "knowledge", "ability",
            "proficiency", "skills", "practices", "fundamentals", "basics", "design", "handling", "usage",
            "using", "used", "must", "should", "candidate", "status", "matched", "weak", "missing"
    );

    private String determineRealignedImportance(CriteriaWeightProjection c, String cNameLower, String jdLower, Set<String> jdExtraNames) {
        if (jdExtraNames.contains(cNameLower) || fit.iuh.modules.assessment.util.TextSanitizationUtil.containsSkillTerm(jdLower, cNameLower)) {
            return "required";
        }

        // Sub-term check: e.g. "State Management (Redux/Zustand)" -> ["state management", "redux", "zustand"]
        if (cNameLower.contains("(") && cNameLower.contains(")")) {
            int openIdx = cNameLower.indexOf('(');
            int closeIdx = cNameLower.indexOf(')', openIdx);
            if (openIdx > 0 && closeIdx > openIdx) {
                String prefix = cNameLower.substring(0, openIdx).trim();
                String inside = cNameLower.substring(openIdx + 1, closeIdx).trim();
                if (prefix.length() >= 4 && fit.iuh.modules.assessment.util.TextSanitizationUtil.containsSkillTerm(jdLower, prefix)) {
                    return "required";
                }
                for (String part : inside.split("[/,]")) {
                    String pt = part.trim();
                    if (pt.length() >= 2 && fit.iuh.modules.assessment.util.TextSanitizationUtil.containsSkillTerm(jdLower, pt)) {
                        return "required";
                    }
                }
            }
        }

        // Tokenized sub-terms
        String cleanName = cNameLower.replaceAll("[()]", " ").replaceAll("[/&,+]", " ");
        for (String token : cleanName.split("\\s+")) {
            String trimmed = token.trim();
            if (trimmed.length() >= 3 && !STOPWORDS_CLASSIFIER.contains(trimmed) && fit.iuh.modules.assessment.util.TextSanitizationUtil.containsSkillTerm(jdLower, trimmed)) {
                return "required";
            }
        }

        // Prompt instruction keyword matching
        String instruction = resolveEffectivePromptInstruction(c);
        if (instruction != null && !instruction.isBlank()) {
            String[] instWords = instruction.split("[^A-Za-z0-9+#/.]");
            for (String word : instWords) {
                String w = word.trim().toLowerCase(Locale.ROOT);
                if (w.length() >= 3 && !STOPWORDS_CLASSIFIER.contains(w)) {
                    if (fit.iuh.modules.assessment.util.TextSanitizationUtil.containsSkillTerm(jdLower, w)) {
                        return "preferred";
                    }
                }
            }
        }

        return "not_in_jd";
    }

    public ClassifiedCriteriaBundle realignBundleWithActualCategory(
            ClassifiedCriteriaBundle originalBundle,
            List<CriteriaWeightProjection> actualDbCriteria,
            String fullJdMarkdown) {

        if (actualDbCriteria == null || actualDbCriteria.isEmpty()) {
            return originalBundle;
        }

        Map<String, ClassifiedCriteria> existingByName = new HashMap<>();
        Map<Long, ClassifiedCriteria> existingById = new HashMap<>();

        if (originalBundle != null && originalBundle.dbCriteria() != null) {
            for (var c : originalBundle.dbCriteria()) {
                if (c.criteriaId() != null) existingById.put(c.criteriaId(), c);
                if (c.criteriaName() != null) existingByName.put(c.criteriaName().toLowerCase(Locale.ROOT).trim(), c);
            }
        }

        Set<String> jdExtraNames = new HashSet<>();
        if (originalBundle != null && originalBundle.jdExtras() != null) {
            for (var extra : originalBundle.jdExtras()) {
                if (extra != null && extra.name() != null) {
                    jdExtraNames.add(extra.name().toLowerCase(Locale.ROOT).trim());
                }
            }
        }

        String jdLower = fullJdMarkdown != null ? fullJdMarkdown.toLowerCase(Locale.ROOT) : "";
        List<ClassifiedCriteria> realignedList = new ArrayList<>();

        for (CriteriaWeightProjection c : actualDbCriteria) {
            Long cid = c.getCriteriaId();
            String cName = c.getCriteriaName();
            String cNameLower = cName != null ? cName.toLowerCase(Locale.ROOT).trim() : "";

            String importance;
            if (existingById.containsKey(cid)) {
                importance = existingById.get(cid).importance();
            } else if (existingByName.containsKey(cNameLower)) {
                importance = existingByName.get(cNameLower).importance();
            } else {
                importance = determineRealignedImportance(c, cNameLower, jdLower, jdExtraNames);
            }

            String promptInst = resolveEffectivePromptInstruction(c);
            realignedList.add(new ClassifiedCriteria(
                    cid, cName, promptInst, c.getWeightPercentage() != null ? c.getWeightPercentage() : 10.0, importance
            ));
        }

        Set<String> activeDbNamesLower = realignedList.stream()
                .filter(c -> !"not_applicable".equalsIgnoreCase(c.importance()))
                .map(c -> c.criteriaName().toLowerCase(Locale.ROOT).trim())
                .collect(Collectors.toSet());

        List<JdExtraCriteria> originalExtras = (originalBundle != null && originalBundle.jdExtras() != null)
                ? originalBundle.jdExtras() : List.of();
        List<JdExtraCriteria> filteredExtras = filterAndDeduplicateJdExtras(originalExtras, activeDbNamesLower);

        return new ClassifiedCriteriaBundle(realignedList, filteredExtras);
    }

    private static <T> List<List<T>> partitionList(List<T> list, int size) {
        List<List<T>> partitions = new ArrayList<>();
        for (int i = 0; i < list.size(); i += size) {
            partitions.add(list.subList(i, Math.min(i + size, list.size())));
        }
        return partitions;
    }
}
