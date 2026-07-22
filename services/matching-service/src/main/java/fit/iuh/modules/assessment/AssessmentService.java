package fit.iuh.modules.assessment;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import fit.iuh.config.AppProperties;
import fit.iuh.config.PromptTemplateConfig;
import fit.iuh.dto.chat.LlmChatRequest;
import fit.iuh.dto.chat.LlmChatResponse;
import fit.iuh.exception.LlmApiException;
import fit.iuh.modules.ingestion.DocumentType;
import fit.iuh.modules.ingestion.SessionDocument;
import fit.iuh.modules.ingestion.SessionDocumentRepository;
import fit.iuh.modules.rulengine.JobCriteriaRepository;
import fit.iuh.modules.rulengine.JobCriteriaRepository.CriteriaWeightProjection;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Qualifier;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.reactive.function.client.WebClient;
import org.springframework.web.reactive.function.client.WebClientResponseException;

import java.util.*;
import fit.iuh.modules.assessment.ScoringService.ScoringResult;

/**
 * Orchestrates the 4-step SimInterview assessment pipeline.
 *
 * <h2>Execution Flow (Strictly Enforced)</h2>
 * <pre>
 *   Step 1 (Ingestion) — already done by IngestionService
 *        ↓
 *   Step 2 — MetadataExtractionService: lightweight LLM call on JD Markdown
 *             → {JobCategory, SeniorityLevel} ENUMs
 *        ↓
 *   Step 3 — JobCriteriaRepository: WITH RECURSIVE CTE fetches criteria + weights from DB
 *        ↓
 *   Step 4a — LLM (Evidence-Matching Engine): full CV Markdown + full JD Markdown
 *              + injected criteria instructions → evidence_items[] (NO scores)
 *        ↓
 *   Step 4b — ScoringService: pure Java math → overall_match_score (0-100)
 *        ↓
 *   Persist ResumeAssessment + return AssessmentResponse
 * </pre>
 *
 * <h2>Key Architectural Rules Enforced</h2>
 * <ul>
 *   <li><strong>Full Markdown only:</strong> Assessment uses {@code SessionDocument.markdownContent}
 *       (full document), never chunks. Chunks are exclusively for question generation.</li>
 *   <li><strong>LLM as evidence extractor only:</strong> The LLM returns {@code evidence_items[]}
 *       with {@code status} values. No numerical scores are requested from or produced by the LLM.</li>
 *   <li><strong>Java owns scoring:</strong> {@link ScoringService} performs all mathematical
 *       scoring using the weights from {@code category_criteria_mapping}.</li>
 * </ul>
 */
@Slf4j
@Service
public class AssessmentService {

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
    private final fit.iuh.modules.admin.SystemSettingRepository systemSettingRepository;
    private final EvidenceGroundingValidator evidenceGroundingValidator;

    private final java.util.concurrent.Semaphore globalLlmSemaphore = new java.util.concurrent.Semaphore(10, true);

    public AssessmentService(
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
            fit.iuh.modules.admin.SystemSettingRepository systemSettingRepository,
            EvidenceGroundingValidator evidenceGroundingValidator) {
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
    }

    // -------------------------------------------------------------------------
    // Public API — Cache-Aside (Blocking)
    // -------------------------------------------------------------------------

    /**
     * Executes the full 4-step assessment pipeline for the given session.
     *
     * <p>Implements Cache-Aside: if a result already exists in DB it is returned immediately.
     * Use {@code forceRefresh=true} to bypass the cache and regenerate.
     *
     * @param sessionId    the unique interview session identifier
     * @param forceRefresh if {@code true}, deletes any cached result and regenerates
     * @return {@link AssessmentResponse} containing the structured assessment outputs
     * @throws LlmApiException if session documents are missing or LLM calls fail
     */
    @Transactional
    public AssessmentResponse assessResumeBlocking(String sessionId, boolean forceRefresh) {
        return assessResumeBlocking(sessionId, forceRefresh, null);
    }

