package fit.iuh.modules.assessment.service.impl;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import fit.iuh.config.AppProperties;
import fit.iuh.config.PromptTemplateConfig;
import fit.iuh.dto.chat.LlmChatRequest;
import fit.iuh.dto.chat.LlmChatResponse;
import fit.iuh.exception.LlmApiException;
import fit.iuh.modules.admin.repository.SystemSettingRepository;
import fit.iuh.modules.assessment.dto.*;
import fit.iuh.modules.assessment.entity.Eligibility;
import fit.iuh.modules.assessment.entity.ResumeAssessment;
import fit.iuh.modules.assessment.repository.ResumeAssessmentRepository;
import fit.iuh.modules.assessment.service.*;
import fit.iuh.modules.assessment.service.ScoringService.ScoringResult;
import fit.iuh.modules.ingestion.entity.DocumentType;
import fit.iuh.modules.ingestion.entity.SessionDocument;
import fit.iuh.modules.ingestion.repository.SessionDocumentRepository;
import fit.iuh.modules.rulengine.repository.JobCriteriaRepository;
import fit.iuh.modules.rulengine.repository.JobCriteriaRepository.CriteriaWeightProjection;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Qualifier;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.reactive.function.client.WebClient;
import org.springframework.web.reactive.function.client.WebClientResponseException;

import java.util.*;
import java.util.concurrent.CompletableFuture;
import java.util.concurrent.Semaphore;
import java.util.concurrent.TimeUnit;
import java.util.stream.Collectors;

@Slf4j
@Service
public class AssessmentServiceImpl implements AssessmentService {

    private static final Map<String, String> JSON_RESPONSE_FORMAT = Map.of("type", "json_object");

    private final AppProperties appProperties;
    private final WebClient llmWebClient;
    private final ResumeAssessmentRepository resumeAssessmentRepository;
    private final SessionDocumentRepository sessionDocumentRepository;
    private final MetadataExtractionService metadataExtractionService;
    private final JobCriteriaRepository jobCriteriaRepository;
    private final ScoringService scoringService;
    private final SuggestedCriteriaService suggestedCriteriaService;
    private final GateExtractionService gateExtractionService;
    private final ObjectMapper objectMapper;
    private final SystemSettingRepository systemSettingRepository;
    private final EvidenceGroundingValidator evidenceGroundingValidator;
    private final fit.iuh.modules.chunking.service.RetrievalService retrievalService;

    private final Semaphore globalLlmSemaphore = new Semaphore(10, true);

    public AssessmentServiceImpl(
            AppProperties appProperties,
            @Qualifier("llmWebClient") WebClient llmWebClient,
            ResumeAssessmentRepository resumeAssessmentRepository,
            SessionDocumentRepository sessionDocumentRepository,
            MetadataExtractionService metadataExtractionService,
            JobCriteriaRepository jobCriteriaRepository,
            ScoringService scoringService,
            SuggestedCriteriaService suggestedCriteriaService,
            GateExtractionService gateExtractionService,
            ObjectMapper objectMapper,
            SystemSettingRepository systemSettingRepository,
            EvidenceGroundingValidator evidenceGroundingValidator,
            fit.iuh.modules.chunking.service.RetrievalService retrievalService) {
        this.appProperties = appProperties;
        this.llmWebClient = llmWebClient;
        this.resumeAssessmentRepository = resumeAssessmentRepository;
        this.sessionDocumentRepository = sessionDocumentRepository;
        this.metadataExtractionService = metadataExtractionService;
        this.jobCriteriaRepository = jobCriteriaRepository;
        this.scoringService = scoringService;
        this.suggestedCriteriaService = suggestedCriteriaService;
        this.gateExtractionService = gateExtractionService;
        this.objectMapper = objectMapper;
        this.systemSettingRepository = systemSettingRepository;
        this.evidenceGroundingValidator = evidenceGroundingValidator;
        this.retrievalService = retrievalService;
    }

    @Override
    @Transactional
    public AssessmentResponse assessResumeBlocking(String sessionId, boolean forceRefresh) {
        return assessResumeBlocking(sessionId, forceRefresh, null, null);
    }

    @Override
    @Transactional
    public AssessmentResponse assessResumeBlocking(String sessionId, boolean forceRefresh, String fromSessionId) {
        return assessResumeBlocking(sessionId, forceRefresh, fromSessionId, null);
    }

