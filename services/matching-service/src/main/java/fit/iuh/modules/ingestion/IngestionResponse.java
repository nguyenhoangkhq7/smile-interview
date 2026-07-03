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

    /** Number of CV chunks saved to the database after splitting. */
    private int cvChunksCount;

    /** Number of JD chunks saved to the database after splitting. */
    private int jdChunksCount;

    /** Total number of chunks saved (cvChunksCount + jdChunksCount). */
    private int totalChunksCount;

    /** High-level status: {@code "SUCCESS"} or {@code "PARTIAL_SUCCESS"}. */
    private String status;

    /** Human-readable message describing the result. */
    private String message;
}
