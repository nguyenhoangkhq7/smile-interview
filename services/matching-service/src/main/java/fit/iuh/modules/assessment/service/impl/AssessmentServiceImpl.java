package fit.iuh.modules.assessment.service.impl;

import com.fasterxml.jackson.databind.ObjectMapper;
import fit.iuh.exception.LlmApiException;
import fit.iuh.modules.admin.repository.SystemSettingRepository;
import fit.iuh.modules.assessment.dto.*;
import fit.iuh.modules.assessment.entity.EligibilityStatus;
import fit.iuh.modules.assessment.entity.ResumeAssessment;
import fit.iuh.modules.assessment.repository.ResumeAssessmentRepository;
import fit.iuh.modules.assessment.service.*;
import fit.iuh.modules.assessment.service.AssessmentCriteriaPreparer.MetadataResult;
import fit.iuh.modules.assessment.service.AssessmentCriteriaPreparer.PreparedJdBundle;
import fit.iuh.modules.assessment.service.AssessmentScoringEngine.ScoringResult;
import fit.iuh.modules.session.entity.Session;
import fit.iuh.modules.session.repository.SessionRepository;
import fit.iuh.modules.rulengine.repository.JobCriteriaRepository.CriteriaWeightProjection;
import lombok.AllArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.data.redis.core.StringRedisTemplate;

import java.time.Duration;
import java.util.*;
import java.util.stream.Collectors;

/**
 * High-performance Orchestrator Service for resume assessment utilizing 2-Phase Hybrid LLM architecture:
 * Phase 1: Consolidated single-pass JD analysis (Metadata, Gates, Criteria Classification in 1 LLM Call).
 * Phase 2: Batched CV evaluation with self-consistency voting and evidence grounding.
 */
@Slf4j
@Service
@AllArgsConstructor
public class AssessmentServiceImpl implements AssessmentService {

    private static final String STATUS_NOT_APPLICABLE = "not_applicable";
    private static final String IMPORTANCE_NOT_APPLICABLE = "NOT_APPLICABLE";

    private final ResumeAssessmentRepository resumeAssessmentRepository;
    private final SessionRepository sessionRepository;
    private final SystemSettingRepository systemSettingRepository;
    private final AssessmentCriteriaPreparer criteriaPreparer;
    private final AssessmentLlmRunner llmRunner;
    private final AssessmentScoringEngine scoringEngine;
    private final ObjectMapper objectMapper;
    private final fit.iuh.config.AppProperties appProperties;
    private final StringRedisTemplate stringRedisTemplate;

    public record CriteriaWeightDto(
            Long criteriaId,
            String criteriaName,
            String promptInstruction,
            String levelPromptInstruction,
            Double weightPercentage,
            String embedding
    ) implements CriteriaWeightProjection {
        @Override public Long getCriteriaId() { return criteriaId; }
        @Override public String getCriteriaName() { return criteriaName; }
        @Override public String getPromptInstruction() { return promptInstruction; }
        @Override public String getLevelPromptInstruction() { return levelPromptInstruction; }
        @Override public Double getWeightPercentage() { return weightPercentage; }
        @Override public String getEmbedding() { return embedding; }
    }

    public record JdPhase1And4Bundle(
            PreparedJdBundle preparedJd,
            List<CriteriaWeightDto> criteriaList
    ) {}

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

        log.info("[PIPELINE START] 2-PHASE ASSESSMENT PIPELINE | SessionId: {}, ForceRefresh: {}, FromSessionId: {}", sessionId, forceRefresh, fromSessionId);

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

        boolean shouldIncludeNotApp = includeNotApplicable != null
                ? includeNotApplicable
                : (systemSettingRepository != null && systemSettingRepository.getBoolean("INCLUDE_NOT_APPLICABLE_CRITERIA", false));

        // Execute Step 3 and Step 4 with caching
        JdPhase1And4Bundle phase1And4Bundle = executeAndCachePhase1And4(
                session.getJobDescription().getId().toString(),
                fullJdMarkdown,
                sessionId,
                shouldIncludeNotApp
        );

