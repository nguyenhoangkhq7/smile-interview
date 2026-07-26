package fit.iuh.modules.assessment.service.impl;

import com.fasterxml.jackson.databind.ObjectMapper;
import fit.iuh.exception.LlmApiException;
import fit.iuh.modules.chunking.service.RetrievalService;
import fit.iuh.modules.admin.repository.SystemSettingRepository;
import fit.iuh.modules.assessment.dto.*;
import fit.iuh.modules.assessment.entity.Eligibility;
import fit.iuh.modules.assessment.entity.ResumeAssessment;
import fit.iuh.modules.assessment.prompt.AssessmentPrompts;
import fit.iuh.modules.assessment.repository.ResumeAssessmentRepository;
import fit.iuh.modules.assessment.service.*;
import fit.iuh.modules.assessment.service.ScoringService.ScoringResult;
import fit.iuh.modules.assessment.util.TextSanitizationUtil;
import fit.iuh.modules.ingestion.entity.DocumentType;
import fit.iuh.modules.ingestion.entity.SessionDocument;
import fit.iuh.modules.ingestion.repository.SessionDocumentRepository;
import fit.iuh.modules.rulengine.repository.JobCriteriaRepository;
import fit.iuh.modules.rulengine.repository.JobCriteriaRepository.CriteriaWeightProjection;
import lombok.AllArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.jetbrains.annotations.NotNull;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.*;
import java.util.concurrent.CompletableFuture;
import java.util.concurrent.Semaphore;
import java.util.stream.Collectors;

