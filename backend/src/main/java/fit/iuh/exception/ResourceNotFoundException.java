package fit.iuh.exception;

/**
 * Thrown when a requested resource cannot be found in the database.
 *
 * <p>Causes include: querying a {@code QuestionBank} by a {@code sessionId} that
 * does not yet have generated questions, or fetching any entity by an ID that
 * does not exist.
 *
 * <p>Mapped to {@code 404 Not Found} by {@link GlobalExceptionHandler}.
 */
public class ResourceNotFoundException extends RuntimeException {

    public ResourceNotFoundException(String message) {
        super(message);
    }

    public ResourceNotFoundException(String resourceName, String fieldName, Object fieldValue) {
        super(String.format("%s not found with %s: '%s'", resourceName, fieldName, fieldValue));
    }
}
