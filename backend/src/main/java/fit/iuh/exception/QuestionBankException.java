package fit.iuh.exception;

/**
 * Thrown when the question bank generation pipeline encounters an error.
 *
 * <p>Causes include: LLM returning invalid JSON for question generation,
 * difficulty distribution calculation failures, missing prerequisite data
 * (no assessment found for session), or validation errors in generated questions.
 */
public class QuestionBankException extends RuntimeException {

    public QuestionBankException(String message) {
        super(message);
    }

    public QuestionBankException(String message, Throwable cause) {
        super(message, cause);
    }
}