@Slf4j
@Service
@AllArgsConstructor
public class AssessmentServiceImpl implements AssessmentService {
    private final ResumeAssessmentRepository resumeAssessmentRepository;
    private final SessionDocumentRepository sessionDocumentRepository;
    private final MetadataExtractionService metadataExtractionService;
    private final CriteriaLoaderService criteriaLoaderService;
    private final LlmCallerService llmCallerService;
    private final AssessmentResponseParser assessmentResponseParser;
    private final ScoringService scoringService;
    private final SuggestedCriteriaService suggestedCriteriaService;
    private final GateExtractionService gateExtractionService;
    private final ObjectMapper objectMapper;
    private final SystemSettingRepository systemSettingRepository;
    private final EvidenceGroundingValidator evidenceGroundingValidator;
    private final RetrievalService retrievalService;

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
    public AssessmentResponse assessResumeBlocking(
            String sessionId,
            boolean forceRefresh,
            String fromSessionId,
            Boolean includeNotApplicable) {

        // kiểm tra xem đánh giá chưa, nếu forceRefresh thì xoá cái cũ đánh giá lại
        if (!forceRefresh) {
            if (resumeAssessmentRepository.existsBySessionId(sessionId)) {
                log.info("[Assessment] Cache HIT for sessionId={}. Returning saved assessment.", sessionId);
                var entity = resumeAssessmentRepository.findBySessionId(sessionId).get();
                return buildResponseWithScoring(sessionId, entity, toResponse(entity, true));
            }

            if (fromSessionId != null && !fromSessionId.isBlank()) {
                Optional<ResumeAssessment> otherOpt = resumeAssessmentRepository.findBySessionId(fromSessionId);
                if (otherOpt.isPresent()) {
                    log.info("[Assessment] Session-cloning HIT! Reusing assessment from sessionId={} for new sessionId={}", fromSessionId, sessionId);
                    return cloneAndBuildResponse(sessionId, otherOpt.get());
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
                    return cloneAndBuildResponse(sessionId, otherAssessment);
                }
            }
        } else if (resumeAssessmentRepository.existsBySessionId(sessionId)) {
            log.warn("[Assessment] Force-refresh for sessionId={}. Deleting cached result.", sessionId);
            resumeAssessmentRepository.deleteBySessionId(sessionId);
            resumeAssessmentRepository.flush();
        }

        // lấy toàn bộ cv và jd lên để đánh giá
        SessionDocument cvDoc = sessionDocumentRepository
                .findBySessionIdAndDocumentType(sessionId, DocumentType.CV)
                .orElseThrow(() -> new LlmApiException("No CV found for session '" + sessionId + "'. Please ingest files first."));

        SessionDocument jdDoc = sessionDocumentRepository
                .findBySessionIdAndDocumentType(sessionId, DocumentType.JD)
                .orElseThrow(() -> new LlmApiException("No JD found for session '" + sessionId + "'. Please ingest files first."));

        log.info("[PIPELINE START] ASSESSMENT | Session: {}", sessionId);

        String fullCvMarkdown = cvDoc.getMarkdownContent();
        String fullJdMarkdown = jdDoc.getMarkdownContent();

        // kiểm tra trình độ và vị trí công việc JD đang tuyển
        MetadataExtractionService.ExtractionResult metadata = metadataExtractionService.extract(fullJdMarkdown);

        boolean shouldIncludeNotApp = includeNotApplicable != null
                ? includeNotApplicable
                : (systemSettingRepository != null && systemSettingRepository.getBoolean("INCLUDE_NOT_APPLICABLE_CRITERIA", false));

        fit.iuh.modules.assessment.dto.ClassifiedCriteriaBundle bundle = criteriaLoaderService.loadAndClassifyCriteria(
                metadata.category().name(),
                metadata.level().name(),
                fullJdMarkdown
        );

        List<CriteriaWeightProjection> criteriaList = criteriaLoaderService.loadAndFilterCriteria(
                metadata.category().name(),
                metadata.level().name(),
                sessionId,
                fullJdMarkdown,
                true
        );

        // tiến hành đánh giá với ClassifiedCriteriaBundle
        AssessmentResponseDto dto = runBatchedAssessmentWithSelfConsistencyClassified(
                sessionId,
                fullCvMarkdown,
                fullJdMarkdown,
                bundle,
                shouldIncludeNotApp
        );

        List<AssessmentResponseDto.AdHocEvidenceItem> filteredAdHoc = filterDuplicateAdHocItems(
                dto.mustHaveEvidenceItems(),
                dto.preferToHaveEvidenceItems()
        );

        if (!shouldIncludeNotApp) {
            List<AssessmentResponseDto.EvidenceItem> filteredEvidence = dto.mustHaveEvidenceItems() != null
                    ? dto.mustHaveEvidenceItems().stream()
                            .filter(item -> item != null
                                    && !"NOT_APPLICABLE".equalsIgnoreCase(item.importance())
                                    && !"not_applicable".equalsIgnoreCase(item.status()))
                            .collect(Collectors.toList())
                    : List.of();

            List<AssessmentResponseDto.AdHocEvidenceItem> filteredAdHocList = filteredAdHoc != null
                    ? filteredAdHoc.stream()
                            .filter(item -> item != null
                                    && !"NOT_APPLICABLE".equalsIgnoreCase(item.importance())
                                    && !"not_applicable".equalsIgnoreCase(item.status())
                                    && item.jdRequirement() != null
                                    && !item.jdRequirement().isBlank())
                            .collect(Collectors.toList())
                    : List.of();

            dto = new AssessmentResponseDto(filteredEvidence, filteredAdHocList);
        } else {
            dto = new AssessmentResponseDto(dto.mustHaveEvidenceItems(), filteredAdHoc);
        }

        ScoringResult scoringResult = scoringService.calculateWithBreakdown(
                dto.mustHaveEvidenceItems(),
                dto.preferToHaveEvidenceItems(),
                criteriaList,
                metadata.level()
        );

        Eligibility eligibility = gateExtractionService.evaluateEligibility(fullJdMarkdown, fullCvMarkdown);

        try {
            suggestedCriteriaService.recordAdHocCriteria(metadata.category(), dto.preferToHaveEvidenceItems());
        } catch (Exception e) {
            log.warn("[Assessment] Non-blocking warning recording ad-hoc criteria: {}", e.getMessage());
        }

        List<Map<String, String>> weaknesses = new ArrayList<>();
        if (scoringResult.evidenceItems() != null) {
            for (var item : scoringResult.evidenceItems()) {
                boolean isNotApp = "NOT_APPLICABLE".equalsIgnoreCase(item.importance()) || "not_applicable".equalsIgnoreCase(item.status());
                if (!isNotApp && ("missing".equalsIgnoreCase(item.status()) || "weak".equalsIgnoreCase(item.status()))) {
                    weaknesses.add(Map.of(
                            "criteriaName", item.criteriaName() != null ? item.criteriaName() : "",
                            "status", item.status() != null ? item.status() : "",
                            "reasoning", item.reasoning() != null ? item.reasoning() : ""
                    ));
                }
            }
        }

        List<ImprovementResponseDto.ImprovementItem> improvements = generateTopImprovements(sessionId, weaknesses);
        ResumeAssessment entity = buildAndPersistEntity(sessionId, metadata, scoringResult, dto.preferToHaveEvidenceItems(), improvements, eligibility);

        AssessmentResponse response = toResponse(entity, false);
        response.setScoreBreakdown(scoringResult.breakdown());
        return response;
    }

