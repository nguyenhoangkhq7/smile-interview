package fit.iuh.modules.assessment.service;

import com.fasterxml.jackson.annotation.JsonIgnoreProperties;
import com.fasterxml.jackson.annotation.JsonProperty;
import com.fasterxml.jackson.databind.ObjectMapper;
import fit.iuh.config.AppProperties;
import fit.iuh.dto.chat.LlmChatRequest;
import fit.iuh.dto.chat.LlmChatResponse;
import fit.iuh.exception.LlmApiException;
import fit.iuh.modules.assessment.dto.AssessmentResponseDto;
import fit.iuh.modules.assessment.dto.ClassifiedCriteriaBundle;
import fit.iuh.modules.assessment.dto.ClassifiedCriteriaBundle.ClassifiedCriteria;
import fit.iuh.modules.assessment.dto.ClassifiedCriteriaBundle.JdExtraCriteria;
import fit.iuh.modules.assessment.entity.*;
import fit.iuh.modules.assessment.prompt.AssessmentPrompts;
import fit.iuh.modules.assessment.util.TextSanitizationUtil;
import fit.iuh.modules.assessment.repository.SuggestedCriteriaRepository;
import fit.iuh.modules.chunking.entity.DocumentChunk;
import fit.iuh.modules.chunking.repository.DocumentChunkRepository;
import fit.iuh.modules.chunking.service.EmbeddingService;
import fit.iuh.modules.ingestion.entity.DocumentType;
import fit.iuh.modules.rulengine.repository.JobCriteriaRepository;
import fit.iuh.modules.rulengine.repository.JobCriteriaRepository.CriteriaWeightProjection;
import fit.iuh.modules.rulengine.repository.JobCriteriaRepository.ConcreteCriteriaWeightDto;
import lombok.Data;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.beans.factory.annotation.Qualifier;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.cache.annotation.Cacheable;
import org.springframework.context.annotation.Lazy;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.reactive.function.client.WebClient;
import org.springframework.web.reactive.function.client.WebClientResponseException;
import org.springframework.data.redis.core.StringRedisTemplate;

import java.time.Duration;
import java.time.LocalDate;
import java.time.LocalDateTime;
import java.time.temporal.ChronoUnit;
import java.util.*;
import java.util.regex.Matcher;
import java.util.regex.Pattern;
import java.util.stream.Collectors;

/**
 * High-cohesion service responsible for pre-assessment preparation:
 * 1. Step 1a: Fast Metadata extraction (Category & Level) to load exact DB criteria tree.
 * 2. Step 1b: Consolidated Criteria Classification & Gate Extraction matching exact DB domain tree.
 * 3. Hard Gate Checks evaluation (YOE, Degree, etc.)
 * 4. Recording Ad-Hoc criteria discovered in JD text.
 */
@Slf4j
@Service
public class AssessmentCriteriaPreparer {

    private static final Map<String, String> JSON_RESPONSE_FORMAT = Map.of("type", "json_object");
    private static final int METADATA_MAX_TOKENS = 1024;
    private static final int MAX_CLASSIFIER_BATCH_SIZE = 15;

    private static final Set<String> HEAVY_DEVOPS_CRITERIA_KEYWORDS = Set.of(
            "auto-scaling", "auto scaling", "autoscaling",
            "lambda", "serverless",
            "kubernetes", "k8s", "eks", "ecs",
            "vpc", "vpc & networking", "vpc networking",
            "iam & security", "aws iam",
            "cost optimization",
            "linux administration", "shell scripting"
    );

    private final AppProperties appProperties;
    private final WebClient llmWebClient;
    private final ObjectMapper objectMapper;
    private final JobCriteriaRepository jobCriteriaRepository;
    private final DocumentChunkRepository documentChunkRepository;
    private final EmbeddingService embeddingService;
    private final SuggestedCriteriaRepository suggestedCriteriaRepository;
    private final CriteriaEmbeddingInitializer criteriaEmbeddingInitializer;
    private final StringRedisTemplate stringRedisTemplate;

    @Autowired
    @Lazy
    private AssessmentCriteriaPreparer self;

    @Value("${app.llm.chat-path:/v1/chat/completions}")
    private String llmChatPath;

    @Value("${app.assessment.gate.gpa.default-importance:PREFERRED}")
    private Importance defaultGpaImportance = Importance.PREFERRED;

    public record MetadataResult(JobCategory category, SeniorityLevel level) {}
    public record JdRawMetadata(JobCategory category, List<SeniorityLevel> acceptedLevels) {}
    public record PreparedJdBundle(
            MetadataResult metadata,
            ClassifiedCriteriaBundle bundle,
            List<GateCheckDto> rawGateRequirements
    ) {}

    @Autowired
    public AssessmentCriteriaPreparer(
            AppProperties appProperties,
            @Qualifier("llmWebClient") WebClient llmWebClient,
            ObjectMapper objectMapper,
            JobCriteriaRepository jobCriteriaRepository,
            @Autowired(required = false) DocumentChunkRepository documentChunkRepository,
            @Autowired(required = false) EmbeddingService embeddingService,
            SuggestedCriteriaRepository suggestedCriteriaRepository,
            @Autowired(required = false) CriteriaEmbeddingInitializer criteriaEmbeddingInitializer,
            StringRedisTemplate stringRedisTemplate) {
        this.appProperties = appProperties;
        this.llmWebClient = llmWebClient;
        this.objectMapper = objectMapper;
        this.jobCriteriaRepository = jobCriteriaRepository;
        this.documentChunkRepository = documentChunkRepository;
        this.embeddingService = embeddingService;
        this.suggestedCriteriaRepository = suggestedCriteriaRepository;
        this.criteriaEmbeddingInitializer = criteriaEmbeddingInitializer;
        this.stringRedisTemplate = stringRedisTemplate;
    }

    // =========================================================================
    // 1. SMART 2-STEP PHASE 1 JD PREPARATION
    // =========================================================================

    public PreparedJdBundle prepareJdConsolidatedSinglePass(String jdId, String fullJdMarkdown, String fullCvMarkdown) {
        if (fullJdMarkdown == null) fullJdMarkdown = "";
        if (fullCvMarkdown == null) fullCvMarkdown = "";
        
        final String jdContent = fullJdMarkdown;

        log.info("[Phase1-3Pass] Step 1 & 2: Extracting Category, Level, and Gate Requirements concurrently from JD...");
        
        final String finalCvMarkdown = fullCvMarkdown;
        java.util.concurrent.CompletableFuture<MetadataResult> metaFuture = java.util.concurrent.CompletableFuture.supplyAsync(() -> extractMetadata(jdContent, finalCvMarkdown));
        java.util.concurrent.CompletableFuture<List<GateCheckDto>> gatesFuture = java.util.concurrent.CompletableFuture.supplyAsync(() -> extractGateFromJd(jdContent));

        MetadataResult metadata = metaFuture.join();

        log.info("[Phase1-3Pass] Step 3: Loading DB criteria tree and classifying criteria for Category={} Level={}...",
                metadata.category(), metadata.level());
        ClassifiedCriteriaBundle bundle = loadAndClassifyCriteria(
                metadata.category().name(), metadata.level().name(), jdContent);

        List<GateCheckDto> gates = gatesFuture.join();

        log.info("[Phase1-3Pass] SUCCESS (3-Pass Pipeline): Category={}, Level={}, Gates={}, Classified Criteria={}",
                metadata.category(), metadata.level(), gates.size(), bundle.dbCriteria().size());

        return new PreparedJdBundle(metadata, bundle, gates);
    }

