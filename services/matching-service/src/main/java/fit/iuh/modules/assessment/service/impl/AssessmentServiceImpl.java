package fit.iuh.modules.assessment.service.impl;

import com.fasterxml.jackson.databind.ObjectMapper;
import fit.iuh.exception.LlmApiException;
import fit.iuh.modules.admin.repository.SystemSettingRepository;
import fit.iuh.modules.assessment.dto.*;
import fit.iuh.modules.assessment.entity.Eligibility;
import fit.iuh.modules.assessment.entity.ResumeAssessment;
import fit.iuh.modules.assessment.repository.ResumeAssessmentRepository;
import fit.iuh.modules.assessment.service.*;
import fit.iuh.modules.assessment.service.AssessmentCriteriaPreparer.MetadataResult;
import fit.iuh.modules.assessment.service.AssessmentCriteriaPreparer.PreparedJdBundle;
import fit.iuh.modules.assessment.service.AssessmentScoringEngine.ScoringResult;
import fit.iuh.modules.ingestion.entity.DocumentType;
import fit.iuh.modules.ingestion.entity.SessionDocument;
import fit.iuh.modules.ingestion.repository.SessionDocumentRepository;
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
 * Phase 2: Batched CV evaluation with self-consistency voting and evidence grounding.
 */
@Slf4j
@Service
@AllArgsConstructor
public class AssessmentServiceImpl implements AssessmentService {

    private static final String STATUS_NOT_APPLICABLE = "not_applicable";
    private static final String IMPORTANCE_NOT_APPLICABLE = "NOT_APPLICABLE";

    private final ResumeAssessmentRepository resumeAssessmentRepository;
    private final SessionDocumentRepository sessionDocumentRepository;
    private final SystemSettingRepository systemSettingRepository;
    private final AssessmentCriteriaPreparer criteriaPreparer;
    private final AssessmentLlmRunner llmRunner;
    private final AssessmentScoringEngine scoringEngine;
    private final ObjectMapper objectMapper;
    private final fit.iuh.config.AppProperties appProperties;

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
        log.info("[STEP 2/7] Loading ingested CV and JD Markdown documents from DB for sessionId: {}...", sessionId);
        SessionDocument cvDoc = sessionDocumentRepository
                .findBySessionIdAndDocumentType(sessionId, DocumentType.CV)
                .orElseThrow(() -> new LlmApiException("No CV found for session '" + sessionId + "'. Please ingest files first."));

        SessionDocument jdDoc = sessionDocumentRepository
                .findBySessionIdAndDocumentType(sessionId, DocumentType.JD)
                .orElseThrow(() -> new LlmApiException("No JD found for session '" + sessionId + "'. Please ingest files first."));

        String fullCvMarkdown = cvDoc.getMarkdownContent();
        String fullJdMarkdown = jdDoc.getMarkdownContent();
        log.info("[STEP 2/7] [DEBUG] CV Loaded: ID={}, Size={} chars | JD Loaded: ID={}, Size={} chars",
                cvDoc.getId(), fullCvMarkdown.length(), jdDoc.getId(), fullJdMarkdown.length());

        // Step 3: Phase 1 — 3-Pass LLM JD Preparation (Metadata + Gates + Classification)
        log.info("[STEP 3/7] Phase 1 — Preparing JD (3-Pass LLM: Metadata, Gates & Classification)...");
        PreparedJdBundle preparedJd = criteriaPreparer.prepareJdConsolidatedSinglePass(fullJdMarkdown);
        MetadataResult metadata = preparedJd.metadata();
        ClassifiedCriteriaBundle bundle = preparedJd.bundle();

        log.info("[STEP 3/7] [DEBUG] Metadata Result -> Category: {}, Seniority Level: {}", metadata.category(), metadata.level());
        if (preparedJd.rawGateRequirements() != null) {
            log.info("[STEP 3/7] [DEBUG] Extracted Gate Requirements ({}) -> {}",
                    preparedJd.rawGateRequirements().size(),
                    preparedJd.rawGateRequirements().stream().map(g -> g.getCriteriaName() + ": " + g.getRequiredValue()).collect(Collectors.joining("; ")));
        }
        log.info("[STEP 3/7] [DEBUG] Criteria Classification -> DB Criteria: {}, JD Extra Ad-hoc: {}",
                bundle.dbCriteria().size(), bundle.jdExtras().size());

        boolean shouldIncludeNotApp = includeNotApplicable != null
                ? includeNotApplicable
                : (systemSettingRepository != null && systemSettingRepository.getBoolean("INCLUDE_NOT_APPLICABLE_CRITERIA", false));

        // Step 4: Record ad-hoc criteria discovered in JD prior to assessment
        log.info("[STEP 4/7] Recording discovered Ad-hoc criteria and loading domain criteria tree for Category: {}, Level: {}...", metadata.category(), metadata.level());
        recordAdHocCriteriaPreAssessment(metadata, bundle);