    private AssessmentResponse buildResponseWithScoring(String sessionId, ResumeAssessment entity, AssessmentResponse response) {
        List<CriteriaWeightProjection> criteriaList = criteriaLoaderService.loadAndFilterCriteria(
                entity.getJobCategory().name(),
                entity.getSeniorityLevel().name(),
                sessionId,
                "",
                true
        );
        ScoringResult scoringResult = scoringService.calculateWithBreakdown(
                entity.getMustHaveEvidenceItems(),
                entity.getPreferToHaveEvidenceItems(),
                criteriaList,
                entity.getSeniorityLevel()
        );

        response.setScoreBreakdown(scoringResult.breakdown());
        return response;
    }

    private AssessmentResponse cloneAndBuildResponse(String sessionId, ResumeAssessment otherAssessment) {
        ResumeAssessment clonedAssessment = ResumeAssessment.builder()
                .sessionId(sessionId)
                .jobCategory(otherAssessment.getJobCategory())
                .seniorityLevel(otherAssessment.getSeniorityLevel())
                .overallMatchScore(otherAssessment.getOverallMatchScore())
                .mustHaveEvidenceItems(otherAssessment.getMustHaveEvidenceItems())
                .preferToHaveEvidenceItems(otherAssessment.getPreferToHaveEvidenceItems())
                .topPriorityImprovements(otherAssessment.getTopPriorityImprovements())
                .eligibility(otherAssessment.getEligibility())
                .build();

        ResumeAssessment savedCloned = resumeAssessmentRepository.save(clonedAssessment);
        return buildResponseWithScoring(sessionId, clonedAssessment, toResponse(savedCloned, true));
    }

    @Override
    public AssessmentResponseDto runBatchedAssessmentWithSelfConsistency(
            String sessionId,
            String fullCvMarkdown,
            String fullJdMarkdown,
            List<CriteriaWeightProjection> criteriaList) {

        int maxBatchSize = systemSettingRepository != null ? systemSettingRepository.getInt("CRITERIA_BATCH_SIZE", 5) : 5;
        if (maxBatchSize < 1) {
            maxBatchSize = 1;
        }
        int selfConsistencyRuns = systemSettingRepository != null ? systemSettingRepository.getInt("SELF_CONSISTENCY_RUNS", 1) : 1;
        double groundingThreshold = systemSettingRepository != null ? systemSettingRepository.getDouble("EVIDENCE_GROUNDING_THRESHOLD", 0.75) : 0.75;
        int batchConcurrency = systemSettingRepository != null ? systemSettingRepository.getInt("CRITERIA_BATCH_CONCURRENCY", 3) : 3;
        Semaphore batchSemaphore = new Semaphore(batchConcurrency, true);

        List<List<CriteriaWeightProjection>> batches = partitionCriteria(criteriaList, maxBatchSize);

        List<CompletableFuture<BatchResult>> batchFutures = new ArrayList<>();
        for (List<CriteriaWeightProjection> batchCriteria : batches) {
            CompletableFuture<BatchResult> batchFuture = CompletableFuture.supplyAsync(() -> {
                boolean acquired = false;
                try {
                    acquired = batchSemaphore.tryAcquire(120, java.util.concurrent.TimeUnit.SECONDS);
                    if (!acquired) {
                        throw new LlmApiException("Batch concurrency limit reached waiting for permit.");
                    }
                    return processBatchWithSelfConsistency(
                            sessionId,
                            fullCvMarkdown,
                            fullJdMarkdown,
                            batchCriteria,
                            selfConsistencyRuns,
                            groundingThreshold
                    );
                } catch (InterruptedException e) {
                    Thread.currentThread().interrupt();
                    throw new LlmApiException("Interrupted waiting for batch concurrency semaphore.", e);
                } finally {
                    if (acquired) {
                        batchSemaphore.release();
                    }
                }
            });
            batchFutures.add(batchFuture);
        }

        List<AssessmentResponseDto.EvidenceItem> aggregatedEvidenceItems = new ArrayList<>();
        List<AssessmentResponseDto.AdHocEvidenceItem> aggregatedAdHocItems = new ArrayList<>();

        for (CompletableFuture<BatchResult> future : batchFutures) {
            try {
                BatchResult res = future.join();
                if (res.evidenceItems() != null) {
                    aggregatedEvidenceItems.addAll(res.evidenceItems());
                }
                if (res.preferToHaveEvidenceItems() != null) {
                    aggregatedAdHocItems.addAll(res.preferToHaveEvidenceItems());
                }
            } catch (Exception e) {
                log.error("[Assessment] Batch execution failed: {}", e.getMessage(), e);
            }
        }

        return new AssessmentResponseDto(aggregatedEvidenceItems, aggregatedAdHocItems);
    }

    private record BatchResult(
            List<AssessmentResponseDto.EvidenceItem> evidenceItems,
            List<AssessmentResponseDto.AdHocEvidenceItem> preferToHaveEvidenceItems
    ) {}