    public PreparedJdBundle prepareJdConsolidatedSinglePassWithKnownMetadata(String jdId, String fullJdMarkdown, String fullCvMarkdown, MetadataResult knownMetadata) {
        if (fullJdMarkdown == null) fullJdMarkdown = "";
        if (fullCvMarkdown == null) fullCvMarkdown = "";
        
        final String jdContent = fullJdMarkdown;
        final String finalCvMarkdown = fullCvMarkdown;

        log.info("[Phase1-DirectMatch] Reusing pre-resolved Category={} and Level={}. Bypassing LLM Metadata Extraction!",
                knownMetadata.category(), knownMetadata.level());

        java.util.concurrent.CompletableFuture<List<GateCheckDto>> gatesFuture = java.util.concurrent.CompletableFuture.supplyAsync(() -> extractGateFromJd(jdContent));

        log.info("[Phase1-DirectMatch] Loading DB criteria tree and classifying criteria for Category={} Level={}...",
                knownMetadata.category(), knownMetadata.level());
        ClassifiedCriteriaBundle bundle = loadAndClassifyCriteria(
                knownMetadata.category().name(), knownMetadata.level().name(), jdContent);

        List<GateCheckDto> gates = gatesFuture.join();

        log.info("[Phase1-DirectMatch] SUCCESS: Category={}, Level={}, Gates={}, Classified Criteria={}",
                knownMetadata.category(), knownMetadata.level(), gates.size(), bundle.dbCriteria().size());

        return new PreparedJdBundle(knownMetadata, bundle, gates);
    }

    // =========================================================================
    // 2. METADATA EXTRACTION
    // =========================================================================

