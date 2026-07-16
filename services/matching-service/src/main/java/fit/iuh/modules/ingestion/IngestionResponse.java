package fit.iuh.modules.ingestion;

import com.fasterxml.jackson.annotation.JsonInclude;
import lombok.Builder;
import lombok.Data;

/**
 * API response returned after a successful (or partially successful) ingestion call.
 *
 * <p>Returned by {@code POST /api/v1/ingest/{sessionId}}.
 */
@Data
@Builder
@JsonInclude(JsonInclude.Include.NON_NULL)
public class IngestionResponse {

    /** The session ID associated with this ingestion (echoed back from the URL path). */
    private String sessionId;

    /** High-level status: {@code "SUCCESS"} or {@code "PARTIAL_SUCCESS"}. */
    private String status;

    /** Human-readable message describing the result. */
    private String message;

    /** The processed or cached CV Markdown text. */
    private String cvMarkdown;

    /** The processed or cached JD Markdown text. */
    private String jdMarkdown;

    /**
     * Pre-LLM raw text extracted directly from the CV PDF by PdfService.
     * Populated only on cache-miss paths where PDF parsing was actually performed.
     * Null on cache-hits — BFF reads raw_text from the resumes DB table instead.
     */
    private String rawCvText;

    /**
     * Pre-LLM raw text extracted directly from the JD PDF/text source.
     * Populated only on cache-miss paths where PDF parsing was actually performed.
     * Null on cache-hits — BFF reads raw_text from the job_descriptions DB table instead.
     */
    private String rawJdText;
}
