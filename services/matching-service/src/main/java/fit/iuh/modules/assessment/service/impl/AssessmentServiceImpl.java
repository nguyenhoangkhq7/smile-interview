package fit.iuh.modules.assessment.service.impl;

import com.fasterxml.jackson.databind.ObjectMapper;
import fit.iuh.exception.LlmApiException;
import fit.iuh.modules.assessment.dto.*;
import fit.iuh.modules.assessment.entity.EligibilityStatus;
import fit.iuh.modules.assessment.entity.ResumeAssessment;
import fit.iuh.modules.assessment.gate.EligibilityGateService.GateCheckDto;
import fit.iuh.modules.assessment.mapper.AssessmentMapper;
import fit.iuh.modules.assessment.repository.ResumeAssessmentRepository;
import fit.iuh.modules.assessment.service.*;
import fit.iuh.modules.assessment.service.AssessmentScoringEngine.ScoringResult;
import fit.iuh.modules.session.entity.Session;
import fit.iuh.modules.session.repository.SessionRepository;
import fit.iuh.modules.rulengine.repository.JobCriteriaRepository.CriteriaWeightProjection;
import lombok.AllArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.*;
import java.util.stream.Collectors;

/**
 * High-performance Orchestrator Service for resume assessment utilizing 2-Phase Hybrid LLM architecture:
 * Phase 1: Consolidated single-pass JD analysis (Metadata, Gates, Criteria Classification in 1 LLM Call).
 * Phase 2: Batched CV evaluation with evidence grounding.
 */
@Slf4j
@Service
@AllArgsConstructor
public class AssessmentServiceImpl implements AssessmentService {

    private static final String STATUS_NOT_APPLICABLE = "not_applicable";
    private static final String IMPORTANCE_NOT_APPLICABLE = "NOT_APPLICABLE";

    private final ResumeAssessmentRepository resumeAssessmentRepository;
    private final SessionRepository sessionRepository;
    private final AssessmentCriteriaPreparer criteriaPreparer;
    private final AssessmentLlmRunner llmRunner;
    private final AssessmentScoringEngine scoringEngine;
    private final ObjectMapper objectMapper;
    private final java.util.concurrent.Executor assessmentTaskExecutor;

