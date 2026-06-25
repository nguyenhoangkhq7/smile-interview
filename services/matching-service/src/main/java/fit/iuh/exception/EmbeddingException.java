package fit.iuh.exception;

/**
 * Thrown when the OpenAI Embeddings API call fails or returns an invalid response.
 * Causes: invalid API key (401), rate limiting (429), network issues, or an
 * embedding vector of unexpected dimension (not 1536).
 */
public class EmbeddingException extends RuntimeException {

    public EmbeddingException(String message) {
        super(message);
    }

    public EmbeddingException(String message, Throwable cause) {
        super(message, cause);
    }
}
