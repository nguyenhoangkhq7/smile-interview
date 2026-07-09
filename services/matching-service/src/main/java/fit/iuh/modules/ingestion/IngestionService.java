package fit.iuh.modules.ingestion;

import fit.iuh.modules.ingestion.SessionDocument;
import fit.iuh.modules.ingestion.DocumentType;
import fit.iuh.exception.IngestionException;
import fit.iuh.modules.ingestion.SessionDocumentRepository;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.multipart.MultipartFile;

import java.util.List;

/**
 * Orchestrator service for the full Data Ingestion pipeline.
 *
 * <p><strong>Pipeline Steps:</strong>
 * <pre>
 *  ┌──────────┐    ┌──────────────┐    ┌───────────────────────┐
 *  │ PDF File │───▶│  PdfService  │───▶│ StandardizationService│
 *  │ (CV/JD)  │    │ (extract txt)│    │ (Groq LLM → Markdown) │
 *  └──────────┘    └──────────────┘    └───────────────────────┘
 * </pre>
 *
 * <p><strong>Re-ingestion behavior:</strong> If documents already exist for a given
 * {@code sessionId}, they are deleted before the new pipeline runs. This allows
 * safe re-ingestion with updated files.
 *
 * <p>The {@code jdFile} parameter is optional — if not provided, {@code jdText}
 * (plain string) is used instead. At least one of {@code jdFile} or {@code jdText}
 * must be supplied.
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class IngestionService {

    private final PdfService pdfService;
    private final StandardizationService standardizationService;
    private final SessionDocumentRepository sessionDocumentRepository;

    /**
     * Executes the full ingestion pipeline for a given interview session.
     *
     * @param sessionId the unique identifier for the interview session
     * @param cvFile    the candidate's CV uploaded as a PDF (required)
     * @param jdFile    the Job Description uploaded as a PDF (optional)
     * @param jdText    the Job Description as plain text (used if {@code jdFile} is absent)
     * @return an {@link IngestionResponse} summarizing the result
     * @throws IngestionException if both {@code jdFile} and {@code jdText} are absent,
     *                            or any other validation error occurs
     */
    @Transactional
    public IngestionResponse ingest(
             String sessionId,
             MultipartFile cvFile,
             MultipartFile jdFile,
             String jdText) {

        // ── Validate inputs ──────────────────────────────────────────────────
        validateInputs(sessionId, cvFile, jdFile, jdText);

        long totalStartTime = System.currentTimeMillis();
        log.info("=== [INGESTION START] sessionId={} ===", sessionId);

        // ── Re-ingestion: clean up existing documents for this session ──────────
        if (sessionDocumentRepository.existsBySessionId(sessionId)) {
            log.warn("Existing full documents found for session={}. Deleting before re-ingestion.", sessionId);
            sessionDocumentRepository.deleteAllBySessionId(sessionId);
        }

        // ────────────────────────────────────────────────────────────────────
        // STEP 1 — Extract raw text from PDFs
        // ────────────────────────────────────────────────────────────────────
        log.info("[Step 1/4] Extracting raw text from uploaded files...");
        long step1Start = System.currentTimeMillis();
        String rawCvText = pdfService.extractText(cvFile);

        String rawJdText;
        if (jdFile != null && !jdFile.isEmpty()) {
            rawJdText = pdfService.extractText(jdFile);
        } else {
            // Fall back to plain text JD input
            rawJdText = jdText;
        }
        long step1Time = System.currentTimeMillis() - step1Start;

        log.info("[Step 1/4] Done in {}ms. CV: {} chars | JD: {} chars",
                step1Time, rawCvText.length(), rawJdText.length());

        // ────────────────────────────────────────────────────────────────────
        // STEP 2 — Standardize to Markdown via Groq LLM
        // ────────────────────────────────────────────────────────────────────
        log.info("[Step 2/4] Standardizing documents via Groq LLM (Running parallel on Virtual Threads)...");
        long step2Start = System.currentTimeMillis();
        String markdownCv;
        String markdownJd;

        try (var executor = java.util.concurrent.Executors.newVirtualThreadPerTaskExecutor()) {
            java.util.concurrent.CompletableFuture<String> futureCv = java.util.concurrent.CompletableFuture.supplyAsync(
                    () -> standardizationService.standardizeCv(rawCvText), executor);

            java.util.concurrent.CompletableFuture<String> futureJd = java.util.concurrent.CompletableFuture.supplyAsync(
                    () -> standardizationService.standardizeJd(rawJdText), executor);

            markdownCv = futureCv.join();
            markdownJd = futureJd.join();
        }
        long step2Time = System.currentTimeMillis() - step2Start;
        log.info("[Step 2/4] Done in {}ms. CV Markdown: {} chars | JD Markdown: {} chars",
                step2Time, markdownCv.length(), markdownJd.length());

        // ── Save full Markdown documents ──────────────────────────────────────
        log.info("Saving full standardized Markdown documents to database...");
        sessionDocumentRepository.save(SessionDocument.builder()
                .sessionId(sessionId)
                .documentType(DocumentType.CV)
                .markdownContent(markdownCv)
                .build());
        sessionDocumentRepository.save(SessionDocument.builder()
                .sessionId(sessionId)
                .documentType(DocumentType.JD)
                .markdownContent(markdownJd)
                .build());

        long totalTime = System.currentTimeMillis() - totalStartTime;
        log.info("=== [INGESTION COMPLETE] sessionId={} | time={}ms ===",
                sessionId, totalTime);

        // ── Build and return response ─────────────────────────────────────
        return IngestionResponse.builder()
                .sessionId(sessionId)
                .status("SUCCESS")
                .message(String.format(
                        "Successfully ingested CV and JD for session '%s'.",
                        sessionId))
                .build();
    }

    // -------------------------------------------------------------------------
    // Private helpers
    // -------------------------------------------------------------------------

    /**
     * Validates all required inputs before starting the pipeline.
     *
     * @throws IngestionException if any required input is missing or invalid
     */
    private void validateInputs(String sessionId, MultipartFile cvFile,
                                 MultipartFile jdFile, String jdText) {
        if (sessionId == null || sessionId.isBlank()) {
            throw new IngestionException("Session ID must not be null or blank.");
        }

        if (cvFile == null || cvFile.isEmpty()) {
            throw new IngestionException("CV file is required but was not provided.");
        }

        boolean hasJdFile = jdFile != null && !jdFile.isEmpty();
        boolean hasJdText = jdText != null && !jdText.isBlank();

        if (!hasJdFile && !hasJdText) {
            throw new IngestionException(
                    "At least one of 'jdFile' (PDF) or 'jdText' (plain text) must be provided.");
        }
    }
}