    @Override
    @Transactional
    public AssessmentResponse assessResumeBlocking(String sessionId, boolean forceRefresh, String fromSessionId, Boolean includeNotApplicable) {
        log.info("[Assessment] Request for sessionId={}, forceRefresh={}, fromSessionId={}, includeNotApplicable={}", sessionId, forceRefresh, fromSessionId, includeNotApplicable);

        if (!forceRefresh) {
            var cached = resumeAssessmentRepository.findBySessionId(sessionId);
            if (cached.isPresent()) {
                log.info("[Assessment] Cache HIT for sessionId={}", sessionId);
                return toResponse(cached.get(), true);
            }

            if (fromSessionId != null && !fromSessionId.isBlank()) {
                var otherAssessmentOpt = resumeAssessmentRepository.findBySessionId(fromSessionId);
                if (otherAssessmentOpt.isPresent()) {
                    var otherAssessment = otherAssessmentOpt.get();
                    log.info("[Assessment] Direct Cache HIT by fromSessionId! Reusing assessment from sessionId={} for new sessionId={}", fromSessionId, sessionId);

                    ResumeAssessment clonedAssessment = ResumeAssessment.builder()
                            .sessionId(sessionId)
                            .jobCategory(otherAssessment.getJobCategory())
                            .seniorityLevel(otherAssessment.getSeniorityLevel())
                            .overallMatchScore(otherAssessment.getOverallMatchScore())
                            .evidenceItems(otherAssessment.getEvidenceItems())
                            .additionalEvidenceItems(otherAssessment.getAdditionalEvidenceItems())
                            .topPriorityImprovements(otherAssessment.getTopPriorityImprovements())
                            .eligibility(otherAssessment.getEligibility())
                            .build();

                    ResumeAssessment savedCloned = resumeAssessmentRepository.save(clonedAssessment);

                    List<CriteriaWeightProjection> criteriaList = jobCriteriaRepository.findCriteriaTreeByCategory(
                            clonedAssessment.getJobCategory().name(),
                            clonedAssessment.getSeniorityLevel().name()
                    );
                    if (criteriaList.isEmpty()) {
                        criteriaList = jobCriteriaRepository.findCriteriaTreeByCategory("SOFTWARE_ENGINEERING", "ALL");
                    }
                    ScoringResult scoringResult = scoringService.calculateWithBreakdown(
                            clonedAssessment.getEvidenceItems(),
                            clonedAssessment.getAdditionalEvidenceItems(),
                            criteriaList,
                            clonedAssessment.getSeniorityLevel()
                    );

                    AssessmentResponse response = toResponse(savedCloned, true);
                    response.setScoreBreakdown(scoringResult.breakdown());
                    return response;
                }
            }

            Optional<SessionDocument> cvDocOpt = sessionDocumentRepository.findBySessionIdAndDocumentType(sessionId, DocumentType.CV);
            Optional<SessionDocument> jdDocOpt = sessionDocumentRepository.findBySessionIdAndDocumentType(sessionId, DocumentType.JD);
            if (cvDocOpt.isPresent() && jdDocOpt.isPresent()) {
                String cvContent = cvDocOpt.get().getMarkdownContent();
                String jdContent = jdDocOpt.get().getMarkdownContent();
                Optional<String> otherSessionIdOpt = sessionDocumentRepository.findSessionWithSameContentAndAssessment(cvContent, jdContent, sessionId);
                if (otherSessionIdOpt.isPresent()) {
                    String otherSessionId = otherSessionIdOpt.get();
                    log.info("[Assessment] Content-based Cache HIT! Reusing assessment from sessionId={} for new sessionId={}", otherSessionId, sessionId);

                    var otherAssessment = resumeAssessmentRepository.findBySessionId(otherSessionId).get();

                    ResumeAssessment clonedAssessment = ResumeAssessment.builder()
                            .sessionId(sessionId)
                            .jobCategory(otherAssessment.getJobCategory())
                            .seniorityLevel(otherAssessment.getSeniorityLevel())
                            .overallMatchScore(otherAssessment.getOverallMatchScore())
                            .evidenceItems(otherAssessment.getEvidenceItems())
                            .additionalEvidenceItems(otherAssessment.getAdditionalEvidenceItems())
                            .topPriorityImprovements(otherAssessment.getTopPriorityImprovements())
                            .eligibility(otherAssessment.getEligibility())
                            .build();

                    ResumeAssessment savedCloned = resumeAssessmentRepository.save(clonedAssessment);

                    List<CriteriaWeightProjection> criteriaList = jobCriteriaRepository.findCriteriaTreeByCategory(
                            clonedAssessment.getJobCategory().name(),
                            clonedAssessment.getSeniorityLevel().name()
                    );
                    if (criteriaList.isEmpty()) {
                        criteriaList = jobCriteriaRepository.findCriteriaTreeByCategory("SOFTWARE_ENGINEERING", "ALL");
                    }
                    ScoringResult scoringResult = scoringService.calculateWithBreakdown(
                            clonedAssessment.getEvidenceItems(),
                            clonedAssessment.getAdditionalEvidenceItems(),
                            criteriaList,
                            clonedAssessment.getSeniorityLevel()
                    );

                    AssessmentResponse response = toResponse(savedCloned, true);
                    response.setScoreBreakdown(scoringResult.breakdown());
                    return response;
                }
            }
        } else if (resumeAssessmentRepository.existsBySessionId(sessionId)) {
            log.warn("[Assessment] Force-refresh for sessionId={}. Deleting cached result.", sessionId);
            resumeAssessmentRepository.deleteBySessionId(sessionId);
            resumeAssessmentRepository.flush();
        }

        long startPipeline = System.currentTimeMillis();

        SessionDocument cvDoc = sessionDocumentRepository
                .findBySessionIdAndDocumentType(sessionId, DocumentType.CV)
                .orElseThrow(() -> new LlmApiException(
                        "No CV found for session '" + sessionId + "'. Please ingest files first."));

        SessionDocument jdDoc = sessionDocumentRepository
                .findBySessionIdAndDocumentType(sessionId, DocumentType.JD)
                .orElseThrow(() -> new LlmApiException(
                        "No JD found for session '" + sessionId + "'. Please ingest files first."));

        String fullCvMarkdown = cvDoc.getMarkdownContent();
        String fullJdMarkdown = jdDoc.getMarkdownContent();

        long startMetadata = System.currentTimeMillis();
        MetadataExtractionService.ExtractionResult metadata =
                metadataExtractionService.extract(fullJdMarkdown);
        long tMetadata = System.currentTimeMillis() - startMetadata;

        List<CriteriaWeightProjection> criteriaList = jobCriteriaRepository
                .findCriteriaTreeByCategory(
                        metadata.category().name(),
                        metadata.level().name()
                );

        if (criteriaList.isEmpty()) {
            criteriaList = jobCriteriaRepository
                    .findCriteriaTreeByCategory("SOFTWARE_ENGINEERING", "ALL");
        }

        // Determine if we should include NOT_APPLICABLE criteria (360 degree audit vs strict JD matching)
        boolean shouldIncludeNotApp = includeNotApplicable != null
                ? includeNotApplicable
                : (systemSettingRepository != null && systemSettingRepository.getBoolean("INCLUDE_NOT_APPLICABLE_CRITERIA", false));

        // PRE-FILTERING: If strict JD matching, pre-filter criteria list BEFORE LLM calls!
        if (!shouldIncludeNotApp) {
            List<CriteriaWeightProjection> preFiltered = preFilterCriteriaForJd(fullJdMarkdown, criteriaList);
            log.info("[Assessment] PRE-FILTERING: Reduced criteria count from {} down to {} for JD matching (sessionId={})",
                    criteriaList.size(), preFiltered.size(), sessionId);
            if (!preFiltered.isEmpty()) {
                criteriaList = preFiltered;
            }
        }

        long startBatches = System.currentTimeMillis();
        AssessmentResponseDto dto = runBatchedAssessmentWithSelfConsistency(
                sessionId,
                fullCvMarkdown,
                fullJdMarkdown,
                criteriaList
        );
        long tLlmbatch = System.currentTimeMillis() - startBatches;

        List<AssessmentResponseDto.AdHocEvidenceItem> filteredAdHoc = filterDuplicateAdHocItems(
                dto.evidenceItems(),
                dto.additionalEvidenceItems()
        );
        dto = new AssessmentResponseDto(dto.evidenceItems(), filteredAdHoc);

        if (!shouldIncludeNotApp) {
            List<AssessmentResponseDto.EvidenceItem> filteredEvidence = dto.evidenceItems() != null
                    ? dto.evidenceItems().stream()
                            .filter(item -> item != null
                                    && !"NOT_APPLICABLE".equalsIgnoreCase(item.importance())
                                    && !"not_applicable".equalsIgnoreCase(item.status()))
                            .collect(Collectors.toList())
                    : List.of();

            List<AssessmentResponseDto.AdHocEvidenceItem> filteredAdHocList = dto.additionalEvidenceItems() != null
                    ? dto.additionalEvidenceItems().stream()
                            .filter(item -> item != null
                                    && !"NOT_APPLICABLE".equalsIgnoreCase(item.importance())
                                    && !"not_applicable".equalsIgnoreCase(item.status()))
                            .collect(Collectors.toList())
                    : List.of();

            dto = new AssessmentResponseDto(filteredEvidence, filteredAdHocList);
        }

        ScoringResult scoringResult = scoringService.calculateWithBreakdown(
                dto.evidenceItems(),
                dto.additionalEvidenceItems(),
                criteriaList,
                metadata.level()
        );

        long startGate = System.currentTimeMillis();
        Eligibility eligibility = gateExtractionService.evaluateEligibility(fullJdMarkdown, fullCvMarkdown);
        long tGate = System.currentTimeMillis() - startGate;

        try {
            suggestedCriteriaService.recordAdHocCriteria(metadata.category(), dto.additionalEvidenceItems());
        } catch (Exception e) {
            log.warn("[Assessment] Non-blocking warning recording ad-hoc criteria: {}", e.getMessage());
        }

        // Audit source_span reuse count (Rule 2)
        Map<String, Integer> spanUsageMap = new HashMap<>();
        List<AssessmentResponseDto.EvidenceItem> auditedEvidence = new ArrayList<>();

        if (scoringResult.evidenceItems() != null) {
            for (var item : scoringResult.evidenceItems()) {
                String span = item.sourceSpan() != null ? item.sourceSpan().trim() : null;
                boolean needsReview = Boolean.TRUE.equals(item.needsManualReview());
                double finalScoreContrib = item.scoreContribution() != null ? item.scoreContribution() : 0.0;

                if (span != null && !span.isEmpty()) {
                    int count = spanUsageMap.getOrDefault(span, 0) + 1;
                    spanUsageMap.put(span, count);

                    if (count >= 3) {
                        needsReview = true;
                        finalScoreContrib = finalScoreContrib * 0.5; // penalize 3rd+ reuse
                        log.debug("[SpanAudit] source_span reused {} times for criterion '{}'. Flagged needs_manual_review and halved score_contribution.", count, item.criteriaName());
                    }
                }

                auditedEvidence.add(new AssessmentResponseDto.EvidenceItem(
                        item.criteriaId(),
                        item.criteriaName(),
                        item.importance(),
                        item.jdRequirement(),
                        item.cvEvidence(),
                        item.status(),
                        item.reasoning(),
                        item.weightUsed(),
                        finalScoreContrib,
                        item.sourceSpan(),
                        item.groundingScore(),
                        item.confidenceVotes(),
                        item.lowConfidence(),
                        needsReview
                ));
            }
        }

        ScoringResult auditedScoringResult = new ScoringResult(
                scoringResult.score(),
                scoringResult.breakdown(),
                auditedEvidence
        );

        List<Map<String, String>> weaknesses = new ArrayList<>();
        if (auditedScoringResult.evidenceItems() != null) {
            for (var item : auditedScoringResult.evidenceItems()) {
                boolean isNotApp = "NOT_APPLICABLE".equalsIgnoreCase(item.importance()) || "not_applicable".equalsIgnoreCase(item.status());
                if (!isNotApp && ("weak".equalsIgnoreCase(item.status()) || "missing".equalsIgnoreCase(item.status()))) {
                    weaknesses.add(Map.of("criteria_name", item.criteriaName(), "status", item.status(), "cv_evidence", item.cvEvidence() == null ? "" : item.cvEvidence()));
                }
            }
        }
        if (dto.additionalEvidenceItems() != null) {
            for (var item : dto.additionalEvidenceItems()) {
                boolean isNotApp = "NOT_APPLICABLE".equalsIgnoreCase(item.importance()) || "not_applicable".equalsIgnoreCase(item.status());
                if (!isNotApp && ("weak".equalsIgnoreCase(item.status()) || "missing".equalsIgnoreCase(item.status()))) {
                    weaknesses.add(Map.of("criteria_name", item.criteriaName(), "status", item.status(), "cv_evidence", item.cvEvidence() == null ? "" : item.cvEvidence()));
                }
            }
        }

        long startAdvisor = System.currentTimeMillis();
        List<ImprovementResponseDto.ImprovementItem> improvements = List.of();
        if (!weaknesses.isEmpty()) {
            try {
                String weaknessJson = objectMapper.writeValueAsString(weaknesses);
                String phase2SystemPrompt = PromptTemplateConfig.SYSTEM_PROMPT_IMPROVEMENT_ADVISOR;
                String phase2UserPrompt = PromptTemplateConfig.buildImprovementUserPrompt(weaknessJson);

                int maxAttempts = 3;
                ImprovementResponseDto phase2Dto = null;
                for (int attempt = 1; attempt <= maxAttempts; attempt++) {
                    try {
                        String phase2Response = callLlmBlocking(phase2SystemPrompt, phase2UserPrompt);
                        phase2Dto = parseImprovementDto(sessionId, phase2Response);
                        break;
                    } catch (Exception e) {
                        if (attempt >= maxAttempts) {
                            throw e;
                        }
                    }
                }

                if (phase2Dto != null) {
                    improvements = phase2Dto.topPriorityImprovements();
                }
            } catch (Exception e) {
                log.warn("[Assessment] Phase 2 advisor fallback due to: {}", e.getMessage());
            }
        }
        long tAdvisor = System.currentTimeMillis() - startAdvisor;

        long totalPipelineMs = System.currentTimeMillis() - startPipeline;
        log.info("=== [PERF ASSESSMENT] sessionId={} | category={} | level={} | score={} | total={}ms (Metadata={}ms, LLMBatches={}ms, GateCheck={}ms, Advisor={}ms) ===",
                sessionId, metadata.category(), metadata.level(), auditedScoringResult.score(), totalPipelineMs, tMetadata, tLlmbatch, tGate, tAdvisor);

        ResumeAssessment entity = buildAndPersistEntity(
                sessionId,
                metadata,
                auditedScoringResult.score(),
                dto,
                auditedScoringResult.evidenceItems(),
                improvements,
                eligibility
        );
        AssessmentResponse response = toResponse(entity, false);
        response.setScoreBreakdown(auditedScoringResult.breakdown());
        return response;
    }

