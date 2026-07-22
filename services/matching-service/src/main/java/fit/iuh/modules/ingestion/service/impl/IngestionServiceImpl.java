package fit.iuh.modules.ingestion.service.impl;

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

import java.util.List;

@Slf4j
@Service
@RequiredArgsConstructor
public class IngestionServiceImpl implements IngestionService {

    private final PdfService pdfService;
    private final StandardizationService standardizationService;
    private final SessionDocumentRepository sessionDocumentRepository;

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
        log.info("=== [INGESTION START] sessionId={} ===", sessionId);

        if (sessionDocumentRepository.existsBySessionId(sessionId)) {
            log.warn("Existing full documents found for session={}. Deleting before re-ingestion.", sessionId);
            sessionDocumentRepository.deleteAllBySessionId(sessionId);
        }

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

        long step2Start = System.currentTimeMillis();
        if (markdownCv == null) {
            markdownCv = standardizationService.standardizeCv(rawCvText);
        }
        if (markdownJd == null) {
            markdownJd = standardizationService.standardizeJd(rawJdText);
        }
        long step2Time = System.currentTimeMillis() - step2Start;

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

        long totalDurationMs = System.currentTimeMillis() - totalStartTime;
        log.info("=== [INGESTION COMPLETE] sessionId={} in {}ms (Step1={}ms, Step2={}ms) ===",
                sessionId, totalDurationMs, step1Time, step2Time);

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
}