    @Override
    @Transactional
    public AssessmentResponse assessResumeBlocking(
            String sessionId,
            boolean forceRefresh,
            String fromSessionId) {

        log.info("[PIPELINE START] 2-PHASE ASSESSMENT PIPELINE | SessionId: {}, ForceRefresh: {}, FromSessionId: {}",
                sessionId, forceRefresh, fromSessionId);

        // Step 1: Check cache or session cloning if not force refreshed
        log.info("[STEP 1/7] Checking cache and session cloning status for sessionId: {}...", sessionId);
        Optional<AssessmentResponse> cachedResponse = checkCachedAssessment(sessionId, forceRefresh, fromSessionId);
        if (cachedResponse.isPresent()) {
            log.info("[STEP 1/7] Cache or cloning HIT. Returning saved assessment for sessionId: {}", sessionId);
            return cachedResponse.get();
        }

        // Step 2: Load ingested CV and JD documents
        Session session = sessionRepository.findById(sessionId)
                .orElseThrow(() -> new LlmApiException("Session not found: " + sessionId));
        if (session.getResume() == null || session.getResume().getParsedContent() == null) {
            throw new LlmApiException("No parsed CV found for session '" + sessionId + "'. Please ingest files first.");
        }
        if (session.getJobDescription() == null || session.getJobDescription().getParsedContent() == null) {
            throw new LlmApiException("No parsed JD found for session '" + sessionId + "'. Please ingest files first.");
        }
        String fullCvMarkdown = session.getResume().getParsedContent();
        String fullJdMarkdown = session.getJobDescription().getParsedContent();
        log.info("[STEP 2/7] [DEBUG] CV Loaded: Size={} chars | JD Loaded: Size={} chars",
                fullCvMarkdown.length(), fullJdMarkdown.length());

        // Step 3 & 4: Get or prepare JD context per target seniority level (2-tier Redis cached)
        PreparedJdContext jdContext = criteriaPreparer.getOrPrepareJdContext(
                session.getJobDescription().getId().toString(),
                fullJdMarkdown,
                session.getJobDescription().getJobCategory(),
                session.getJobDescription().getAcceptedLevels(),
                session.getResume().getSeniorityLevel(),
                fullCvMarkdown,
                forceRefresh
        );

        // Step 5: Phase 2 — Batched LLM assessment pipeline
        log.info("[STEP 5/7] Phase 2 — Running Batched LLM assessment pipeline for sessionId: {}...", sessionId);
        AssessmentResponseDto dto = llmRunner.runBatchedAssessment(
                sessionId,
                fullCvMarkdown,
                fullJdMarkdown,
                jdContext.bundle()
        );

        List<AssessmentResponseDto.AdHocEvidenceItem> filteredAdHoc = filterDuplicateAdHocItems(
                dto.mustHaveEvidenceItems(),
                dto.preferToHaveEvidenceItems()
        );

        dto = filterNotApplicableItems(dto, filteredAdHoc);
        log.info("[STEP 5/7] [DEBUG] Phase 2 LLM Assessment Output -> Must-Have Evidence Items: {}, Prefer-To-Have / Ad-Hoc Items: {}",
                dto.mustHaveEvidenceItems() != null ? dto.mustHaveEvidenceItems().size() : 0,
                dto.preferToHaveEvidenceItems() != null ? dto.preferToHaveEvidenceItems().size() : 0);

        // Step 6 & 7: Calculate final scores, evaluate hard eligibility gate checks, and generate improvements concurrently
        log.info("[STEP 6/7 & 7/7] Executing Scoring, Eligibility Check, and Improvements generation in parallel...");

        final AssessmentResponseDto finalDto = dto;

        var scoringFuture = executeScoringAsync(finalDto, jdContext.criteriaList(), jdContext.targetLevel());
        var eligibilityFuture = executeGateSyncAndEvaluationAsync(jdContext.gateRequirements(), fullJdMarkdown, fullCvMarkdown, finalDto);
        var improvementsFuture = executeImprovementsAsync(sessionId, finalDto.mustHaveEvidenceItems(), fullCvMarkdown);

        ScoringResult scoringResult = scoringFuture.join();
        var eligibilityResult = eligibilityFuture.join();
        EligibilityStatus eligibility = eligibilityResult.status();

        log.info("[STEP 6/7] [DEBUG] Scoring Result -> Overall Score: {}%, Category Breakdown: {}", scoringResult.overallScore(), scoringResult.breakdown());
        log.info("[STEP 6/7] [DEBUG] Eligibility Check -> Status: {}", eligibility);

        ImprovementResponseDto improvements = improvementsFuture.join();
        int impCount = (improvements != null && improvements.quickWins() != null ? improvements.quickWins().size() : 0) +
                       (improvements != null && improvements.skillGaps() != null ? improvements.skillGaps().size() : 0);
        log.info("[STEP 7/7] [DEBUG] Top Improvements Generated ({})", impCount);

        log.info("[STEP 7/7] Persisting assessment entity for sessionId: {}...", sessionId);
        ResumeAssessment entity = buildAndPersistEntity(
                sessionId, jdContext.category(), jdContext.targetLevel(), scoringResult,
                finalDto.preferToHaveEvidenceItems(), eligibilityResult.gateItems(), improvements, eligibility
        );
        log.info("[STEP 7/7] [DEBUG] Entity Persisted Successfully -> ID: {}, SessionId: {}", entity.getId(), entity.getSessionId());

        AssessmentResponse response = toResponse(entity, false);
        response.setScoreBreakdown(scoringResult.breakdown());
        log.info("[PIPELINE COMPLETE] Assessment successfully saved and returned for sessionId: {} | Final Score: {}% | Eligibility: {}",
                sessionId, scoringResult.overallScore(), eligibility);
        return response;
    }

    private java.util.concurrent.CompletableFuture<ScoringResult> executeScoringAsync(
            AssessmentResponseDto finalDto,
            List<? extends CriteriaWeightProjection> criteriaList,
            fit.iuh.modules.assessment.entity.SeniorityLevel level) {
        return java.util.concurrent.CompletableFuture.supplyAsync(
                () -> scoringEngine.calculateWithBreakdown(
                        finalDto.mustHaveEvidenceItems(),
                        finalDto.preferToHaveEvidenceItems(),
                        criteriaList != null ? new ArrayList<>(criteriaList) : List.of(),
                        level
                ),
                assessmentTaskExecutor
        );
    }