    @Override
    public AssessmentResponseDto runBatchedAssessmentWithSelfConsistency(
            String sessionId,
            String fullCvMarkdown,
            String fullJdMarkdown,
            List<CriteriaWeightProjection> criteriaList) {

        int batchSize = systemSettingRepository != null ? systemSettingRepository.getInt("CRITERIA_BATCH_SIZE", 5) : 5;
        int selfConsistencyRuns = systemSettingRepository != null ? systemSettingRepository.getInt("SELF_CONSISTENCY_RUNS", 1) : 1;
        double groundingThreshold = systemSettingRepository != null ? systemSettingRepository.getDouble("EVIDENCE_GROUNDING_THRESHOLD", 0.75) : 0.75;

        List<List<CriteriaWeightProjection>> batches = partitionCriteria(criteriaList, batchSize);
        log.info("[Assessment] Processing {} criteria in {} batches (batch_size={}, self_consistency_runs={})...",
                criteriaList.size(), batches.size(), batchSize, selfConsistencyRuns);

        List<AssessmentResponseDto.EvidenceItem> aggregatedEvidenceItems = new ArrayList<>();
        List<AssessmentResponseDto.AdHocEvidenceItem> aggregatedAdHocItems = new ArrayList<>();

        List<CompletableFuture<BatchResult>> batchFutures = new ArrayList<>();
        for (int i = 0; i < batches.size(); i++) {
            final int batchIndex = i + 1;
            final List<CriteriaWeightProjection> batchCriteria = batches.get(i);

            CompletableFuture<BatchResult> future = CompletableFuture.supplyAsync(() ->
                    processBatchWithSelfConsistency(sessionId, fullCvMarkdown, fullJdMarkdown, batchCriteria, batchIndex, batches.size(), selfConsistencyRuns)
            );
            batchFutures.add(future);
        }

        CompletableFuture.allOf(batchFutures.toArray(new CompletableFuture[0])).join();

        for (CompletableFuture<BatchResult> f : batchFutures) {
            BatchResult res = f.join();
            if (res != null) {
                if (res.evidenceItems() != null) {
                    aggregatedEvidenceItems.addAll(res.evidenceItems());
                }
                if (res.adHocItems() != null) {
                    aggregatedAdHocItems.addAll(res.adHocItems());
                }
            }
        }

        List<AssessmentResponseDto.EvidenceItem> groundedItems = new ArrayList<>();
        for (AssessmentResponseDto.EvidenceItem item : aggregatedEvidenceItems) {
            AssessmentResponseDto.EvidenceItem grounded = evidenceGroundingValidator != null
                    ? evidenceGroundingValidator.validateAndApply(item, fullCvMarkdown, groundingThreshold)
                    : item;
            groundedItems.add(grounded);
        }

        List<AssessmentResponseDto.AdHocEvidenceItem> distinctAdHoc = aggregatedAdHocItems.stream()
                .filter(Objects::nonNull)
                .filter(item -> item.criteriaName() != null)
                .collect(Collectors.toMap(
                        AssessmentResponseDto.AdHocEvidenceItem::criteriaName,
                        item -> item,
                        (existing, replacement) -> existing
                ))
                .values().stream().toList();

        return new AssessmentResponseDto(groundedItems, distinctAdHoc);
    }

