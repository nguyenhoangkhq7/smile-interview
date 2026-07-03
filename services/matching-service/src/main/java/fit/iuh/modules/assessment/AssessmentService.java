package fit.iuh.modules.assessment;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import fit.iuh.config.AppProperties;
import fit.iuh.config.PromptTemplateConfig;
import fit.iuh.modules.assessment.AssessmentResponse;
import fit.iuh.modules.assessment.AssessmentResponseDto;
import fit.iuh.modules.assessment.InterviewEvaluationRequest;
import fit.iuh.modules.assessment.QuestionAnswerDto;
import fit.iuh.dto.chat.LlmChatRequest;
import fit.iuh.dto.chat.LlmChatResponse;
import fit.iuh.modules.ingestion.DocumentChunk;
import fit.iuh.modules.assessment.ResumeAssessment;
import fit.iuh.modules.ingestion.SessionDocument;
import fit.iuh.modules.ingestion.DocumentType;
import fit.iuh.exception.LlmApiException;
import fit.iuh.modules.ingestion.DocumentChunkRepository;
import fit.iuh.modules.assessment.ResumeAssessmentRepository;
import fit.iuh.modules.ingestion.SessionDocumentRepository;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Qualifier;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.reactive.function.client.WebClient;
import org.springframework.web.reactive.function.client.WebClientResponseException;

import java.util.*;
import java.util.stream.Collectors;

/**
 * Service responsible for holistic resume assessment following the SimInterview
 * 3-part architecture (Competency Fit Score, Section-wise Feedback, Actionable Suggestions).
 *
 * <h3>Cache-Aside Flow</h3>
 * <pre>
 *  Client → GET /api/v2/assess-resume?sessionId=X
 *    └── AssessmentService.assessResumeBlocking(sessionId, forceRefresh)
 *          ├── 1. Check DB cache → if hit: return cached AssessmentResponse immediately
 *          ├── 2. Load CV &amp; JD chunks from PostgreSQL
 *          ├── 3. Semantic Cross-Matching (Cosine Similarity, threshold 0.75, topK 5)
 *          ├── 4. Call Groq API (JSON mode, stream=false, temperature=0.0)
 *          ├── 5. Deserialize LLM JSON → AssessmentResponseDto
 *          ├── 6. Persist ResumeAssessment entity (3 JSONB fields)
 *          └── 7. Return AssessmentResponse to Controller
 * </pre>
 *
 * <h3>JSON Mode</h3>
 * The request includes {@code "response_format": {"type": "json_object"}} and
 * {@code "stream": false}. This forces Groq to return a well-formed JSON object
 * that can be directly deserialized into {@link AssessmentResponseDto}.
 */
@Slf4j
@Service
public class AssessmentService {

    /** Path on the LLM provider's base URL for chat completions (OpenAI-compatible). */
    private static final String CHAT_COMPLETIONS_PATH = "/openai/v1/chat/completions";

    /**
     * {@code response_format} payload for Groq/OpenAI JSON mode.
     * Instructs the model to return a valid JSON object (no Markdown wrapping).
     */
    private static final Map<String, String> JSON_RESPONSE_FORMAT = Map.of("type", "json_object");

    private final AppProperties appProperties;
    private final WebClient llmWebClient;
    private final DocumentChunkRepository documentChunkRepository;
    private final ResumeAssessmentRepository resumeAssessmentRepository;
    private final SessionDocumentRepository sessionDocumentRepository;
    private final ObjectMapper objectMapper;

    public AssessmentService(
            AppProperties appProperties,
            @Qualifier("llmWebClient") WebClient llmWebClient,
            DocumentChunkRepository documentChunkRepository,
            ResumeAssessmentRepository resumeAssessmentRepository,
            SessionDocumentRepository sessionDocumentRepository,
            ObjectMapper objectMapper) {
        this.appProperties = appProperties;
        this.llmWebClient = llmWebClient;
        this.documentChunkRepository = documentChunkRepository;
        this.resumeAssessmentRepository = resumeAssessmentRepository;
        this.sessionDocumentRepository = sessionDocumentRepository;
        this.objectMapper = objectMapper;
    }

