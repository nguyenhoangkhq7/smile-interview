package fit.iuh.dto;

import com.fasterxml.jackson.annotation.JsonInclude;
import lombok.Builder;
import lombok.Data;

import java.time.Instant;

/**
 * Standardized error response body returned by {@link fit.iuh.exception.GlobalExceptionHandler}
 * for all API error scenarios.
 */
@Data
@Builder
@JsonInclude(JsonInclude.Include.NON_NULL)
public class ErrorResponse {

    /** HTTP status code (e.g., 400, 500). */
    private int status;

    /** Short error code identifier (e.g., {@code "PDF_PARSING_ERROR"}). */
    private String errorCode;

    /** Human-readable description of the error. */
    private String message;

    /** Optional additional details (e.g., which field failed, stack trace summary). */
    private String detail;

    /** The request path that triggered the error. */
    private String path;

    /** ISO-8601 timestamp of when the error occurred. */
    @Builder.Default
    private Instant timestamp = Instant.now();
}
