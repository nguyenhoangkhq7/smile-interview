package fit.iuh.service;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import fit.iuh.config.AppProperties;
import fit.iuh.config.PromptTemplateConfig;
import fit.iuh.dto.AssessmentResponse;
import fit.iuh.dto.chat.LlmChatRequest;
import fit.iuh.dto.chat.LlmChatResponse;
import fit.iuh.dto.chat.LlmChatStreamResponse;
import fit.iuh.entity.DocumentChunk;
import fit.iuh.entity.ResumeAssessment;
import fit.iuh.entity.enums.DocumentType;
import fit.iuh.exception.LlmApiException;
import fit.iuh.repository.DocumentChunkRepository;
import fit.iuh.repository.ResumeAssessmentRepository;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Qualifier;
import org.springframework.http.codec.ServerSentEvent;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.reactive.function.client.WebClient;
import org.springframework.web.reactive.function.client.WebClientResponseException;
import reactor.core.publisher.Flux;

import java.util.*;
import java.util.regex.Matcher;
import java.util.regex.Pattern;
import java.util.stream.Collectors;

/**
 * Service responsible for holistic resume assessment with persistence (Cache-Aside pattern).
 *
 * <p><strong>Cache-Aside Flow (Blocking API):</strong>
 * <pre>
 *  Client (GET /api/v2/assess-resume?sessionId=X)
 *    └── AssessmentService.assessResumeBlocking(sessionId)
 *          ├── 1. Check DB cache → if found: return cached AssessmentResponse immediately
 *          ├── 2. Load CV & JD chunks → Semantic Cross-Matching
 *          ├── 3. Call LLM API (stream=false) → receive full Markdown report
 *          ├── 4. Extract overallScore & hiringRecommendation from Markdown
 *          ├── 5. Persist ResumeAssessment entity → PostgreSQL
 *          └── 6. Return AssessmentResponse to Controller
 * </pre>
 *
 * <p><strong>SSE Streaming Flow:</strong>
 * <pre>
 *  Client (GET /api/v2/assess-resume/stream?sessionId=X)
 *    └── AssessmentService.streamAssessment(sessionId)
 *          ├── 1. Load CV & JD chunks → Semantic Cross-Matching
 *          ├── 2. Call LLM API (stream=true) → Flux<String> tokens via SSE
 *          ├── 3. Collect all tokens → persist full report on stream completion
 *          └── 4. Emit each token as ServerSentEvent to Client
 * </pre>
 */
@Slf4j
@Service
public class AssessmentService {

    /** Path on the LLM provider's base URL for chat completions. */
    private static final String CHAT_COMPLETIONS_PATH = "/openai/v1/chat/completions";

    /** Sentinel value sent by OpenAI-compatible APIs to signal stream end. */
    private static final String SSE_DONE_SENTINEL = "[DONE]";

    /**
     * Regex to extract the overall match score from the Markdown report.
     * Looks for patterns like "OVERALL MATCH SCORE | 72/100" or "Overall Match Score: 72".
     */
    private static final Pattern SCORE_PATTERN = Pattern.compile(
            "(?i)overall\\s*match\\s*score.*?(\\d{1,3})\\s*/\\s*100");

    /**
     * Regex to extract the hiring verdict from the Markdown report.
     * Looks for patterns like "**Verdict:** Strong Fit" or "Verdict: Good Fit".
     */
    private static final Pattern VERDICT_PATTERN = Pattern.compile(
            "(?i)\\*{0,2}verdict\\*{0,2}[:\\s]+\\*{0,2}(Strong Fit|Good Fit|Partial Fit|Poor Fit)\\*{0,2}");

    private final AppProperties appProperties;
    private final WebClient llmWebClient;
    private final DocumentChunkRepository documentChunkRepository;
    private final ResumeAssessmentRepository resumeAssessmentRepository;
    private final ObjectMapper objectMapper;

    public AssessmentService(
            AppProperties appProperties,
            @Qualifier("llmWebClient") WebClient llmWebClient,
            DocumentChunkRepository documentChunkRepository,
            ResumeAssessmentRepository resumeAssessmentRepository,
            ObjectMapper objectMapper) {
        this.appProperties = appProperties;
        this.llmWebClient = llmWebClient;
        this.documentChunkRepository = documentChunkRepository;
        this.resumeAssessmentRepository = resumeAssessmentRepository;
        this.objectMapper = objectMapper;
    }