    // -------------------------------------------------------------------------
    // Public API — Blocking (Cache-Aside)
    // -------------------------------------------------------------------------

    /**
     * Returns the SimInterview 3-part assessment for the given session.
     *
     * <p>Implements Cache-Aside: if a result already exists in DB it is returned
     * immediately without calling the LLM. Otherwise the LLM is called (JSON mode),
     * the 3 structured parts are parsed and persisted, then returned.
     *
     * @param sessionId    the unique interview session identifier
     * @param forceRefresh if {@code true}, deletes any cached result and regenerates from LLM
     * @return {@link AssessmentResponse} containing the 3 SimInterview outputs and metadata
     * @throws LlmApiException if CV/JD chunks are missing, the LLM call fails,
     *                         or the LLM response is not valid JSON
     */
    @Transactional
    public AssessmentResponse assessResumeBlocking(String sessionId, boolean forceRefresh) {
        log.info("[Assessment] Blocking request for sessionId={}, forceRefresh={}", sessionId, forceRefresh);

        // ── Cache-Aside: Check DB first ──────────────────────────────────────
        if (!forceRefresh) {
            Optional<ResumeAssessment> cached = resumeAssessmentRepository.findBySessionId(sessionId);
            if (cached.isPresent()) {
                log.info("[Assessment] Cache HIT for sessionId={}, returning persisted result.", sessionId);
                return toResponse(cached.get(), true);
            }
        } else if (resumeAssessmentRepository.existsBySessionId(sessionId)) {
            log.warn("[Assessment] Force-refresh for sessionId={}. Deleting cached result.", sessionId);
            resumeAssessmentRepository.deleteBySessionId(sessionId);
            resumeAssessmentRepository.flush();
        }

        // ── Cache MISS: Generate via LLM (JSON mode) ─────────────────────────
        log.info("[Assessment] Cache MISS for sessionId={}. Calling LLM API (JSON mode)...", sessionId);

        SessionDocument cvDoc = sessionDocumentRepository
                .findBySessionIdAndDocumentType(sessionId, DocumentType.CV)
                .orElseThrow(() -> new LlmApiException(
                        "No CV data found for session '" + sessionId + "'. Please ingest files first."));

        SessionDocument jdDoc = sessionDocumentRepository
                .findBySessionIdAndDocumentType(sessionId, DocumentType.JD)
                .orElseThrow(() -> new LlmApiException(
                        "No JD data found for session '" + sessionId + "'. Please ingest files first."));

        String fullCvText = cvDoc.getMarkdownContent();
        String aggregatedJdText = jdDoc.getMarkdownContent();

        List<DocumentChunk> cvChunks = documentChunkRepository.findBySessionIdAndDocumentType(sessionId, DocumentType.CV);
        List<DocumentChunk> jdChunks = documentChunkRepository.findBySessionIdAndDocumentType(sessionId, DocumentType.JD);
        String filteredCvText = matchAndAggregateCv(cvChunks, jdChunks);

        log.info("[Assessment] Semantic matching CV: {} chars (down from {} chars) | JD: {} chars → sending to LLM.",
                filteredCvText.length(), fullCvText.length(), aggregatedJdText.length());

        String userContent = buildUserContent(filteredCvText, aggregatedJdText);
        String llmJsonResponse = callLlmBlocking(userContent);

        // ── Parse JSON → DTO → Entity → Persist ──────────────────────────────
        AssessmentResponseDto dto = parseAssessmentDto(sessionId, llmJsonResponse);
        ResumeAssessment entity = buildAndPersistEntity(sessionId, dto);

        return toResponse(entity, false);
    }

    // -------------------------------------------------------------------------
    // Private — LLM Call (JSON mode)
    // -------------------------------------------------------------------------