    public MetadataResult extractMetadata(String jdMarkdown, String cvMarkdown) {
        log.info("[CriteriaPreparer] Extracting job category and seniority levels from JD...");

        int truncateLength = (appProperties != null && appProperties.getAssessment() != null && appProperties.getAssessment().getMetadataJdTruncateLength() > 0)
                ? appProperties.getAssessment().getMetadataJdTruncateLength() : 600;
        String truncatedJd = jdMarkdown;
        if (jdMarkdown != null && jdMarkdown.length() > truncateLength) {
            truncatedJd = jdMarkdown.substring(0, truncateLength) + "\n...[TRUNCATED]";
        }

        var taskConfig = appProperties.getLlm().getTasks().getMetadataExtraction();
        List<String> models = appProperties.getLlm().resolveModels(taskConfig);
        String model = models.isEmpty() ? appProperties.getLlm().resolveModel(taskConfig) : models.get(0);
        int maxTokens = appProperties.getLlm().resolveMaxTokens(taskConfig);
        Duration timeout = Duration.ofSeconds(appProperties.getLlm().resolveTimeoutSeconds(taskConfig));

        LlmChatRequest request = LlmChatRequest.builder()
                .model(model)
                .models(models)
                .maxTokens(maxTokens)
                .temperature(0.1)
                .stream(false)
                .responseFormat(JSON_RESPONSE_FORMAT)
                .messages(List.of(
                        LlmChatRequest.Message.system(AssessmentPrompts.SYSTEM_PROMPT_METADATA_EXTRACTION),
                        LlmChatRequest.Message.user(truncatedJd)
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

                if (responseBody == null || responseBody.isBlank()) {
                    throw new LlmApiException("LLM API returned empty HTTP body.");
                }

                LlmChatResponse response = objectMapper.readValue(responseBody, LlmChatResponse.class);
                if (response != null && response.getFirstChoiceContent() != null) {
                    String rawJson = response.getFirstChoiceContent().strip();
                    return parseAndMapToEnums(rawJson, cvMarkdown);
                }

            } catch (WebClientResponseException e) {
                log.warn("[CriteriaPreparer] Metadata extraction OpenRouter HTTP {} Error: {}", e.getStatusCode(), e.getResponseBodyAsString());
                if (e.getStatusCode().value() == 400 && request.getResponseFormat() != null) {
                    log.warn("[CriteriaPreparer] Model '{}' rejected response_format. Retrying without response_format...", model);
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
                return fallbackMetadataResult();
            } catch (Exception e) {
                log.error("[CriteriaPreparer] Metadata extraction error (attempt {}/2): {}", attempt, e.getMessage());
            }
        }
        return fallbackMetadataResult();
    }

    private MetadataResult parseAndMapToEnums(String rawJson, String cvMarkdown) {
        String json = rawJson.replaceAll("(?s)^```json\\s*", "").replaceAll("(?s)\\s*```$", "").strip();
        try {
            RawMetadataDto raw = objectMapper.readValue(json, RawMetadataDto.class);
            JobCategory category = parseJobCategory(raw.category());
            
            List<SeniorityLevel> jdLevels = new ArrayList<>();
            if (raw.acceptedLevels() != null && !raw.acceptedLevels().isEmpty()) {
                for (String lvlStr : raw.acceptedLevels()) {
                    jdLevels.add(parseSeniorityLevel(lvlStr));
                }
            } else if (raw.level() != null) { // Fallback for old prompt structure
                jdLevels.add(parseSeniorityLevel(raw.level()));
            }

            if (jdLevels.isEmpty()) {
                jdLevels.add(SeniorityLevel.MID);
            }

            // Remove duplicates and sort based on natural enum order (INTERN < FRESHER < JUNIOR < MID < SENIOR < LEAD)
            List<SeniorityLevel> distinctSortedLevels = jdLevels.stream()
                    .distinct()
                    .sorted()
                    .toList();

            SeniorityLevel targetLevel;
            if (distinctSortedLevels.size() == 1) {
                // Optimization: If JD is strict about 1 level, skip CV extraction.
                targetLevel = distinctSortedLevels.get(0);
                log.info("[CriteriaPreparer] JD has single accepted level: {}. Skipping CV level extraction.", targetLevel);
            } else {
                log.info("[CriteriaPreparer] JD accepts multiple levels: {}. Extracting level from CV...", distinctSortedLevels);
                SeniorityLevel cvLevel = extractCvSeniorityLevel(cvMarkdown);
                targetLevel = resolveTargetSeniorityLevel(distinctSortedLevels, cvLevel);
            }

            log.info("[CriteriaPreparer] Final extracted metadata: category={}, targetLevel={}", category, targetLevel);
            return new MetadataResult(category, targetLevel);
        } catch (Exception e) {
            log.error("[CriteriaPreparer] Failed to parse Metadata JSON: {}", e.getMessage(), e);
            return fallbackMetadataResult();
        }
    }

    public JdRawMetadata extractJdRawMetadata(String jdMarkdown) {
        if (jdMarkdown == null || jdMarkdown.isBlank()) {
            return new JdRawMetadata(JobCategory.OTHER, List.of(SeniorityLevel.MID));
        }
        try {
            MetadataResult res = extractMetadata(jdMarkdown, null);
            // Re-parse raw metadata json if needed, or extract metadata
            return new JdRawMetadata(res.category(), List.of(res.level()));
        } catch (Exception e) {
            return new JdRawMetadata(JobCategory.OTHER, List.of(SeniorityLevel.MID));
        }
    }

    public SeniorityLevel extractCvSeniorityLevel(String cvMarkdown) {
        if (cvMarkdown == null || cvMarkdown.isBlank()) return SeniorityLevel.JUNIOR;
        log.info("[CriteriaPreparer] Extracting Candidate Seniority Level from CV...");
        
        int truncateLength = 2000;
        String truncatedCv = cvMarkdown;
        if (cvMarkdown.length() > truncateLength) {
            truncatedCv = cvMarkdown.substring(0, truncateLength) + "\n...[TRUNCATED]";
        }

        var taskConfig = appProperties.getLlm().getTasks().getMetadataExtraction();
        List<String> models = appProperties.getLlm().resolveModels(taskConfig);
        String model = models.isEmpty() ? appProperties.getLlm().resolveModel(taskConfig) : models.get(0);
        Duration timeout = Duration.ofSeconds(appProperties.getLlm().resolveTimeoutSeconds(taskConfig));

        LlmChatRequest request = LlmChatRequest.builder()
                .model(model)
                .models(models)
                .maxTokens(150)
                .temperature(0.1)
                .stream(false)
                .responseFormat(JSON_RESPONSE_FORMAT)
                .messages(List.of(
                        LlmChatRequest.Message.system(AssessmentPrompts.SYSTEM_PROMPT_CV_LEVEL_EXTRACTION),
                        LlmChatRequest.Message.user(truncatedCv)
                ))
                .build();

        try {
            String responseBody = llmWebClient.post()
                    .uri(appProperties.getLlm().getChatPath())
                    .bodyValue(request)
                    .retrieve()
                    .bodyToMono(String.class)
                    .timeout(timeout)
                    .block();

            LlmChatResponse response = objectMapper.readValue(responseBody, LlmChatResponse.class);
            if (response != null && response.getFirstChoiceContent() != null) {
                String rawJson = response.getFirstChoiceContent().strip();
                String json = rawJson.replaceAll("(?s)^```json\\s*", "").replaceAll("(?s)\\s*```$", "").strip();
                java.util.Map<String, String> result = objectMapper.readValue(json, new com.fasterxml.jackson.core.type.TypeReference<>() {});
                return parseSeniorityLevel(result.get("level"));
            }
        } catch (Exception e) {
            log.warn("[CriteriaPreparer] Failed to extract CV level: {}", e.getMessage());
        }
        return SeniorityLevel.JUNIOR; // Safe fallback for Tech
    }

    public SeniorityLevel resolveTargetSeniorityLevel(List<SeniorityLevel> jdLevels, SeniorityLevel cvLevel) {
        if (jdLevels.contains(cvLevel)) {
            log.info("[CriteriaPreparer] CV level {} is accepted by JD. Using it as target level.", cvLevel);
            return cvLevel;
        }
        
        SeniorityLevel minLevel = jdLevels.get(0);
        SeniorityLevel maxLevel = jdLevels.get(jdLevels.size() - 1);
        
        if (cvLevel.compareTo(minLevel) < 0) {
            log.info("[CriteriaPreparer] CV level {} is LOWER than JD min level {}. Evaluating at min level.", cvLevel, minLevel);
            return minLevel;
        } else {
            log.info("[CriteriaPreparer] CV level {} is HIGHER than JD max level {}. Evaluating at max level.", cvLevel, maxLevel);
            return maxLevel;
        }
    }

    public JobCategory parseJobCategory(String value) {
        if (value == null) return JobCategory.OTHER;
        String normalized = value.toUpperCase().strip().replace(" ", "_").replace("-", "_");

        // Alias map: handle legacy/alternative LLM outputs → canonical JobCategory enum values
        // Prompts now use exact enum names, but aliases guard against model drift or old prompts.
        switch (normalized) {
            case "ML_ENGINEERING":
            case "ML":
            case "MACHINE_LEARNING":
            case "AI":
            case "AI_ML":
                return JobCategory.AI_ML;
            case "QA":
            case "QA_TESTING":
            case "TESTING":
            case "QUALITY_ASSURANCE":
                return JobCategory.QA_TESTING;
            case "DATA":
            case "DATA_ENGINEERING":
            case "DATA_SCIENCE":
            case "DATA_ANALYST":
                return JobCategory.DATA_ENGINEERING;
            case "SECURITY":
            case "CYBERSECURITY":
            case "APPSEC":
            case "INFOSEC":
                // SECURITY is not in JobCategory enum — map to OTHER to use SOFTWARE_ENGINEERING fallback
                // (Security-specific criteria are under SECURITY job_category code in DB)
                return JobCategory.OTHER;
            default:
                try {
                    return JobCategory.valueOf(normalized);
                } catch (IllegalArgumentException e) {
                    log.warn("[CriteriaPreparer] Unknown category '{}' from LLM — falling back to OTHER.", value);
                    return JobCategory.OTHER;
                }
        }
    }

    public SeniorityLevel parseSeniorityLevel(String value) {
        if (value == null) return SeniorityLevel.JUNIOR; // Safe fallback
        
        String normalized = value.toUpperCase().strip().replace(" ", "_").replace("-", "_");
        switch (normalized) {
            case "INTERN": case "INTERNSHIP": return SeniorityLevel.INTERN;
            case "FRESHER": case "FRESHER_JUNIOR": case "FRESH": return SeniorityLevel.FRESHER;
            case "JUNIOR": case "JR": return SeniorityLevel.JUNIOR;
            case "MID": case "MIDDLE": case "MID_LEVEL": return SeniorityLevel.MID;
            case "SENIOR": case "SR": return SeniorityLevel.SENIOR;
            case "LEAD": case "TECH_LEAD": case "ARCHITECT": return SeniorityLevel.LEAD;
            default: return SeniorityLevel.JUNIOR; // Fallback an toàn về JUNIOR
        }
    }

    private MetadataResult fallbackMetadataResult() {
        log.warn("[CriteriaPreparer] Using fallback defaults: category=OTHER, level=JUNIOR");
        return new MetadataResult(JobCategory.OTHER, SeniorityLevel.JUNIOR);
    }

    // =========================================================================
    // 3. CRITERIA LOADING & CLASSIFICATION
    // =========================================================================

    public ClassifiedCriteriaBundle loadAndClassifyCriteria(String categoryName, String seniorityLevelName, String fullJdMarkdown) {
        List<CriteriaWeightProjection> dbCriteria = (self != null ? self : this).loadCriteriaWithFallback(categoryName, seniorityLevelName);
        log.info("[CriteriaPreparer] Loading DB criteria tree: Fetched {} base criteria for Category={}, Level={}",
                dbCriteria.size(), categoryName, seniorityLevelName);

        ClassifiedCriteriaBundle bundle = classifyCriteria(fullJdMarkdown, dbCriteria, seniorityLevelName);

        long requiredCount = bundle.dbCriteria() != null ? bundle.dbCriteria().stream().filter(c -> "required".equalsIgnoreCase(c.importance())).count() : 0;
        long preferredCount = bundle.dbCriteria() != null ? bundle.dbCriteria().stream().filter(c -> "preferred".equalsIgnoreCase(c.importance())).count() : 0;
        long notInJdCount = bundle.dbCriteria() != null ? bundle.dbCriteria().stream().filter(c -> "not_in_jd".equalsIgnoreCase(c.importance())).count() : 0;
        long adHocCount = bundle.jdExtras() != null ? bundle.jdExtras().size() : 0;

        log.info("[CriteriaPreparer] LLM Classification & Single-Pass Filtering Report: DB Loaded={} -> [Required={}, Preferred={}, NotInJD={}] | Discovered Ad-hoc={}",
                dbCriteria.size(), requiredCount, preferredCount, notInJdCount, adHocCount);

        return bundle;
    }

    public List<CriteriaWeightProjection> loadAndFilterCriteria(
            String categoryName, String seniorityLevelName, String sessionId, String fullJdMarkdown, boolean shouldIncludeNotApp) {
        List<CriteriaWeightProjection> criteriaList = (self != null ? self : this).loadCriteriaWithFallback(categoryName, seniorityLevelName);

        if (!shouldIncludeNotApp) {
            List<CriteriaWeightProjection> preFiltered = preFilterCriteriaForJd(sessionId, fullJdMarkdown, criteriaList);
            if (!preFiltered.isEmpty()) {
                criteriaList = preFiltered;
            }
        }
        return criteriaList;
    }

    @Cacheable(value = "criteria_prompts", key = "#categoryName + '_' + #seniorityLevelName")
    public List<CriteriaWeightProjection> loadCriteriaWithFallback(String categoryName, String seniorityLevelName) {
        List<CriteriaWeightProjection> criteriaList = jobCriteriaRepository.findCriteriaTreeByCategory(categoryName, seniorityLevelName);
        if (criteriaList.isEmpty()) {
            criteriaList = jobCriteriaRepository.findCriteriaTreeByCategory(categoryName, "ALL");
        }
        if (criteriaList.isEmpty()) {
            criteriaList = jobCriteriaRepository.findCriteriaTreeByCategory("SOFTWARE_ENGINEERING", "ALL");
        }
        List<CriteriaWeightProjection> deduplicated = deduplicateCriteria(criteriaList);
        List<CriteriaWeightProjection> result = new ArrayList<>(deduplicated.size());
        for (CriteriaWeightProjection p : deduplicated) {
            result.add(ConcreteCriteriaWeightDto.from(p));
        }
        return result;
    }

    private List<CriteriaWeightProjection> deduplicateCriteria(List<CriteriaWeightProjection> list) {
        if (list == null || list.isEmpty()) return list;
        Map<Long, CriteriaWeightProjection> uniqueMap = new LinkedHashMap<>();
        for (CriteriaWeightProjection c : list) {
            uniqueMap.putIfAbsent(c.getCriteriaId(), c);
        }
        return new ArrayList<>(uniqueMap.values());
    }

    private List<CriteriaWeightProjection> preFilterCriteriaForJd(String sessionId, String jdText, List<CriteriaWeightProjection> allCriteria) {
        if (jdText == null || jdText.isBlank() || allCriteria == null || allCriteria.isEmpty()) {
            return allCriteria;
        }

        List<CriteriaFilterDebugDetail> details = executeLlmCriteriaPreFiltering(jdText, allCriteria);
        Set<Long> matchedIds = details.stream()
                .filter(CriteriaFilterDebugDetail::isMatched)
                .map(CriteriaFilterDebugDetail::criteriaId)
                .collect(Collectors.toSet());

        List<CriteriaWeightProjection> filtered = allCriteria.stream()
                .filter(c -> matchedIds.contains(c.getCriteriaId()))
                .collect(Collectors.toList());

        List<CriteriaWeightProjection> finalResult = filtered.isEmpty() ? allCriteria : filtered;
        log.info("[CriteriaPreparer] LLM Criteria Pre-Filtering Report: Original={} -> Matched={} (Returned={}, Fallback={})",
                allCriteria.size(), filtered.size(), finalResult.size(), filtered.isEmpty());

        return finalResult;
    }

    public record CriteriaFilterDebugDetail(
            Long criteriaId,
            String criteriaName,
            Double weightPercentage,
            Double matchConfidence,
            String matchReason,
            boolean isMatched
    ) {}

    public List<CriteriaFilterDebugDetail> debugFilterCriteriaDetails(
            String categoryName, String seniorityLevelName, String jdText, double threshold) {

        List<CriteriaWeightProjection> allCriteria = (self != null ? self : this).loadCriteriaWithFallback(categoryName, seniorityLevelName);
        return executeLlmCriteriaPreFiltering(jdText, allCriteria);
    }

    private List<CriteriaFilterDebugDetail> executeLlmCriteriaPreFiltering(String jdMarkdown, List<CriteriaWeightProjection> allCriteria) {
        if (allCriteria == null || allCriteria.isEmpty()) {
            return List.of();
        }

        if (jdMarkdown == null || jdMarkdown.isBlank()) {
            return allCriteria.stream().map(c -> new CriteriaFilterDebugDetail(
                    c.getCriteriaId(),
                    c.getCriteriaName(),
                    c.getWeightPercentage(),
                    1.0,
                    "FALLBACK_EMPTY_JD",
                    true
            )).collect(Collectors.toList());
        }

        StringBuilder criteriaListBuilder = new StringBuilder();
        Map<Long, CriteriaWeightProjection> criteriaMap = new LinkedHashMap<>();
        for (CriteriaWeightProjection c : allCriteria) {
            criteriaListBuilder.append(String.format("- %s (ID: %d)\n", c.getCriteriaName(), c.getCriteriaId()));
            criteriaMap.put(c.getCriteriaId(), c);
        }

        String userPrompt = String.format(
                "Job Description (Markdown):\n%s\n\nDatabase Criteria List to Filter:\n%s",
                jdMarkdown, criteriaListBuilder
        );

        var taskConfig = appProperties.getLlm().getTasks().getCriteriaClassification();
        List<String> models = appProperties.getLlm().resolveModels(taskConfig);
        String model = models.isEmpty() ? appProperties.getLlm().resolveModel(taskConfig) : models.get(0);
        int maxTokens = appProperties.getLlm().resolveMaxTokens(taskConfig);
        Duration timeout = Duration.ofSeconds(Math.max(120, appProperties.getLlm().resolveTimeoutSeconds(taskConfig)));

        LlmChatRequest request = LlmChatRequest.builder()
                .model(model)
                .models(models)
                .maxTokens(maxTokens)
                .temperature(0.1)
                .stream(false)
                .responseFormat(JSON_RESPONSE_FORMAT)
                .messages(List.of(
                        LlmChatRequest.Message.system(AssessmentPrompts.SYSTEM_PROMPT_PRE_FILTER_CRITERIA),
                        LlmChatRequest.Message.user(userPrompt)
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

                if (responseBody != null && !responseBody.isBlank()) {
                    LlmChatResponse response = objectMapper.readValue(responseBody, LlmChatResponse.class);
                    if (response != null && response.getFirstChoiceContent() != null) {
                        return parseLlmFilterJson(response.getFirstChoiceContent(), criteriaMap, allCriteria);
                    }
                }
            } catch (WebClientResponseException e) {
                log.warn("[CriteriaPreparer] Pre-filter criteria OpenRouter HTTP {} Error: {}", e.getStatusCode(), e.getResponseBodyAsString());
                if (e.getStatusCode().value() == 400 && request.getResponseFormat() != null) {
                    log.warn("[CriteriaPreparer] Model '{}' rejected response_format. Retrying without response_format...", model);
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
                log.warn("[CriteriaPreparer] Pre-filter LLM call failed (attempt {}/2): {}", attempt, e.getMessage());
            }
        }

        // Fallback if LLM fails: include all criteria
        return allCriteria.stream().map(c -> new CriteriaFilterDebugDetail(
                c.getCriteriaId(),
                c.getCriteriaName(),
                c.getWeightPercentage(),
                1.0,
                "LLM_FALLBACK_ALL_INCLUDED",
                true
        )).collect(Collectors.toList());
    }

    private List<CriteriaFilterDebugDetail> parseLlmFilterJson(
            String rawJson, Map<Long, CriteriaWeightProjection> criteriaMap, List<CriteriaWeightProjection> allCriteria) {
        String cleanJson = TextSanitizationUtil.extractCleanJson(rawJson);
        List<CriteriaFilterDebugDetail> details = new ArrayList<>();
        Set<Long> matchedIdSet = new HashSet<>();

        try {
            var rootNode = objectMapper.readTree(cleanJson);
            if (rootNode.has("matched_ids") && rootNode.get("matched_ids").isArray()) {
                for (var idNode : rootNode.get("matched_ids")) {
                    matchedIdSet.add(idNode.asLong());
                }
            } else if (rootNode.has("filtered_criteria") && rootNode.get("filtered_criteria").isArray()) {
                for (var item : rootNode.get("filtered_criteria")) {
                    Long id = item.has("id") ? item.get("id").asLong() : (item.has("criteria_id") ? item.get("criteria_id").asLong() : null);
                    boolean isMatched = (item.has("matched") && item.get("matched").asBoolean()) || (item.has("is_matched") && item.get("is_matched").asBoolean());
                    if (id != null && isMatched) {
                        matchedIdSet.add(id);
                    }
                }
            } else if (rootNode.isArray()) {
                for (var item : rootNode) {
                    if (item.isNumber()) {
                        matchedIdSet.add(item.asLong());
                    }
                }
            }
        } catch (Exception e) {
            log.warn("[CriteriaPreparer] Failed to parse LLM pre-filter JSON: {}", e.getMessage());
        }

        for (CriteriaWeightProjection c : allCriteria) {
            boolean isMatched = matchedIdSet.contains(c.getCriteriaId());
            details.add(new CriteriaFilterDebugDetail(
                    c.getCriteriaId(),
                    c.getCriteriaName(),
                    c.getWeightPercentage(),
                    isMatched ? 1.0 : 0.0,
                    isMatched ? "LLM_MATCH (Matched ID)" : "LLM_NO_MATCH: Not in matched_ids",
                    isMatched
            ));
        }

        return details;
    }



    public ClassifiedCriteriaBundle classifyCriteria(String jdMarkdown, List<CriteriaWeightProjection> dbCriteria, String seniorityLevel) {
        if (dbCriteria == null || dbCriteria.isEmpty()) {
            return new ClassifiedCriteriaBundle(List.of(), List.of());
        }
        if (jdMarkdown == null || jdMarkdown.isBlank()) {
            List<ClassifiedCriteria> fallbackList = dbCriteria.stream()
                    .map(c -> new ClassifiedCriteria(c.getCriteriaId(), c.getCriteriaName(), resolveEffectivePromptInstruction(c), c.getWeightPercentage(), "preferred"))
                    .collect(Collectors.toList());
            return new ClassifiedCriteriaBundle(fallbackList, List.of());
        }

        List<ClassifiedCriteria> classifiedResults = new ArrayList<>();
        List<JdExtraCriteria> extraResults = new ArrayList<>();

        List<List<CriteriaWeightProjection>> batches = partitionList(dbCriteria, MAX_CLASSIFIER_BATCH_SIZE);
        for (int i = 0; i < batches.size(); i++) {
            List<CriteriaWeightProjection> batch = batches.get(i);
            boolean isLastBatch = (i == batches.size() - 1);
            classifyBatch(jdMarkdown, batch, seniorityLevel, isLastBatch, classifiedResults, extraResults);
        }

        enforceSeniorityDevOpsRules(classifiedResults, seniorityLevel);
        List<JdExtraCriteria> filteredExtras = filterAndDeduplicateJdExtras(classifiedResults, extraResults);
        return new ClassifiedCriteriaBundle(classifiedResults, filteredExtras);
    }

    private List<JdExtraCriteria> filterAndDeduplicateJdExtras(
            List<ClassifiedCriteria> classifiedResults, List<JdExtraCriteria> extraResults) {
        if (extraResults == null || extraResults.isEmpty()) {
            return List.of();
        }

        Set<String> activeDbCriteriaNamesLower = classifiedResults.stream()
                .filter(c -> !"not_in_jd".equalsIgnoreCase(c.importance()))
                .map(c -> c.criteriaName() != null ? c.criteriaName().toLowerCase(Locale.ROOT) : "")
                .collect(Collectors.toSet());

        List<JdExtraCriteria> filteredExtras = new ArrayList<>();
        Set<String> addedNamesLower = new HashSet<>();

        for (JdExtraCriteria extra : extraResults) {
            if (extra == null || extra.name() == null || extra.name().isBlank()) continue;

            String extraNameLower = extra.name().trim().toLowerCase(Locale.ROOT);
            if (addedNamesLower.contains(extraNameLower)) continue;

            boolean overlaps = isOverlappingWithDbCriteria(extraNameLower, activeDbCriteriaNamesLower);
            if (overlaps) {
                log.info("[CriteriaPreparer] Filtered out redundant ad-hoc criteria '{}' (overlaps with DB criteria tree).", extra.name());
                continue;
            }

            filteredExtras.add(extra);
            addedNamesLower.add(extraNameLower);

            if (filteredExtras.size() >= 5) {
                log.info("[CriteriaPreparer] Capped ad-hoc criteria at maximum 5 items.");
                break;
            }
        }

        return filteredExtras;
    }

    private boolean isOverlappingWithDbCriteria(String extraNameLower, Set<String> activeDbNamesLower) {
        for (String dbName : activeDbNamesLower) {
            if (dbName.isBlank()) continue;
            if (dbName.contains(extraNameLower) || extraNameLower.contains(dbName)) return true;

            String cleanExtra = extraNameLower.replaceAll("[^a-z0-9]", "");
            String cleanDb = dbName.replaceAll("[^a-z0-9]", "");
            if (!cleanExtra.isEmpty() && !cleanDb.isEmpty() && (cleanDb.contains(cleanExtra) || cleanExtra.contains(cleanDb))) {
                return true;
            }
        }

        if (containsAnyKeyword(extraNameLower, "mysql", "postgresql", "postgres", "mongodb", "sql", "nosql")
                && activeDbNamesLower.stream().anyMatch(d -> containsAnyKeyword(d, "database", "sql", "nosql"))) {
            return true;
        }

        if (containsAnyKeyword(extraNameLower, "agile", "scrum", "jira", "sprint")
                && activeDbNamesLower.stream().anyMatch(d -> containsAnyKeyword(d, "agile", "sdlc", "scrum"))) {
            return true;
        }

        if (containsAnyKeyword(extraNameLower, "docker", "container", "containerization")
                && activeDbNamesLower.stream().anyMatch(d -> containsAnyKeyword(d, "docker", "container"))) {
            return true;
        }

        if (containsAnyKeyword(extraNameLower, "git", "github", "gitlab", "pr workflow")
                && activeDbNamesLower.stream().anyMatch(d -> containsAnyKeyword(d, "git", "version control", "vcs"))) {
            return true;
        }

        if (containsAnyKeyword(extraNameLower, "rest", "restful", "graphql", "api design")
                && activeDbNamesLower.stream().anyMatch(d -> containsAnyKeyword(d, "api", "rest", "graphql"))) {
            return true;
        }

        return false;
    }

    private boolean containsAnyKeyword(String text, String... keywords) {
        if (text == null) return false;
        for (String kw : keywords) {
            if (text.contains(kw)) return true;
        }
        return false;
    }

    private String resolveEffectivePromptInstruction(CriteriaWeightProjection c) {
        if (c == null) return "";
        String levelInst = c.getLevelPromptInstruction();
        if (levelInst != null && !levelInst.isBlank()) {
            return levelInst.strip();
        }
        return c.getPromptInstruction() != null ? c.getPromptInstruction() : "";
    }

    private void classifyBatch(
            String jdMarkdown, List<CriteriaWeightProjection> batch, String seniorityLevel,
            boolean includeExtras, List<ClassifiedCriteria> classifiedResults, List<JdExtraCriteria> extraResults) {

        StringBuilder listBuilder = new StringBuilder();
        Map<Long, CriteriaWeightProjection> batchMap = new LinkedHashMap<>();
        for (CriteriaWeightProjection c : batch) {
            listBuilder.append(String.format("%d. %s (ID: %d)\n", c.getCriteriaId(), c.getCriteriaName(), c.getCriteriaId()));
            batchMap.put(c.getCriteriaId(), c);
        }

        String userPrompt = String.format(
                "Candidate Seniority Level: %s\n\nDatabase Criteria List:\n%s\n\nJob Description:\n%s",
                seniorityLevel, listBuilder, jdMarkdown);
        var taskConfig = appProperties.getLlm().getTasks().getCriteriaClassification();
        List<String> models = appProperties.getLlm().resolveModels(taskConfig);
        String model = models.isEmpty() ? appProperties.getLlm().resolveModel(taskConfig) : models.get(0);
        long timeoutSec = Math.max(180, appProperties.getLlm().resolveTimeoutSeconds(taskConfig));
        Duration timeout = Duration.ofSeconds(timeoutSec);

        LlmChatRequest request = LlmChatRequest.builder()
                .model(model)
                .models(models)
                .maxTokens(appProperties.getLlm().resolveMaxTokens(taskConfig))
                .temperature(0.1)
                .stream(false)
                .responseFormat(JSON_RESPONSE_FORMAT)
                .messages(List.of(
                        LlmChatRequest.Message.system(AssessmentPrompts.SYSTEM_PROMPT_CRITERIA_CLASSIFICATION),
                        LlmChatRequest.Message.user(userPrompt)
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
                        boolean parsedSuccessfully = parseClassifierJson(res.getFirstChoiceContent(), batchMap, classifiedResults, includeExtras ? extraResults : null);
                        if (parsedSuccessfully) {
                            return;
                        }
                    }
                }
            } catch (WebClientResponseException e) {
                log.warn("[CriteriaPreparer] Classify batch OpenRouter HTTP {} Error: {}", e.getStatusCode(), e.getResponseBodyAsString());
                if (e.getStatusCode().value() == 400 && request.getResponseFormat() != null) {
                    log.warn("[CriteriaPreparer] Model '{}' rejected response_format. Retrying classify batch without response_format...", request.getModel());
                    request = LlmChatRequest.builder()
                            .model(request.getModel())
                            .models(request.getModels())
                            .maxTokens(request.getMaxTokens())
                            .temperature(0.1)
                            .stream(false)
                            .messages(request.getMessages())
                            .build();
                    continue;
                }
                break;
            } catch (Exception e) {
                log.warn("[CriteriaPreparer] Batch classification failed (attempt {}/2): {}", attempt, e.getMessage());
            }
        }

        log.warn("[CriteriaPreparer] Batch classification failed after retries. Applying fallback 'preferred' to {} criteria in batch.", batch.size());
        for (CriteriaWeightProjection c : batch) {
            classifiedResults.add(new ClassifiedCriteria(c.getCriteriaId(), c.getCriteriaName(), resolveEffectivePromptInstruction(c), c.getWeightPercentage(), "preferred"));
        }
    }