    private BatchResult processBatchWithSelfConsistency(
            String sessionId,
            String fullCvMarkdown,
            String fullJdMarkdown,
            List<CriteriaWeightProjection> batchCriteria,
            int selfConsistencyRuns,
            double groundingThreshold) {

        String criteriaInstructions = buildCriteriaInstructions(batchCriteria);

        int topKPerCriteria = systemSettingRepository != null ? systemSettingRepository.getInt("CV_CHUNKS_TOP_K", 2) : 2;
        int maxChunks = batchCriteria.size() * topKPerCriteria;

        List<String> criteriaSkills = batchCriteria.stream()
                .map(c -> c.getCriteriaName() + " " + (c.getPromptInstruction() != null ? c.getPromptInstruction() : ""))
                .collect(Collectors.toList());

        String cvContext = "";
        if (retrievalService != null) {
            try {
                cvContext = retrievalService.retrieveRelevantCvContext(sessionId, criteriaSkills, maxChunks);
            } catch (Exception e) {
                log.warn("[Assessment] Semantic retrieval failed for batch, falling back to full CV: {}", e.getMessage());
            }
        }
        final String cvContextMarkdown = (cvContext == null || cvContext.isBlank()) ? fullCvMarkdown : cvContext;

        if (cvContext == null || cvContext.isBlank()) {
            log.debug("[Assessment] Batch CV context: FALLBACK to full CV markdown (no chunks found)");
        } else {
            log.debug("[Assessment] Batch CV context: {} chars from semantic chunk retrieval (topK={}/criteria, {} criteria)",
                    cvContext.length(), topKPerCriteria, batchCriteria.size());
        }

        List<CompletableFuture<AssessmentResponseDto>> runFutures = new ArrayList<>();
        for (int run = 0; run < selfConsistencyRuns; run++) {
            CompletableFuture<AssessmentResponseDto> runFuture = CompletableFuture.supplyAsync(() -> {
                String systemPrompt = AssessmentPrompts.buildAssessmentSystemPrompt();
                String userPrompt = AssessmentPrompts.buildAssessmentUserPrompt(cvContextMarkdown, criteriaInstructions);

                String llmResponse = llmCallerService.callLlmBlockingWithSemaphore(systemPrompt, userPrompt);
                AssessmentResponseDto dto = assessmentResponseParser.parseAssessmentDto(sessionId, llmResponse);

                List<AssessmentResponseDto.EvidenceItem> validatedEvidence = dto.mustHaveEvidenceItems().stream()
                        .map(item -> evidenceGroundingValidator.validateAndApply(item, fullCvMarkdown, groundingThreshold))
                        .collect(Collectors.toList());

                return new AssessmentResponseDto(validatedEvidence, dto.preferToHaveEvidenceItems());
            });
            runFutures.add(runFuture);
        }

        List<AssessmentResponseDto> successfulDtos = new ArrayList<>();
        for (CompletableFuture<AssessmentResponseDto> future : runFutures) {
            try {
                successfulDtos.add(future.join());
            } catch (Exception e) {
                log.warn("[Assessment] Self-consistency run failed: {}", e.getMessage());
            }
        }

        if (successfulDtos.isEmpty()) {
            log.error("[Assessment] All {} self-consistency runs failed for criteria batch.", selfConsistencyRuns);
            return new BatchResult(List.of(), List.of());
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
                if (dto.preferToHaveEvidenceItems() != null) {
                    batchAdHoc.addAll(dto.preferToHaveEvidenceItems());
                }
                for (AssessmentResponseDto.EvidenceItem item : dto.mustHaveEvidenceItems()) {
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
                if (tiedStatuses.contains("matched") && tiedStatuses.contains("weak") && !tiedStatuses.contains("missing")) {
                    winningStatus = "weak";
                } else if (tiedStatuses.contains("weak")) {
                    winningStatus = "weak";
                } else if (tiedStatuses.contains("missing")) {
                    winningStatus = "missing";
                } else {
                    winningStatus = "matched";
                }
                lowConfidence = true;
            }

            AssessmentResponseDto.EvidenceItem sampleItem = statusToSampleItem.get(winningStatus);
            if (sampleItem == null) {
                sampleItem = statusToSampleItem.values().stream().findFirst().orElse(null);
            }

            aggregatedBatchItems.add(new AssessmentResponseDto.EvidenceItem(
                    c.getCriteriaId(),
                    c.getCriteriaName(),
                    sampleItem != null ? sampleItem.importance() : "REQUIRED",
                    sampleItem != null ? sampleItem.jdRequirement() : c.getPromptInstruction(),
                    sampleItem != null ? sampleItem.cvEvidence() : null,
                    winningStatus,
                    sampleItem != null ? sampleItem.reasoning() : "Majority vote.",
                    null, null, null, votes, lowConfidence, false
            ));
        }

        return new BatchResult(aggregatedBatchItems, batchAdHoc);
    }

