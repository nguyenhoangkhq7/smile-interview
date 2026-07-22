package fit.iuh.common.exception;

/**
 * Domain exception for all LLM inference failures — covers timeout, HTTP errors,
 * and JSON parse failures from the OpenRouter API.
 * <p>
 * Using a typed exception instead of generic {@link RuntimeException} allows
 * callers to distinguish LLM-specific failures from unrelated system errors.
 */
public class LlmInferenceException extends RuntimeException {

    public LlmInferenceException(String message) {
        super(message);
    }

    public LlmInferenceException(String message, Throwable cause) {
        super(message, cause);
    }
}