    private boolean parseClassifierJson(String rawJson, Map<Long, CriteriaWeightProjection> batchMap, List<ClassifiedCriteria> classifiedResults, List<JdExtraCriteria> extraResults) {
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
                        classifiedResults.add(new ClassifiedCriteria(c.getCriteriaId(), c.getCriteriaName(), resolveEffectivePromptInstruction(c), c.getWeightPercentage(), importance));
                        processedIds.add(id);
                    }
                }
                for (CriteriaWeightProjection c : batchMap.values()) {
                    if (!processedIds.contains(c.getCriteriaId())) {
                        classifiedResults.add(new ClassifiedCriteria(c.getCriteriaId(), c.getCriteriaName(), resolveEffectivePromptInstruction(c), c.getWeightPercentage(), "preferred"));
                    }
                }
            } else {
                log.warn("[CriteriaPreparer] Classifier JSON missing 'classified' array: {}", cleanJson);
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
            log.warn("[CriteriaPreparer] Classifier JSON parse error: {}", e.getMessage());
            return false;
        }
    }

    private void enforceSeniorityDevOpsRules(List<ClassifiedCriteria> classifiedList, String seniorityLevel) {
        if (seniorityLevel == null || classifiedList == null) return;
        String level = seniorityLevel.trim().toUpperCase();
        if ("INTERN".equals(level) || "FRESHER".equals(level)) {
            for (int i = 0; i < classifiedList.size(); i++) {
                ClassifiedCriteria item = classifiedList.get(i);
                if ("required".equalsIgnoreCase(item.importance())) {
                    String cNameLower = item.criteriaName() != null ? item.criteriaName().toLowerCase() : "";
                    for (String kw : HEAVY_DEVOPS_CRITERIA_KEYWORDS) {
                        if (cNameLower.contains(kw)) {
                            classifiedList.set(i, new ClassifiedCriteria(
                                    item.criteriaId(), item.criteriaName(), item.promptInstruction(), item.weightPercentage(), "preferred"));
                            break;
                        }
                    }
                }
            }
        }
    }

    // =========================================================================
    // 4. GATE EXTRACTION & ELIGIBILITY EVALUATION
    // =========================================================================

    public record EligibilityEvaluationResult(
            EligibilityStatus status,
            List<fit.iuh.modules.assessment.dto.AssessmentResponseDto.EvidenceItem> gateItems
    ) {}

    public EligibilityEvaluationResult evaluateEligibility(String jdContent, String cvContent) {
        return evaluateEligibilityWithRawGates(null, jdContent, cvContent);
    }

    public EligibilityEvaluationResult evaluateEligibilityWithRawGates(List<GateCheckDto> preExtractedGates, String jdContent, String cvContent) {
        log.info("[CriteriaPreparer] Extracting GATE requirements from JD...");
        List<GateCheckDto> rawGates = (preExtractedGates != null && !preExtractedGates.isEmpty())
                ? preExtractedGates
                : null;

        if (rawGates == null) {
            try {
                rawGates = extractGateFromJd(jdContent);
            } catch (Exception e) {
                log.error("[CriteriaPreparer] Gate extraction exception: {}", e.getMessage());
            }
        }

        if (rawGates == null || rawGates.isEmpty()) {
            return new EligibilityEvaluationResult(EligibilityStatus.PARTIAL, List.of());
        }

        double candidateYoe = calculateCandidateYoe(cvContent);
        boolean failedRequired = false;
        List<fit.iuh.modules.assessment.dto.AssessmentResponseDto.EvidenceItem> gateItems = new java.util.ArrayList<>();

        for (GateCheckDto dto : rawGates) {
            String name = dto.getCriteriaName();
            Importance imp = parseImportance(dto.getImportance());
            String reqVal = dto.getRequiredValue();

            boolean evaluated = false;
            boolean pass = false;
            String cvEvidence = "Not Evaluated";

            if (name != null && (name.toLowerCase().contains("experience") || name.toLowerCase().contains("yoe"))) {
                double reqYoe = parseRequiredYoe(reqVal);
                pass = candidateYoe >= reqYoe;
                cvEvidence = candidateYoe > 0 ? candidateYoe + " years of experience" : (pass ? "0 YOE (Fresher/Entry-level requirement met)" : "No quantifiable experience found");
                evaluated = true;
            } else if (name != null && (name.toLowerCase().contains("degree") || name.toLowerCase().contains("education") || name.toLowerCase().contains("academic") || name.toLowerCase().contains("university") || name.toLowerCase().contains("bachelor"))) {
                boolean hasDegree = checkDegreeInCv(cvContent);
                pass = hasDegree;
                cvEvidence = hasDegree ? "Degree/Education mentioned in CV" : "No relevant education/degree found in CV";
                evaluated = true;
            }

            if (evaluated) {
                if (!pass && imp == Importance.REQUIRED) failedRequired = true;
            } else {
                // Cannot auto-evaluate this gate with simple heuristics. 
                // Default to pass = true to avoid unfairly rejecting candidates, but mark for manual review.
                pass = true;
                cvEvidence = "Manual verification required";
            }

            gateItems.add(new fit.iuh.modules.assessment.dto.AssessmentResponseDto.EvidenceItem(
                    null,
                    (name != null && !"Certification".equalsIgnoreCase(name)) ? name : (reqVal != null && reqVal.length() <= 30 ? reqVal : name),
                    "GATE",
                    reqVal,
                    cvEvidence,
                    null,
                    evaluated ? (pass ? "Pass" : "Not Pass") : "Not Evaluated",
                    evaluated ? (pass ? "Candidate meets the gate requirement." : "Candidate does not meet the gate requirement.") 
                              : "System heuristics currently only auto-evaluate YOE and Degree gates. Please manually verify this requirement.",
                    null, null, null, null, null, null, null
            ));
        }

        EligibilityStatus finalStatus = failedRequired ? EligibilityStatus.NOT_ELIGIBILITY : EligibilityStatus.ELIGIBILITY;
        return new EligibilityEvaluationResult(finalStatus, gateItems);
    }

    private List<GateCheckDto> extractGateFromJd(String jdContent) {
        if (jdContent == null || jdContent.isBlank()) return List.of();

        // Use full JD text (or safe 8000 char limit for extremely long JDs) so requirements at the end are never missed
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
                log.warn("[CriteriaPreparer] Gate extraction OpenRouter HTTP {} Error: {}", e.getStatusCode(), e.getResponseBodyAsString());
                if (e.getStatusCode().value() == 400 && request.getResponseFormat() != null) {
                    log.warn("[CriteriaPreparer] Retrying gate extraction without response_format...");
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
                if (e instanceof java.util.concurrent.TimeoutException || (e.getCause() != null && e.getCause() instanceof java.util.concurrent.TimeoutException) || (e.getMessage() != null && e.getMessage().contains("TimeoutException"))) {
                    log.warn("[CriteriaPreparer] Gate extraction LLM request timed out after {}s: {}", timeout.getSeconds(), e.getMessage());
                    break;
                }
                log.warn("[CriteriaPreparer] Failed to parse gate extraction output: {}", e.getMessage());
            }
        }
        return List.of();
    }

    private double calculateCandidateYoe(String cvContent) {
        if (cvContent == null || cvContent.isBlank()) return 0.0;
        List<DateRange> ranges = extractDateRanges(cvContent);
        if (ranges.isEmpty()) return 0.0;

        ranges.sort(Comparator.comparing(r -> r.start));
        List<DateRange> merged = new ArrayList<>();
        DateRange current = null;

        for (DateRange r : ranges) {
            if (current == null) {
                current = new DateRange(r.start, r.end);
            } else if (!r.start.isAfter(current.end)) {
                if (r.end.isAfter(current.end)) current.end = r.end;
            } else {
                merged.add(current);
                current = new DateRange(r.start, r.end);
            }
        }
        if (current != null) merged.add(current);

        long totalDays = merged.stream().mapToLong(r -> ChronoUnit.DAYS.between(r.start, r.end)).sum();
        return Math.round((totalDays / 365.25) * 10.0) / 10.0;
    }

    private List<DateRange> extractDateRanges(String text) {
        List<DateRange> ranges = new ArrayList<>();
        Pattern pattern = Pattern.compile("(?i)(0[1-9]|1[0-2])[/-](\\d{4})\\s*(?:-|to|until|—)\\s*(Present|Now|Current|(?:0[1-9]|1[0-2])[/-](\\d{4}))");
        Matcher matcher = pattern.matcher(text);
        while (matcher.find()) {
            try {
                int startMonth = Integer.parseInt(matcher.group(1));
                int startYear = Integer.parseInt(matcher.group(2));
                LocalDate start = LocalDate.of(startYear, startMonth, 1);

                String endStr = matcher.group(3);
                LocalDate end;
                if (endStr.matches("(?i)Present|Now|Current")) {
                    end = LocalDate.now();
                } else {
                    int endMonth = Integer.parseInt(endStr.substring(0, 2));
                    int endYear = Integer.parseInt(matcher.group(4));
                    end = LocalDate.of(endYear, endMonth, 1);
                }
                if (!end.isBefore(start)) ranges.add(new DateRange(start, end));
            } catch (Exception ignored) {}
        }
        return ranges;
    }

    private double parseRequiredYoe(String reqVal) {
        if (reqVal == null) return 0.0;
        Matcher m = Pattern.compile("(\\d+(?:\\.\\d+)?)").matcher(reqVal);
        if (m.find()) {
            try { return Double.parseDouble(m.group(1)); } catch (Exception ignored) {}
        }
        return 0.0;
    }

    private boolean checkDegreeInCv(String cvContent) {
        if (cvContent == null) return false;
        String lower = cvContent.toLowerCase();
        return lower.contains("bachelor") || lower.contains("master") || lower.contains("degree") || lower.contains("cử nhân") || lower.contains("kỹ sư");
    }

    private Importance parseImportance(String imp) {
        if (imp == null) return Importance.REQUIRED;
        try { return Importance.valueOf(imp.toUpperCase()); } catch (Exception e) { return Importance.REQUIRED; }
    }

    // =========================================================================
    // 5. AD-HOC CRITERIA RECORDING
    // =========================================================================

    @Transactional
    public void recordAdHocCriteria(JobCategory jobCategory, List<AssessmentResponseDto.AdHocEvidenceItem> adHocItems) {
        if (adHocItems == null || adHocItems.isEmpty()) return;

        Map<String, AssessmentResponseDto.AdHocEvidenceItem> uniqueItems = new LinkedHashMap<>();
        for (AssessmentResponseDto.AdHocEvidenceItem item : adHocItems) {
            if (item != null && item.criteriaName() != null && !item.criteriaName().isBlank()) {
                uniqueItems.putIfAbsent(item.criteriaName().trim().toLowerCase(), item);
            }
        }

        for (AssessmentResponseDto.AdHocEvidenceItem item : uniqueItems.values()) {
            String cleanName = item.criteriaName().trim();
            try {
                suggestedCriteriaRepository.findByJobCategoryAndCriteriaNameIgnoreCase(jobCategory, cleanName)
                        .ifPresentOrElse(
                                existing -> {
                                    existing.setOccurrenceCount(existing.getOccurrenceCount() + 1);
                                    existing.setLastSeenAt(LocalDateTime.now());
                                    if (item.jdRequirement() != null &&
                                            (existing.getSampleJdText() == null || item.jdRequirement().length() > existing.getSampleJdText().length())) {
                                        existing.setSampleJdText(item.jdRequirement());
                                    }
                                    suggestedCriteriaRepository.save(existing);
                                },
                                () -> {
                                    SuggestedCriteria newCriteria = SuggestedCriteria.builder()
                                            .jobCategory(jobCategory)
                                            .criteriaName(cleanName)
                                            .occurrenceCount(1)
                                            .lastSeenAt(LocalDateTime.now())
                                            .sampleJdText(item.jdRequirement())
                                            .promoted(false)
                                            .build();
                                    suggestedCriteriaRepository.saveAndFlush(newCriteria);
                                }
                        );
            } catch (Exception e) {
                log.warn("[CriteriaPreparer] Duplicate constraint conflict recording ad-hoc criteria '{}': {}", cleanName, e.getMessage());
            }
        }
    }

    // Helper classes
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

    private static class DateRange {
        LocalDate start; LocalDate end;
        DateRange(LocalDate start, LocalDate end) { this.start = start; this.end = end; }
    }

    private static <T> List<List<T>> partitionList(List<T> list, int size) {
        List<List<T>> partitions = new ArrayList<>();
        for (int i = 0; i < list.size(); i += size) {
            partitions.add(list.subList(i, Math.min(i + size, list.size())));
        }
        return partitions;
    }

    private void sleepQuietly(long ms) {
        try { Thread.sleep(ms); } catch (InterruptedException ie) { Thread.currentThread().interrupt(); }
    }

    @JsonIgnoreProperties(ignoreUnknown = true)
    private record RawMetadataDto(
            @JsonProperty("category") String category,
            @JsonProperty("accepted_levels") List<String> acceptedLevels,
            @JsonProperty("level") String level // For backwards compatibility
    ) {}
}
