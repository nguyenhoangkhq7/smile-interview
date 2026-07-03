package fit.iuh.exception;

import fit.iuh.dto.ErrorResponse;
import jakarta.servlet.http.HttpServletRequest;
import lombok.extern.slf4j.Slf4j;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.RestControllerAdvice;
import org.springframework.web.multipart.MaxUploadSizeExceededException;

/**
 * Global exception handler for all REST controllers in the matching-service.
 *
 * <p>Catches domain-specific exceptions thrown during the ingestion pipeline and
 * maps them to appropriate HTTP status codes with a consistent {@link ErrorResponse}
 * body.
 *
 * <p>Hierarchy of handled exceptions:
 * <ul>
 *   <li>{@link PdfParsingException}         → 400 Bad Request</li>
 *   <li>{@link IngestionException}           → 400 Bad Request</li>
 *   <li>{@link LlmApiException}              → 502 Bad Gateway</li>
 *   <li>{@link EmbeddingException}           → 502 Bad Gateway</li>
 *   <li>{@link MaxUploadSizeExceededException} → 413 Payload Too Large</li>
 *   <li>{@link QuestionBankException}         → 422 Unprocessable Entity</li>
 *   <li>{@link Exception} (catch-all)        → 500 Internal Server Error</li>
 * </ul>
 */
@Slf4j
@RestControllerAdvice
public class GlobalExceptionHandler {

    // -------------------------------------------------------------------------
    // 400 Bad Request — client-side errors
    // -------------------------------------------------------------------------

    /**
     * Handles failures during PDF text extraction (corrupted file, wrong type, etc.).
     */
    @ExceptionHandler(PdfParsingException.class)
    public ResponseEntity<ErrorResponse> handlePdfParsingException(
            PdfParsingException ex, HttpServletRequest request) {

        log.error("[PDF_PARSING_ERROR] path={} | {}", request.getRequestURI(), ex.getMessage(), ex);
        return ResponseEntity.status(HttpStatus.BAD_REQUEST)
                .body(ErrorResponse.builder()
                        .status(HttpStatus.BAD_REQUEST.value())
                        .errorCode("PDF_PARSING_ERROR")
                        .message("Failed to parse the uploaded PDF file.")
                        .detail(ex.getMessage())
                        .path(request.getRequestURI())
                        .build());
    }

    /**
     * Handles high-level ingestion pipeline errors (missing input, invalid session, etc.).
     */
    @ExceptionHandler(IngestionException.class)
    public ResponseEntity<ErrorResponse> handleIngestionException(
            IngestionException ex, HttpServletRequest request) {

        log.error("[INGESTION_ERROR] path={} | {}", request.getRequestURI(), ex.getMessage(), ex);
        return ResponseEntity.status(HttpStatus.BAD_REQUEST)
                .body(ErrorResponse.builder()
                        .status(HttpStatus.BAD_REQUEST.value())
                        .errorCode("INGESTION_ERROR")
                        .message("Ingestion pipeline failed.")
                        .detail(ex.getMessage())
                        .path(request.getRequestURI())
                        .build());
    }

    // -------------------------------------------------------------------------
    // 413 Payload Too Large — file size limit exceeded
    // -------------------------------------------------------------------------

    /**
     * Handles multipart file upload size violations (configured in application.yaml).
     */
    @ExceptionHandler(MaxUploadSizeExceededException.class)
    public ResponseEntity<ErrorResponse> handleMaxUploadSizeExceeded(
            MaxUploadSizeExceededException ex, HttpServletRequest request) {

        log.warn("[FILE_TOO_LARGE] path={} | {}", request.getRequestURI(), ex.getMessage());
        return ResponseEntity.status(HttpStatus.PAYLOAD_TOO_LARGE)
                .body(ErrorResponse.builder()
                        .status(HttpStatus.PAYLOAD_TOO_LARGE.value())
                        .errorCode("FILE_TOO_LARGE")
                        .message("Uploaded file exceeds the maximum allowed size (50 MB).")
                        .path(request.getRequestURI())
                        .build());
    }