        List<CriteriaWeightProjection> criteriaList = criteriaPreparer.loadAndFilterCriteria(
                metadata.category().name(),
                metadata.level().name(),
                sessionId,
                fullJdMarkdown,
                shouldIncludeNotApp
        );
        log.info("[STEP 4/7] [DEBUG] Loaded {} criteria weights from DB for Category={} Level={}", criteriaList.size(), metadata.category(), metadata.level());

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

        Eligibility eligibility = criteriaPreparer.evaluateEligibilityWithRawGates(
                preparedJd.rawGateRequirements(), fullJdMarkdown, fullCvMarkdown);
        log.info("[STEP 6/7] [DEBUG] Scoring Result -> Overall Score: {}%, Category Breakdown: {}", scoringResult.overallScore(), scoringResult.breakdown());
        log.info("[STEP 6/7] [DEBUG] Eligibility Check -> Status: {}, Checks: {}", eligibility.getStatus(),
                eligibility.getGateChecks() != null ? eligibility.getGateChecks().stream().map(c -> c.getCriteriaName() + " (" + c.getStatus() + ")").collect(Collectors.joining(", ")) : "[]");

        // Step 7: Generate grounded improvement recommendations and persist assessment
        log.info("[STEP 7/7] Generating resume improvements and persisting assessment entity for sessionId: {}...", sessionId);
        List<Map<String, String>> weaknesses = extractWeaknesses(scoringResult.updatedItems());
        log.info("[STEP 7/7] [DEBUG] Extracted Weaknesses Count: {}", weaknesses.size());

        List<ImprovementResponseDto.ImprovementItem> improvements = generateTopImprovements(sessionId, weaknesses, fullCvMarkdown);
        log.info("[STEP 7/7] [DEBUG] Top Improvements Generated ({}) -> {}", improvements.size(),
                improvements.stream().map(ImprovementResponseDto.ImprovementItem::criteriaName).collect(Collectors.joining("; ")));

        ResumeAssessment entity = buildAndPersistEntity(sessionId, metadata, scoringResult, dto.preferToHaveEvidenceItems(), improvements, eligibility);
        log.info("[STEP 7/7] [DEBUG] Entity Persisted Successfully -> ID: {}, SessionId: {}", entity.getId(), entity.getSessionId());

        AssessmentResponse response = toResponse(entity, false);
        response.setScoreBreakdown(scoringResult.breakdown());
        log.info("[PIPELINE COMPLETE] Assessment successfully saved and returned for sessionId: {} | Final Score: {}% | Eligibility: {}",
                sessionId, scoringResult.overallScore(), eligibility.getStatus());
        return response;
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

            Optional<SessionDocument> cvDocOpt = sessionDocumentRepository.findBySessionIdAndDocumentType(sessionId, DocumentType.CV);
            Optional<SessionDocument> jdDocOpt = sessionDocumentRepository.findBySessionIdAndDocumentType(sessionId, DocumentType.JD);
            if (cvDocOpt.isPresent() && jdDocOpt.isPresent()) {
                String cvContent = cvDocOpt.get().getMarkdownContent();
                String jdContent = jdDocOpt.get().getMarkdownContent();
                Optional<String> otherSessionIdOpt = sessionDocumentRepository.findSessionWithSameContentAndAssessment(cvContent, jdContent, sessionId);
                if (otherSessionIdOpt.isPresent()) {
                    String otherSessionId = otherSessionIdOpt.get();
                    log.info("[Assessment] Content-based Cache HIT! Reusing assessment for new sessionId={}", sessionId);
                    var otherAssessment = resumeAssessmentRepository.findBySessionId(otherSessionId).get();
                    return Optional.of(cloneAndBuildResponse(sessionId, otherAssessment));
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
                            null, e.name(), e.importance(), e.promptInstruction(), null, null, null))
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
            String prompt = "Generate top priority resume improvements based on weaknesses:\n" + jsonStr;
            String llmRes = llmRunner.callLlmBlockingWithSemaphore(null, prompt);
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
            List<ImprovementResponseDto.ImprovementItem> improvements, Eligibility eligibility) {

        ResumeAssessment entity = ResumeAssessment.builder()
                .sessionId(sessionId)
                .jobCategory(metadata.category())
                .seniorityLevel(metadata.level())
                .overallMatchScore(scoringResult.overallScore())
                .mustHaveEvidenceItems(scoringResult.updatedItems())
                .preferToHaveEvidenceItems(preferToHaveItems)
                .topPriorityImprovements(improvements)
                .eligibility(eligibility)
                .build();

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
        ScoringResult scoringResult = scoringEngine.calculateWithBreakdown(
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
