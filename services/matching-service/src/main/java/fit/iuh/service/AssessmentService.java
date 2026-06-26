package fit.iuh.service;

import com.fasterxml.jackson.databind.ObjectMapper;
import fit.iuh.config.AppProperties;
import fit.iuh.config.PromptTemplateConfig;
import fit.iuh.dto.chat.LlmChatRequest;
import fit.iuh.dto.chat.LlmChatStreamResponse;
import fit.iuh.entity.DocumentChunk;
import fit.iuh.entity.enums.DocumentType;
import fit.iuh.exception.LlmApiException;
import fit.iuh.repository.DocumentChunkRepository;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Qualifier;
import org.springframework.http.codec.ServerSentEvent;
import org.springframework.stereotype.Service;
import org.springframework.web.reactive.function.client.WebClient;
import reactor.core.publisher.Flux;

import java.util.List;
import java.util.stream.Collectors;

/**
 * Service responsible for streaming a holistic resume assessment via SSE.
 *
 * <p><strong>Flow:</strong>
 * <pre>
 *  Client (GET /api/v2/assess-resume/stream?sessionId=X)
 *    └── AssessmentController
 *          └── AssessmentService.streamAssessment(sessionId)
 *                ├── 1. Load CV chunks from DB → aggregate into single text block
 *                ├── 2. Load JD chunks from DB → aggregate into single text block
 *                ├── 3. Build LlmChatRequest (stream=true, assessment prompt)
 *                └── 4. WebClient POST → SSE Flux<ServerSentEvent<String>>
 * </pre>
 *
 * <p>Each SSE event carries one token of the LLM response, allowing the client
 * to render the analysis progressively, exactly like ChatGPT.
 */
@Slf4j
@Service
public class AssessmentService {

    /** Path on the LLM provider's base URL for streaming chat completions. */
    private static final String CHAT_COMPLETIONS_PATH = "/openai/v1/chat/completions";

    /** Sentinel value sent by OpenAI-compatible APIs to signal stream end. */
    private static final String SSE_DONE_SENTINEL = "[DONE]";

    private final AppProperties appProperties;
    private final WebClient llmWebClient;
    private final DocumentChunkRepository documentChunkRepository;
    private final ObjectMapper objectMapper;

    public AssessmentService(
            AppProperties appProperties,
            @Qualifier("llmWebClient") WebClient llmWebClient,
            DocumentChunkRepository documentChunkRepository,
            ObjectMapper objectMapper) {
        this.appProperties = appProperties;
        this.llmWebClient = llmWebClient;
        this.documentChunkRepository = documentChunkRepository;
        this.objectMapper = objectMapper;
    }

    // -------------------------------------------------------------------------
    // Public API
    // -------------------------------------------------------------------------

    /**
     * Streams a holistic resume assessment report for the given session as
     * Server-Sent Events.
     *
     * <p>Each event carries a plain text token fragment. The stream terminates
     * naturally when the LLM finishes generating or with an error event on failure.
     *
     * @param sessionId the unique interview session identifier; must have been
     *                  previously ingested via {@code POST /api/v1/ingest/{sessionId}}
     * @return a reactive {@link Flux} of SSE events; never null
     * @throws LlmApiException if no CV or JD chunks exist for the given session
     */
    public Flux<ServerSentEvent<String>> streamAssessment(String sessionId) {
        log.info("[Assessment] Starting SSE stream for sessionId={}", sessionId);

        // ── Step 1: Load and aggregate CV chunks ────────────────────────────
        String aggregatedCv = aggregateChunks(sessionId, DocumentType.CV);
        if (aggregatedCv.isBlank()) {
            log.error("[Assessment] No CV chunks found for sessionId={}", sessionId);
            return Flux.error(new LlmApiException(
                    "No CV data found for session '" + sessionId + "'. " +
                    "Please run the ingestion pipeline first (POST /api/v1/ingest/{sessionId})."));
        }

        // ── Step 2: Load and aggregate JD chunks ────────────────────────────
        String aggregatedJd = aggregateChunks(sessionId, DocumentType.JD);
        if (aggregatedJd.isBlank()) {
            log.error("[Assessment] No JD chunks found for sessionId={}", sessionId);
            return Flux.error(new LlmApiException(
                    "No JD data found for session '" + sessionId + "'. " +
                    "Please run the ingestion pipeline first (POST /api/v1/ingest/{sessionId})."));
        }

        log.info("[Assessment] Loaded {} CV chars and {} JD chars for sessionId={}",
                aggregatedCv.length(), aggregatedJd.length(), sessionId);

        // ── Step 3: Build the user message with both documents ───────────────
        String userContent = buildUserContent(aggregatedCv, aggregatedJd);

        // ── Step 4: Build streaming LLM request ─────────────────────────────
        LlmChatRequest request = LlmChatRequest.builder()
                .model(appProperties.getLlm().getModel())
                .maxTokens(appProperties.getLlm().getMaxTokens())
                .temperature(0.0)
                .stream(true)                  // Enable SSE streaming
                .messages(List.of(
                        LlmChatRequest.Message.system(PromptTemplateConfig.SYSTEM_PROMPT_ASSESSMENT),
                        LlmChatRequest.Message.user(userContent)
                ))
                .build();

        // ── Step 5: Stream LLM response as SSE ──────────────────────────────
        return llmWebClient.post()
                .uri(CHAT_COMPLETIONS_PATH)
                .bodyValue(request)
                .retrieve()
                .bodyToFlux(String.class)          // Each SSE line arrives as a String
                .filter(line -> !line.isBlank())
                .flatMap(this::parseStreamLine)    // Parse each chunk → token string
                .map(token -> ServerSentEvent.<String>builder()
                        .data(token)
                        .build())
                .doOnComplete(() ->
                        log.info("[Assessment] SSE stream complete for sessionId={}", sessionId))
                .doOnError(err ->
                        log.error("[Assessment] SSE stream error for sessionId={}: {}",
                                sessionId, err.getMessage()))
                .onErrorResume(err -> Flux.just(
                        ServerSentEvent.<String>builder()
                                .event("error")
                                .data("[ERROR] " + err.getMessage())
                                .build()
                ));
    }