    private java.util.concurrent.CompletableFuture<fit.iuh.modules.assessment.gate.EligibilityGateService.EligibilityEvaluationResult> executeGateSyncAndEvaluationAsync(
            List<GateCheckDto> gateRequirements,
            String fullJdMarkdown,
            String fullCvMarkdown,
            AssessmentResponseDto finalDto) {
        return java.util.concurrent.CompletableFuture.supplyAsync(() -> {
            var rawResult = criteriaPreparer.evaluateEligibilityWithRawGates(
                    gateRequirements, fullJdMarkdown, fullCvMarkdown
            );

            if (rawResult == null || rawResult.gateItems() == null) {
                return rawResult;
            }

            List<AssessmentResponseDto.EvidenceItem> syncedGates = new ArrayList<>();
            boolean anySynced = false;

            for (var gate : rawResult.gateItems()) {
                if (isNotEvaluatedStatus(gate.status())) {
                    var newGate = syncGateWithLlmEvidence(gate, finalDto.mustHaveEvidenceItems(), finalDto.preferToHaveEvidenceItems());
                    if (newGate != null) {
                        syncedGates.add(newGate);
                        anySynced = true;
                        log.info("[GateSync] Gate '{}' synchronized to PASSED via LLM Evidence.", gate.criteriaName());
                    } else {
                        syncedGates.add(gate);
                    }
                } else {
                    syncedGates.add(gate);
                }
            }

            boolean allRequiredMet = syncedGates.stream()
                    .filter(g -> "REQUIRED".equalsIgnoreCase(g.importance()))
                    .allMatch(g -> "met".equalsIgnoreCase(g.status()) || "PASSED".equalsIgnoreCase(g.status()) || "PASS".equalsIgnoreCase(g.status()));
            boolean hasNotEvaluated = syncedGates.stream()
                    .filter(g -> "REQUIRED".equalsIgnoreCase(g.importance()))
                    .anyMatch(g -> isNotEvaluatedStatus(g.status()));

            if (anySynced && rawResult.status() == EligibilityStatus.NOT_ELIGIBILITY && allRequiredMet && !hasNotEvaluated) {
                return new fit.iuh.modules.assessment.gate.EligibilityGateService.EligibilityEvaluationResult(EligibilityStatus.ELIGIBILITY, syncedGates);
            } else if (anySynced) {
                EligibilityStatus newStatus = (hasNotEvaluated && allRequiredMet)
                        ? EligibilityStatus.PARTIAL
                        : rawResult.status();
                return new fit.iuh.modules.assessment.gate.EligibilityGateService.EligibilityEvaluationResult(newStatus, syncedGates);
            }
            return rawResult;
        }, assessmentTaskExecutor);
    }

    private java.util.concurrent.CompletableFuture<ImprovementResponseDto> executeImprovementsAsync(
            String sessionId,
            List<AssessmentResponseDto.EvidenceItem> mustHaveItems,
            String fullCvMarkdown) {
        return java.util.concurrent.CompletableFuture.supplyAsync(() -> {
            List<Map<String, String>> weaknesses = extractWeaknesses(mustHaveItems);
            log.info("[STEP 7/7] [DEBUG] Extracted Weaknesses Count for Improvements: {}", weaknesses.size());
            return generateTopImprovements(sessionId, weaknesses, fullCvMarkdown);
        }, assessmentTaskExecutor);
    }

    private AssessmentResponseDto.EvidenceItem syncGateWithLlmEvidence(
            AssessmentResponseDto.EvidenceItem gate,
            List<AssessmentResponseDto.EvidenceItem> mustHaveItems,
            List<AssessmentResponseDto.AdHocEvidenceItem> preferToHaveItems) {
        if (mustHaveItems != null) {
            for (var item : mustHaveItems) {
                if (isGateMatch(gate, item.status(), item.criteriaName(), item.jdRequirement())) {
                    return createPassedGateEvidence(gate, item.cvEvidence());
                }
            }
        }
        if (preferToHaveItems != null) {
            for (var item : preferToHaveItems) {
                if (isGateMatch(gate, item.status(), item.criteriaName(), item.jdRequirement())) {
                    return createPassedGateEvidence(gate, item.cvEvidence());
                }
            }
        }
        return null;
    }

