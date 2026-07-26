package fit.iuh.modules.ingestion.service.impl;

import fit.iuh.modules.chunking.entity.DocumentChunk;
import fit.iuh.modules.chunking.repository.DocumentChunkRepository;
import fit.iuh.modules.chunking.service.ChunkerService;
import fit.iuh.modules.chunking.service.EmbeddingService;
import fit.iuh.exception.IngestionException;
import fit.iuh.modules.ingestion.dto.IngestionResponse;
import fit.iuh.modules.ingestion.entity.DocumentType;
import fit.iuh.modules.ingestion.entity.SessionDocument;
import fit.iuh.modules.ingestion.repository.SessionDocumentRepository;
import fit.iuh.modules.ingestion.service.IngestionService;
import fit.iuh.modules.ingestion.service.PdfService;
import fit.iuh.modules.ingestion.service.StandardizationService;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.multipart.MultipartFile;

import java.util.ArrayList;
import java.util.List;

@Slf4j
@Service
@RequiredArgsConstructor
public class IngestionServiceImpl implements IngestionService {

    private final PdfService pdfService;
    private final StandardizationService standardizationService;
    private final SessionDocumentRepository sessionDocumentRepository;
    private final ChunkerService chunkerService;
    private final EmbeddingService embeddingService;
    private final DocumentChunkRepository documentChunkRepository;

    @Override
    @Transactional
    public IngestionResponse ingest(
            String sessionId,
            MultipartFile cvFile,
            MultipartFile jdFile,
            String jdText,
            String resumeMarkdown,
            String jdMarkdown) {

        validateInputs(sessionId, cvFile, jdFile, jdText, resumeMarkdown, jdMarkdown);

        long totalStartTime = System.currentTimeMillis();
        log.info("""
                
                ================================================================================
                >>> [PIPELINE START] INGESTION | Session: {}
                ================================================================================
                """, sessionId);

        if (sessionDocumentRepository.existsBySessionId(sessionId)) {
            log.warn("[INGEST] Existing documents found for session={}. Deleting old session documents.", sessionId);
            sessionDocumentRepository.deleteAllBySessionId(sessionId);
        }

        long step1Start = System.currentTimeMillis();

        String rawCvText = null;
        String markdownCv = null;
        if (resumeMarkdown != null && !resumeMarkdown.isBlank()) {
            log.info("[INGEST STEP 1/3] CV Cache Hit: Using pre-extracted Markdown ({} chars).", resumeMarkdown.length());
            markdownCv = resumeMarkdown;
        } else {
            rawCvText = pdfService.extractText(cvFile);
            log.info("[INGEST STEP 1/3] PDF Extraction: Extracted CV raw text ({} chars from file '{}').",
                    rawCvText != null ? rawCvText.length() : 0, cvFile != null ? cvFile.getOriginalFilename() : "N/A");
        }

        String rawJdText = null;
        String markdownJd = null;
        if (jdMarkdown != null && !jdMarkdown.isBlank()) {
            log.info("[INGEST STEP 1/3] JD Cache Hit: Using pre-extracted Markdown ({} chars).", jdMarkdown.length());
            markdownJd = jdMarkdown;
        } else if (jdFile != null && !jdFile.isEmpty()) {
            rawJdText = pdfService.extractText(jdFile);
            log.info("[INGEST STEP 1/3] PDF Extraction: Extracted JD raw text ({} chars from file '{}').",
                    rawJdText != null ? rawJdText.length() : 0, jdFile.getOriginalFilename());
        } else {
            rawJdText = jdText;
            log.info("[INGEST STEP 1/3] Raw Input: Provided JD raw text ({} chars).", rawJdText != null ? rawJdText.length() : 0);
        }
        long step1Time = System.currentTimeMillis() - step1Start;

        long step2Start = System.currentTimeMillis();
        if (markdownCv == null) {
            log.info("[INGEST STEP 2/3] LLM Standardization: Standardizing CV text to Markdown...");
            markdownCv = standardizationService.standardizeCv(rawCvText);
        }
        if (markdownJd == null) {
            log.info("[INGEST STEP 2/3] LLM Standardization: Standardizing JD text to Markdown...");
            markdownJd = standardizationService.standardizeJd(rawJdText);
        }
        long step2Time = System.currentTimeMillis() - step2Start;
        log.info("[INGEST STEP 2/3] Standardization Complete: CV Markdown ({} chars), JD Markdown ({} chars).",
                markdownCv.length(), markdownJd.length());

        SessionDocument cvDoc = SessionDocument.builder()
                .sessionId(sessionId)
                .documentType(DocumentType.CV)
                .markdownContent(markdownCv)
                .build();

        SessionDocument jdDoc = SessionDocument.builder()
                .sessionId(sessionId)
                .documentType(DocumentType.JD)
                .markdownContent(markdownJd)
                .build();

        sessionDocumentRepository.saveAll(List.of(cvDoc, jdDoc));

        // Step 3: Structure-Aware Chunking, Enrichment, and Ollama Batch Embedding
        long step3Start = System.currentTimeMillis();
        if (documentChunkRepository.existsBySessionId(sessionId)) {
            documentChunkRepository.deleteBySessionId(sessionId);
        }

        List<DocumentChunk> cvChunks = chunkerService.chunk(markdownCv, sessionId, "cv");
        List<DocumentChunk> jdChunks = chunkerService.chunk(markdownJd, sessionId, "jd");

        long tChunking = System.currentTimeMillis() - step3Start;
        log.info("[INGEST STEP 3/3] Structure-Aware Chunking: Created {} CV Chunks, {} JD Chunks (in {}ms).",
                cvChunks.size(), jdChunks.size(), tChunking);

        long tEmbedStart = System.currentTimeMillis();
        embeddingService.embedBatch(cvChunks);
        embeddingService.embedBatch(jdChunks);
        long tEmbedding = System.currentTimeMillis() - tEmbedStart;

        List<DocumentChunk> allChunks = new ArrayList<>();
        allChunks.addAll(cvChunks);
        allChunks.addAll(jdChunks);

        documentChunkRepository.saveAll(allChunks);
        long step3Time = System.currentTimeMillis() - step3Start;

        long totalDurationMs = System.currentTimeMillis() - totalStartTime;
        log.info("""
                
                ================================================================================
                <<< [PIPELINE COMPLETE] INGESTION | Session: {} in {}ms
                    • Step 1 (Text Extraction): {}ms
                    • Step 2 (LLM Standardization): {}ms
                    • Step 3 (Chunking & Embedding): {}ms [Chunking: {}ms, Embedding: {}ms]
                    • Total Chunks Persisted to pgvector: {}
                ================================================================================
                """, sessionId, totalDurationMs, step1Time, step2Time, step3Time, tChunking, tEmbedding, allChunks.size());

        return IngestionResponse.builder()
                .sessionId(sessionId)
                .status("SUCCESS")
                .message("Documents successfully ingested for session " + sessionId + ".")
                .cvMarkdown(markdownCv)
                .jdMarkdown(markdownJd)
                .rawCvText(rawCvText)
                .rawJdText(rawJdText)
                .build();
    }