    private record BatchResult(
            List<AssessmentResponseDto.EvidenceItem> evidenceItems,
            List<AssessmentResponseDto.AdHocEvidenceItem> adHocItems
    ) {}

    private BatchResult processBatchWithSelfConsistency(
            String sessionId,
            String fullCvMarkdown,
            String fullJdMarkdown,
            List<CriteriaWeightProjection> batchCriteria,
            int batchIndex,
            int totalBatches,
            int selfConsistencyRuns) {

        List<String> batchSkills = batchCriteria.stream()
                .map(CriteriaWeightProjection::getCriteriaName)
                .filter(Objects::nonNull)
                .toList();

        String cvContextToUse = fullCvMarkdown;
        if (retrievalService != null) {
            try {
                String retrieved = retrievalService.retrieveRelevantCvContext(sessionId, batchSkills, 5);
                if (retrieved != null && !retrieved.isBlank()) {
                    cvContextToUse = retrieved;
                    log.info("[Assessment] Batch {}/{} prompt using retrieved CV context ({} chars vs full {} chars)",
                            batchIndex, totalBatches, cvContextToUse.length(), fullCvMarkdown.length());
                }
            } catch (Exception e) {
                log.warn("[Assessment] Retrieval failed for batch {}/{}, falling back to full CV: {}",
                        batchIndex, totalBatches, e.getMessage());
            }
        }

        String criteriaInstructions = buildCriteriaInstructions(batchCriteria);
        String systemPrompt = PromptTemplateConfig.buildAssessmentSystemPrompt();
        String userPrompt = PromptTemplateConfig.buildAssessmentUserPrompt(cvContextToUse, fullJdMarkdown, criteriaInstructions);

        List<CompletableFuture<AssessmentResponseDto>> runFutures = new ArrayList<>();
        for (int r = 1; r <= selfConsistencyRuns; r++) {
            final int runIndex = r;
            CompletableFuture<AssessmentResponseDto> future = CompletableFuture.supplyAsync(() -> {
                int maxAttempts = 3;
                for (int attempt = 1; attempt <= maxAttempts; attempt++) {
                    try {
                        String llmJsonResponse = callLlmBlockingWithSemaphore(systemPrompt, userPrompt);
                        return parseAssessmentDto(sessionId, llmJsonResponse);
                    } catch (Exception e) {
                        log.warn("[Assessment] Batch {}/{} run {}/{} LLM call failed (attempt {}/{}): {}",
                                batchIndex, totalBatches, runIndex, selfConsistencyRuns, attempt, maxAttempts, e.getMessage());
                        if (attempt >= maxAttempts) {
                            return null;
                        }
                    }
                }
                return null;
            });
            runFutures.add(future);
        }

        CompletableFuture.allOf(runFutures.toArray(new CompletableFuture[0])).join();

        List<AssessmentResponseDto> successfulDtos = new ArrayList<>();
        for (var f : runFutures) {
            AssessmentResponseDto dto = f.join();
            if (dto != null && dto.evidenceItems() != null && !dto.evidenceItems().isEmpty()) {
                successfulDtos.add(dto);
            }
        }

        if (successfulDtos.isEmpty()) {
            log.warn("[BatchEngine] batch={}/{} | ALL_RUNS_FAILED | criteria_count={} | action=FALLBACK_MISSING_MANUAL_REVIEW",
                    batchIndex, totalBatches, batchCriteria.size());

            List<AssessmentResponseDto.EvidenceItem> fallbackItems = new ArrayList<>();
            for (CriteriaWeightProjection c : batchCriteria) {
                fallbackItems.add(new AssessmentResponseDto.EvidenceItem(
                        c.getCriteriaId(),
                        c.getCriteriaName(),
                        "REQUIRED",
                        c.getPromptInstruction(),
                        null,
                        "missing",
                        "Lỗi hệ thống khi gọi LLM batch. Cần kiểm tra thủ công.",
                        null,
                        null,
                        null,
                        1.0,
                        Map.of("missing", 0),
                        false,
                        true
                ));
            }
            return new BatchResult(fallbackItems, List.of());
        }

        List<AssessmentResponseDto.EvidenceItem> aggregatedBatchItems = new ArrayList<>();
        List<AssessmentResponseDto.AdHocEvidenceItem> batchAdHoc = new ArrayList<>();

        for (CriteriaWeightProjection c : batchCriteria) {
            Map<String, Integer> votes = new HashMap<>();
            votes.put("matched", 0);
            votes.put("weak", 0);
            votes.put("missing", 0);

            Map<String, AssessmentResponseDto.EvidenceItem> statusToSampleItem = new HashMap<>();

            for (AssessmentResponseDto dto : successfulDtos) {
                if (dto.additionalEvidenceItems() != null) {
                    batchAdHoc.addAll(dto.additionalEvidenceItems());
                }
                for (AssessmentResponseDto.EvidenceItem item : dto.evidenceItems()) {
                    if (Objects.equals(item.criteriaId(), c.getCriteriaId())) {
                        String st = item.status() != null ? item.status().toLowerCase(Locale.ROOT) : "missing";
                        if (!votes.containsKey(st)) {
                            st = "missing";
                        }
                        votes.put(st, votes.get(st) + 1);
                        statusToSampleItem.putIfAbsent(st, item);
                    }
                }
            }

            int maxVotes = Collections.max(votes.values());
            List<String> tiedStatuses = votes.entrySet().stream()
                    .filter(e -> e.getValue() == maxVotes)
                    .map(Map.Entry::getKey)
                    .toList();

            String winningStatus;
            boolean lowConfidence;

            if (tiedStatuses.size() == 1) {
                winningStatus = tiedStatuses.get(0);
                lowConfidence = false;
            } else {
                if (tiedStatuses.contains("missing")) {
                    winningStatus = "missing";
                } else if (tiedStatuses.contains("weak")) {
                    winningStatus = "weak";
                } else {
                    winningStatus = "matched";
                }
                lowConfidence = true;
            }

            AssessmentResponseDto.EvidenceItem sampleItem = statusToSampleItem.get(winningStatus);
            if (sampleItem == null && !statusToSampleItem.isEmpty()) {
                sampleItem = statusToSampleItem.values().iterator().next();
            }

            String importance = (sampleItem != null && sampleItem.importance() != null && !sampleItem.importance().isBlank())
                    ? sampleItem.importance() : "REQUIRED";
            String jdReq = sampleItem != null ? sampleItem.jdRequirement() : c.getPromptInstruction();
            String cvEv = sampleItem != null ? sampleItem.cvEvidence() : null;
            String reasoning = sampleItem != null ? sampleItem.reasoning() : "Xác định từ cơ chế Self-Consistency majority vote.";
            String sourceSpan = sampleItem != null ? sampleItem.sourceSpan() : null;

            aggregatedBatchItems.add(new AssessmentResponseDto.EvidenceItem(
                    c.getCriteriaId(),
                    c.getCriteriaName(),
                    importance,
                    jdReq,
                    cvEv,
                    winningStatus,
                    reasoning,
                    null,
                    null,
                    sourceSpan,
                    null,
                    votes,
                    lowConfidence,
                    false
            ));
        }

        return new BatchResult(aggregatedBatchItems, batchAdHoc);
    }