    // -------------------------------------------------------------------------
    // 502 Bad Gateway — upstream AI API errors
    // -------------------------------------------------------------------------

    /**
     * Handles failures when communicating with the LLM API
     * (timeout, rate limit, invalid API key, malformed response).
     */
    @ExceptionHandler(LlmApiException.class)
    public ResponseEntity<ErrorResponse> handleLlmApiException(
            LlmApiException ex, HttpServletRequest request) {

        log.error("[LLM_API_ERROR] path={} | {}", request.getRequestURI(), ex.getMessage(), ex);
        return ResponseEntity.status(HttpStatus.BAD_GATEWAY)
                .body(ErrorResponse.builder()
                        .status(HttpStatus.BAD_GATEWAY.value())
                        .errorCode("LLM_API_ERROR")
                        .message("Failed to communicate with the LLM API. Please retry.")
                        .detail(ex.getMessage())
                        .path(request.getRequestURI())
                        .build());
    }

    /**
     * Handles failures when calling the OpenAI Embeddings API
     * (timeout, rate limit, invalid API key, wrong dimension).
     */
    @ExceptionHandler(EmbeddingException.class)
    public ResponseEntity<ErrorResponse> handleEmbeddingException(
            EmbeddingException ex, HttpServletRequest request) {

        log.error("[EMBEDDING_ERROR] path={} | {}", request.getRequestURI(), ex.getMessage(), ex);
        return ResponseEntity.status(HttpStatus.BAD_GATEWAY)
                .body(ErrorResponse.builder()
                        .status(HttpStatus.BAD_GATEWAY.value())
                        .errorCode("EMBEDDING_ERROR")
                        .message("Failed to generate embedding vectors via local/configured Embeddings API. Please retry.")
                        .detail(ex.getMessage())
                        .path(request.getRequestURI())
                        .build());
    }

    // -------------------------------------------------------------------------
    // 422 Unprocessable Entity — question bank generation errors
    // -------------------------------------------------------------------------

    /**
     * Handles failures during question bank generation (invalid LLM JSON output,
     * missing prerequisite data, validation errors in generated questions).
     */
    @ExceptionHandler(QuestionBankException.class)
    public ResponseEntity<ErrorResponse> handleQuestionBankException(
            QuestionBankException ex, HttpServletRequest request) {

        log.error("[QUESTION_BANK_ERROR] path={} | {}", request.getRequestURI(), ex.getMessage(), ex);
        return ResponseEntity.status(HttpStatus.UNPROCESSABLE_ENTITY)
                .body(ErrorResponse.builder()
                        .status(HttpStatus.UNPROCESSABLE_ENTITY.value())
                        .errorCode("QUESTION_BANK_ERROR")
                        .message("Failed to generate question bank. Please retry.")
                        .detail(ex.getMessage())
                        .path(request.getRequestURI())
                        .build());
    }

    // -------------------------------------------------------------------------
    // 500 Internal Server Error — unexpected errors
    // -------------------------------------------------------------------------

    /**
     * Catch-all handler for any unexpected, unhandled exceptions.
     * Logs the full stack trace and returns a generic 500 response.
     */
    @ExceptionHandler(Exception.class)
    public ResponseEntity<ErrorResponse> handleGenericException(
            Exception ex, HttpServletRequest request) {

        log.error("[UNEXPECTED_ERROR] path={} | {}", request.getRequestURI(), ex.getMessage(), ex);
        return ResponseEntity.status(HttpStatus.INTERNAL_SERVER_ERROR)
                .body(ErrorResponse.builder()
                        .status(HttpStatus.INTERNAL_SERVER_ERROR.value())
                        .errorCode("INTERNAL_SERVER_ERROR")
                        .message("An unexpected error occurred. Please contact support.")
                        .path(request.getRequestURI())
                        .build());
    }
}