    @Transactional
    public AssessmentResponse assessResumeBlocking(String sessionId, boolean forceRefresh, String fromSessionId) {
        log.info("[Assessment] Request for sessionId={}, forceRefresh={}, fromSessionId={}", sessionId, forceRefresh, fromSessionId);

        // ── Cache-Aside: Check DB first ──────────────────────────────────────
        if (!forceRefresh) {
            var cached = resumeAssessmentRepository.findBySessionId(sessionId);
            if (cached.isPresent()) {
                log.info("[Assessment] Cache HIT for sessionId={}", sessionId);
                return toResponse(cached.get(), true);
            }

            // Direct clone by fromSessionId if provided
            if (fromSessionId != null && !fromSessionId.isBlank()) {
                var otherAssessmentOpt = resumeAssessmentRepository.findBySessionId(fromSessionId);
                if (otherAssessmentOpt.isPresent()) {
                    var otherAssessment = otherAssessmentOpt.get();
                    log.info("[Assessment] Direct Cache HIT by fromSessionId! Reusing assessment from sessionId={} for new sessionId={}", fromSessionId, sessionId);
                    
                    // Clone the assessment for the current sessionId
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

            // Fallback to Content-based Cache HIT check
            java.util.Optional<SessionDocument> cvDocOpt = sessionDocumentRepository.findBySessionIdAndDocumentType(sessionId, DocumentType.CV);
            java.util.Optional<SessionDocument> jdDocOpt = sessionDocumentRepository.findBySessionIdAndDocumentType(sessionId, DocumentType.JD);
            if (cvDocOpt.isPresent() && jdDocOpt.isPresent()) {
                String cvContent = cvDocOpt.get().getMarkdownContent();
                String jdContent = jdDocOpt.get().getMarkdownContent();
                java.util.Optional<String> otherSessionIdOpt = sessionDocumentRepository.findSessionWithSameContentAndAssessment(cvContent, jdContent, sessionId);
                if (otherSessionIdOpt.isPresent()) {
                    String otherSessionId = otherSessionIdOpt.get();
                    log.info("[Assessment] Content-based Cache HIT! Reusing assessment from sessionId={} for new sessionId={}", otherSessionId, sessionId);
                    
                    var otherAssessment = resumeAssessmentRepository.findBySessionId(otherSessionId).get();
                    
                    // Clone the assessment for the current sessionId
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

        log.info("[Assessment] Cache MISS — running full 4-step pipeline for sessionId={}", sessionId);

        // ── Load Full Markdown Documents (NOT chunks) ─────────────────────────
        // Violation fix: Assessment MUST use full session_documents.markdown_content.
        // DocumentChunks are exclusively reserved for the Question Bank (Step 3 question gen).
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

        log.info("[Assessment] Loaded full Markdown — CV: {} chars | JD: {} chars",
                fullCvMarkdown.length(), fullJdMarkdown.length());

        // ── Step 2: Metadata Extraction ───────────────────────────────────────
        // Lightweight LLM call on JD only → {JobCategory, SeniorityLevel} ENUMs
        MetadataExtractionService.ExtractionResult metadata =
                metadataExtractionService.extract(fullJdMarkdown);

        log.info("[Assessment] Step 2 complete — category={}, level={}",
                metadata.category(), metadata.level());

        // ── Step 3: Dynamic Criteria Fetching via WITH RECURSIVE CTE ─────────
        List<CriteriaWeightProjection> criteriaList = jobCriteriaRepository
                .findCriteriaTreeByCategory(
                        metadata.category().name(),
                        metadata.level().name()
                );

        if (criteriaList.isEmpty()) {
            log.warn("[Assessment] No criteria found for category={}, level={}. " +
                    "Falling back to SOFTWARE_ENGINEERING root criteria.",
                    metadata.category(), metadata.level());
            criteriaList = jobCriteriaRepository
                    .findCriteriaTreeByCategory("SOFTWARE_ENGINEERING", "ALL");
        }

        log.info("[Assessment] Step 3 complete — fetched {} criteria from rule engine.", criteriaList.size());

        // ── Step 4a: LLM Assessment (Evidence-Matching Engine) ─────────────────
        // Batched criteria evaluation + N-run Self-Consistency + Evidence Grounding Check
        AssessmentResponseDto dto = runBatchedAssessmentWithSelfConsistency(
                sessionId,
                fullCvMarkdown,
                fullJdMarkdown,
                criteriaList
        );

        log.info("[Assessment] Step 4a complete — LLM returned {} grounded evidence items.",
                dto.evidenceItems() != null ? dto.evidenceItems().size() : 0);

        // ── Step 4b: Java Scoring (ScoringService) ────────────────────────────
        ScoringResult scoringResult = scoringService.calculateWithBreakdown(
                dto.evidenceItems(),
                dto.additionalEvidenceItems(),
                criteriaList,
                metadata.level()
        );

        log.info("[Assessment] Step 4b complete — overall_match_score={}", scoringResult.score());

        // ── Step 4c: GATE & Eligibility Evaluation ─────────────────────────────
        Eligibility eligibility = gateExtractionService.evaluateEligibility(fullJdMarkdown, fullCvMarkdown);
        log.info("[Assessment] Step 4c complete — eligibility_status={}", eligibility.getStatus());

        // Process Ad-Hoc criteria
        suggestedCriteriaService.recordAdHocCriteria(metadata.category(), dto.additionalEvidenceItems());

        // ── Step 4c: Improvement Advisor (Phase 2) ─────────────────────────────
        List<Map<String, String>> weaknesses = new java.util.ArrayList<>();
        if (scoringResult.evidenceItems() != null) {
            for (var item : scoringResult.evidenceItems()) {
                if ("weak".equalsIgnoreCase(item.status()) || "missing".equalsIgnoreCase(item.status())) {
                    weaknesses.add(Map.of("criteria_name", item.criteriaName(), "status", item.status(), "cv_evidence", item.cvEvidence() == null ? "" : item.cvEvidence()));
                }
            }
        }
        if (dto.additionalEvidenceItems() != null) {
             for (var item : dto.additionalEvidenceItems()) {
                if ("weak".equalsIgnoreCase(item.status()) || "missing".equalsIgnoreCase(item.status())) {
                    weaknesses.add(Map.of("criteria_name", item.criteriaName(), "status", item.status(), "cv_evidence", item.cvEvidence() == null ? "" : item.cvEvidence()));
                }
            }
        }

        List<ImprovementResponseDto.ImprovementItem> improvements = List.of();
        if (!weaknesses.isEmpty()) {
            try {
                String weaknessJson = objectMapper.writeValueAsString(weaknesses);
                String phase2SystemPrompt = PromptTemplateConfig.SYSTEM_PROMPT_IMPROVEMENT_ADVISOR;
                String phase2UserPrompt = PromptTemplateConfig.buildImprovementUserPrompt(weaknessJson);
                
                log.info("[Assessment] Calling Phase 2 (Improvement Advisor) for {} weaknesses...", weaknesses.size());
                
                int maxAttempts = 3;
                ImprovementResponseDto phase2Dto = null;
                for (int attempt = 1; attempt <= maxAttempts; attempt++) {
                    try {
                        String phase2Response = callLlmBlocking(phase2SystemPrompt, phase2UserPrompt);
                        phase2Dto = parseImprovementDto(sessionId, phase2Response);
                        break;
                    } catch (Exception e) {
                        log.warn("[Assessment] Phase 2 LLM Call/Parse failed (attempt {}/{}): {}", attempt, maxAttempts, e.getMessage());
                        if (attempt >= maxAttempts) {
                            throw e;
                        }
                    }
                }
                
                improvements = phase2Dto.topPriorityImprovements();
                log.info("[Assessment] Phase 2 complete — generated {} improvements.", improvements != null ? improvements.size() : 0);
            } catch (Exception e) {
                log.warn("[Assessment] Phase 2 failed, falling back to empty improvements: {}", e.getMessage());
            }
        }

        // ── Step 5: Build & Persist Result ────────────────────────────────────
        ResumeAssessment entity = buildAndPersistEntity(
                sessionId,
                metadata,
                scoringResult.score(),
                dto,
                scoringResult.evidenceItems(),
                improvements,
                eligibility
        );
        AssessmentResponse response = toResponse(entity, false);
        response.setScoreBreakdown(scoringResult.breakdown());
        return response;
    }

    // -------------------------------------------------------------------------
    // Private — Criteria Instruction Builder
    // -------------------------------------------------------------------------

    /**
     * Formats the list of DB criteria into numbered, injection-ready instructions
     * for the LLM assessment system prompt.
     *
     * <p>Format:
     * <pre>
     * Criterion 1 (ID: 1, Weight: 30.0%) — Tech Stack Alignment
     * [prompt_instruction from DB]
     *
     * Criterion 2 (ID: 2, Weight: 20.0%) — CS Fundamentals
     * [prompt_instruction from DB]
     * </pre>
     */
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

    // -------------------------------------------------------------------------
    // Private — LLM Call (JSON mode, blocking)
    // -------------------------------------------------------------------------

    private String callLlmBlocking(String systemPrompt, String userPrompt) {
        LlmChatRequest request = LlmChatRequest.builder()
                .model(appProperties.getLlm().getModel())
                .maxTokens(appProperties.getLlm().getMaxTokens())
                .temperature(0.1) // Changed from 0.0 to 0.1 to avoid empty response bugs on some OpenRouter providers
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

    // -------------------------------------------------------------------------
    // Private — JSON Parsing
    // -------------------------------------------------------------------------

    private AssessmentResponseDto parseAssessmentDto(String sessionId, String llmJsonResponse) {
        String json = llmJsonResponse
                .replaceAll("(?s)^```json\\s*", "")
                .replaceAll("(?s)\\s*```$", "")
                .strip();

        log.debug("[Assessment] Raw LLM JSON for sessionId={}: {}", sessionId, json);

        try {
            AssessmentResponseDto dto = objectMapper.readValue(json, AssessmentResponseDto.class);

            if (dto.evidenceItems() == null || dto.evidenceItems().isEmpty()) {
                throw new LlmApiException(
                        "LLM response missing 'evidence_items' for sessionId=" + sessionId);
            }

            log.info("[Assessment] Parsed {} evidence items for sessionId={}",
                    dto.evidenceItems().size(),
                    sessionId);

            return dto;

        } catch (JsonProcessingException e) {
            log.error("[Assessment] Failed to parse LLM JSON for sessionId={}: {}\nRaw: {}",
                    sessionId, e.getMessage(), json);
            throw new LlmApiException(
                    "LLM returned invalid JSON for sessionId=" + sessionId + ": " + e.getMessage(), e);
        }
    }

    private ImprovementResponseDto parseImprovementDto(String sessionId, String llmJsonResponse) {
        String json = llmJsonResponse
                .replaceAll("(?s)^```json\\s*", "")
                .replaceAll("(?s)\\s*```$", "")
                .strip();

        log.debug("[Assessment] Phase 2 Raw LLM JSON for sessionId={}: {}", sessionId, json);

        try {
            return objectMapper.readValue(json, ImprovementResponseDto.class);
        } catch (JsonProcessingException e) {
            log.error("[Assessment] Phase 2 failed to parse LLM JSON for sessionId={}: {}\nRaw: {}",
                    sessionId, e.getMessage(), json);
            throw new LlmApiException(
                    "Phase 2 LLM returned invalid JSON for sessionId=" + sessionId + ": " + e.getMessage(), e);
        }
    }

    // -------------------------------------------------------------------------
    // Private — Persistence
    // -------------------------------------------------------------------------

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
                .overallMatchScore(overallMatchScore)   // Java-computed
                .evidenceItems(populatedEvidenceItems)
                .additionalEvidenceItems(dto.additionalEvidenceItems())
                .topPriorityImprovements(improvements)
                .eligibility(eligibility)
                .build();

        ResumeAssessment saved = resumeAssessmentRepository.save(entity);
        log.info("[Assessment] Persisted ResumeAssessment id={} for sessionId={} | score={}",
                saved.getId(), sessionId, saved.getOverallMatchScore());
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

    // -------------------------------------------------------------------------
    // Interview Session Evaluation
    // -------------------------------------------------------------------------

    /**
     * Evaluates a completed mock interview session using zero-shot JSON schema prompt.
     *
     * @param request contains the role title, interview type, and Q&A turns
     * @return raw JSON string conforming to the evaluation schema
     */
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
                    .append(t.answer() != null && !t.answer().trim().isEmpty()
                            ? t.answer()
                            : "[Không trả lời]")
                    .append("\n");
            userPrompt.append("Điểm sơ bộ: ").append(t.score() != null ? t.score() : 0)
                    .append("/10\n\n");
        }

        LlmChatRequest llmRequest = LlmChatRequest.builder()
                .model(appProperties.getLlm().getModel())
                .maxTokens(appProperties.getLlm().getMaxTokens())
                .temperature(0.3)
                .stream(false)
                .responseFormat(JSON_RESPONSE_FORMAT)
                .messages(List.of(
                        LlmChatRequest.Message.system(
                                PromptTemplateConfig.SYSTEM_PROMPT_INTERVIEW_EVALUATION),
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

    // -------------------------------------------------------------------------
    // Task 1, 2, 3 — Batched Assessment, Self-Consistency & Concurrency Throttling
    // -------------------------------------------------------------------------

    private String callLlmBlockingWithSemaphore(String systemPrompt, String userPrompt) {
        boolean acquired = false;
        try {
            acquired = globalLlmSemaphore.tryAcquire(60, java.util.concurrent.TimeUnit.SECONDS);
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

    public AssessmentResponseDto runBatchedAssessmentWithSelfConsistency(
            String sessionId,
            String fullCvMarkdown,
            String fullJdMarkdown,
            List<CriteriaWeightProjection> criteriaList) {

        int batchSize = systemSettingRepository != null ? systemSettingRepository.getInt("CRITERIA_BATCH_SIZE", 5) : 5;
        int selfConsistencyRuns = systemSettingRepository != null ? systemSettingRepository.getInt("SELF_CONSISTENCY_RUNS", 3) : 3;
        double groundingThreshold = systemSettingRepository != null ? systemSettingRepository.getDouble("EVIDENCE_GROUNDING_THRESHOLD", 0.75) : 0.75;

        List<List<CriteriaWeightProjection>> batches = partitionCriteria(criteriaList, batchSize);
        log.info("[Assessment] Processing {} criteria in {} batches (batch_size={}, self_consistency_runs={})...",
                criteriaList.size(), batches.size(), batchSize, selfConsistencyRuns);

        List<AssessmentResponseDto.EvidenceItem> aggregatedEvidenceItems = new java.util.ArrayList<>();
        List<AssessmentResponseDto.AdHocEvidenceItem> aggregatedAdHocItems = new java.util.ArrayList<>();

        List<java.util.concurrent.CompletableFuture<BatchResult>> batchFutures = new java.util.ArrayList<>();
        for (int i = 0; i < batches.size(); i++) {
            final int batchIndex = i + 1;
            final List<CriteriaWeightProjection> batchCriteria = batches.get(i);

            java.util.concurrent.CompletableFuture<BatchResult> future = java.util.concurrent.CompletableFuture.supplyAsync(() ->
                    processBatchWithSelfConsistency(sessionId, fullCvMarkdown, fullJdMarkdown, batchCriteria, batchIndex, batches.size(), selfConsistencyRuns)
            );
            batchFutures.add(future);
        }

        java.util.concurrent.CompletableFuture.allOf(batchFutures.toArray(new java.util.concurrent.CompletableFuture[0])).join();

        for (java.util.concurrent.CompletableFuture<BatchResult> f : batchFutures) {
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

        // Apply Evidence Grounding Check (Task 1)
        List<AssessmentResponseDto.EvidenceItem> groundedItems = new java.util.ArrayList<>();
        for (AssessmentResponseDto.EvidenceItem item : aggregatedEvidenceItems) {
            AssessmentResponseDto.EvidenceItem grounded = evidenceGroundingValidator != null
                    ? evidenceGroundingValidator.validateAndApply(item, fullCvMarkdown, groundingThreshold)
                    : item;
            groundedItems.add(grounded);
        }

        List<AssessmentResponseDto.AdHocEvidenceItem> distinctAdHoc = aggregatedAdHocItems.stream()
                .filter(java.util.Objects::nonNull)
                .filter(item -> item.criteriaName() != null)
                .collect(java.util.stream.Collectors.toMap(
                        AssessmentResponseDto.AdHocEvidenceItem::criteriaName,
                        item -> item,
                        (existing, replacement) -> existing
                ))
                .values().stream().toList();

        return new AssessmentResponseDto(groundedItems, distinctAdHoc);
    }

    public record BatchResult(
            List<AssessmentResponseDto.EvidenceItem> evidenceItems,
            List<AssessmentResponseDto.AdHocEvidenceItem> adHocItems
    ) {}

    public BatchResult processBatchWithSelfConsistency(
            String sessionId,
            String fullCvMarkdown,
            String fullJdMarkdown,
            List<CriteriaWeightProjection> batchCriteria,
            int batchIndex,
            int totalBatches,
            int selfConsistencyRuns) {

        String criteriaInstructions = buildCriteriaInstructions(batchCriteria);
        String systemPrompt = PromptTemplateConfig.buildAssessmentSystemPrompt(criteriaInstructions);
        String userPrompt = PromptTemplateConfig.buildAssessmentUserPrompt(fullCvMarkdown, fullJdMarkdown);

        List<java.util.concurrent.CompletableFuture<AssessmentResponseDto>> runFutures = new java.util.ArrayList<>();
        for (int r = 1; r <= selfConsistencyRuns; r++) {
            final int runIndex = r;
            java.util.concurrent.CompletableFuture<AssessmentResponseDto> future = java.util.concurrent.CompletableFuture.supplyAsync(() -> {
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

        java.util.concurrent.CompletableFuture.allOf(runFutures.toArray(new java.util.concurrent.CompletableFuture[0])).join();

        List<AssessmentResponseDto> successfulDtos = new java.util.ArrayList<>();
        for (var f : runFutures) {
            AssessmentResponseDto dto = f.join();
            if (dto != null && dto.evidenceItems() != null && !dto.evidenceItems().isEmpty()) {
                successfulDtos.add(dto);
            }
        }

        // Batch Fallback if all N runs failed
        if (successfulDtos.isEmpty()) {
            log.warn("[BatchEngine] batch={}/{} | ALL_RUNS_FAILED | criteria_count={} | action=FALLBACK_MISSING_MANUAL_REVIEW",
                    batchIndex, totalBatches, batchCriteria.size());

            List<AssessmentResponseDto.EvidenceItem> fallbackItems = new java.util.ArrayList<>();
            for (CriteriaWeightProjection c : batchCriteria) {
                fallbackItems.add(new AssessmentResponseDto.EvidenceItem(
                        c.getCriteriaId(),
                        c.getCriteriaName(),
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
                        true // needs_manual_review = true
                ));
            }
            return new BatchResult(fallbackItems, List.of());
        }

        // Majority Vote Aggregation
        List<AssessmentResponseDto.EvidenceItem> aggregatedBatchItems = new java.util.ArrayList<>();
        List<AssessmentResponseDto.AdHocEvidenceItem> batchAdHoc = new java.util.ArrayList<>();

        for (CriteriaWeightProjection c : batchCriteria) {
            Map<String, Integer> votes = new java.util.HashMap<>();
            votes.put("matched", 0);
            votes.put("weak", 0);
            votes.put("missing", 0);

            Map<String, AssessmentResponseDto.EvidenceItem> statusToSampleItem = new java.util.HashMap<>();

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

            // Determine winner status
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
                // Conservative tie-breaking: missing > weak > matched
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

            String jdReq = sampleItem != null ? sampleItem.jdRequirement() : c.getPromptInstruction();
            String cvEv = sampleItem != null ? sampleItem.cvEvidence() : null;
            String reasoning = sampleItem != null ? sampleItem.reasoning() : "Xác định từ cơ chế Self-Consistency majority vote.";
            String sourceSpan = sampleItem != null ? sampleItem.sourceSpan() : null;

            aggregatedBatchItems.add(new AssessmentResponseDto.EvidenceItem(
                    c.getCriteriaId(),
                    c.getCriteriaName(),
                    jdReq,
                    cvEv,
                    winningStatus,
                    reasoning,
                    null,
                    null,
                    sourceSpan,
                    null, // groundingScore populated in Step 4a validation filter
                    votes,
                    lowConfidence,
                    false // needs_manual_review = false
            ));
        }

        return new BatchResult(aggregatedBatchItems, batchAdHoc);
    }

    private List<List<CriteriaWeightProjection>> partitionCriteria(List<CriteriaWeightProjection> list, int size) {
        List<List<CriteriaWeightProjection>> partitions = new java.util.ArrayList<>();
        for (int i = 0; i < list.size(); i += size) {
            partitions.add(list.subList(i, Math.min(i + size, list.size())));
        }
        return partitions;
    }

    // -------------------------------------------------------------------------
    // Private utility
    // -------------------------------------------------------------------------

    private void sleepQuietly(long ms) {
        try {
            Thread.sleep(ms);
        } catch (InterruptedException ie) {
            Thread.currentThread().interrupt();
        }
    }
}