    private boolean isGateMatch(AssessmentResponseDto.EvidenceItem gate, String itemStatus, String itemName, String itemRequirement) {
        if (!"matched".equalsIgnoreCase(itemStatus)) return false;
        String gateName = gate.criteriaName() != null ? gate.criteriaName().toLowerCase(Locale.ROOT) : "";
        String name = itemName != null ? itemName.toLowerCase(Locale.ROOT) : "";
        String req = itemRequirement != null ? itemRequirement.toLowerCase(Locale.ROOT) : "";

        if (gateName.contains("degree") || gateName.contains("bằng") || gateName.contains("học vị")) {
            return name.contains("degree") || name.contains("bằng") || req.contains("degree") || req.contains("bachelor") || req.contains("đại học");
        } else if (gateName.contains("experience") || gateName.contains("kinh nghiệm") || gateName.contains("yoe")) {
            return name.contains("experience") || name.contains("kinh nghiệm") || req.contains("year") || req.contains("năm");
        } else if (gateName.contains("cert") || gateName.contains("chứng chỉ")) {
            return name.contains("cert") || name.contains("chứng chỉ") || req.contains("aws") || req.contains("pmp");
        }
        return false;
    }

    private AssessmentResponseDto.EvidenceItem createPassedGateEvidence(AssessmentResponseDto.EvidenceItem gate, String cvEvidence) {
        String evidence = (cvEvidence != null && !cvEvidence.isBlank()) ? cvEvidence : "Verified via CV content matching criteria.";
        return new AssessmentResponseDto.EvidenceItem(
                gate.criteriaId(), gate.criteriaName(), gate.importance(), gate.jdRequirement(),
                evidence, gate.cvQuote(), "met",
                "Successfully fulfilled and validated from extracted CV evidence.",
                gate.weightUsed(), gate.scoreContribution(), 1.0,
                gate.confidenceVotes(), gate.lowConfidence(), gate.needsManualReview(), gate.matchMetadata()
        );
    }

    private boolean isNotEvaluatedStatus(String status) {
        if (status == null) return true;
        String s = status.trim();
        return "NOT_EVALUATED".equalsIgnoreCase(s) || "Not Evaluated".equalsIgnoreCase(s) || "not_evaluated".equalsIgnoreCase(s);
    }

    private Optional<AssessmentResponse> checkCachedAssessment(String sessionId, boolean forceRefresh, String fromSessionId) {
        if (!forceRefresh) {
            Optional<ResumeAssessment> entityOpt = resumeAssessmentRepository.findBySessionId(sessionId);
            if (entityOpt.isPresent()) {
                log.info("[Assessment] Cache HIT for sessionId={}. Returning saved assessment.", sessionId);
                ResumeAssessment entity = entityOpt.get();
                return Optional.of(toResponse(entity, true));
            }

            if (fromSessionId != null && !fromSessionId.isBlank()) {
                Optional<ResumeAssessment> otherOpt = resumeAssessmentRepository.findBySessionId(fromSessionId);
                if (otherOpt.isPresent()) {
                    log.info("[Assessment] Session-cloning HIT! Reusing assessment from sessionId={} for new sessionId={}", fromSessionId, sessionId);
                    return Optional.of(cloneAndBuildResponse(sessionId, otherOpt.get()));
                }
            } else {
                Optional<Session> sessionOpt = sessionRepository.findById(sessionId);
                if (sessionOpt.isPresent()) {
                    Session session = sessionOpt.get();
                    if (session.getResume() != null && session.getResume().getParsedContent() != null &&
                        session.getJobDescription() != null && session.getJobDescription().getParsedContent() != null) {

                        String cvContent = session.getResume().getParsedContent();
                        String jdContent = session.getJobDescription().getParsedContent();

                        Optional<String> otherSessionIdOpt = sessionRepository.findSessionWithSameContentAndAssessment(cvContent, jdContent, sessionId);
                        if (otherSessionIdOpt.isPresent()) {
                            String otherSessionId = otherSessionIdOpt.get();
                            log.info("[Assessment] Content-based Cache HIT! Reusing assessment for new sessionId={}", sessionId);
                            var otherAssessment = resumeAssessmentRepository.findBySessionId(otherSessionId).get();
                            return Optional.of(cloneAndBuildResponse(sessionId, otherAssessment));
                        }
                    }
                }
            }
        } else if (resumeAssessmentRepository.existsBySessionId(sessionId)) {
            log.warn("[Assessment] Force-refresh for sessionId={}. Deleting cached result.", sessionId);
            resumeAssessmentRepository.deleteBySessionId(sessionId);
            resumeAssessmentRepository.flush();
        }
        return Optional.empty();
    }

