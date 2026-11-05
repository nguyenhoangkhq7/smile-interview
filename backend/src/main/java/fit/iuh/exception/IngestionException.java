package fit.iuh.exception;

/**
 * General-purpose exception for errors that occur during the top-level
 * ingestion orchestration (e.g., invalid session ID, missing required input,
 * or a combination of pipeline failures).
 */
public class IngestionException extends RuntimeException {

    public IngestionException(String message) {
        super(message);
    }

    public IngestionException(String message, Throwable cause) {
        super(message, cause);
    }
}