        PreparedJdBundle preparedJd = phase1And4Bundle.preparedJd();
        MetadataResult metadata = preparedJd.metadata();
        ClassifiedCriteriaBundle bundle = preparedJd.bundle();
        List<CriteriaWeightProjection> criteriaList = new ArrayList<>(phase1And4Bundle.criteriaList());

        // Step 5: Phase 2 — Batched LLM assessment pipeline with self-consistency voting
        log.info("[STEP 5/7] Phase 2 — Running Batched LLM assessment pipeline with self-consistency voting for sessionId: {}...", sessionId);
        AssessmentResponseDto dto = llmRunner.runBatchedAssessmentWithSelfConsistencyClassified(
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

        dto = filterNotApplicableItemsIfNeeded(dto, filteredAdHoc, shouldIncludeNotApp);
        log.info("[STEP 5/7] [DEBUG] Phase 2 LLM Assessment Output -> Must-Have Evidence Items: {}, Prefer-To-Have / Ad-Hoc Items: {}",
                dto.mustHaveEvidenceItems() != null ? dto.mustHaveEvidenceItems().size() : 0,
                dto.preferToHaveEvidenceItems() != null ? dto.preferToHaveEvidenceItems().size() : 0);

        // Step 6: Calculate final scores and evaluate hard eligibility gate checks
        log.info("[STEP 6/7] Calculating final weighted scores and evaluating eligibility gates...");
        ScoringResult scoringResult = scoringEngine.calculateWithBreakdown(
                dto.mustHaveEvidenceItems(),
                dto.preferToHaveEvidenceItems(),
                criteriaList,
                metadata.level()
        );

        var eligibilityResult = criteriaPreparer.evaluateEligibilityWithRawGates(
                preparedJd.rawGateRequirements(), fullJdMarkdown, fullCvMarkdown);
        EligibilityStatus eligibility = eligibilityResult.status();
        log.info("[STEP 6/7] [DEBUG] Scoring Result -> Overall Score: {}%, Category Breakdown: {}", scoringResult.overallScore(), scoringResult.breakdown());
        log.info("[STEP 6/7] [DEBUG] Eligibility Check -> Status: {}", eligibility);

        // Step 7: Generate grounded improvement recommendations and persist assessment
        log.info("[STEP 7/7] Generating resume improvements and persisting assessment entity for sessionId: {}...", sessionId);
        List<Map<String, String>> weaknesses = extractWeaknesses(scoringResult.updatedItems());
        log.info("[STEP 7/7] [DEBUG] Extracted Weaknesses Count: {}", weaknesses.size());

        List<ImprovementResponseDto.ImprovementItem> improvements = generateTopImprovements(sessionId, weaknesses, fullCvMarkdown);
        log.info("[STEP 7/7] [DEBUG] Top Improvements Generated ({}) -> {}", improvements.size(),
                improvements.stream().map(ImprovementResponseDto.ImprovementItem::criteriaName).collect(Collectors.joining("; ")));

        ResumeAssessment entity = buildAndPersistEntity(sessionId, metadata, scoringResult, dto.preferToHaveEvidenceItems(), eligibilityResult.gateItems(), improvements, eligibility);
        log.info("[STEP 7/7] [DEBUG] Entity Persisted Successfully -> ID: {}, SessionId: {}", entity.getId(), entity.getSessionId());

        AssessmentResponse response = toResponse(entity, false);
        response.setScoreBreakdown(scoringResult.breakdown());
        log.info("[PIPELINE COMPLETE] Assessment successfully saved and returned for sessionId: {} | Final Score: {}% | Eligibility: {}",
                sessionId, scoringResult.overallScore(), eligibility);
        return response;
    }