    private AssessmentResponseDto filterNotApplicableItems(
            AssessmentResponseDto dto,
            List<AssessmentResponseDto.AdHocEvidenceItem> filteredAdHoc) {

        List<AssessmentResponseDto.EvidenceItem> filteredEvidence = dto.mustHaveEvidenceItems() != null
                ? dto.mustHaveEvidenceItems().stream()
                        .filter(item -> item != null
                                && !IMPORTANCE_NOT_APPLICABLE.equalsIgnoreCase(item.importance())
                                && !STATUS_NOT_APPLICABLE.equalsIgnoreCase(item.status()))
                        .collect(Collectors.toList())
                : List.of();

        List<AssessmentResponseDto.AdHocEvidenceItem> filteredAdHocList = filteredAdHoc != null
                ? filteredAdHoc.stream()
                        .filter(item -> item != null
                                && !IMPORTANCE_NOT_APPLICABLE.equalsIgnoreCase(item.importance())
                                && !STATUS_NOT_APPLICABLE.equalsIgnoreCase(item.status())
                                && item.jdRequirement() != null
                                && !item.jdRequirement().isBlank())
                        .collect(Collectors.toList())
                : List.of();

        return new AssessmentResponseDto(filteredEvidence, filteredAdHocList);
    }

    private List<Map<String, String>> extractWeaknesses(List<AssessmentResponseDto.EvidenceItem> items) {
        List<Map<String, String>> weaknesses = new ArrayList<>();
        if (items == null) return weaknesses;
        for (var item : items) {
            if ("partial".equalsIgnoreCase(item.status()) || "weak".equalsIgnoreCase(item.status()) || "missing".equalsIgnoreCase(item.status())) {
                weaknesses.add(Map.of(
                        "name", item.criteriaName() != null ? item.criteriaName() : "",
                        "requirement", item.jdRequirement() != null ? item.jdRequirement() : "",
                        "reasoning", item.reasoning() != null ? item.reasoning() : ""
                ));
            }
        }
        return weaknesses;
    }

    private ImprovementResponseDto generateTopImprovements(
            String sessionId, List<Map<String, String>> weaknesses, String cvMarkdown) {
        if (weaknesses.isEmpty()) return new ImprovementResponseDto(List.of(), List.of());
        try {
            String jsonStr = objectMapper.writeValueAsString(weaknesses);
            String sysPrompt = fit.iuh.modules.assessment.prompt.AssessmentPrompts.SYSTEM_PROMPT_IMPROVEMENT_ADVISOR;
            String userPrompt = fit.iuh.modules.assessment.prompt.AssessmentPrompts.buildImprovementUserPrompt(jsonStr, cvMarkdown);
            String llmRes = llmRunner.callLlmBlockingWithSemaphore(sysPrompt, userPrompt);
            String clean = fit.iuh.modules.assessment.util.TextSanitizationUtil.extractCleanJson(llmRes);
            var res = objectMapper.readValue(clean, ImprovementResponseDto.class);
            return res != null ? res : new ImprovementResponseDto(List.of(), List.of());
        } catch (Exception e) {
            log.warn("[Assessment] Improvement generation failed: {}", e.getMessage());
            return new ImprovementResponseDto(List.of(), List.of());
        }
    }