    /**
     * Distributes criteria evenly across batches.
     * Example: 17 criteria / maxBatchSize=5 → [5, 4, 4, 4] instead of [5, 5, 5, 2].
     */
    private List<List<CriteriaWeightProjection>> partitionCriteria(List<CriteriaWeightProjection> list, int maxBatchSize) {
        if (list == null || list.isEmpty()) return List.of();
        int n = list.size();
        int numBatches = (int) Math.ceil((double) n / maxBatchSize);
        int baseSize = n / numBatches;
        int remainder = n % numBatches; // first `remainder` batches get one extra item

        List<List<CriteriaWeightProjection>> partitions = new ArrayList<>(numBatches);
        int idx = 0;
        for (int i = 0; i < numBatches; i++) {
            int batchSize = baseSize + (i < remainder ? 1 : 0);
            partitions.add(list.subList(idx, idx + batchSize));
            idx += batchSize;
        }
        log.debug("[Assessment] partitionCriteria: {} criteria → {} batches {}",
                n, numBatches,
                partitions.stream().map(b -> String.valueOf(b.size())).collect(Collectors.joining(", ", "[", "]")));
        return partitions;
    }

    public AssessmentResponseDto runBatchedAssessmentWithSelfConsistencyClassified(
            String sessionId,
            String fullCvMarkdown,
            String fullJdMarkdown,
            fit.iuh.modules.assessment.dto.ClassifiedCriteriaBundle bundle,
            boolean comprehensiveMode) {

        // Filter out 'not_in_jd' criteria before LLM evaluation to save tokens.
        // The JdCriteriaClassifier must be conservative: only mark criteria as not_in_jd
        // if they are CLEARLY unrelated to the job domain (e.g., ML criteria for a Fullstack JD).
        // Core tech skills mentioned in the JD must always be 'required' or 'preferred'.
        List<fit.iuh.modules.assessment.dto.ClassifiedCriteriaBundle.ClassifiedCriteria> dbCriteria = bundle.dbCriteriaForMode(comprehensiveMode);
        List<fit.iuh.modules.assessment.dto.ClassifiedCriteriaBundle.JdExtraCriteria> jdExtras = bundle.jdExtras();

        // Single item wrapper for instructions building
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

        int maxBatchSize = systemSettingRepository != null ? systemSettingRepository.getInt("CRITERIA_BATCH_SIZE", 5) : 5;
        if (maxBatchSize < 1) maxBatchSize = 1;
        int selfConsistencyRuns = systemSettingRepository != null ? systemSettingRepository.getInt("SELF_CONSISTENCY_RUNS", 1) : 1;
        double groundingThreshold = systemSettingRepository != null ? systemSettingRepository.getDouble("EVIDENCE_GROUNDING_THRESHOLD", 0.75) : 0.75;
        int batchConcurrency = systemSettingRepository != null ? systemSettingRepository.getInt("CRITERIA_BATCH_CONCURRENCY", 3) : 3;
        Semaphore batchSemaphore = new Semaphore(batchConcurrency, true);

        List<List<CriteriaInstructionItem>> batches = partitionInstructionItems(allItems, maxBatchSize);

        List<CompletableFuture<BatchResult>> batchFutures = new ArrayList<>();
        for (List<CriteriaInstructionItem> batchItems : batches) {
            CompletableFuture<BatchResult> batchFuture = CompletableFuture.supplyAsync(() -> {
                boolean acquired = false;
                try {
                    acquired = batchSemaphore.tryAcquire(120, java.util.concurrent.TimeUnit.SECONDS);
                    if (!acquired) {
                        throw new LlmApiException("Batch concurrency limit reached waiting for permit.");
                    }
                    return processBatchInstructionItemsWithSelfConsistency(
                            sessionId,
                            fullCvMarkdown,
                            batchItems,
                            selfConsistencyRuns,
                            groundingThreshold
                    );
                } catch (InterruptedException e) {
                    Thread.currentThread().interrupt();
                    throw new LlmApiException("Interrupted waiting for batch concurrency semaphore.", e);
                } finally {
                    if (acquired) {
                        batchSemaphore.release();
                    }
                }
            });
            batchFutures.add(batchFuture);
        }

        List<AssessmentResponseDto.EvidenceItem> aggregatedEvidenceItems = new ArrayList<>();
        List<AssessmentResponseDto.AdHocEvidenceItem> aggregatedAdHocItems = new ArrayList<>();

        for (CompletableFuture<BatchResult> future : batchFutures) {
            try {
                BatchResult res = future.join();
                if (res.evidenceItems() != null) {
                    aggregatedEvidenceItems.addAll(res.evidenceItems());
                }
                if (res.preferToHaveEvidenceItems() != null) {
                    aggregatedAdHocItems.addAll(res.preferToHaveEvidenceItems());
                }
            } catch (Exception e) {
                log.error("[Assessment] Batch execution failed: {}", e.getMessage(), e);
            }
        }

        return new AssessmentResponseDto(aggregatedEvidenceItems, aggregatedAdHocItems);
    }