    private List<List<CriteriaWeightProjection>> partitionCriteria(List<CriteriaWeightProjection> list, int maxBatchSize) {
        List<List<CriteriaWeightProjection>> partitions = new ArrayList<>();
        if (list == null || list.isEmpty()) {
            return partitions;
        }

        int totalRules = list.size();
        if (maxBatchSize <= 0 || totalRules <= maxBatchSize) {
            partitions.add(list);
            return partitions;
        }

        int numBatches = (int) Math.ceil((double) totalRules / maxBatchSize);
        int baseSize = totalRules / numBatches;
        int remainder = totalRules % numBatches;

        int currentIndex = 0;
        for (int i = 0; i < numBatches; i++) {
            int currentBatchSize = baseSize + (i < remainder ? 1 : 0);
            int nextIndex = currentIndex + currentBatchSize;
            partitions.add(list.subList(currentIndex, Math.min(nextIndex, totalRules)));
            currentIndex = nextIndex;
        }

        return partitions;
    }

    private String buildCriteriaInstructions(List<CriteriaWeightProjection> criteria) {
        StringBuilder sb = new StringBuilder();
        for (int i = 0; i < criteria.size(); i++) {
            CriteriaWeightProjection c = criteria.get(i);
            sb.append(String.format(
                    "- Criteria ID: %d (Weight: %.1f%%) — %s%n%s%n%n",
                    c.getCriteriaId(),
                    c.getWeightPercentage(),
                    c.getCriteriaName(),
                    c.getPromptInstruction()
            ));
        }
        return sb.toString().strip();
    }

