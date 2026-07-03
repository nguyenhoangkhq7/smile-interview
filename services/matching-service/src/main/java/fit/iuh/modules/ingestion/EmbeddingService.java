package fit.iuh.modules.ingestion;

import fit.iuh.config.AppProperties;
import fit.iuh.dto.embedding.VectorEmbeddingRequest;
import fit.iuh.dto.embedding.VectorEmbeddingResponse;
import fit.iuh.modules.ingestion.DocumentChunk;
import fit.iuh.modules.ingestion.DocumentType;
import fit.iuh.exception.EmbeddingException;
import fit.iuh.modules.ingestion.DocumentChunkRepository;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Qualifier;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.reactive.function.client.WebClient;
import org.springframework.web.reactive.function.client.WebClientResponseException;
import reactor.core.publisher.Mono;

import java.time.Duration;
import java.util.ArrayList;
import java.util.List;

/**
 * Service responsible for generating text embeddings via a configurable
 * Embeddings API and persisting the resulting {@link DocumentChunk} entities.
 *
 * <p><strong>Vendor-Agnostic Design:</strong> This service uses generic
 * {@link VectorEmbeddingRequest} / {@link VectorEmbeddingResponse} DTOs.
 * The underlying embedding provider (currently OpenAI) is selected at the
 * infrastructure level via {@link fit.iuh.config.WebClientConfig} and
 * {@link AppProperties}. Switching to a different provider (e.g., Cohere,
 * Voyage AI, Azure OpenAI) only requires changing environment variables.
 *
 * <p><strong>Pipeline role:</strong> Step 4 (final) of the ingestion pipeline.
 * <pre>
 *   Text chunks → [EmbeddingService] → float[1536] vectors → PostgreSQL (vector column)
 * </pre>
 *
 * <p><strong>Embedding dimension:</strong> Fixed at 1536 to match the
 * {@code vector(1536)} column in {@code document_chunks} and the
 * {@code text-embedding-3-small} model's output.
 *
 * <p>If any chunk fails to embed, the entire {@link #embedAndSave} transaction
 * is rolled back, preventing partial data from being written to the database.
 */
@Slf4j
@Service
public class EmbeddingService {

    private final AppProperties appProperties;
    private final DocumentChunkRepository documentChunkRepository;

    /**
     * Pre-configured embeddings WebClient (currently pointing to OpenAI).
     * Injected by qualifier to avoid ambiguity with the LLM WebClient.
     */
    private final WebClient embeddingWebClient;

    public EmbeddingService(
            AppProperties appProperties,
            DocumentChunkRepository documentChunkRepository,
            @Qualifier("embeddingWebClient") WebClient embeddingWebClient) {
        this.appProperties = appProperties;
        this.documentChunkRepository = documentChunkRepository;
        this.embeddingWebClient = embeddingWebClient;
    }

    private static final String EMBEDDINGS_PATH = "/api/embed";
    private static final int EXPECTED_DIMENSION  = 2560;

    // -------------------------------------------------------------------------
    // Public API
    // -------------------------------------------------------------------------

    /**
     * Generates a 4096-dimensional embedding vector for a single text chunk.
     *
     * <p>Calls the configured Embeddings API endpoint and validates the response
     * dimension before returning.
     *
     * @param text the text chunk to embed (must not be null or blank)
     * @return a {@code float[4096]} embedding vector
     * @throws EmbeddingException if the API call fails, times out, or returns
     *                            a vector with an unexpected dimension
     */
    public float[] generateEmbedding(String text) {
        if (text == null || text.isBlank()) {
            throw new EmbeddingException("Cannot generate embedding for null or blank text.");
        }
        List<float[]> embeddings = generateEmbeddings(List.of(text));
        if (embeddings == null || embeddings.isEmpty()) {
            throw new EmbeddingException("Failed to generate embedding for the input text.");
        }
        return embeddings.get(0);
    }