    private JdPhase1And4Bundle executeAndCachePhase1And4(String jdId, String fullJdMarkdown, String sessionId, boolean shouldIncludeNotApp) {
        String cacheKey = "jd_p1_p4:v1:" + jdId + ":" + shouldIncludeNotApp;
        try {
            String cachedData = stringRedisTemplate.opsForValue().get(cacheKey);
            if (cachedData != null) {
                log.info("[Phase1+4-Cache] HIT! Reusing Phase 1 & 4 profile for JD {} (0ms, 0 LLM calls).", jdId);
                return objectMapper.readValue(cachedData, JdPhase1And4Bundle.class);
            }
        } catch (Exception e) {
            log.warn("[Phase1+4-Cache] Warning: Failed to read from Redis for cacheKey {}: {}", cacheKey, e.getMessage());
        }

        // Run Step 3
        log.info("[STEP 3/7] Phase 1 — Preparing JD (3-Pass LLM: Metadata, Gates & Classification)...");
        PreparedJdBundle preparedJd = criteriaPreparer.prepareJdConsolidatedSinglePass(jdId, fullJdMarkdown);
        MetadataResult metadata = preparedJd.metadata();
        ClassifiedCriteriaBundle bundle = preparedJd.bundle();

        // Run Step 4
        log.info("[STEP 4/7] Recording discovered Ad-hoc criteria and loading domain criteria tree for Category: {}, Level: {}...", metadata.category(), metadata.level());
        recordAdHocCriteriaPreAssessment(metadata, bundle);
        List<CriteriaWeightProjection> criteriaListProj = criteriaPreparer.loadAndFilterCriteria(
                metadata.category().name(),
                metadata.level().name(),
                sessionId,
                fullJdMarkdown,
                shouldIncludeNotApp
        );

        List<CriteriaWeightDto> criteriaListDto = criteriaListProj.stream()
                .map(c -> new CriteriaWeightDto(
                        c.getCriteriaId(),
                        c.getCriteriaName(),
                        c.getPromptInstruction(),
                        c.getLevelPromptInstruction(),
                        c.getWeightPercentage(),
                        c.getEmbedding()
                ))
                .collect(Collectors.toList());

        JdPhase1And4Bundle bundleToCache = new JdPhase1And4Bundle(preparedJd, criteriaListDto);

        try {
            String json = objectMapper.writeValueAsString(bundleToCache);
            stringRedisTemplate.opsForValue().set(cacheKey, json, Duration.ofDays(30));
        } catch (Exception e) {
            log.warn("[Phase1+4-Cache] Warning: Failed to save to Redis for cacheKey {}: {}", cacheKey, e.getMessage());
        }

        return bundleToCache;
    }

    private Optional<AssessmentResponse> checkCachedAssessment(String sessionId, boolean forceRefresh, String fromSessionId) {
        if (!forceRefresh) {
            if (resumeAssessmentRepository.existsBySessionId(sessionId)) {
                log.info("[Assessment] Cache HIT for sessionId={}. Returning saved assessment.", sessionId);
                var entity = resumeAssessmentRepository.findBySessionId(sessionId).get();
                return Optional.of(buildResponseWithScoring(sessionId, entity, toResponse(entity, true)));
            }

            if (fromSessionId != null && !fromSessionId.isBlank()) {
                Optional<ResumeAssessment> otherOpt = resumeAssessmentRepository.findBySessionId(fromSessionId);
                if (otherOpt.isPresent()) {
                    log.info("[Assessment] Session-cloning HIT! Reusing assessment from sessionId={} for new sessionId={}", fromSessionId, sessionId);
                    return Optional.of(cloneAndBuildResponse(sessionId, otherOpt.get()));
                }
            }

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
        } else if (resumeAssessmentRepository.existsBySessionId(sessionId)) {
            log.warn("[Assessment] Force-refresh for sessionId={}. Deleting cached result.", sessionId);
            resumeAssessmentRepository.deleteBySessionId(sessionId);
            resumeAssessmentRepository.flush();
        }
        return Optional.empty();
    }