    private String callLlmBlockingWithSemaphore(String systemPrompt, String userPrompt) {
        boolean acquired = false;
        try {
            acquired = globalLlmSemaphore.tryAcquire(60, TimeUnit.SECONDS);
            if (!acquired) {
                throw new LlmApiException("System LLM concurrency limit reached. Please try again later.");
            }
            return callLlmBlocking(systemPrompt, userPrompt);
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
            throw new LlmApiException("Interrupted waiting for LLM concurrency permit.", e);
        } finally {
            if (acquired) {
                globalLlmSemaphore.release();
            }
        }
    }

    private String callLlmBlocking(String systemPrompt, String userPrompt) {
        LlmChatRequest request = LlmChatRequest.builder()
                .model(appProperties.getLlm().getModel())
                .maxTokens(appProperties.getLlm().getMaxTokens())
                .temperature(0.0)
                .stream(false)
                .responseFormat(JSON_RESPONSE_FORMAT)
                .messages(List.of(
                        LlmChatRequest.Message.system(systemPrompt),
                        LlmChatRequest.Message.user(userPrompt)
                ))
                .build();

        int maxRetries = 3;
        for (int i = 0; i <= maxRetries; i++) {
            try {
                String responseBody = llmWebClient.post()
                        .uri(appProperties.getLlm().getChatPath())
                        .bodyValue(request)
                        .retrieve()
                        .bodyToMono(String.class)
                        .block();

                if (responseBody == null || responseBody.isBlank()) {
                    throw new LlmApiException("LLM API returned empty HTTP body during assessment.");
                }

                log.debug("[Assessment] Raw HTTP response body: {}", responseBody);

                if (responseBody.contains("\"error\"") && (responseBody.contains("\"message\"") || responseBody.contains("\"code\""))) {
                    throw new LlmApiException("LLM API returned error JSON during assessment: " + responseBody);
                }

                LlmChatResponse response = objectMapper.readValue(responseBody, LlmChatResponse.class);

                if (response == null || response.getFirstChoiceContent() == null) {
                    throw new LlmApiException("LLM API returned empty assessment response. Response: " + responseBody);
                }

                if (response.getUsage() != null) {
                    var usage = response.getUsage();
                    log.info("[LLM_USAGE] Model={} | Input={} | Output={} | Total={}",
                            response.getModel(),
                            usage.getPromptTokens(),
                            usage.getCompletionTokens(),
                            usage.getTotalTokens());
                }

                return response.getFirstChoiceContent().strip();

            } catch (WebClientResponseException e) {
                if (e.getStatusCode().value() == 429 && i < maxRetries) {
                    log.warn("[Assessment] LLM 429 — retrying after 35s...");
                    sleepQuietly(35_000);
                    continue;
                }
                throw new LlmApiException("LLM HTTP " + e.getStatusCode() + ": " + e.getResponseBodyAsString(), e);
            } catch (LlmApiException e) {
                throw e;
            } catch (Exception e) {
                throw new LlmApiException("Unexpected error calling LLM: " + e.getMessage(), e);
            }
        }
        throw new LlmApiException("Max retries exceeded for assessment LLM call.");
    }

    private AssessmentResponseDto parseAssessmentDto(String sessionId, String llmJsonResponse) {
        String json = extractCleanJson(llmJsonResponse);

        try {
            AssessmentResponseDto dto = objectMapper.readValue(json, AssessmentResponseDto.class);
            if (dto.evidenceItems() == null || dto.evidenceItems().isEmpty()) {
                throw new LlmApiException("LLM response missing 'evidence_items' for sessionId=" + sessionId);
            }
            return dto;
        } catch (JsonProcessingException e) {
            log.error("[Assessment] Failed to parse LLM JSON for sessionId={}: {}\nRaw: {}", sessionId, e.getMessage(), json);
            throw new LlmApiException("LLM returned invalid JSON for sessionId=" + sessionId + ": " + e.getMessage(), e);
        }
    }

    private ImprovementResponseDto parseImprovementDto(String sessionId, String llmJsonResponse) {
        String json = extractCleanJson(llmJsonResponse);

        try {
            return objectMapper.readValue(json, ImprovementResponseDto.class);
        } catch (JsonProcessingException e) {
            log.error("[Assessment] Phase 2 failed to parse LLM JSON for sessionId={}: {}\nRaw: {}", sessionId, e.getMessage(), json);
            throw new LlmApiException("Phase 2 LLM returned invalid JSON for sessionId=" + sessionId + ": " + e.getMessage(), e);
        }
    }

    private String extractCleanJson(String rawResponse) {
        if (rawResponse == null) return "";
        String text = rawResponse.replaceAll("(?s)<think>.*?</think>", "").strip();

        int firstBrace = text.indexOf('{');
        int lastBrace = text.lastIndexOf('}');
        if (firstBrace >= 0 && lastBrace > firstBrace) {
            return text.substring(firstBrace, lastBrace + 1).strip();
        }
        return text;
    }

    @Transactional
    protected ResumeAssessment buildAndPersistEntity(
            String sessionId,
            MetadataExtractionService.ExtractionResult metadata,
            int overallMatchScore,
            AssessmentResponseDto dto,
            List<AssessmentResponseDto.EvidenceItem> populatedEvidenceItems,
            List<ImprovementResponseDto.ImprovementItem> improvements,
            Eligibility eligibility) {

        ResumeAssessment entity = ResumeAssessment.builder()
                .sessionId(sessionId)
                .jobCategory(metadata.category())
                .seniorityLevel(metadata.level())
                .overallMatchScore(overallMatchScore)
                .evidenceItems(populatedEvidenceItems)
                .additionalEvidenceItems(dto.additionalEvidenceItems())
                .topPriorityImprovements(improvements)
                .eligibility(eligibility)
                .build();

        ResumeAssessment saved = resumeAssessmentRepository.save(entity);
        log.info("[Assessment] Persisted ResumeAssessment id={} for sessionId={} | score={}", saved.getId(), sessionId, saved.getOverallMatchScore());
        return saved;
    }