    @Transactional
    public ResumeAssessment buildAndPersistEntity(
            String sessionId, fit.iuh.modules.assessment.entity.JobCategory jobCategory,
            fit.iuh.modules.assessment.entity.SeniorityLevel seniorityLevel,
            ScoringResult scoringResult,
            List<AssessmentResponseDto.AdHocEvidenceItem> preferToHaveItems,
            List<AssessmentResponseDto.EvidenceItem> gateItems,
            ImprovementResponseDto improvements, EligibilityStatus eligibility) {

        ResumeAssessment entity = ResumeAssessment.builder()
                .sessionId(sessionId)
                .jobCategory(jobCategory)
                .seniorityLevel(seniorityLevel)
                .overallMatchScore(scoringResult.overallScore())
                .eligibility(eligibility)
                .build();

        List<fit.iuh.modules.assessment.entity.EvidenceItem> evidenceEntities = new ArrayList<>();
        if (scoringResult.updatedItems() != null) {
            for (var item : scoringResult.updatedItems()) {
                evidenceEntities.add(fit.iuh.modules.assessment.entity.EvidenceItem.builder()
                        .assessment(entity)
                        .criteriaId(item.criteriaId() != null ? item.criteriaId().intValue() : null)
                        .criteriaName(item.criteriaName())
                        .importance(item.importance())
                        .jdRequirement(item.jdRequirement())
                        .cvEvidence(item.cvEvidence())
                        .status(item.status())
                        .reasoning(item.reasoning())
                        .build());
            }
        }
        if (preferToHaveItems != null) {
            for (var item : preferToHaveItems) {
                evidenceEntities.add(fit.iuh.modules.assessment.entity.EvidenceItem.builder()
                        .assessment(entity)
                        .criteriaId(item.criteriaId() != null ? item.criteriaId().intValue() : null)
                        .criteriaName(item.criteriaName())
                        .importance(item.importance())
                        .jdRequirement(item.jdRequirement())
                        .cvEvidence(item.cvEvidence())
                        .status(item.status())
                        .reasoning(item.reasoning())
                        .build());
            }
        }
        if (gateItems != null) {
            for (var item : gateItems) {
                evidenceEntities.add(fit.iuh.modules.assessment.entity.EvidenceItem.builder()
                        .assessment(entity)
                        .criteriaId(item.criteriaId() != null ? item.criteriaId().intValue() : null)
                        .criteriaName(item.criteriaName())
                        .importance(item.importance())
                        .jdRequirement(item.jdRequirement())
                        .cvEvidence(item.cvEvidence())
                        .status(item.status())
                        .reasoning(item.reasoning())
                        .build());
            }
        }
        entity.setEvidenceItems(evidenceEntities);

        List<fit.iuh.modules.assessment.entity.ScoreBreakdown> breakdownEntities = new ArrayList<>();
        if (scoringResult.breakdown() != null) {
            breakdownEntities.add(fit.iuh.modules.assessment.entity.ScoreBreakdown.builder()
                    .assessment(entity)
                    .category("Must-Have")
                    .score(scoringResult.breakdown().rawMustHaveScore())
                    .maxScore(100)
                    .feedback("Weight: " + scoringResult.breakdown().mustHaveWeightRatio())
                    .build());
            breakdownEntities.add(fit.iuh.modules.assessment.entity.ScoreBreakdown.builder()
                    .assessment(entity)
                    .category("Prefer-To-Have")
                    .score(scoringResult.breakdown().rawPreferToHaveScore())
                    .maxScore(100)
                    .feedback("Weight: " + scoringResult.breakdown().preferToHaveWeightRatio())
                    .build());
            breakdownEntities.add(fit.iuh.modules.assessment.entity.ScoreBreakdown.builder()
                    .assessment(entity)
                    .category("Overall")
                    .score(scoringResult.breakdown().finalScore())
                    .maxScore(100)
                    .feedback("Final Score")
                    .build());
        }
        entity.setScoreBreakdowns(breakdownEntities);

        List<fit.iuh.modules.assessment.entity.Improvement> improvementEntities = new ArrayList<>();
        if (improvements != null) {
            int rank = 1;
            if (improvements.quickWins() != null) {
                for (var imp : improvements.quickWins()) {
                    improvementEntities.add(fit.iuh.modules.assessment.entity.Improvement.builder()
                            .assessment(entity)
                            .priorityRank(rank++)
                            .topic("[QW] " + imp.criteriaName())
                            .suggestionDetails(imp.actionableAdvice())
                            .build());
                }
            }
            if (improvements.skillGaps() != null) {
                for (var imp : improvements.skillGaps()) {
                    improvementEntities.add(fit.iuh.modules.assessment.entity.Improvement.builder()
                            .assessment(entity)
                            .priorityRank(rank++)
                            .topic("[SG] " + imp.criteriaName())
                            .suggestionDetails(imp.actionableAdvice())
                            .build());
                }
            }
        }
        entity.setImprovements(improvementEntities);

        return resumeAssessmentRepository.save(entity);
    }