    private record CriteriaInstructionItem(Long criteriaId, String name, String label, String promptInstruction) {}

    private BatchResult processBatchInstructionItemsWithSelfConsistency(
            String sessionId,
            String fullCvMarkdown,
            List<CriteriaInstructionItem> batchItems,
            int selfConsistencyRuns,
            double groundingThreshold) {

        StringBuilder sb = new StringBuilder();
        for (CriteriaInstructionItem item : batchItems) {
            sb.append("- ").append(item.label()).append(" ")
                    .append(item.name()).append(": ")
                    .append(item.promptInstruction() != null ? item.promptInstruction() : "")
                    .append("\n");
        }
        String criteriaInstructions = sb.toString().strip();

        int topKPerCriteria = systemSettingRepository != null ? systemSettingRepository.getInt("CV_CHUNKS_TOP_K", 2) : 2;
        int maxChunks = batchItems.size() * topKPerCriteria;

        List<String> criteriaSkills = batchItems.stream()
                .map(c -> c.name() + " " + (c.promptInstruction() != null ? c.promptInstruction() : ""))
                .collect(Collectors.toList());

        String cvContext = "";
        if (retrievalService != null) {
            try {
                cvContext = retrievalService.retrieveRelevantCvContext(sessionId, criteriaSkills, maxChunks);
            } catch (Exception e) {
                log.warn("[Assessment] Semantic retrieval failed for batch, falling back to full CV: {}", e.getMessage());
            }
        }
        final String cvContextMarkdown = (cvContext == null || cvContext.isBlank()) ? fullCvMarkdown : cvContext;

        List<CompletableFuture<AssessmentResponseDto>> runFutures = new ArrayList<>();
        for (int run = 0; run < selfConsistencyRuns; run++) {
            CompletableFuture<AssessmentResponseDto> runFuture = CompletableFuture.supplyAsync(() -> {
                String systemPrompt = AssessmentPrompts.buildAssessmentSystemPrompt();
                String userPrompt = AssessmentPrompts.buildAssessmentUserPrompt(cvContextMarkdown, criteriaInstructions);

                String llmResponse = llmCallerService.callLlmBlockingWithSemaphore(systemPrompt, userPrompt);
                AssessmentResponseDto dto = assessmentResponseParser.parseAssessmentDto(sessionId, llmResponse);

                List<AssessmentResponseDto.EvidenceItem> validatedEvidence = dto.mustHaveEvidenceItems().stream()
                        .map(item -> evidenceGroundingValidator.validateAndApply(item, fullCvMarkdown, groundingThreshold))
                        .collect(Collectors.toList());

                return new AssessmentResponseDto(validatedEvidence, dto.preferToHaveEvidenceItems());
            });
            runFutures.add(runFuture);
        }

        List<AssessmentResponseDto> successfulDtos = new ArrayList<>();
        for (CompletableFuture<AssessmentResponseDto> future : runFutures) {
            try {
                successfulDtos.add(future.join());
            } catch (Exception e) {
                log.warn("[Assessment] Self-consistency run failed: {}", e.getMessage());
            }
        }

        if (successfulDtos.isEmpty()) {
            return new BatchResult(List.of(), List.of());
        }

        // Majority voting across selfConsistencyRuns for each instruction item
        List<AssessmentResponseDto.EvidenceItem> aggregatedBatchItems = new ArrayList<>();
        List<AssessmentResponseDto.AdHocEvidenceItem> batchAdHoc = new ArrayList<>();

        for (CriteriaInstructionItem item : batchItems) {
            if (item.criteriaId() != null) {
                // DB Criteria: vote on status
                Map<String, Integer> votes = new HashMap<>();
                votes.put("matched", 0);
                votes.put("weak", 0);
                votes.put("missing", 0);

                Map<String, AssessmentResponseDto.EvidenceItem> statusToSampleItem = new HashMap<>();

                for (AssessmentResponseDto dto : successfulDtos) {
                    if (dto.preferToHaveEvidenceItems() != null) {
                        batchAdHoc.addAll(dto.preferToHaveEvidenceItems());
                    }
                    if (dto.mustHaveEvidenceItems() != null) {
                        for (AssessmentResponseDto.EvidenceItem ev : dto.mustHaveEvidenceItems()) {
                            if (Objects.equals(ev.criteriaId(), item.criteriaId())) {
                                String st = ev.status() != null ? ev.status().toLowerCase(Locale.ROOT) : "missing";
                                if (!votes.containsKey(st)) st = "missing";
                                votes.put(st, votes.get(st) + 1);
                                statusToSampleItem.putIfAbsent(st, ev);
                            }
                        }
                    }
                }

                int maxVotes = Collections.max(votes.values());
                List<String> tiedStatuses = votes.entrySet().stream()
                        .filter(e -> e.getValue() == maxVotes)
                        .map(Map.Entry::getKey)
                        .toList();

                String winningStatus = tiedStatuses.size() == 1 ? tiedStatuses.get(0) : (tiedStatuses.contains("weak") ? "weak" : "missing");
                boolean lowConfidence = tiedStatuses.size() > 1;

                AssessmentResponseDto.EvidenceItem sampleItem = statusToSampleItem.get(winningStatus);
                if (sampleItem == null) sampleItem = statusToSampleItem.values().stream().findFirst().orElse(null);

                String finalImportance = "[REQUIRED]".equals(item.label()) ? "REQUIRED" :
                                         "[PREFERRED]".equals(item.label()) ? "PREFERRED" : "NOT_APPLICABLE";

                aggregatedBatchItems.add(new AssessmentResponseDto.EvidenceItem(
                        item.criteriaId(),
                        item.name(),
                        finalImportance,
                        sampleItem != null ? sampleItem.jdRequirement() : item.promptInstruction(),
                        sampleItem != null ? sampleItem.cvEvidence() : null,
                        winningStatus,
                        sampleItem != null ? sampleItem.reasoning() : "Evaluated.",
                        null, null, null, votes, lowConfidence, false
                ));
            } else {
                // JD Extra Criteria (ad-hoc): take items directly
                for (AssessmentResponseDto dto : successfulDtos) {
                    if (dto.mustHaveEvidenceItems() != null) {
                        for (AssessmentResponseDto.EvidenceItem ev : dto.mustHaveEvidenceItems()) {
                            if (ev.criteriaId() == null && item.name().equalsIgnoreCase(ev.criteriaName())) {
                                aggregatedBatchItems.add(ev);
                            }
                        }
                    }
                    if (dto.preferToHaveEvidenceItems() != null) {
                        for (AssessmentResponseDto.AdHocEvidenceItem adHoc : dto.preferToHaveEvidenceItems()) {
                            if (item.name().equalsIgnoreCase(adHoc.criteriaName())) {
                                batchAdHoc.add(adHoc);
                            }
                        }
                    }
                }
            }
        }

        return new BatchResult(aggregatedBatchItems, batchAdHoc);
    }