    private void recordAdHocCriteriaPreAssessment(MetadataResult metadata, ClassifiedCriteriaBundle bundle) {
        try {
            List<AssessmentResponseDto.AdHocEvidenceItem> jdExtrasForRecording = bundle.jdExtras().stream()
                    .map(e -> new AssessmentResponseDto.AdHocEvidenceItem(
                            null, e.name(), e.importance(), e.promptInstruction(), null, null, null, null))
                    .collect(Collectors.toList());
            criteriaPreparer.recordAdHocCriteria(metadata.category(), jdExtrasForRecording);
        } catch (Exception e) {
            log.warn("[Assessment] Non-blocking warning recording ad-hoc criteria: {}", e.getMessage());
        }
    }

    private AssessmentResponseDto filterNotApplicableItemsIfNeeded(
            AssessmentResponseDto dto,
            List<AssessmentResponseDto.AdHocEvidenceItem> filteredAdHoc,
            boolean shouldIncludeNotApp) {

        if (!shouldIncludeNotApp) {
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
        return new AssessmentResponseDto(dto.mustHaveEvidenceItems(), filteredAdHoc);
    }

    private List<Map<String, String>> extractWeaknesses(List<AssessmentResponseDto.EvidenceItem> items) {
        List<Map<String, String>> weaknesses = new ArrayList<>();
        if (items == null) return weaknesses;
        for (var item : items) {
            if ("weak".equalsIgnoreCase(item.status()) || "missing".equalsIgnoreCase(item.status())) {
                weaknesses.add(Map.of(
                        "name", item.criteriaName() != null ? item.criteriaName() : "",
                        "requirement", item.jdRequirement() != null ? item.jdRequirement() : "",
                        "reasoning", item.reasoning() != null ? item.reasoning() : ""
                ));
            }
        }
        return weaknesses;
    }

    private List<ImprovementResponseDto.ImprovementItem> generateTopImprovements(
            String sessionId, List<Map<String, String>> weaknesses, String cvMarkdown) {
        if (weaknesses.isEmpty()) return List.of();
        try {
            String jsonStr = objectMapper.writeValueAsString(weaknesses);
            String sysPrompt = "You are a career expert. Analyze candidate weaknesses and generate top priority resume improvements in valid JSON matching the ImprovementResponseDto schema.";
            String userPrompt = "Generate top priority resume improvements based on weaknesses:\n" + jsonStr;
            String llmRes = llmRunner.callLlmBlockingWithSemaphore(sysPrompt, userPrompt);
            String clean = fit.iuh.modules.assessment.util.TextSanitizationUtil.extractCleanJson(llmRes);
            var res = objectMapper.readValue(clean, ImprovementResponseDto.class);
            return res != null && res.topPriorityImprovements() != null ? res.topPriorityImprovements() : List.of();
        } catch (Exception e) {
            log.warn("[Assessment] Improvement generation failed: {}", e.getMessage());
            return List.of();
        }
    }

    private ResumeAssessment buildAndPersistEntity(
            String sessionId, MetadataResult metadata, ScoringResult scoringResult,
            List<AssessmentResponseDto.AdHocEvidenceItem> preferToHaveItems,
            List<AssessmentResponseDto.EvidenceItem> gateItems,
            List<ImprovementResponseDto.ImprovementItem> improvements, EligibilityStatus eligibility) {

        ResumeAssessment entity = ResumeAssessment.builder()
                .sessionId(sessionId)
                .jobCategory(metadata.category())
                .seniorityLevel(metadata.level())
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
            // AssessmentResponse.ScoreBreakdown contains rawMustHaveScore, etc.
            // Let's store MustHave and PreferToHave as categories
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
            for (int i = 0; i < improvements.size(); i++) {
                var imp = improvements.get(i);
                improvementEntities.add(fit.iuh.modules.assessment.entity.Improvement.builder()
                        .assessment(entity)
                        .priorityRank(i + 1)
                        .topic(imp.criteriaName())
                        .suggestionDetails(imp.actionableAdvice())
                        .build());
            }
        }
        entity.setImprovements(improvementEntities);

        return resumeAssessmentRepository.save(entity);
    }

