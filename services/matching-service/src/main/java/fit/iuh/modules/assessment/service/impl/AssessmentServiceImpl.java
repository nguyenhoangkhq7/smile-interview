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
import fit.iuh.modules.session.entity.JobDescription;
import fit.iuh.modules.session.entity.Resume;
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

        // Execute Step 3 and Step 4 with caching per target level
        JdPhase1And4Bundle phase1And4Bundle = executeAndCachePhase1And4(
                session.getJobDescription().getId().toString(),
                fullJdMarkdown,
                fullCvMarkdown,
                session,
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

        // Step 6 & 7: Calculate final scores, evaluate hard eligibility gate checks, and generate improvements concurrently
        log.info("[STEP 6/7 & 7/7] Executing Scoring, Eligibility Check, and Improvements generation in parallel...");

        final AssessmentResponseDto finalDto = dto;

        java.util.concurrent.CompletableFuture<ScoringResult> scoringFuture = java.util.concurrent.CompletableFuture.supplyAsync(() -> 
                scoringEngine.calculateWithBreakdown(
                        finalDto.mustHaveEvidenceItems(),
                        finalDto.preferToHaveEvidenceItems(),
                        criteriaList,
                        metadata.level()
                )
        );

        java.util.concurrent.CompletableFuture<AssessmentCriteriaPreparer.EligibilityEvaluationResult> eligibilityFuture = java.util.concurrent.CompletableFuture.supplyAsync(() -> {
            var rawResult = criteriaPreparer.evaluateEligibilityWithRawGates(
                    preparedJd.rawGateRequirements(), fullJdMarkdown, fullCvMarkdown
            );
            
            // GATE SYNC ENGINE: Cross-check NOT_EVALUATED gates with LLM Evidence
            if (rawResult != null && rawResult.gateItems() != null) {
                List<AssessmentResponseDto.EvidenceItem> syncedGates = new ArrayList<>();
                boolean anySynced = false;
                for (var gate : rawResult.gateItems()) {
                    if ("NOT_EVALUATED".equals(gate.status())) {
                        var newGate = syncGateWithLlmEvidence(gate, finalDto.mustHaveEvidenceItems());
                        if (newGate == null) newGate = syncGateWithLlmEvidenceAdHoc(gate, finalDto.preferToHaveEvidenceItems());
                        
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
                
                // Re-evaluate overall eligibility status if gates were synced
                boolean allRequiredMet = syncedGates.stream()
                        .filter(g -> "REQUIRED".equalsIgnoreCase(g.importance()))
                        .allMatch(g -> "met".equalsIgnoreCase(g.status()) || "PASSED".equalsIgnoreCase(g.status()) || "NOT_EVALUATED".equalsIgnoreCase(g.status()));
                if (anySynced && rawResult.status() == EligibilityStatus.NOT_ELIGIBILITY && allRequiredMet) {
                    rawResult = new AssessmentCriteriaPreparer.EligibilityEvaluationResult(EligibilityStatus.ELIGIBILITY, syncedGates);
                } else if (anySynced) {
                    rawResult = new AssessmentCriteriaPreparer.EligibilityEvaluationResult(rawResult.status(), syncedGates);
                }
            }
            return rawResult;
        });

        java.util.concurrent.CompletableFuture<ImprovementResponseDto> improvementsFuture = java.util.concurrent.CompletableFuture.supplyAsync(() -> {
            List<Map<String, String>> weaknesses = extractWeaknesses(finalDto.mustHaveEvidenceItems());
            log.info("[STEP 7/7] [DEBUG] Extracted Weaknesses Count for Improvements: {}", weaknesses.size());
            return generateTopImprovements(sessionId, weaknesses, fullCvMarkdown);
        });

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
        ResumeAssessment entity = buildAndPersistEntity(sessionId, metadata, scoringResult, finalDto.preferToHaveEvidenceItems(), eligibilityResult.gateItems(), improvements, eligibility);
        log.info("[STEP 7/7] [DEBUG] Entity Persisted Successfully -> ID: {}, SessionId: {}", entity.getId(), entity.getSessionId());

        AssessmentResponse response = toResponse(entity, false);
        response.setScoreBreakdown(scoringResult.breakdown());
        extractAndSetUiBadges(response);
        log.info("[PIPELINE COMPLETE] Assessment successfully saved and returned for sessionId: {} | Final Score: {}% | Eligibility: {}",
                sessionId, scoringResult.overallScore(), eligibility);
        return response;
    }

    private void extractAndSetUiBadges(AssessmentResponse response) {
        if (response.getMustHaveEvidenceItems() != null) {
            List<AssessmentResponseDto.EvidenceItem> updated = new ArrayList<>();
            for (var item : response.getMustHaveEvidenceItems()) {
                updated.add(extractBadgeFromMustHave(item));
            }
            response.setMustHaveEvidenceItems(updated);
        }

        if (response.getPreferToHaveEvidenceItems() != null) {
            List<AssessmentResponseDto.AdHocEvidenceItem> updated = new ArrayList<>();
            for (var item : response.getPreferToHaveEvidenceItems()) {
                updated.add(extractBadgeFromPreferToHave(item));
            }
            response.setPreferToHaveEvidenceItems(updated);
        }
    }

    private AssessmentResponseDto.EvidenceItem extractBadgeFromMustHave(AssessmentResponseDto.EvidenceItem item) {
        if (item.reasoning() == null || !item.reasoning().contains("[Ontology:")) return item;
        
        java.util.regex.Pattern pattern = java.util.regex.Pattern.compile("\\[Ontology:\\s*(.*?)\\]");
        java.util.regex.Matcher matcher = pattern.matcher(item.reasoning());
        
        if (matcher.find()) {
            String badgeLabel = matcher.group(1).trim();
            String cleanReasoning = matcher.replaceAll("").trim();
            
            AssessmentResponseDto.MatchMetadata metadata = new AssessmentResponseDto.MatchMetadata(
                    "ontology", badgeLabel, "purple"
            );
            
            return new AssessmentResponseDto.EvidenceItem(
                    item.criteriaId(), item.criteriaName(), item.importance(), item.jdRequirement(),
                    item.cvEvidence(), item.cvQuote(), item.status(), cleanReasoning,
                    item.weightUsed(), item.scoreContribution(), item.groundingScore(),
                    item.confidenceVotes(), item.lowConfidence(), item.needsManualReview(), metadata
            );
        }
        return item;
    }

    private AssessmentResponseDto.AdHocEvidenceItem extractBadgeFromPreferToHave(AssessmentResponseDto.AdHocEvidenceItem item) {
        if (item.reasoning() == null || !item.reasoning().contains("[Ontology:")) return item;
        
        java.util.regex.Pattern pattern = java.util.regex.Pattern.compile("\\[Ontology:\\s*(.*?)\\]");
        java.util.regex.Matcher matcher = pattern.matcher(item.reasoning());
        
        if (matcher.find()) {
            String badgeLabel = matcher.group(1).trim();
            String cleanReasoning = matcher.replaceAll("").trim();
            
            AssessmentResponseDto.MatchMetadata metadata = new AssessmentResponseDto.MatchMetadata(
                    "ontology", badgeLabel, "purple"
            );
            
            return new AssessmentResponseDto.AdHocEvidenceItem(
                    item.criteriaId(), item.criteriaName(), item.importance(), item.jdRequirement(),
                    item.cvEvidence(), item.cvQuote(), item.status(), cleanReasoning, metadata
            );
        }
        return item;
    }

    private AssessmentResponseDto.EvidenceItem syncGateWithLlmEvidence(AssessmentResponseDto.EvidenceItem gate, List<? extends AssessmentResponseDto.EvidenceItem> evidenceItems) {
        if (evidenceItems == null) return null;
        for (var item : evidenceItems) {
            if (isGateMatch(gate, item.status(), item.criteriaName(), item.jdRequirement())) {
                return new AssessmentResponseDto.EvidenceItem(
                        gate.criteriaId(), gate.criteriaName(), gate.importance(), gate.jdRequirement(),
                        item.cvEvidence(), gate.cvQuote(), "PASSED", gate.reasoning(),
                        gate.weightUsed(), gate.scoreContribution(), gate.groundingScore(),
                        gate.confidenceVotes(), gate.lowConfidence(), gate.needsManualReview(), gate.matchMetadata()
                );
            }
        }
        return null;
    }

    private AssessmentResponseDto.EvidenceItem syncGateWithLlmEvidenceAdHoc(AssessmentResponseDto.EvidenceItem gate, List<AssessmentResponseDto.AdHocEvidenceItem> evidenceItems) {
        if (evidenceItems == null) return null;
        for (var item : evidenceItems) {
            if (isGateMatch(gate, item.status(), item.criteriaName(), item.jdRequirement())) {
                return new AssessmentResponseDto.EvidenceItem(
                        gate.criteriaId(), gate.criteriaName(), gate.importance(), gate.jdRequirement(),
                        item.cvEvidence(), gate.cvQuote(), "PASSED", gate.reasoning(),
                        gate.weightUsed(), gate.scoreContribution(), gate.groundingScore(),
                        gate.confidenceVotes(), gate.lowConfidence(), gate.needsManualReview(), gate.matchMetadata()
                );
            }
        }
        return null;
    }

    private boolean isGateMatch(AssessmentResponseDto.EvidenceItem gate, String itemStatus, String itemName, String itemJdReq) {
        if (!"matched".equalsIgnoreCase(itemStatus)) return false;
        
        String gateName = gate.criteriaName() != null ? gate.criteriaName().toLowerCase().trim() : "";
        String gateReq = gate.jdRequirement() != null ? gate.jdRequirement().toLowerCase().trim() : "";
        String cName = itemName != null ? itemName.toLowerCase().trim() : "";
        String cReq = itemJdReq != null ? itemJdReq.toLowerCase().trim() : "";

        if (!gateName.isEmpty() && !"certification".equals(gateName) && (cName.contains(gateName) || gateName.contains(cName))) return true;
        if (!gateReq.isEmpty() && (cName.contains(gateReq) || cReq.contains(gateReq) || gateReq.contains(cName))) return true;

        return false;
    }

    private JdPhase1And4Bundle executeAndCachePhase1And4(String jdId, String fullJdMarkdown, String fullCvMarkdown, Session session, boolean shouldIncludeNotApp) {
        JobDescription jd = session.getJobDescription();
        Resume resume = session.getResume();
        AssessmentCriteriaPreparer.MetadataResult preResolvedMetadata = resolvePreStoredMetadata(jd, resume);

        String cacheKey;
        if (preResolvedMetadata != null) {
            cacheKey = "jd_p1_p4:v3:" + jdId + ":" + preResolvedMetadata.category().name() + ":" + preResolvedMetadata.level().name() + ":" + shouldIncludeNotApp;
        } else {
            cacheKey = "jd_p1_p4:v3:" + jdId + ":UNKNOWN:" + session.getId() + ":" + shouldIncludeNotApp;
        }

        try {
            String cachedData = stringRedisTemplate.opsForValue().get(cacheKey);
            if (cachedData != null) {
                log.info("[Phase1+4-Cache] HIT! Reusing Phase 1 & 4 profile for JD {} and CacheKey {} (0ms, 0 LLM calls).", jdId, cacheKey);
                return objectMapper.readValue(cachedData, JdPhase1And4Bundle.class);
            }
        } catch (Exception e) {
            log.warn("[Phase1+4-Cache] Warning: Failed to read from Redis for cacheKey {}: {}", cacheKey, e.getMessage());
        }

        PreparedJdBundle preparedJd;
        if (preResolvedMetadata != null) {
            log.info("[STEP 3/7] Phase 1 — Preparing JD using pre-stored Metadata (Category={}, Level={})...",
                    preResolvedMetadata.category(), preResolvedMetadata.level());
            preparedJd = criteriaPreparer.prepareJdConsolidatedSinglePassWithKnownMetadata(jdId, fullJdMarkdown, fullCvMarkdown, preResolvedMetadata);
        } else {
            log.info("[STEP 3/7] Phase 1 — Preparing JD (3-Pass LLM: Metadata, Gates & Classification)...");
            preparedJd = criteriaPreparer.prepareJdConsolidatedSinglePass(jdId, fullJdMarkdown, fullCvMarkdown);
        }

        MetadataResult metadata = preparedJd.metadata();
        ClassifiedCriteriaBundle bundle = preparedJd.bundle();

        if (preResolvedMetadata == null) {
            cacheKey = "jd_p1_p4:v3:" + jdId + ":" + metadata.category().name() + ":" + metadata.level().name() + ":" + shouldIncludeNotApp;
        }

        // Run Step 4: Reuse Phase 1 single-pass classified criteria bundle directly (0 extra LLM calls)
        int adHocCount = bundle.jdExtras() != null ? bundle.jdExtras().size() : 0;
        log.info("[STEP 4/7] Recording {} discovered Ad-hoc criteria and preparing final criteria list for Category: {}, Level: {}...",
                adHocCount, metadata.category(), metadata.level());
        recordAdHocCriteriaPreAssessment(metadata, bundle);

        List<CriteriaWeightDto> criteriaListDto = buildCriteriaListFromBundle(bundle, shouldIncludeNotApp);
        int totalDb = bundle.dbCriteria() != null ? bundle.dbCriteria().size() : 0;
        int filteredOut = totalDb - criteriaListDto.size();

        log.info("[STEP 4/7] Final Criteria List prepared: Active Criteria Count={} (Filtered out {} 'not_in_jd' criteria, shouldIncludeNotApp={}) | Ad-hoc Count={}",
                criteriaListDto.size(), Math.max(0, filteredOut), shouldIncludeNotApp, adHocCount);

        JdPhase1And4Bundle bundleToCache = new JdPhase1And4Bundle(preparedJd, criteriaListDto);

        try {
            String json = objectMapper.writeValueAsString(bundleToCache);
            stringRedisTemplate.opsForValue().set(cacheKey, json, Duration.ofDays(30));
        } catch (Exception e) {
            log.warn("[Phase1+4-Cache] Warning: Failed to save to Redis for cacheKey {}: {}", cacheKey, e.getMessage());
        }

        return bundleToCache;
    }

    private List<CriteriaWeightDto> buildCriteriaListFromBundle(ClassifiedCriteriaBundle bundle, boolean shouldIncludeNotApp) {
        if (bundle == null || bundle.dbCriteria() == null) return List.of();
        List<ClassifiedCriteriaBundle.ClassifiedCriteria> classified = bundle.dbCriteriaForMode(shouldIncludeNotApp);
        return classified.stream()
                .map(c -> new CriteriaWeightDto(
                        c.criteriaId(),
                        c.criteriaName(),
                        c.promptInstruction(),
                        c.promptInstruction(),
                        c.weightPercentage() != null ? c.weightPercentage() : 10.0,
                        null
                ))
                .collect(Collectors.toList());
    }

    private AssessmentCriteriaPreparer.MetadataResult resolvePreStoredMetadata(JobDescription jd, Resume resume) {
        if (jd == null && resume == null) return null;

        String rawRole = null;
        if (jd != null && jd.getJobCategory() != null && !jd.getJobCategory().isBlank()) {
            rawRole = jd.getJobCategory();
        } else if (resume != null && resume.getJobCategory() != null && !resume.getJobCategory().isBlank()) {
            rawRole = resume.getJobCategory();
        }

        fit.iuh.modules.assessment.entity.JobCategory category = rawRole != null ? criteriaPreparer.parseJobCategory(rawRole) : null;

        List<fit.iuh.modules.assessment.entity.SeniorityLevel> jdLevels = parseAcceptedLevels(jd != null ? jd.getAcceptedLevels() : null);
        fit.iuh.modules.assessment.entity.SeniorityLevel cvLevel = (resume != null && resume.getSeniorityLevel() != null)
                ? criteriaPreparer.parseSeniorityLevel(resume.getSeniorityLevel()) : null;

        if (category != null && !jdLevels.isEmpty() && cvLevel != null) {
            fit.iuh.modules.assessment.entity.SeniorityLevel targetLevel = criteriaPreparer.resolveTargetSeniorityLevel(jdLevels, cvLevel);
            return new AssessmentCriteriaPreparer.MetadataResult(category, targetLevel);
        }
        return null;
    }

    private List<fit.iuh.modules.assessment.entity.SeniorityLevel> parseAcceptedLevels(String acceptedLevelsJson) {
        if (acceptedLevelsJson == null || acceptedLevelsJson.isBlank()) return List.of();
        try {
            List<String> list = objectMapper.readValue(acceptedLevelsJson, new com.fasterxml.jackson.core.type.TypeReference<List<String>>() {});
            return list.stream().map(criteriaPreparer::parseSeniorityLevel).distinct().sorted().toList();
        } catch (Exception e) {
            String[] parts = acceptedLevelsJson.replaceAll("[\\[\\]\"]", "").split(",");
            List<fit.iuh.modules.assessment.entity.SeniorityLevel> res = new ArrayList<>();
            for (String p : parts) {
                if (!p.isBlank()) res.add(criteriaPreparer.parseSeniorityLevel(p.trim()));
            }
            return res.stream().distinct().sorted().toList();
        }
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
                            null, e.name(), e.importance(), e.promptInstruction(), null, null, null, null, null))
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

    private ResumeAssessment buildAndPersistEntity(
            String sessionId, MetadataResult metadata, ScoringResult scoringResult,
            List<AssessmentResponseDto.AdHocEvidenceItem> preferToHaveItems,
            List<AssessmentResponseDto.EvidenceItem> gateItems,
            ImprovementResponseDto improvements, EligibilityStatus eligibility) {

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
                .quickWins(mapToImprovementDto(entity.getImprovements(), "[QW]"))
                .skillGaps(mapToImprovementDto(entity.getImprovements(), "[SG]"))
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
                        null, i.getStatus(), i.getReasoning(), null, null, null, null, null, null, null
                )).collect(Collectors.toList());
    }

    private List<AssessmentResponseDto.EvidenceItem> mapToGateDto(List<fit.iuh.modules.assessment.entity.EvidenceItem> items) {
        if (items == null) return List.of();
        return items.stream()
                .filter(i -> "GATE".equalsIgnoreCase(i.getImportance()))
                .map(i -> new AssessmentResponseDto.EvidenceItem(
                        i.getCriteriaId() != null ? i.getCriteriaId().longValue() : null,
                        i.getCriteriaName(), i.getImportance(), i.getJdRequirement(), i.getCvEvidence(),
                        null, i.getStatus(), i.getReasoning(), null, null, null, null, null, null, null
                )).collect(Collectors.toList());
    }

    private List<AssessmentResponseDto.AdHocEvidenceItem> mapToPreferDto(List<fit.iuh.modules.assessment.entity.EvidenceItem> items) {
        if (items == null) return List.of();
        return items.stream()
                .filter(i -> "PREFERRED".equalsIgnoreCase(i.getImportance()))
                .map(i -> new AssessmentResponseDto.AdHocEvidenceItem(
                        i.getCriteriaId() != null ? i.getCriteriaId().longValue() : null,
                        i.getCriteriaName(), i.getImportance(), i.getJdRequirement(),
                        i.getCvEvidence(), null, i.getStatus(), i.getReasoning(), null
                )).collect(Collectors.toList());
    }

    private List<ImprovementResponseDto.ImprovementItem> mapToImprovementDto(List<fit.iuh.modules.assessment.entity.Improvement> items, String prefix) {
        if (items == null) return List.of();
        return items.stream()
                .filter(i -> i.getTopic() != null && i.getTopic().startsWith(prefix))
                .sorted(Comparator.comparing(fit.iuh.modules.assessment.entity.Improvement::getPriorityRank))
                .map(i -> new ImprovementResponseDto.ImprovementItem(
                        i.getTopic().substring(5).trim(), // Remove "[QW] " or "[SG] "
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

    @Override
    public AssessmentResponseDto runBatchedAssessmentWithSelfConsistency(
            String sessionId, String fullCvMarkdown, String fullJdMarkdown, List<CriteriaWeightProjection> criteriaList) {
        return llmRunner.runBatchedAssessmentWithSelfConsistency(sessionId, fullCvMarkdown, fullJdMarkdown, criteriaList);
    }
}
