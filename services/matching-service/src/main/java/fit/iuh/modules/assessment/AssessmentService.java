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

import java.util.List;
import java.util.Map;
import java.util.stream.Collectors;

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
    private final ObjectMapper objectMapper;

    public AssessmentService(
            AppProperties appProperties,
            @Qualifier("llmWebClient") WebClient llmWebClient,
            ResumeAssessmentRepository resumeAssessmentRepository,
            SessionDocumentRepository sessionDocumentRepository,
            MetadataExtractionService metadataExtractionService,
            JobCriteriaRepository jobCriteriaRepository,
            ScoringService scoringService,
            ObjectMapper objectMapper) {
        this.appProperties = appProperties;
        this.llmWebClient = llmWebClient;
        this.resumeAssessmentRepository = resumeAssessmentRepository;
        this.sessionDocumentRepository = sessionDocumentRepository;
        this.metadataExtractionService = metadataExtractionService;
        this.jobCriteriaRepository = jobCriteriaRepository;
        this.scoringService = scoringService;
        this.objectMapper = objectMapper;
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
        log.info("[Assessment] Request for sessionId={}, forceRefresh={}", sessionId, forceRefresh);

        // ── Cache-Aside: Check DB first ──────────────────────────────────────
        if (!forceRefresh) {
            var cached = resumeAssessmentRepository.findBySessionId(sessionId);
            if (cached.isPresent()) {
                log.info("[Assessment] Cache HIT for sessionId={}", sessionId);
                return toResponse(cached.get(), true);
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
        // Build system prompt by injecting dynamically fetched criteria instructions
        String criteriaInstructions = buildCriteriaInstructions(criteriaList);
        String systemPrompt = PromptTemplateConfig.buildAssessmentSystemPrompt(criteriaInstructions);
        String userPrompt   = PromptTemplateConfig.buildAssessmentUserPrompt(fullCvMarkdown, fullJdMarkdown);

        String llmJsonResponse = callLlmBlocking(systemPrompt, userPrompt);
        AssessmentResponseDto dto = parseAssessmentDto(sessionId, llmJsonResponse);

        log.info("[Assessment] Step 4a complete — LLM returned {} evidence items.",
                dto.evidenceItems() != null ? dto.evidenceItems().size() : 0);

        // ── Step 4b: Java Scoring (ScoringService) ────────────────────────────
        int overallMatchScore = scoringService.calculate(dto.evidenceItems(), criteriaList);

        log.info("[Assessment] Step 4b complete — overall_match_score={}", overallMatchScore);

        // ── Persist and Return ─────────────────────────────────────────────────
        ResumeAssessment entity = buildAndPersistEntity(sessionId, metadata, overallMatchScore, dto);
        return toResponse(entity, false);
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
                    "Criterion %d (ID: %d, Weight: %.1f%%) — %s%n%s%n%n",
                    i + 1,
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
                .temperature(0.0)
                .stream(false)
                .responseFormat(JSON_RESPONSE_FORMAT)
                .messages(List.of(
                        LlmChatRequest.Message.system(systemPrompt),
                        LlmChatRequest.Message.user(userPrompt)
                ))
                .build();

        int maxRetries = 1;
        for (int i = 0; i <= maxRetries; i++) {
            try {
                LlmChatResponse response = llmWebClient.post()
                        .uri(appProperties.getLlm().getChatPath())
                        .bodyValue(request)
                        .retrieve()
                        .bodyToMono(LlmChatResponse.class)
                        .block();

                if (response == null || response.getFirstChoiceContent() == null) {
                    throw new LlmApiException("LLM API returned empty assessment response.");
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

            log.info("[Assessment] Parsed {} evidence items, {} improvements for sessionId={}",
                    dto.evidenceItems().size(),
                    dto.topPriorityImprovements() != null ? dto.topPriorityImprovements().size() : 0,
                    sessionId);

            return dto;

        } catch (JsonProcessingException e) {
            log.error("[Assessment] Failed to parse LLM JSON for sessionId={}: {}\nRaw: {}",
                    sessionId, e.getMessage(), json);
            throw new LlmApiException(
                    "LLM returned invalid JSON for sessionId=" + sessionId + ": " + e.getMessage(), e);
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
            AssessmentResponseDto dto) {

        ResumeAssessment entity = ResumeAssessment.builder()
                .sessionId(sessionId)
                .jobCategory(metadata.category())
                .seniorityLevel(metadata.level())
                .overallMatchScore(overallMatchScore)   // Java-computed
                .evidenceItems(dto.evidenceItems())
                .topPriorityImprovements(dto.topPriorityImprovements())
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
                .topPriorityImprovements(entity.getTopPriorityImprovements())
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