    private AssessmentResponse cloneAndBuildResponse(String sessionId, ResumeAssessment otherAssessment) {
        ResumeAssessment clonedAssessment = ResumeAssessment.builder()
                .sessionId(sessionId)
                .jobCategory(otherAssessment.getJobCategory())
                .seniorityLevel(otherAssessment.getSeniorityLevel())
                .overallMatchScore(otherAssessment.getOverallMatchScore())
                .eligibility(otherAssessment.getEligibility())
                .build();

        List<fit.iuh.modules.assessment.entity.EvidenceItem> clonedEvidences = new ArrayList<>();
        if (otherAssessment.getEvidenceItems() != null) {
            for (var ev : otherAssessment.getEvidenceItems()) {
                clonedEvidences.add(fit.iuh.modules.assessment.entity.EvidenceItem.builder()
                        .assessment(clonedAssessment)
                        .criteriaId(ev.getCriteriaId())
                        .criteriaName(ev.getCriteriaName())
                        .importance(ev.getImportance())
                        .jdRequirement(ev.getJdRequirement())
                        .cvEvidence(ev.getCvEvidence())
                        .status(ev.getStatus())
                        .reasoning(ev.getReasoning())
                        .build());
            }
        }
        clonedAssessment.setEvidenceItems(clonedEvidences);

        List<fit.iuh.modules.assessment.entity.ScoreBreakdown> clonedBreakdowns = new ArrayList<>();
        if (otherAssessment.getScoreBreakdowns() != null) {
            for (var sb : otherAssessment.getScoreBreakdowns()) {
                clonedBreakdowns.add(fit.iuh.modules.assessment.entity.ScoreBreakdown.builder()
                        .assessment(clonedAssessment)
                        .category(sb.getCategory())
                        .score(sb.getScore())
                        .maxScore(sb.getMaxScore())
                        .feedback(sb.getFeedback())
                        .build());
            }
        }
        clonedAssessment.setScoreBreakdowns(clonedBreakdowns);

        List<fit.iuh.modules.assessment.entity.Improvement> clonedImprovements = new ArrayList<>();
        if (otherAssessment.getImprovements() != null) {
            for (var imp : otherAssessment.getImprovements()) {
                clonedImprovements.add(fit.iuh.modules.assessment.entity.Improvement.builder()
                        .assessment(clonedAssessment)
                        .priorityRank(imp.getPriorityRank())
                        .topic(imp.getTopic())
                        .suggestionDetails(imp.getSuggestionDetails())
                        .build());
            }
        }
        clonedAssessment.setImprovements(clonedImprovements);

        ResumeAssessment savedCloned = resumeAssessmentRepository.save(clonedAssessment);
        return toResponse(savedCloned, true);
    }

    private AssessmentResponse toResponse(ResumeAssessment entity, boolean cached) {
        return AssessmentResponse.builder()
                .id(entity.getId())
                .sessionId(entity.getSessionId())
                .jobCategory(entity.getJobCategory())
                .seniorityLevel(entity.getSeniorityLevel())
                .overallMatchScore(entity.getOverallMatchScore())
                .mustHaveEvidenceItems(mapToMustHaveDto(entity.getEvidenceItems()))
                .preferToHaveEvidenceItems(mapToPreferDto(entity.getEvidenceItems()))
                .gateEvidenceItems(mapToGateDto(entity.getEvidenceItems()))
                .scoreBreakdown(mapToScoreBreakdownDto(entity.getScoreBreakdowns(), entity.getOverallMatchScore()))
                .quickWins(mapToImprovementDto(entity.getImprovements(), "[QW]"))
                .skillGaps(mapToImprovementDto(entity.getImprovements(), "[SG]"))
                .eligibility(entity.getEligibility())
                .cached(cached)
                .createdAt(entity.getCreatedAt())
                .build();
    }