    // -------------------------------------------------------------------------
    // Public API — Blocking (Cache-Aside)
    // -------------------------------------------------------------------------

    /**
     * Returns a holistic resume assessment for the given session.
     *
     * <p>Implements Cache-Aside: if a result already exists in DB it is returned
     * immediately without calling the LLM. Otherwise the LLM is called, the result
     * is persisted, and then returned.
     *
     * @param sessionId the unique interview session identifier
     * @param forceRefresh if {@code true}, deletes any cached result and regenerates from LLM
     * @return {@link AssessmentResponse} containing the full report and metadata
     * @throws LlmApiException if CV/JD chunks are missing or the LLM call fails
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
            log.warn("[Assessment] Force-refresh requested for sessionId={}. Deleting cached result.", sessionId);
            resumeAssessmentRepository.deleteBySessionId(sessionId);
        }

        // ── Cache MISS: Generate via LLM ─────────────────────────────────────
        log.info("[Assessment] Cache MISS for sessionId={}. Calling LLM API...", sessionId);

        List<DocumentChunk> cvChunks = documentChunkRepository.findBySessionIdAndDocumentType(sessionId, DocumentType.CV);
        if (cvChunks.isEmpty()) {
            throw new LlmApiException("No CV data found for session '" + sessionId + "'. Please ingest files first.");
        }
        List<DocumentChunk> jdChunks = documentChunkRepository.findBySessionIdAndDocumentType(sessionId, DocumentType.JD);
        if (jdChunks.isEmpty()) {
            throw new LlmApiException("No JD data found for session '" + sessionId + "'. Please ingest files first.");
        }

        String matchedCvText = matchAndAggregateCv(cvChunks, jdChunks);
        String aggregatedJdText = jdChunks.stream()
                .map(DocumentChunk::getChunkText)
                .collect(Collectors.joining("\n\n"));

        log.info("[Assessment] Matched CV: {} chars, JD: {} chars → sending to LLM.",
                matchedCvText.length(), aggregatedJdText.length());

        String userContent = buildUserContent(matchedCvText, aggregatedJdText);
        String reportMarkdown = callLlmBlocking(userContent);

        // ── Extract metadata & persist ────────────────────────────────────────
        ResumeAssessment entity = buildAndPersistEntity(sessionId, reportMarkdown);

        return toResponse(entity, false);
    }

    // -------------------------------------------------------------------------
    // Public API — SSE Streaming
    // -------------------------------------------------------------------------

    /**
     * Streams a holistic resume assessment report for the given session as
     * Server-Sent Events. Persists the complete report after the stream finishes.
     *
     * @param sessionId the unique interview session identifier
     * @return a reactive {@link Flux} of SSE events; never null
     */
    public Flux<ServerSentEvent<String>> streamAssessment(String sessionId) {
        log.info("[Assessment] SSE stream request for sessionId={}", sessionId);

        List<DocumentChunk> cvChunks = documentChunkRepository.findBySessionIdAndDocumentType(sessionId, DocumentType.CV);
        if (cvChunks.isEmpty()) {
            return Flux.error(new LlmApiException(
                    "No CV data found for session '" + sessionId + "'. Please ingest first."));
        }
        List<DocumentChunk> jdChunks = documentChunkRepository.findBySessionIdAndDocumentType(sessionId, DocumentType.JD);
        if (jdChunks.isEmpty()) {
            return Flux.error(new LlmApiException(
                    "No JD data found for session '" + sessionId + "'. Please ingest first."));
        }

        String matchedCvText = matchAndAggregateCv(cvChunks, jdChunks);
        String aggregatedJdText = jdChunks.stream()
                .map(DocumentChunk::getChunkText)
                .collect(Collectors.joining("\n\n"));

        String userContent = buildUserContent(matchedCvText, aggregatedJdText);

        LlmChatRequest request = LlmChatRequest.builder()
                .model(appProperties.getLlm().getModel())
                .maxTokens(appProperties.getLlm().getMaxTokens())
                .temperature(0.0)
                .stream(true)
                .messages(List.of(
                        LlmChatRequest.Message.system(PromptTemplateConfig.SYSTEM_PROMPT_ASSESSMENT),
                        LlmChatRequest.Message.user(userContent)
                ))
                .build();

        // Collect all tokens for persistence after stream completes
        StringBuilder fullReportBuffer = new StringBuilder();

        return llmWebClient.post()
                .uri(CHAT_COMPLETIONS_PATH)
                .bodyValue(request)
                .retrieve()
                .bodyToFlux(String.class)
                .filter(line -> !line.isBlank())
                .flatMap(this::parseStreamLine)
                .doOnNext(token -> fullReportBuffer.append(token))
                .doOnComplete(() -> {
                    log.info("[Assessment] SSE stream complete for sessionId={}. Persisting report...", sessionId);
                    try {
                        buildAndPersistEntity(sessionId, fullReportBuffer.toString());
                        log.info("[Assessment] Assessment persisted for sessionId={}", sessionId);
                    } catch (Exception e) {
                        log.error("[Assessment] Failed to persist assessment for sessionId={}: {}", sessionId, e.getMessage());
                    }
                })
                .map(token -> ServerSentEvent.<String>builder()
                        .data(token)
                        .build())
                .doOnError(err -> log.error("[Assessment] SSE error for sessionId={}: {}", sessionId, err.getMessage()))
                .onErrorResume(err -> Flux.just(
                        ServerSentEvent.<String>builder()
                                .event("error")
                                .data("[ERROR] " + err.getMessage())
                                .build()
                ));
    }