    private AssessmentResponse toResponse(ResumeAssessment entity, boolean cached) {
        return AssessmentResponse.builder()
                .id(entity.getId())
                .sessionId(entity.getSessionId())
                .jobCategory(entity.getJobCategory())
                .seniorityLevel(entity.getSeniorityLevel())
                .overallMatchScore(entity.getOverallMatchScore())
                .evidenceItems(entity.getEvidenceItems())
                .additionalEvidenceItems(entity.getAdditionalEvidenceItems())
                .topPriorityImprovements(entity.getTopPriorityImprovements())
                .eligibility(entity.getEligibility())
                .cached(cached)
                .createdAt(entity.getCreatedAt())
                .build();
    }

    @Override
    public String evaluateSession(InterviewEvaluationRequest request) {
        StringBuilder userPrompt = new StringBuilder();
        userPrompt.append("Vị trí ứng tuyển: ").append(request.roleTitle()).append("\n");
        userPrompt.append("Thể loại phỏng vấn: ").append(request.interviewType()).append("\n\n");
        userPrompt.append("Chi tiết các câu hỏi và câu trả lời:\n");

        List<QuestionAnswerDto> turns = request.turns();
        for (int i = 0; i < turns.size(); i++) {
            QuestionAnswerDto t = turns.get(i);
            userPrompt.append("CÂU HỎI ").append(i + 1).append(":\n");
            userPrompt.append("Hỏi: ").append(t.question()).append("\n");
            userPrompt.append("Trả lời: ")
                    .append(t.answer() != null && !t.answer().trim().isEmpty() ? t.answer() : "[Không trả lời]")
                    .append("\n");
            userPrompt.append("Điểm sơ bộ: ").append(t.score() != null ? t.score() : 0).append("/10\n\n");
        }

        LlmChatRequest llmRequest = LlmChatRequest.builder()
                .model(appProperties.getLlm().getModel())
                .maxTokens(appProperties.getLlm().getMaxTokens())
                .temperature(0.3)
                .stream(false)
                .responseFormat(JSON_RESPONSE_FORMAT)
                .messages(List.of(
                        LlmChatRequest.Message.system(PromptTemplateConfig.SYSTEM_PROMPT_INTERVIEW_EVALUATION),
                        LlmChatRequest.Message.user(userPrompt.toString())
                ))
                .build();

        LlmChatResponse response = llmWebClient.post()
                .uri(appProperties.getLlm().getChatPath())
                .bodyValue(llmRequest)
                .retrieve()
                .bodyToMono(LlmChatResponse.class)
                .block();

        if (response == null || response.getFirstChoiceContent() == null) {
            throw new LlmApiException("LLM returned empty evaluation response.");
        }
        return response.getFirstChoiceContent().strip();
    }

    private void sleepQuietly(long ms) {
        try {
            Thread.sleep(ms);
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
        }
    }

    private List<AssessmentResponseDto.AdHocEvidenceItem> filterDuplicateAdHocItems(
            List<AssessmentResponseDto.EvidenceItem> standardItems,
            List<AssessmentResponseDto.AdHocEvidenceItem> adHocItems) {

        if (adHocItems == null || adHocItems.isEmpty()) {
            return List.of();
        }

        List<AssessmentResponseDto.AdHocEvidenceItem> selfDeduplicated = deduplicateSelfAdHocItems(adHocItems);

        if (standardItems == null || standardItems.isEmpty()) {
            List<AssessmentResponseDto.AdHocEvidenceItem> sanitized = new ArrayList<>();
            for (var item : selfDeduplicated) {
                sanitized.add(sanitizeAdHocItem(item));
            }
            return sanitized;
        }

        List<AssessmentResponseDto.AdHocEvidenceItem> filtered = new ArrayList<>();
        for (var adHoc : selfDeduplicated) {
            if (adHoc == null || adHoc.criteriaName() == null || adHoc.criteriaName().isBlank()) {
                continue;
            }

            boolean duplicate = standardItems.stream()
                    .anyMatch(std -> isDuplicateCriteriaName(std.criteriaName(), adHoc.criteriaName()));

            if (!duplicate) {
                filtered.add(sanitizeAdHocItem(adHoc));
            } else {
                log.debug("[AdHocDeduplication] Filtered out duplicate ad-hoc criterion '{}' as it overlaps with standard criteria.", adHoc.criteriaName());
            }
        }
        return filtered;
    }

    private List<AssessmentResponseDto.AdHocEvidenceItem> deduplicateSelfAdHocItems(List<AssessmentResponseDto.AdHocEvidenceItem> items) {
        if (items == null || items.isEmpty()) return List.of();
        Map<String, AssessmentResponseDto.AdHocEvidenceItem> map = new LinkedHashMap<>();

        for (var item : items) {
            if (item == null || item.criteriaName() == null || item.criteriaName().isBlank()) continue;
            String key = item.criteriaName().toLowerCase().replaceAll("[^a-z0-9]", "").trim();

            if (!map.containsKey(key)) {
                map.put(key, item);
            } else {
                var existing = map.get(key);
                if ("matched".equalsIgnoreCase(item.status()) && !"matched".equalsIgnoreCase(existing.status())) {
                    map.put(key, item);
                }
            }
        }
        return new ArrayList<>(map.values());
    }

    private AssessmentResponseDto.AdHocEvidenceItem sanitizeAdHocItem(AssessmentResponseDto.AdHocEvidenceItem item) {
        if (item == null) return null;
        return new AssessmentResponseDto.AdHocEvidenceItem(
                item.criteriaName(),
                item.importance(),
                sanitizeLanguageText(item.jdRequirement()),
                sanitizeLanguageText(item.cvEvidence()),
                item.status(),
                sanitizeLanguageText(item.reasoning()),
                item.sourceSpan()
        );
    }