    /**
     * Calls the Groq LLM API in blocking mode with JSON mode enabled.
     *
     * <p>The request explicitly sets:
     * <ul>
     *   <li>{@code "stream": false} — required by Groq to populate the {@code content} field.
     *   <li>{@code "response_format": {"type": "json_object"}} — enforces valid JSON output.
     *   <li>{@code "temperature": 0.0} — deterministic output for consistent schema compliance.
     * </ul>
     *
     * @param userContent the user-role prompt containing the CV and JD text
     * @return the raw JSON string returned by the LLM
     * @throws LlmApiException on HTTP error or empty response
     */
    private String callLlmBlocking(String userContent) {
        LlmChatRequest request = LlmChatRequest.builder()
                .model(appProperties.getLlm().getModel())
                .maxTokens(appProperties.getLlm().getMaxTokens())
                .temperature(0.0)
                .stream(false)
                .responseFormat(JSON_RESPONSE_FORMAT)
                .messages(List.of(
                        LlmChatRequest.Message.system(PromptTemplateConfig.SYSTEM_PROMPT_ASSESSMENT),
                        LlmChatRequest.Message.user(userContent)
                ))
                .build();

        int maxRetries = 1;
        for (int i = 0; i <= maxRetries; i++) {
            try {
                LlmChatResponse response = llmWebClient.post()
                        .uri(CHAT_COMPLETIONS_PATH)
                        .bodyValue(request)
                        .retrieve()
                        .bodyToMono(LlmChatResponse.class)
                        .block();

                if (response == null || response.getFirstChoiceContent() == null) {
                    throw new LlmApiException("LLM API returned an empty assessment response.");
                }

                if (response.getUsage() != null) {
                    LlmChatResponse.Usage usage = response.getUsage();
                    log.info("[LLM_USAGE] Model: {} | Prompt (Input): {} | Completion (Output): {} | Total: {}",
                            response.getModel(),
                            usage.getPromptTokens(),
                            usage.getCompletionTokens(),
                            usage.getTotalTokens());
                }

                return response.getFirstChoiceContent().strip();

            } catch (WebClientResponseException e) {
                if (e.getStatusCode().value() == 429 && i < maxRetries) {
                    log.warn("[LLM] 429 Too Many Requests. Retrying after 35 seconds...");
                    try {
                        Thread.sleep(35000);
                    } catch (InterruptedException ie) {
                        Thread.currentThread().interrupt();
                    }
                    continue; // try again
                }
                throw new LlmApiException(
                        "LLM API HTTP " + e.getStatusCode() + ": " + e.getResponseBodyAsString(), e);
            } catch (LlmApiException e) {
                throw e;
            } catch (Exception e) {
                throw new LlmApiException("Unexpected error calling LLM API: " + e.getMessage(), e);
            }
        }
        throw new LlmApiException("Max retries exceeded");
    }

    // -------------------------------------------------------------------------
    // Private — JSON Parsing
    // -------------------------------------------------------------------------