    private AssessmentResponse buildResponseWithScoring(String sessionId, ResumeAssessment entity, AssessmentResponse response) {
        List<CriteriaWeightProjection> criteriaList = criteriaPreparer.loadAndFilterCriteria(
                entity.getJobCategory().name(),
                entity.getSeniorityLevel().name(),
                sessionId,
                "",
                true
        );
        List<AssessmentResponseDto.EvidenceItem> mustHave = mapToMustHaveDto(entity.getEvidenceItems());
        List<AssessmentResponseDto.AdHocEvidenceItem> prefer = mapToPreferDto(entity.getEvidenceItems());

        ScoringResult scoringResult = scoringEngine.calculateWithBreakdown(
                mustHave,
                prefer,
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
        return buildResponseWithScoring(sessionId, clonedAssessment, toResponse(savedCloned, true));
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
                .topPriorityImprovements(mapToImprovementDto(entity.getImprovements()))
                .eligibility(entity.getEligibility())
                .cached(cached)
                .createdAt(entity.getCreatedAt())
                .build();
    }

    private List<AssessmentResponseDto.EvidenceItem> mapToMustHaveDto(List<fit.iuh.modules.assessment.entity.EvidenceItem> items) {
        if (items == null) return List.of();
        return items.stream()
                .filter(i -> !"PREFERRED".equalsIgnoreCase(i.getImportance()) && !"GATE".equalsIgnoreCase(i.getImportance()))
                .map(i -> new AssessmentResponseDto.EvidenceItem(
                        i.getCriteriaId() != null ? i.getCriteriaId().longValue() : null,
                        i.getCriteriaName(), i.getImportance(), i.getJdRequirement(), i.getCvEvidence(),
                        null, i.getStatus(), i.getReasoning(), null, null, null, null, null, null
                )).collect(Collectors.toList());
    }

    private List<AssessmentResponseDto.EvidenceItem> mapToGateDto(List<fit.iuh.modules.assessment.entity.EvidenceItem> items) {
        if (items == null) return List.of();
        return items.stream()
                .filter(i -> "GATE".equalsIgnoreCase(i.getImportance()))
                .map(i -> new AssessmentResponseDto.EvidenceItem(
                        i.getCriteriaId() != null ? i.getCriteriaId().longValue() : null,
                        i.getCriteriaName(), i.getImportance(), i.getJdRequirement(), i.getCvEvidence(),
                        null, i.getStatus(), i.getReasoning(), null, null, null, null, null, null
                )).collect(Collectors.toList());
    }

    private List<AssessmentResponseDto.AdHocEvidenceItem> mapToPreferDto(List<fit.iuh.modules.assessment.entity.EvidenceItem> items) {
        if (items == null) return List.of();
        return items.stream()
                .filter(i -> "PREFERRED".equalsIgnoreCase(i.getImportance()))
                .map(i -> new AssessmentResponseDto.AdHocEvidenceItem(
                        i.getCriteriaId() != null ? i.getCriteriaId().longValue() : null,
                        i.getCriteriaName(), i.getImportance(), null, i.getJdRequirement(),
                        i.getCvEvidence(), i.getStatus(), i.getReasoning()
                )).collect(Collectors.toList());
    }

    private List<ImprovementResponseDto.ImprovementItem> mapToImprovementDto(List<fit.iuh.modules.assessment.entity.Improvement> items) {
        if (items == null) return List.of();
        return items.stream()
                .sorted(Comparator.comparing(fit.iuh.modules.assessment.entity.Improvement::getPriorityRank))
                .map(i -> new ImprovementResponseDto.ImprovementItem(i.getTopic(), i.getSuggestionDetails(), String.valueOf(i.getPriorityRank())))
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

    @Override
    public AssessmentResponseDto runBatchedAssessmentWithSelfConsistency(
            String sessionId, String fullCvMarkdown, String fullJdMarkdown, List<CriteriaWeightProjection> criteriaList) {
        return llmRunner.runBatchedAssessmentWithSelfConsistency(sessionId, fullCvMarkdown, fullJdMarkdown, criteriaList);
    }
}