    private List<List<CriteriaInstructionItem>> partitionInstructionItems(List<CriteriaInstructionItem> list, int maxBatchSize) {
        if (list == null || list.isEmpty()) return List.of();
        int n = list.size();
        int numBatches = (int) Math.ceil((double) n / maxBatchSize);
        int baseSize = n / numBatches;
        int remainder = n % numBatches;

        List<List<CriteriaInstructionItem>> partitions = new ArrayList<>(numBatches);
        int idx = 0;
        for (int i = 0; i < numBatches; i++) {
            int batchSize = baseSize + (i < remainder ? 1 : 0);
            partitions.add(list.subList(idx, idx + batchSize));
            idx += batchSize;
        }
        return partitions;
    }

    private String buildCriteriaInstructions(List<CriteriaWeightProjection> criteria) {
        StringBuilder sb = new StringBuilder();
        for (CriteriaWeightProjection c : criteria) {
            sb.append("- ").append(c.getCriteriaName()).append(": ").append(c.getPromptInstruction()).append("\n");
        }
        return sb.toString().strip();
    }

    private List<ImprovementResponseDto.ImprovementItem> generateTopImprovements(
            String sessionId,
            List<Map<String, String>> weaknesses) {

        if (weaknesses == null || weaknesses.isEmpty()) {
            return List.of();
        }

        try {
            String systemPrompt = AssessmentPrompts.SYSTEM_PROMPT_IMPROVEMENT_ADVISOR;
            String userPrompt = objectMapper.writeValueAsString(weaknesses);

            String responseContent = llmCallerService.callLlmBlockingWithSemaphore(systemPrompt, userPrompt);
            ImprovementResponseDto dto = parseImprovementDto(sessionId, responseContent);

            return dto.topPriorityImprovements() != null ? dto.topPriorityImprovements() : List.of();

        } catch (Exception e) {
            log.error("[Assessment] Failed to generate top improvements for session {}: {}", sessionId, e.getMessage());
            return List.of();
        }
    }

