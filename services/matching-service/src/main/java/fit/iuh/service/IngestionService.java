package fit.iuh.service;

import fit.iuh.dto.IngestionResponse;
import fit.iuh.entity.DocumentChunk;
import fit.iuh.entity.SessionDocument;
import fit.iuh.entity.enums.DocumentType;
import fit.iuh.exception.IngestionException;
import fit.iuh.repository.DocumentChunkRepository;
import fit.iuh.repository.SessionDocumentRepository;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.multipart.MultipartFile;

import java.util.List;

/**
 * Orchestrator service for the full Data Ingestion & Vectorization pipeline.
 *
 * <p><strong>Pipeline Steps:</strong>
 * <pre>
 *  ┌──────────┐    ┌──────────────┐    ┌───────────────────────┐    ┌──────────────┐    ┌───────────────┐
 *  │ PDF File │───▶│  PdfService  │───▶│ StandardizationService│───▶│ChunkingService│───▶│EmbeddingService│
 *  │ (CV/JD)  │    │ (extract txt)│    │ (Groq LLM → Markdown) │    │(LangChain4j) │    │(OpenAI + save) │
 *  └──────────┘    └──────────────┘    └───────────────────────┘    └──────────────┘    └───────────────┘
 * </pre>
 *
 * <p><strong>Re-ingestion behavior:</strong> If chunks already exist for a given
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
    private final ChunkingService chunkingService;
    private final EmbeddingService embeddingService;
    private final DocumentChunkRepository documentChunkRepository;
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

        log.info("=== [INGESTION START] sessionId={} ===", sessionId);

        // ── Re-ingestion: clean up existing chunks and documents for this session ──────────
        if (documentChunkRepository.existsBySessionId(sessionId)) {
            log.warn("Existing chunks found for session={}. Deleting before re-ingestion.", sessionId);
            documentChunkRepository.deleteAllBySessionId(sessionId);
        }
        if (sessionDocumentRepository.existsBySessionId(sessionId)) {
            log.warn("Existing full documents found for session={}. Deleting before re-ingestion.", sessionId);
            sessionDocumentRepository.deleteAllBySessionId(sessionId);
        }

        // ────────────────────────────────────────────────────────────────────
        // STEP 1 — Extract raw text from PDFs
        // ────────────────────────────────────────────────────────────────────
        log.info("[Step 1/4] Extracting raw text from uploaded files...");
        String rawCvText = pdfService.extractText(cvFile);

        String rawJdText;
        if (jdFile != null && !jdFile.isEmpty()) {
            rawJdText = pdfService.extractText(jdFile);
        } else {
            // Fall back to plain text JD input
            rawJdText = jdText;
        }

        log.info("[Step 1/4] Done. CV: {} chars | JD: {} chars",
                rawCvText.length(), rawJdText.length());

        // ────────────────────────────────────────────────────────────────────
        // STEP 2 — Standardize to Markdown via Groq LLM
        // ────────────────────────────────────────────────────────────────────
        log.info("[Step 2/4] Standardizing documents via Groq LLM (this may take ~10-30s)...");
        String markdownCv = standardizationService.standardizeCv(rawCvText);
        String markdownJd = standardizationService.standardizeJd(rawJdText);
        log.info("[Step 2/4] Done. CV Markdown: {} chars | JD Markdown: {} chars",
                markdownCv.length(), markdownJd.length());

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

        // ────────────────────────────────────────────────────────────────────
        // STEP 3 — Split Markdown into token-bounded chunks
        // ────────────────────────────────────────────────────────────────────
        log.info("[Step 3/4] Chunking Markdown into token-bounded segments...");
        List<String> cvChunks = chunkingService.chunkText(markdownCv);
        List<String> jdChunks = chunkingService.chunkText(markdownJd);
        log.info("[Step 3/4] Done. CV chunks: {} | JD chunks: {}", cvChunks.size(), jdChunks.size());

        // ────────────────────────────────────────────────────────────────────
        // STEP 4 — Generate embeddings and save to PostgreSQL
        // ────────────────────────────────────────────────────────────────────
        log.info("[Step 4/4] Generating embeddings and saving to database...");
        List<DocumentChunk> savedCvChunks = embeddingService.embedAndSave(
                cvChunks, sessionId, DocumentType.CV);
        List<DocumentChunk> savedJdChunks = embeddingService.embedAndSave(
                jdChunks, sessionId, DocumentType.JD);

        int totalSaved = savedCvChunks.size() + savedJdChunks.size();
        log.info("[Step 4/4] Done. Total saved: {} chunks (CV={}, JD={})",
                totalSaved, savedCvChunks.size(), savedJdChunks.size());

        log.info("=== [INGESTION COMPLETE] sessionId={} | total={} chunks ===",
                sessionId, totalSaved);

        // ── Build and return response ─────────────────────────────────────
        return IngestionResponse.builder()
                .sessionId(sessionId)
                .cvChunksCount(savedCvChunks.size())
                .jdChunksCount(savedJdChunks.size())
                .totalChunksCount(totalSaved)
                .status("SUCCESS")
                .message(String.format(
                        "Successfully ingested and vectorized %d chunks (%d CV + %d JD) for session '%s'.",
                        totalSaved, savedCvChunks.size(), savedJdChunks.size(), sessionId))
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
