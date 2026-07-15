package fit.iuh.modules.ingestion;

import fit.iuh.modules.ingestion.IngestionResponse;
import fit.iuh.modules.ingestion.IngestionService;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.multipart.MultipartFile;

/**
 * REST Controller exposing the Data Ingestion & Vectorization API.
 *
 * <p>Base path: {@code /api/v1/ingest}
 *
 * <p>This controller accepts multipart form-data requests containing CV and JD
 * documents and delegates the full ingestion pipeline to {@link IngestionService}.
 *
 * <h2>Endpoint Summary</h2>
 * <pre>
 *   POST /api/v1/ingest/{sessionId}  — Ingest CV and JD for a given session
 * </pre>
 *
 * <h2>Example cURL</h2>
 * <pre>
 *   # With CV (PDF) + JD (PDF):
 *   curl -X POST http://localhost:8081/api/v1/ingest/session-001 \
 *     -F "cvFile=@/path/to/cv.pdf" \
 *     -F "jdFile=@/path/to/jd.pdf"
 *
 *   # With CV (PDF) + JD (plain text):
 *   curl -X POST http://localhost:8081/api/v1/ingest/session-001 \
 *     -F "cvFile=@/path/to/cv.pdf" \
 *     -F "jdText=We are looking for a Java Backend Engineer..."
 * </pre>
 *
 * <p>Errors are handled globally by {@link fit.iuh.exception.GlobalExceptionHandler}.
 */
@Slf4j
@RestController
@RequestMapping("/api/v1/ingest")
@RequiredArgsConstructor
public class IngestionController {

    private final IngestionService ingestionService;

    /**
     * Triggers the full ingestion pipeline for a given interview session.
     *
     * <p>The pipeline extracts text from PDFs, standardizes them to Markdown via
     * Groq LLM, splits into token-bounded chunks, generates embeddings via OpenAI,
     * and saves all chunks to PostgreSQL with {@code vector(1536)} columns.
     *
     * @param sessionId the unique interview session identifier (URL path variable)
     * @param cvFile    the candidate's CV as a PDF file (required)
     * @param jdFile    the Job Description as a PDF file (optional — use one of jdFile or jdText)
     * @param jdText    the Job Description as a plain text string (optional — used if jdFile absent)
     * @return HTTP 200 with an {@link IngestionResponse} on success
     */
    @PostMapping(
            value = "/{sessionId}",
            consumes = MediaType.MULTIPART_FORM_DATA_VALUE,
            produces = MediaType.APPLICATION_JSON_VALUE
    )
    public ResponseEntity<IngestionResponse> ingest(
            @PathVariable String sessionId,
            @RequestPart(value = "cvFile", required = false) MultipartFile cvFile,
            @RequestPart(value = "jdFile", required = false) MultipartFile jdFile,
            @RequestPart(value = "jdText", required = false) String jdText,
            @RequestPart(value = "resumeMarkdown", required = false) String resumeMarkdown,
            @RequestPart(value = "jdMarkdown", required = false) String jdMarkdown) {

        log.info("Received ingestion request: sessionId={}, cvFile={}, jdFile={}, jdText={}, hasResumeMarkdown={}, hasJdMarkdown={}",
                sessionId,
                cvFile != null ? cvFile.getOriginalFilename() : "null",
                jdFile != null ? jdFile.getOriginalFilename() : "null",
                jdText != null ? "[" + jdText.length() + " chars]" : "null",
                resumeMarkdown != null && !resumeMarkdown.isBlank(),
                jdMarkdown != null && !jdMarkdown.isBlank());

        IngestionResponse response = ingestionService.ingest(
                sessionId, cvFile, jdFile, jdText, resumeMarkdown, jdMarkdown);

        log.info("Ingestion completed successfully: sessionId={}",
                sessionId);

        return ResponseEntity.ok(response);
    }
}