    /**
     * Parses the raw LLM JSON response into an {@link AssessmentResponseDto}.
     *
     * <p>If the LLM wraps the JSON in a Markdown code fence (```json ... ```),
     * the fence is stripped before deserialization as a safety fallback —
     * even though JSON mode should prevent this.
     *
     * @param sessionId        used only for error log context
     * @param llmJsonResponse  the raw string from the LLM content field
     * @return a fully populated {@link AssessmentResponseDto}
     * @throws LlmApiException if the response cannot be parsed into the required schema
     */
    private AssessmentResponseDto parseAssessmentDto(String sessionId, String llmJsonResponse) {
        // Safety: strip Markdown code fences if the LLM ignores JSON mode
        String json = llmJsonResponse
                .replaceAll("(?s)^```json\\s*", "")
                .replaceAll("(?s)\\s*```$", "")
                .strip();

        log.debug("[Assessment] Raw LLM JSON for sessionId={}: {}", sessionId, json);

        try {
            AssessmentResponseDto dto = objectMapper.readValue(json, AssessmentResponseDto.class);

            // Validate required fields are present
            if (dto.overallFit() == null || dto.overallFit().competencyFitScore() == null) {
                throw new LlmApiException(
                        "LLM response missing 'competency_fit_score' inside 'overall_fit' for sessionId=" + sessionId);
            }
            if (dto.sectionWiseFeedback() == null) {
                throw new LlmApiException(
                        "LLM response missing 'section_wise_feedback' for sessionId=" + sessionId);
            }
            if (dto.actionableImprovementSuggestions() == null
                    || dto.actionableImprovementSuggestions().isEmpty()) {
                throw new LlmApiException(
                        "LLM response missing 'actionable_improvement_suggestions' for sessionId=" + sessionId);
            }

            log.info("[Assessment] Parsed LLM JSON: score={}, candidateLevel={}, roleType={}, suggestions={}",
                    dto.overallFit().competencyFitScore(),
                    dto.candidateLevel(),
                    dto.roleTypeDetected(),
                    dto.actionableImprovementSuggestions().size());

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

    /**
     * Maps the parsed {@link AssessmentResponseDto} to a {@link ResumeAssessment} entity,
     * persists it to PostgreSQL, and returns the saved entity.
     *
     * @param sessionId the unique interview session identifier
     * @param dto       the fully populated DTO from LLM response parsing
     * @return the saved {@link ResumeAssessment} entity (with generated id and createdAt)
     */
    @Transactional
    protected ResumeAssessment buildAndPersistEntity(String sessionId, AssessmentResponseDto dto) {
        ResumeAssessment entity = ResumeAssessment.builder()
                .sessionId(sessionId)
                .competencyFitScore(dto.overallFit().competencyFitScore())
                .technicalDepthScore(dto.overallFit().technicalDepthScore())
                .matchLevel(dto.overallFit().matchLevel())
                .candidateLevel(dto.candidateLevel())
                .roleTypeDetected(dto.roleTypeDetected())
                .yearsOfExperienceEstimate(dto.yearsOfExperienceEstimate())
                .strongAreas(dto.strongAreas())
                .gapAreas(dto.gapAreas())
                .criticalMissingSkills(dto.criticalMissingSkills())
                .sectionWiseFeedback(dto.sectionWiseFeedback())
                .actionableSuggestions(dto.actionableImprovementSuggestions())
                .build();

        ResumeAssessment saved = resumeAssessmentRepository.save(entity);
        log.info("[Assessment] Persisted ResumeAssessment id={} for sessionId={} | score={}",
                saved.getId(), sessionId, saved.getCompetencyFitScore());
        return saved;
    }

    /**
     * Converts a persisted {@link ResumeAssessment} entity to the {@link AssessmentResponse} API DTO.
     *
     * @param entity the persisted entity (from DB or fresh save)
     * @param cached {@code true} if the result was served from the DB cache
     * @return the fully populated API response DTO
     */
    private AssessmentResponse toResponse(ResumeAssessment entity, boolean cached) {
        return AssessmentResponse.builder()
                .id(entity.getId())
                .sessionId(entity.getSessionId())
                .competencyFitScore(entity.getCompetencyFitScore())
                .technicalDepthScore(entity.getTechnicalDepthScore())
                .matchLevel(entity.getMatchLevel())
                .candidateLevel(entity.getCandidateLevel())
                .roleTypeDetected(entity.getRoleTypeDetected())
                .yearsOfExperienceEstimate(entity.getYearsOfExperienceEstimate())
                .strongAreas(entity.getStrongAreas())
                .gapAreas(entity.getGapAreas())
                .criticalMissingSkills(entity.getCriticalMissingSkills())
                .sectionWiseFeedback(entity.getSectionWiseFeedback())
                .actionableImprovementSuggestions(entity.getActionableSuggestions())
                .cached(cached)
                .createdAt(entity.getCreatedAt())
                .build();
    }

    // -------------------------------------------------------------------------
    // Private — Semantic Cross-Matching
    // -------------------------------------------------------------------------

    /**
     * Semantically matches CV chunks against JD requirements using Cosine Similarity.
     *
     * <p>For each JD chunk, the top {@code topK} CV chunks with similarity &gt;= threshold
     * are selected. The resulting set is deduplicated and sorted back into natural document
     * order (by chunk UUID, which is monotonically increasing at ingest time).
     *
     * <p>Falls back to all CV chunks if none pass the threshold, ensuring the LLM always
     * receives some context.
     *
     * @param cvChunks all CV {@link DocumentChunk}s for this session
     * @param jdChunks all JD {@link DocumentChunk}s for this session
     * @return the aggregated text of the selected CV chunks, joined by double newlines
     */
    private String matchAndAggregateCv(List<DocumentChunk> cvChunks, List<DocumentChunk> jdChunks) {
        final double SIMILARITY_THRESHOLD = 0.75;
        final int TOP_K = 5;

        Set<DocumentChunk> selectedChunks = new LinkedHashSet<>();

        for (DocumentChunk jdChunk : jdChunks) {
            if (jdChunk.getEmbedding() == null) continue;

            List<Map.Entry<DocumentChunk, Double>> similarities = new ArrayList<>();
            for (DocumentChunk cvChunk : cvChunks) {
                if (cvChunk.getEmbedding() == null) continue;
                double score = calculateCosineSimilarity(jdChunk.getEmbedding(), cvChunk.getEmbedding());
                if (score >= SIMILARITY_THRESHOLD) {
                    similarities.add(new AbstractMap.SimpleEntry<>(cvChunk, score));
                }
            }

            similarities.sort((a, b) -> Double.compare(b.getValue(), a.getValue()));
            similarities.stream()
                    .limit(TOP_K)
                    .map(Map.Entry::getKey)
                    .forEach(selectedChunks::add);
        }

        List<DocumentChunk> sortedList = new ArrayList<>(selectedChunks);
        sortedList.sort(Comparator.comparing(DocumentChunk::getId));

        if (sortedList.isEmpty()) {
            log.warn("[Assessment] No CV chunks crossed similarity threshold {}. Falling back to all {} chunks.",
                    SIMILARITY_THRESHOLD, cvChunks.size());
            return cvChunks.stream()
                    .map(DocumentChunk::getChunkText)
                    .collect(Collectors.joining("\n\n"));
        }

        log.info("[Assessment] Semantic matching: selected {}/{} CV chunks.", sortedList.size(), cvChunks.size());
        return sortedList.stream()
                .map(DocumentChunk::getChunkText)
                .collect(Collectors.joining("\n\n"));
    }

    /** Computes the cosine similarity between two equal-length float vectors. Returns 0.0 on error. */
    private double calculateCosineSimilarity(float[] vectorA, float[] vectorB) {
        if (vectorA.length != vectorB.length) return 0.0;
        double dotProduct = 0.0, normA = 0.0, normB = 0.0;
        for (int i = 0; i < vectorA.length; i++) {
            dotProduct += (double) vectorA[i] * vectorB[i];
            normA += Math.pow(vectorA[i], 2);
            normB += Math.pow(vectorB[i], 2);
        }
        if (normA == 0.0 || normB == 0.0) return 0.0;
        return dotProduct / (Math.sqrt(normA) * Math.sqrt(normB));
    }

    // -------------------------------------------------------------------------
    // Private — Prompt builder
    // -------------------------------------------------------------------------

    /**
     * Builds the user-role message containing the matched CV text and full JD text.
     *
     * <p>The system prompt ({@link PromptTemplateConfig#SYSTEM_PROMPT_ASSESSMENT}) instructs
     * the LLM to produce a JSON object. This user message supplies the raw documents
     * that the LLM analyzes to populate the JSON fields.
     */
    private String buildUserContent(String cvText, String jdText) {
        return """
                Evaluate the following CV against the provided JD and return ONLY the JSON object.

                ====== CANDIDATE RESUME (CV) ======
                %s

                ====== JOB DESCRIPTION (JD) ======
                %s
                """.formatted(cvText, jdText);
    }

    public static final String SYSTEM_PROMPT_INTERVIEW_EVALUATION =
            """
            Bạn là một chuyên gia đánh giá phỏng vấn nhân sự IT (Technical Recruiter & Senior Engineer). 
            Nhiệm vụ của bạn là đánh giá toàn bộ kết quả buổi phỏng vấn giả lập của ứng viên dựa trên danh sách câu hỏi và câu trả lời thực tế.

            Hãy phân tích kỹ các câu trả lời của ứng viên đối với từng câu hỏi và tổng hợp thành một báo cáo đánh giá hoàn chỉnh bằng tiếng Việt.

            Yêu cầu định dạng đầu ra phải là một đối tượng JSON có cấu trúc chính xác như sau:
            {
              "overallScore": <điểm số tổng quan từ 0 đến 100 dựa trên chất lượng các câu trả lời>,
              "overallFeedback": "<tổng hợp nhận xét chung về ứng viên, điểm mạnh lớn nhất và điểm cần cải thiện, viết bằng tiếng Việt, khoảng 3-4 câu ngắn gọn, súc tích>",
              "strongAreas": [<danh sách 3-5 thế mạnh/kỹ năng nổi bật ứng viên thể hiện tốt>],
              "gapAreas": [<danh sách 3-5 kỹ năng/lỗ hổng kiến thức cần cải thiện>],
              "actionableSuggestions": [<danh sách 3-4 lời khuyên cụ thể để ứng viên chuẩn bị tốt hơn cho phỏng vấn thật, bằng tiếng Việt>],
              "evaluatedQuestions": [
                {
                  "question": "<nội dung câu hỏi>",
                  "answer": "<câu trả lời của ứng viên>",
                  "score": <điểm số của câu hỏi này, số nguyên từ 1 đến 10>,
                  "strengths": "<phân tích điểm tốt trong câu trả lời này, bằng tiếng Việt, ngắn gọn>",
                  "improvements": "<phân tích điểm thiếu sót/chưa tốt, bằng tiếng Việt, ngắn gọn>",
                  "suggestedAnswer": "<mẫu câu trả lời gợi ý chuẩn mực và đầy đủ cho câu hỏi này, bằng tiếng Việt>"
                }
              ]
            }

            Chú ý:
            - Tất cả nhận xét, đề xuất và câu trả lời mẫu phải viết bằng tiếng Việt tự nhiên, chuyên nghiệp.
            - Giữ cấu trúc JSON hợp lệ.
            """;

    public String evaluateSession(InterviewEvaluationRequest request) {
        StringBuilder userPrompt = new StringBuilder();
        userPrompt.append("Vị trí ứng tuyển: ").append(request.roleTitle()).append("\n");
        userPrompt.append("Thể loại phỏng vấn: ").append(request.interviewType()).append("\n\n");
        userPrompt.append("Dưới đây là chi tiết các câu hỏi và câu trả lời trong buổi phỏng vấn:\n");
        
        List<QuestionAnswerDto> turns = request.turns();
        for (int i = 0; i < turns.size(); i++) {
            QuestionAnswerDto t = turns.get(i);
            userPrompt.append("CÂU HỎI ").append(i + 1).append(":\n");
            userPrompt.append("Hỏi: ").append(t.question()).append("\n");
            userPrompt.append("Trả lời của ứng viên: ").append(t.answer() != null && !t.answer().trim().isEmpty() ? t.answer() : "[Ứng viên không trả lời hoặc bỏ qua]").append("\n");
            userPrompt.append("Điểm số sơ bộ: ").append(t.score() != null ? t.score() : 0).append("/10\n");
            userPrompt.append("Đánh giá sơ bộ: ").append(t.strengths() != null ? t.strengths() : "N/A").append("\n\n");
        }

        LlmChatRequest llmRequest = LlmChatRequest.builder()
                .model(appProperties.getLlm().getModel())
                .maxTokens(appProperties.getLlm().getMaxTokens())
                .temperature(0.3)
                .stream(false)
                .responseFormat(JSON_RESPONSE_FORMAT)
                .messages(List.of(
                        LlmChatRequest.Message.system(SYSTEM_PROMPT_INTERVIEW_EVALUATION),
                        LlmChatRequest.Message.user(userPrompt.toString())
                ))
                .build();

        LlmChatResponse response = llmWebClient.post()
                .uri(CHAT_COMPLETIONS_PATH)
                .bodyValue(llmRequest)
                .retrieve()
                .bodyToMono(LlmChatResponse.class)
                .block();

        if (response == null || response.getFirstChoiceContent() == null) {
            throw new LlmApiException("LLM API returned an empty evaluation response.");
        }

        return response.getFirstChoiceContent().strip();
    }
}