    private ImprovementResponseDto parseImprovementDto(String sessionId, String llmJsonResponse) {
        String cleanJson = TextSanitizationUtil.extractCleanJson(llmJsonResponse);
        try {
            return objectMapper.readValue(cleanJson, ImprovementResponseDto.class);
        } catch (Exception e) {
            log.error("[Assessment] Parse improvement DTO failed for session {}: {}", sessionId, e.getMessage());
            return new ImprovementResponseDto(List.of());
        }
    }

    protected ResumeAssessment buildAndPersistEntity(
            String sessionId,
            MetadataExtractionService.ExtractionResult metadata,
            ScoringResult scoringResult,
            List<AssessmentResponseDto.AdHocEvidenceItem> preferToHaveItems,
            List<ImprovementResponseDto.ImprovementItem> topPriorityImprovements,
            Eligibility eligibility) {

        ResumeAssessment entity = ResumeAssessment.builder()
                .sessionId(sessionId)
                .jobCategory(metadata.category())
                .seniorityLevel(metadata.level())
                .overallMatchScore(scoringResult.score())
                .mustHaveEvidenceItems(scoringResult.evidenceItems())
                .preferToHaveEvidenceItems(preferToHaveItems)
                .topPriorityImprovements(topPriorityImprovements)
                .eligibility(eligibility)
                .build();

        return resumeAssessmentRepository.save(entity);
    }

    private AssessmentResponse toResponse(ResumeAssessment entity, boolean cached) {
        return AssessmentResponse.builder()
                .id(entity.getId())
                .sessionId(entity.getSessionId())
                .jobCategory(entity.getJobCategory())
                .seniorityLevel(entity.getSeniorityLevel())
                .overallMatchScore(entity.getOverallMatchScore())
                .mustHaveEvidenceItems(entity.getMustHaveEvidenceItems())
                .preferToHaveEvidenceItems(entity.getPreferToHaveEvidenceItems())
                .topPriorityImprovements(entity.getTopPriorityImprovements())
                .eligibility(entity.getEligibility())
                .cached(cached)
                .createdAt(entity.getCreatedAt())
                .build();
    }



    private List<AssessmentResponseDto.AdHocEvidenceItem> filterDuplicateAdHocItems(
            List<AssessmentResponseDto.EvidenceItem> standardItems,
            List<AssessmentResponseDto.AdHocEvidenceItem> adHocItems) {

        if (adHocItems == null || adHocItems.isEmpty()) {
            return List.of();
        }

        Set<String> standardNamesLower = (standardItems != null)
                ? standardItems.stream()
                .map(item -> item.criteriaName() != null ? item.criteriaName().toLowerCase(Locale.ROOT).trim() : "")
                .filter(name -> !name.isEmpty())
                .collect(Collectors.toSet())
                : Set.of();

        Map<String, AssessmentResponseDto.AdHocEvidenceItem> uniqueAdHocMap = new LinkedHashMap<>();

        for (AssessmentResponseDto.AdHocEvidenceItem item : adHocItems) {
            if (item == null || item.criteriaName() == null || item.criteriaName().isBlank()) {
                continue;
            }

            String adHocNameLower = item.criteriaName().toLowerCase(Locale.ROOT).trim();
            boolean matchesStandard = standardNamesLower.stream()
                    .anyMatch(stdName -> isDuplicateCriteriaName(stdName, adHocNameLower));

            if (matchesStandard) {
                log.debug("[Assessment] Filtering out ad-hoc criteria '{}' (duplicate of standard criteria)", item.criteriaName());
                continue;
            }

            uniqueAdHocMap.putIfAbsent(adHocNameLower, item);
        }

        return new ArrayList<>(uniqueAdHocMap.values());
    }

    private boolean isDuplicateCriteriaName(String stdName, String adHocName) {
        // Exact match
        if (stdName.equals(adHocName)) return true;

        // Substring containment (minimum 4-char overlap)
        if (stdName.contains(adHocName) || adHocName.contains(stdName)) {
            int minLen = Math.min(stdName.length(), adHocName.length());
            return minLen >= 4;
        }

        // Tech-prefix synonym matching: criteria sharing the same technology prefix
        // are considered duplicates when both names are long enough to be meaningful.
        // E.g. "aws compute & auto-scaling" and "aws ec2 and rds experience" → same 'aws' domain.
        String[] techPrefixes = {"aws", "docker", "ci/cd", "ci cd", "git", "spring",
                                  "react", "postgresql", "mysql", "database", "testing",
                                  "unit test", "kubernetes", "linux"};
        for (String prefix : techPrefixes) {
            if (stdName.startsWith(prefix) && adHocName.startsWith(prefix)) {
                return true;
            }
        }

        return false;
    }
}