    private AssessmentResponse.ScoreBreakdown mapToScoreBreakdownDto(
            List<fit.iuh.modules.assessment.entity.ScoreBreakdown> breakdowns, Integer overallMatchScore) {
        if (breakdowns == null || breakdowns.isEmpty()) {
            int score = overallMatchScore != null ? overallMatchScore : 0;
            return new AssessmentResponse.ScoreBreakdown(score, 0.8, score, 0.2, score);
        }
        int mustHave = 0;
        double mustHaveRatio = 0.8;
        int prefer = 0;
        double preferRatio = 0.2;
        int overall = overallMatchScore != null ? overallMatchScore : 0;

        for (var b : breakdowns) {
            if ("Must-Have".equalsIgnoreCase(b.getCategory())) {
                mustHave = b.getScore() != null ? b.getScore() : 0;
                if (b.getFeedback() != null && b.getFeedback().startsWith("Weight: ")) {
                    try {
                        mustHaveRatio = Double.parseDouble(b.getFeedback().substring(8).trim());
                    } catch (Exception ignored) {}
                }
            } else if ("Prefer-To-Have".equalsIgnoreCase(b.getCategory())) {
                prefer = b.getScore() != null ? b.getScore() : 0;
                if (b.getFeedback() != null && b.getFeedback().startsWith("Weight: ")) {
                    try {
                        preferRatio = Double.parseDouble(b.getFeedback().substring(8).trim());
                    } catch (Exception ignored) {}
                }
            } else if ("Overall".equalsIgnoreCase(b.getCategory()) && b.getScore() != null) {
                overall = b.getScore();
            }
        }
        return new AssessmentResponse.ScoreBreakdown(mustHave, mustHaveRatio, prefer, preferRatio, overall);
    }

    private List<AssessmentResponseDto.EvidenceItem> mapToMustHaveDto(List<fit.iuh.modules.assessment.entity.EvidenceItem> items) {
        return AssessmentMapper.mapToMustHaveDto(items);
    }

    private List<AssessmentResponseDto.EvidenceItem> mapToGateDto(List<fit.iuh.modules.assessment.entity.EvidenceItem> items) {
        return AssessmentMapper.mapToGateDto(items);
    }

    private List<AssessmentResponseDto.AdHocEvidenceItem> mapToPreferDto(List<fit.iuh.modules.assessment.entity.EvidenceItem> items) {
        return AssessmentMapper.mapToPreferDto(items);
    }

    private List<ImprovementResponseDto.ImprovementItem> mapToImprovementDto(List<fit.iuh.modules.assessment.entity.Improvement> items, String prefix) {
        if (items == null) return List.of();
        return items.stream()
                .filter(i -> i.getTopic() != null && i.getTopic().startsWith(prefix))
                .sorted(Comparator.comparing(fit.iuh.modules.assessment.entity.Improvement::getPriorityRank))
                .map(i -> new ImprovementResponseDto.ImprovementItem(
                        i.getTopic().substring(5).trim(),
                        i.getSuggestionDetails(),
                        String.valueOf(i.getPriorityRank())
                ))
                .collect(Collectors.toList());
    }

    private List<AssessmentResponseDto.AdHocEvidenceItem> filterDuplicateAdHocItems(
            List<AssessmentResponseDto.EvidenceItem> standardItems,
            List<AssessmentResponseDto.AdHocEvidenceItem> adHocItems) {

        if (adHocItems == null || adHocItems.isEmpty()) return List.of();

        Set<String> standardNamesLower = (standardItems != null)
                ? standardItems.stream()
                .map(item -> item.criteriaName() != null ? item.criteriaName().toLowerCase(Locale.ROOT).trim() : "")
                .filter(name -> !name.isEmpty())
                .collect(Collectors.toSet())
                : Set.of();

        Map<String, AssessmentResponseDto.AdHocEvidenceItem> uniqueAdHocMap = new LinkedHashMap<>();
        for (AssessmentResponseDto.AdHocEvidenceItem item : adHocItems) {
            if (item == null || item.criteriaName() == null || item.criteriaName().isBlank()) continue;

            String adHocNameLower = item.criteriaName().toLowerCase(Locale.ROOT).trim();
            boolean matchesStandard = standardNamesLower.stream()
                    .anyMatch(stdName -> isDuplicateCriteriaName(stdName, adHocNameLower));

            if (matchesStandard) continue;
            uniqueAdHocMap.putIfAbsent(adHocNameLower, item);
        }
        return new ArrayList<>(uniqueAdHocMap.values());
    }

    private boolean isDuplicateCriteriaName(String stdName, String adHocName) {
        if (stdName.equals(adHocName)) return true;
        if (stdName.contains(adHocName) || adHocName.contains(stdName)) {
            int minLen = Math.min(stdName.length(), adHocName.length());
            return minLen >= 4;
        }
        String[] techPrefixes = {"aws", "docker", "ci/cd", "ci cd", "git", "spring", "react", "postgresql", "mysql", "database", "testing", "unit test", "kubernetes", "linux"};
        for (String prefix : techPrefixes) {
            if (stdName.startsWith(prefix) && adHocName.startsWith(prefix)) return true;
        }
        return false;
    }
}