    // -------------------------------------------------------------------------
    // Private — LLM call
    // -------------------------------------------------------------------------

    private String callLlmBlocking(String userContent) {
        LlmChatRequest request = LlmChatRequest.builder()
                .model(appProperties.getLlm().getModel())
                .maxTokens(appProperties.getLlm().getMaxTokens())
                .temperature(0.0)
                .stream(false)
                .messages(List.of(
                        LlmChatRequest.Message.system(PromptTemplateConfig.SYSTEM_PROMPT_ASSESSMENT),
                        LlmChatRequest.Message.user(userContent)
                ))
                .build();

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
            return response.getFirstChoiceContent().strip();

        } catch (WebClientResponseException e) {
            throw new LlmApiException("LLM API HTTP " + e.getStatusCode() + ": " + e.getResponseBodyAsString(), e);
        } catch (LlmApiException e) {
            throw e;
        } catch (Exception e) {
            throw new LlmApiException("Unexpected error calling LLM API: " + e.getMessage(), e);
        }
    }

    // -------------------------------------------------------------------------
    // Private — Persistence helpers
    // -------------------------------------------------------------------------

    /**
     * Extracts metadata from the Markdown report, builds a {@link ResumeAssessment}
     * entity, persists it, and returns it.
     *
     * <p>If a record for this session already exists (e.g. concurrent call), the
     * existing record is returned instead to avoid a unique-constraint violation.
     */
    @Transactional
    protected ResumeAssessment buildAndPersistEntity(String sessionId, String reportMarkdown) {
        Integer overallScore = extractOverallScore(reportMarkdown);
        String hiringRecommendation = extractHiringRecommendation(reportMarkdown);

        // Wrap the Markdown in a JSON envelope for the jsonb column
        String assessmentDataJson;
        try {
            assessmentDataJson = objectMapper.writeValueAsString(
                    Map.of("report", reportMarkdown)
            );
        } catch (JsonProcessingException e) {
            log.warn("[Assessment] Could not serialize report to JSON, storing as plain string.");
            assessmentDataJson = "{\"report\": \"serialization_error\"}";
        }

        ResumeAssessment entity = ResumeAssessment.builder()
                .sessionId(sessionId)
                .overallScore(overallScore)
                .hiringRecommendation(hiringRecommendation)
                .assessmentData(assessmentDataJson)
                .build();

        ResumeAssessment saved = resumeAssessmentRepository.save(entity);
        log.info("[Assessment] Persisted ResumeAssessment id={} for sessionId={} | score={} | verdict={}",
                saved.getId(), sessionId, overallScore, hiringRecommendation);
        return saved;
    }

    /**
     * Converts a persisted {@link ResumeAssessment} entity to an {@link AssessmentResponse} DTO.
     * Extracts the plain Markdown text back out of the JSON envelope.
     */
    private AssessmentResponse toResponse(ResumeAssessment entity, boolean cached) {
        String reportMarkdown = entity.getAssessmentData();
        try {
            // Un-wrap the JSON envelope: {"report": "...markdown..."} → "...markdown..."
            Map<?, ?> dataMap = objectMapper.readValue(entity.getAssessmentData(), Map.class);
            Object reportObj = dataMap.get("report");
            if (reportObj != null) {
                reportMarkdown = reportObj.toString();
            }
        } catch (Exception e) {
            log.debug("[Assessment] Could not unwrap assessmentData JSON for id={}, returning raw.", entity.getId());
        }

        return AssessmentResponse.builder()
                .id(entity.getId())
                .sessionId(entity.getSessionId())
                .overallScore(entity.getOverallScore())
                .hiringRecommendation(entity.getHiringRecommendation())
                .report(reportMarkdown)
                .cached(cached)
                .createdAt(entity.getCreatedAt())
                .build();
    }

    // -------------------------------------------------------------------------
    // Private — Metadata extraction (regex)
    // -------------------------------------------------------------------------

    /**
     * Attempts to extract the numeric overall match score from the Markdown report.
     * Returns {@code null} if not found (non-fatal).
     */
    private Integer extractOverallScore(String markdown) {
        Matcher m = SCORE_PATTERN.matcher(markdown);
        if (m.find()) {
            try {
                int score = Integer.parseInt(m.group(1));
                if (score >= 0 && score <= 100) return score;
            } catch (NumberFormatException ignored) { /* fall through */ }
        }
        log.debug("[Assessment] Could not extract overall score from report.");
        return null;
    }

    /**
     * Attempts to extract the hiring recommendation string from the Markdown report.
     * Returns {@code null} if not found (non-fatal).
     */
    private String extractHiringRecommendation(String markdown) {
        Matcher m = VERDICT_PATTERN.matcher(markdown);
        if (m.find()) {
            return m.group(1).trim();
        }
        log.debug("[Assessment] Could not extract hiring recommendation from report.");
        return null;
    }

    // -------------------------------------------------------------------------
    // Private — Semantic Cross-Matching
    // -------------------------------------------------------------------------

    /**
     * Semantically matches CV chunks against JD requirements using Cosine Similarity.
     * For each JD chunk, the top {@code topK} CV chunks with similarity >= threshold
     * are selected. The selected set is then sorted back into natural document order.
     *
     * <p>Falls back to all CV chunks if none pass the threshold.
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
            log.warn("[Assessment] No CV chunks crossed threshold {}. Falling back to all {} chunks.",
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

    /** Computes the cosine similarity between two equal-length float vectors. */
    private double calculateCosineSimilarity(float[] vectorA, float[] vectorB) {
        if (vectorA.length != vectorB.length) return 0.0;
        double dotProduct = 0.0, normA = 0.0, normB = 0.0;
        for (int i = 0; i < vectorA.length; i++) {
            dotProduct += vectorA[i] * vectorB[i];
            normA += Math.pow(vectorA[i], 2);
            normB += Math.pow(vectorB[i], 2);
        }
        if (normA == 0.0 || normB == 0.0) return 0.0;
        return dotProduct / (Math.sqrt(normA) * Math.sqrt(normB));
    }

    // -------------------------------------------------------------------------
    // Private — Prompt builder
    // -------------------------------------------------------------------------

    private String buildUserContent(String cvText, String jdText) {
        return """
                Please perform a comprehensive holistic assessment based on the following documents:

                ====== CANDIDATE RESUME (CV) ======
                %s

                ====== JOB DESCRIPTION (JD) ======
                %s
                """.formatted(cvText, jdText);
    }

    // -------------------------------------------------------------------------
    // Private — SSE stream parser
    // -------------------------------------------------------------------------

    /**
     * Parses a raw SSE data line from the LLM stream into a token string.
     * Strips the "data: " prefix, ignores [DONE], and handles parse errors gracefully.
     */
    private Flux<String> parseStreamLine(String rawLine) {
        String json = rawLine.startsWith("data: ")
                ? rawLine.substring(6).trim()
                : rawLine.trim();

        if (SSE_DONE_SENTINEL.equals(json)) return Flux.empty();

        try {
            LlmChatStreamResponse chunk = objectMapper.readValue(json, LlmChatStreamResponse.class);
            String content = chunk.getDeltaContent();
            return (content == null || content.isEmpty()) ? Flux.empty() : Flux.just(content);
        } catch (Exception e) {
            log.debug("[Assessment] Skipping unparseable SSE chunk: {} | error: {}", rawLine, e.getMessage());
            return Flux.empty();
        }
    }
}