    /**
     * Generates 4096-dimensional embedding vectors for a list of text chunks in a single batch call.
     *
     * <p>Calls the configured Embeddings API endpoint passing all texts in the input list.
     *
     * @param texts the list of text chunks to embed (must not be null or empty)
     * @return a list of {@code float[4096]} embedding vectors in the same order as the inputs
     * @throws EmbeddingException if the API call fails, times out, or returns unexpected dimensions
     */
    public List<float[]> generateEmbeddings(List<String> texts) {
        if (texts == null || texts.isEmpty()) {
            throw new EmbeddingException("Cannot generate embeddings for null or empty text list.");
        }

        VectorEmbeddingRequest request = VectorEmbeddingRequest.builder()
                .model(appProperties.getOllama().getEmbeddingModel())
                .input(texts)
                .build();

        Duration timeout = Duration.ofSeconds(appProperties.getOllama().getTimeoutSeconds());

        try {
            VectorEmbeddingResponse response = embeddingWebClient.post()
                    .uri(EMBEDDINGS_PATH)
                    .bodyValue(request)
                    .retrieve()
                    .bodyToMono(VectorEmbeddingResponse.class)
                    .timeout(
                            timeout,
                            Mono.error(new EmbeddingException(
                                    "Embeddings API call timed out after " +
                                    appProperties.getOllama().getTimeoutSeconds() + " seconds."))
                    )
                    .block();

            if (response == null) {
                throw new EmbeddingException("Embeddings API returned a null response.");
            }

            List<List<Double>> embeddingsList = response.getEmbeddings();
            if (embeddingsList == null || embeddingsList.isEmpty()) {
                throw new EmbeddingException("Embeddings API returned an empty embeddings list.");
            }

            if (embeddingsList.size() != texts.size()) {
                throw new EmbeddingException(String.format(
                        "Mismatch in embeddings count: expected %d, got %d.",
                        texts.size(), embeddingsList.size()));
            }

            List<float[]> results = new ArrayList<>(texts.size());
            for (int i = 0; i < embeddingsList.size(); i++) {
                List<Double> values = embeddingsList.get(i);
                if (values == null || values.isEmpty()) {
                    throw new EmbeddingException("Embeddings API returned null or empty vector at index " + i);
                }

                if (values.size() != EXPECTED_DIMENSION) {
                    throw new EmbeddingException(String.format(
                            "Unexpected embedding dimension at index %d: expected %d, got %d.",
                            i, EXPECTED_DIMENSION, values.size()));
                }

                float[] result = new float[values.size()];
                for (int j = 0; j < values.size(); j++) {
                    result[j] = values.get(j).floatValue();
                }
                results.add(result);
            }

            return results;

        } catch (EmbeddingException e) {
            throw e;
        } catch (WebClientResponseException e) {
            throw new EmbeddingException(
                    "Embeddings API HTTP " + e.getStatusCode() +
                    ": " + e.getResponseBodyAsString(), e);
        } catch (Exception e) {
            throw new EmbeddingException(
                    "Unexpected error calling Embeddings API: " + e.getMessage(), e);
        }
    }

    /**
     * Generates embeddings for all text chunks and persists them as
     * {@link DocumentChunk} entities in a single atomic database transaction.
     *
     * <p>Chunks are embedded in a single batch request to prevent API rate limiting.
     * If any chunk fails, the transaction is rolled back.
     *
     * @param chunks       ordered list of text chunks to embed and persist
     * @param sessionId    the interview session these chunks belong to
     * @param documentType the document type: {@code CV} or {@code JD}
     * @return the list of successfully saved {@link DocumentChunk} entities
     * @throws EmbeddingException if embedding generation fails
     */
    @Transactional
    public List<DocumentChunk> embedAndSave(
            List<String> chunks,
            String sessionId,
            DocumentType documentType) {

        if (chunks == null || chunks.isEmpty()) {
            return new ArrayList<>();
        }

        log.info("Embedding + saving {} {} chunks for session={}",
                chunks.size(), documentType, sessionId);

        // Generate embeddings for all chunks in a single batch request
        List<float[]> vectors = generateEmbeddings(chunks);

        List<DocumentChunk> toSave = new ArrayList<>(chunks.size());
        for (int i = 0; i < chunks.size(); i++) {
            toSave.add(DocumentChunk.builder()
                    .sessionId(sessionId)
                    .documentType(documentType)
                    .chunkText(chunks.get(i))
                    .embedding(vectors.get(i))
                    .build());
        }

        List<DocumentChunk> saved = documentChunkRepository.saveAll(toSave);

        log.info("Saved {} {} chunks to DB (session={})", saved.size(), documentType, sessionId);
        return saved;
    }
}
