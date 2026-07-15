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
             String jdText,
             String resumeMarkdown,
             String jdMarkdown) {

        // ── Validate inputs ──────────────────────────────────────────────────
        validateInputs(sessionId, cvFile, jdFile, jdText, resumeMarkdown, jdMarkdown);

        long totalStartTime = System.currentTimeMillis();
        log.info("=== [INGESTION START] sessionId={} ===", sessionId);

        // ── Re-ingestion: clean up existing documents for this session ──────────
        if (sessionDocumentRepository.existsBySessionId(sessionId)) {
            log.warn("Existing full documents found for session={}. Deleting before re-ingestion.", sessionId);
            sessionDocumentRepository.deleteAllBySessionId(sessionId);
        }

        // ────────────────────────────────────────────────────────────────────
        // STEP 1 — Extract raw text from PDFs (only if not using cached markdown)
        // ────────────────────────────────────────────────────────────────────
        log.info("[Step 1/4] Extracting raw text from uploaded files where cache is miss...");
        long step1Start = System.currentTimeMillis();
        
        String rawCvText = null;
        String markdownCv = null;
        if (resumeMarkdown != null && !resumeMarkdown.isBlank()) {
            log.info("CV Cache Hit: Bypassing PDF text extraction.");
            markdownCv = resumeMarkdown;
        } else {
            rawCvText = pdfService.extractText(cvFile);
        }

        String rawJdText = null;
        String markdownJd = null;
        if (jdMarkdown != null && !jdMarkdown.isBlank()) {
            log.info("JD Cache Hit: Bypassing PDF text extraction.");
            markdownJd = jdMarkdown;
        } else if (jdFile != null && !jdFile.isEmpty()) {
            rawJdText = pdfService.extractText(jdFile);
        } else {
            rawJdText = jdText;
        }
        long step1Time = System.currentTimeMillis() - step1Start;
        log.info("[Step 1/4] Done in {}ms.", step1Time);

        // ────────────────────────────────────────────────────────────────────
        // STEP 2 — Standardize to Markdown via Groq LLM (conditional)
        // ────────────────────────────────────────────────────────────────────
        boolean needCvStandardize = (markdownCv == null);
        boolean needJdStandardize = (markdownJd == null);

        if (needCvStandardize || needJdStandardize) {
            log.info("[Step 2/4] Standardizing documents via Groq LLM (Running parallel on Virtual Threads)...");
            long step2Start = System.currentTimeMillis();
            
            final String finalRawCvText = rawCvText;
            final String finalRawJdText = rawJdText;

            try (var executor = java.util.concurrent.Executors.newVirtualThreadPerTaskExecutor()) {
                java.util.concurrent.CompletableFuture<String> futureCv = needCvStandardize
                        ? java.util.concurrent.CompletableFuture.supplyAsync(() -> {
                            try {
                                return standardizationService.standardizeCv(finalRawCvText);
                            } catch (Exception e) {
                                log.error("Error standardizing CV via Groq LLM: ", e);
                                throw new IngestionException("Failed to standardize CV: " + e.getMessage(), e);
                            }
                        }, executor)
                        : java.util.concurrent.CompletableFuture.completedFuture(markdownCv);

                java.util.concurrent.CompletableFuture<String> futureJd = needJdStandardize
                        ? java.util.concurrent.CompletableFuture.supplyAsync(() -> {
                            try {
                                return standardizationService.standardizeJd(finalRawJdText);
                            } catch (Exception e) {
                                log.error("Error standardizing JD via Groq LLM: ", e);
                                throw new IngestionException("Failed to standardize JD: " + e.getMessage(), e);
                            }
                        }, executor)
                        : java.util.concurrent.CompletableFuture.completedFuture(markdownJd);

                try {
                    markdownCv = futureCv.join();
                    markdownJd = futureJd.join();
                } catch (Exception e) {
                    log.error("Ingestion pipeline failed in parallel standardization task", e);
                    throw new IngestionException("Standardization failed: " + e.getMessage(), e);
                }
            }
            long step2Time = System.currentTimeMillis() - step2Start;
            log.info("[Step 2/4] Done in {}ms. CV Markdown: {} chars | JD Markdown: {} chars",
                    step2Time, markdownCv.length(), markdownJd.length());
        } else {
            log.info("[Step 2/4] Bypassed Groq LLM standardization completely (Eager Cache Hit for both CV and JD).");
        }

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
                .cvMarkdown(markdownCv)
                .jdMarkdown(markdownJd)
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
                                 MultipartFile jdFile, String jdText,
                                 String resumeMarkdown, String jdMarkdown) {
        if (sessionId == null || sessionId.isBlank()) {
            throw new IngestionException("Session ID must not be null or blank.");
        }

        boolean hasCvFile = cvFile != null && !cvFile.isEmpty();
        boolean hasCvMarkdown = resumeMarkdown != null && !resumeMarkdown.isBlank();

        if (!hasCvFile && !hasCvMarkdown) {
            throw new IngestionException("Either 'cvFile' (PDF) or 'resumeMarkdown' must be provided.");
        }

        boolean hasJdFile = jdFile != null && !jdFile.isEmpty();
        boolean hasJdText = jdText != null && !jdText.isBlank();
        boolean hasJdMarkdown = jdMarkdown != null && !jdMarkdown.isBlank();

        if (!hasJdFile && !hasJdText && !hasJdMarkdown) {
            throw new IngestionException(
                    "At least one of 'jdFile' (PDF), 'jdText' (plain text), or 'jdMarkdown' must be provided.");
        }
    }
}