    private void validateInputs(
            String sessionId,
            MultipartFile cvFile,
            MultipartFile jdFile,
            String jdText,
            String resumeMarkdown,
            String jdMarkdown) {

        if (sessionId == null || sessionId.isBlank()) {
            throw new IngestionException("Session ID cannot be null or blank.");
        }

        boolean hasCvFile = (cvFile != null && !cvFile.isEmpty());
        boolean hasCvMarkdown = (resumeMarkdown != null && !resumeMarkdown.isBlank());
        if (!hasCvFile && !hasCvMarkdown) {
            throw new IngestionException("CV file (PDF) or pre-rendered CV markdown is required.");
        }

        boolean hasJdFile = (jdFile != null && !jdFile.isEmpty());
        boolean hasJdText = (jdText != null && !jdText.isBlank());
        boolean hasJdMarkdown = (jdMarkdown != null && !jdMarkdown.isBlank());

        if (!hasJdFile && !hasJdText && !hasJdMarkdown) {
            throw new IngestionException(
                    "Job Description is required. Please provide a JD PDF file, text string, or markdown.");
        }
    }

    @Override
    @Transactional
    public void deleteSession(String sessionId) {
        log.info("[Ingestion] Deleting documents and chunks for session: {}", sessionId);
        documentChunkRepository.deleteBySessionId(sessionId);
        sessionDocumentRepository.deleteAllBySessionId(sessionId);
    }
}
