package fit.iuh.exception;

/**
 * Thrown when communication with the Groq LLM API fails.
 * Causes: network timeout, rate limiting (429), invalid API key (401),
 * unexpected response format, or empty LLM response content.
 */
public class LlmApiException extends RuntimeException {

    public LlmApiException(String message) {
        super(message);
    }

    public LlmApiException(String message, Throwable cause) {
        super(message, cause);
    }
}