    private String sanitizeLanguageText(String text) {
        if (text == null) return null;
        String cleaned = text
                .replace("提到", "nhắc đến ")
                .replace("没有", "không có ")
                .replace("项目", "dự án ")
                .replace("技术", "công nghệ ");
        cleaned = cleaned.replaceAll("[\\u4e00-\\u9fa5]", "").replaceAll("\\s+", " ").trim();
        return cleaned;
    }

    private boolean isDuplicateCriteriaName(String stdName, String adHocName) {
        if (stdName == null || adHocName == null) return false;

        String stdLower = stdName.toLowerCase().trim();
        String adHocLower = adHocName.toLowerCase().trim();

        if (stdLower.equalsIgnoreCase(adHocLower)) return true;

        if (stdLower.contains("(" + adHocLower + ")") || adHocLower.contains("(" + stdLower + ")")) return true;

        String stdNorm = stdLower.replaceAll("\\([^)]*\\)", "").replaceAll("[^a-z0-9]", " ").replaceAll("\\s+", " ").trim();
        String adHocNorm = adHocLower.replaceAll("\\([^)]*\\)", "").replaceAll("[^a-z0-9]", " ").replaceAll("\\s+", " ").trim();

        if (stdNorm.equals(adHocNorm)) return true;
        if (!stdNorm.isEmpty() && !adHocNorm.isEmpty()) {
            if (stdNorm.contains(adHocNorm) || adHocNorm.contains(stdNorm)) return true;
        }

        java.util.Set<String> stdTokens = java.util.Arrays.stream(stdNorm.split(" "))
                .filter(s -> s.length() > 2)
                .collect(java.util.stream.Collectors.toSet());
        java.util.Set<String> adHocTokens = java.util.Arrays.stream(adHocNorm.split(" "))
                .filter(s -> s.length() > 2)
                .collect(java.util.stream.Collectors.toSet());

        if (!stdTokens.isEmpty() && !adHocTokens.isEmpty()) {
            java.util.Set<String> intersection = new java.util.HashSet<>(stdTokens);
            intersection.retainAll(adHocTokens);
            return !intersection.isEmpty();
        }

        return false;
    }

    private List<CriteriaWeightProjection> preFilterCriteriaForJd(
            String fullJdMarkdown,
            List<CriteriaWeightProjection> criteriaList) {

        if (fullJdMarkdown == null || fullJdMarkdown.isBlank() || criteriaList == null || criteriaList.isEmpty()) {
            return criteriaList != null ? criteriaList : List.of();
        }

        String jdLower = fullJdMarkdown.toLowerCase(Locale.ROOT);

        return criteriaList.stream()
                .filter(criteria -> isCriteriaRelevantToJd(jdLower, criteria))
                .collect(Collectors.toList());
    }

    private boolean isCriteriaRelevantToJd(String jdLower, CriteriaWeightProjection criteria) {
        if (criteria == null || criteria.getCriteriaName() == null) {
            return false;
        }

        String nameLower = criteria.getCriteriaName().toLowerCase(Locale.ROOT);

        // 1. Direct name or sub-phrase match
        if (jdLower.contains(nameLower)) {
            return true;
        }

        // 2. Tokenize criteria name and check key technical terms
        String[] keywords = nameLower.split("[^a-zA-Z0-9+#]+");
        int matchedKeywords = 0;

        for (String kw : keywords) {
            if (kw.length() <= 2 && !isSpecialShortTechTerm(kw)) {
                continue; // Skip trivial short words
            }
            if (jdLower.contains(kw)) {
                matchedKeywords++;
            }
        }

        if (matchedKeywords > 0) {
            return true;
        }

        // 3. Synonym / Tech domain relevance check
        return checkSynonymRelevance(jdLower, nameLower);
    }

    private boolean isSpecialShortTechTerm(String kw) {
        return Set.of("c", "go", "qa", "db", "ui", "ai", "ml", "ci", "cd", "js", "ts", "r8", "s3", "ec2").contains(kw);
    }

    private boolean checkSynonymRelevance(String jdLower, String nameLower) {
        if (nameLower.contains("database") || nameLower.contains("sql")) {
            return jdLower.contains("postgres") || jdLower.contains("mysql") || jdLower.contains("oracle")
                    || jdLower.contains("mongodb") || jdLower.contains("redis") || jdLower.contains("database")
                    || jdLower.contains("sql") || jdLower.contains("jpa") || jdLower.contains("hibernate") || jdLower.contains("orm");
        }
        if (nameLower.contains("api") || nameLower.contains("rest")) {
            return jdLower.contains("api") || jdLower.contains("rest") || jdLower.contains("graphql")
                    || jdLower.contains("endpoint") || jdLower.contains("http") || jdLower.contains("grpc");
        }
        if (nameLower.contains("testing") || nameLower.contains("qa") || nameLower.contains("tdd")) {
            return jdLower.contains("test") || jdLower.contains("junit") || jdLower.contains("jest")
                    || jdLower.contains("cypress") || jdLower.contains("selenium") || jdLower.contains("postman");
        }
        if (nameLower.contains("ci/cd") || nameLower.contains("pipeline") || nameLower.contains("devops")) {
            return jdLower.contains("ci/cd") || jdLower.contains("pipeline") || jdLower.contains("jenkins")
                    || jdLower.contains("github actions") || jdLower.contains("gitlab") || jdLower.contains("docker");
        }
        if (nameLower.contains("agile") || nameLower.contains("sdlc")) {
            return jdLower.contains("agile") || jdLower.contains("scrum") || jdLower.contains("kanban")
                    || jdLower.contains("sprint") || jdLower.contains("jira") || jdLower.contains("sdlc");
        }
        if (nameLower.contains("solid") || nameLower.contains("clean code")) {
            return jdLower.contains("solid") || jdLower.contains("clean code") || jdLower.contains("maintainable")
                    || jdLower.contains("refactor") || jdLower.contains("design pattern");
        }
        if (nameLower.contains("microservice") || nameLower.contains("architecture")) {
            return jdLower.contains("microservice") || jdLower.contains("architecture") || jdLower.contains("distributed")
                    || jdLower.contains("system design") || jdLower.contains("event-driven") || jdLower.contains("kafka");
        }
        return false;
    }
}