    /**
     * Performs a standard synchronous (blocking) assessment for the given session.
     *
     * @param sessionId the unique interview session identifier
     * @return the complete assessment report in Markdown format
     * @throws LlmApiException if CV/JD chunks are missing or the API call fails
     */
    public String assessResumeBlocking(String sessionId) {
        log.info("[Assessment] Starting blocking assessment for sessionId={}", sessionId);

        List<DocumentChunk> cvChunks = documentChunkRepository.findBySessionIdAndDocumentType(sessionId, DocumentType.CV);
        if (cvChunks.isEmpty()) {
            throw new LlmApiException("No CV data found for session '" + sessionId + "'. Please ingest files first.");
        }

        List<DocumentChunk> jdChunks = documentChunkRepository.findBySessionIdAndDocumentType(sessionId, DocumentType.JD);
        if (jdChunks.isEmpty()) {
            throw new LlmApiException("No JD data found for session '" + sessionId + "'. Please ingest files first.");
        }

        // Apply Semantic Cross-Matching to filter only relevant CV chunks
        String matchedCvText = matchAndAggregateCv(cvChunks, jdChunks);
        String aggregatedJdText = jdChunks.stream()
                .map(DocumentChunk::getChunkText)
                .collect(Collectors.joining("\n\n"));

        log.info("[Assessment] Semantically matched CV size: {} chars (original: {} chunks -> matched). JD size: {} chars.",
                matchedCvText.length(), cvChunks.size(), aggregatedJdText.length());

        String userContent = buildUserContent(matchedCvText, aggregatedJdText);

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
            fit.iuh.dto.chat.LlmChatResponse response = llmWebClient.post()
                    .uri(CHAT_COMPLETIONS_PATH)
                    .bodyValue(request)
                    .retrieve()
                    .bodyToMono(fit.iuh.dto.chat.LlmChatResponse.class)
                    .block();

            if (response == null || response.getFirstChoiceContent() == null) {
                throw new LlmApiException("LLM API returned an empty response for assessment.");
            }

            return response.getFirstChoiceContent().strip();

        } catch (org.springframework.web.reactive.function.client.WebClientResponseException e) {
            throw new LlmApiException("LLM API HTTP " + e.getStatusCode() + ": " + e.getResponseBodyAsString(), e);
        } catch (Exception e) {
            throw new LlmApiException("Unexpected error calling LLM API: " + e.getMessage(), e);
        }
    }

    // -------------------------------------------------------------------------
    // Private helpers
    // -------------------------------------------------------------------------

    /**
     * Semantically matches CV chunks against JD requirements.
     * For each JD chunk, we find the top 2 CV chunks with similarity >= 0.4.
     * We then aggregate them in their original order.
     */
    private String matchAndAggregateCv(List<DocumentChunk> cvChunks, List<DocumentChunk> jdChunks) {
        double similarityThreshold = 0.75; // Ngưỡng tương đồng tối thiểu
        int topK = 5;                      // Số lượng CV chunk tối đa cho mỗi JD chunk

        java.util.Set<DocumentChunk> selectedChunks = new java.util.LinkedHashSet<>();

        for (DocumentChunk jdChunk : jdChunks) {
            if (jdChunk.getEmbedding() == null) continue;

            List<java.util.Map.Entry<DocumentChunk, Double>> similarities = new java.util.ArrayList<>();
            for (DocumentChunk cvChunk : cvChunks) {
                if (cvChunk.getEmbedding() == null) continue;

                double score = calculateCosineSimilarity(jdChunk.getEmbedding(), cvChunk.getEmbedding());
                if (score >= similarityThreshold) {
                    similarities.add(new java.util.AbstractMap.SimpleEntry<>(cvChunk, score));
                }
            }

            // Sắp xếp giảm dần theo độ tương đồng
            similarities.sort((a, b) -> Double.compare(b.getValue(), a.getValue()));

            // Lấy Top K chunk CV tốt nhất cho yêu cầu JD này
            similarities.stream()
                    .limit(topK)
                    .map(java.util.Map.Entry::getKey)
                    .forEach(selectedChunks::add);
        }

        // Sắp xếp các chunk CV đã chọn theo thứ tự Id tự nhiên (giúp thông tin liền mạch như văn bản gốc)
        List<DocumentChunk> sortedCvList = new java.util.ArrayList<>(selectedChunks);
        sortedCvList.sort(java.util.Comparator.comparing(DocumentChunk::getId));

        // Nếu không có chunk nào đạt ngưỡng, fallback về việc dùng toàn bộ CV chunks để tránh mất mát dữ liệu
        if (sortedCvList.isEmpty()) {
            log.warn("No CV chunks crossed the similarity threshold (>= {}). Falling back to all chunks.", similarityThreshold);
            return cvChunks.stream()
                    .map(DocumentChunk::getChunkText)
                    .collect(Collectors.joining("\n\n"));
        }

        return sortedCvList.stream()
                .map(DocumentChunk::getChunkText)
                .collect(Collectors.joining("\n\n"));
    }

    /**
     * Computes the cosine similarity between two float vectors.
     */
    private double calculateCosineSimilarity(float[] vectorA, float[] vectorB) {
        if (vectorA.length != vectorB.length) {
            return 0.0;
        }
        double dotProduct = 0.0;
        double normA = 0.0;
        double normB = 0.0;
        for (int i = 0; i < vectorA.length; i++) {
            dotProduct += vectorA[i] * vectorB[i];
            normA += Math.pow(vectorA[i], 2);
            normB += Math.pow(vectorB[i], 2);
        }
        if (normA == 0.0 || normB == 0.0) {
            return 0.0;
        }
        return dotProduct / (Math.sqrt(normA) * Math.sqrt(normB));
    }

    private String aggregateChunks(String sessionId, DocumentType type) {
        List<DocumentChunk> chunks = documentChunkRepository
                .findBySessionIdAndDocumentType(sessionId, type);

        return chunks.stream()
                .map(DocumentChunk::getChunkText)
                .collect(Collectors.joining("\n\n"));
    }

    /**
     * Wraps the aggregated CV and JD texts into a structured user message
     * that clearly separates the two documents for the LLM.
     */
    private String buildUserContent(String cvText, String jdText) {
        return """
                Please perform a comprehensive holistic assessment based on the following documents:

                ====== CANDIDATE RESUME (CV) ======
                %s

                ====== JOB DESCRIPTION (JD) ======
                %s
                """.formatted(cvText, jdText);
    }

    /**
     * Parses a raw SSE data line from the LLM stream into a token string.
     *
     * <p>OpenAI-compatible streaming responses prefix each JSON payload with
     * {@code "data: "}. The stream ends with {@code "data: [DONE]"} which
     * must be ignored. Empty content deltas (role-only first chunk) are also
     * filtered out.
     *
     * @param rawLine a raw line received from the SSE stream
     * @return a Flux emitting the extracted token, or empty if nothing to emit
     */
    private Flux<String> parseStreamLine(String rawLine) {
        // Strip the "data: " prefix that OpenAI-compatible APIs prepend
        String json = rawLine.startsWith("data: ")
                ? rawLine.substring(6).trim()
                : rawLine.trim();

        // End-of-stream sentinel — emit nothing
        if (SSE_DONE_SENTINEL.equals(json)) {
            return Flux.empty();
        }

        try {
            LlmChatStreamResponse chunk = objectMapper.readValue(json, LlmChatStreamResponse.class);
            String content = chunk.getDeltaContent();

            // Filter out null/empty deltas (first chunk often only contains role)
            if (content == null || content.isEmpty()) {
                return Flux.empty();
            }

            return Flux.just(content);

        } catch (Exception e) {
            // Non-fatal: log and skip malformed chunks rather than killing the stream
            log.debug("[Assessment] Skipping unparseable SSE chunk: {} | error: {}", rawLine, e.getMessage());
            return Flux.empty();
        }
    }
}

