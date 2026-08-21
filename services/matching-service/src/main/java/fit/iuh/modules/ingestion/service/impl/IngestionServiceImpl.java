package fit.iuh.modules.ingestion.service.impl;

import fit.iuh.modules.auth.entity.User;
import fit.iuh.modules.chunking.entity.DocumentChunk;
import fit.iuh.modules.chunking.repository.DocumentChunkRepository;
import fit.iuh.modules.chunking.service.ChunkerService;
import fit.iuh.modules.chunking.service.EmbeddingService;
import fit.iuh.exception.IngestionException;
import fit.iuh.modules.ingestion.dto.IngestionResponse;
import fit.iuh.modules.session.entity.Session;
import fit.iuh.modules.session.entity.Resume;
import fit.iuh.modules.session.entity.JobDescription;
import fit.iuh.modules.session.repository.SessionRepository;
import fit.iuh.modules.session.repository.ResumeRepository;
import fit.iuh.modules.session.repository.JobDescriptionRepository;
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
import java.util.UUID;

@Slf4j
@Service
@RequiredArgsConstructor
public class IngestionServiceImpl implements IngestionService {

    private final PdfService pdfService;
    private final StandardizationService standardizationService;
    private final SessionRepository sessionRepository;
    private final ResumeRepository resumeRepository;
    private final JobDescriptionRepository jobDescriptionRepository;
    private final ChunkerService chunkerService;
    private final EmbeddingService embeddingService;
    private final DocumentChunkRepository documentChunkRepository;
    @org.springframework.beans.factory.annotation.Autowired(required = false)
    private fit.iuh.modules.assessment.service.AssessmentCriteriaPreparer criteriaPreparer;
    private final com.fasterxml.jackson.databind.ObjectMapper objectMapper;

    @Override
    @Transactional
    public IngestionResponse ingest(
            String sessionId,
            MultipartFile cvFile,
            MultipartFile jdFile,
            String jdText,
            String resumeMarkdown,
            String jdMarkdown,
            String jdCategory,
            String jdAcceptedLevels,
            String cvCategory,
            String cvSeniorityLevel,
            String roleTitle,
            String interviewType,
            User currentUser) {

        validateInputs(sessionId, cvFile, jdFile, jdText, resumeMarkdown, jdMarkdown);

        long totalStartTime = System.currentTimeMillis();
        UUID userId = (currentUser != null) ? currentUser.getId() : null;

        log.info("""
                
                ================================================================================
                >>> [PIPELINE START] INGESTION | Session: {} | User: {}
                ================================================================================
                """, sessionId, currentUser != null ? currentUser.getUsername() : "anonymous");

        Session session = sessionRepository.findById(sessionId)
                .orElseGet(() -> {
                    log.info("[INGESTION] Session '{}' not found in database. Auto-creating a new session with userId: {}", sessionId, userId);
                    Session newSession = Session.builder()
                            .id(sessionId)
                            .userId(userId)
                            .status("In progress")
                            .roleTitle(roleTitle)
                            .interviewType(interviewType != null ? interviewType : "Technical")
                            .startedAt(java.time.LocalDateTime.now())
                            .build();
                    return sessionRepository.save(newSession);
                });

        if (userId != null && session.getUserId() == null) {
            session.setUserId(userId);
        }
        if (roleTitle != null && !roleTitle.isBlank()) {
            session.setRoleTitle(roleTitle);
        }
        if (interviewType != null && !interviewType.isBlank()) {
            session.setInterviewType(interviewType);
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
            if (rawCvText == null || rawCvText.trim().isEmpty()) {
                throw new IngestionException("Extracted CV text is empty. The PDF might be corrupted or image-only.");
            }
            log.info("[INGEST STEP 2/3] LLM Standardization: Standardizing CV text to Markdown...");
            markdownCv = standardizationService.standardizeCv(rawCvText);
        }
        if (markdownJd == null) {
            if (rawJdText == null || rawJdText.trim().isEmpty()) {
                throw new IngestionException("Extracted JD text is empty. The provided file or text might be corrupted, image-only, or invalid.");
            }
            log.info("[INGEST STEP 2/3] LLM Standardization: Standardizing JD text to Markdown...");
            markdownJd = standardizationService.standardizeJd(rawJdText);
        }
        long step2Time = System.currentTimeMillis() - step2Start;
        log.info("[INGEST STEP 2/3] Standardization Complete: CV Markdown ({} chars), JD Markdown ({} chars).",
                markdownCv.length(), markdownJd.length());

        Resume resume = session.getResume();
        if (resume == null) {
            resume = Resume.builder()
                    .id(UUID.randomUUID())
                    .userId(userId)
                    .fileName(cvFile != null ? cvFile.getOriginalFilename() : "Direct_Input_CV")
                    .createdAt(java.time.LocalDateTime.now())
                    .build();
            log.info("[INGESTION] Auto-created new Resume record with ID: {}, userId: {}", resume.getId(), userId);
        }
        if (userId != null && resume.getUserId() == null) {
            resume.setUserId(userId);
        }
        resume.setParsedContent(markdownCv);
        resume.setRawText(rawCvText);

        if (cvCategory != null && !cvCategory.isBlank()) resume.setJobCategory(cvCategory);
        if (cvSeniorityLevel != null && !cvSeniorityLevel.isBlank()) {
            resume.setSeniorityLevel(cvSeniorityLevel);
        } else if (resume.getSeniorityLevel() == null && criteriaPreparer != null) {
            try {
                fit.iuh.modules.assessment.entity.SeniorityLevel extractedLvl = criteriaPreparer.extractCvSeniorityLevel(markdownCv);
                resume.setSeniorityLevel(extractedLvl.name());
                log.info("[INGESTION] Auto-extracted CV Seniority Level: {}", extractedLvl);
            } catch (Exception e) {
                log.warn("[INGESTION] Warning auto-extracting CV level: {}", e.getMessage());
            }
        }

        resume = resumeRepository.save(resume);
        session.setResume(resume);

        JobDescription jd = session.getJobDescription();
        if (jd == null) {
            jd = JobDescription.builder()
                    .id(UUID.randomUUID())
                    .userId(userId)
                    .title(jdFile != null ? jdFile.getOriginalFilename() : "Direct_Input_JD")
                    .createdAt(java.time.LocalDateTime.now())
                    .build();
            log.info("[INGESTION] Auto-created new JobDescription record with ID: {}, userId: {}", jd.getId(), userId);
        }
        if (userId != null && jd.getUserId() == null) {
            jd.setUserId(userId);
        }
        jd.setParsedContent(markdownJd);
        jd.setRawText(rawJdText);

        if (jdCategory != null && !jdCategory.isBlank()) jd.setJobCategory(jdCategory);
        if (jdAcceptedLevels != null && !jdAcceptedLevels.isBlank()) jd.setAcceptedLevels(jdAcceptedLevels);
        else if ((jd.getAcceptedLevels() == null || jd.getJobCategory() == null) && criteriaPreparer != null) {
            try {
                var rawMeta = criteriaPreparer.extractJdRawMetadata(markdownJd);
                if (jd.getJobCategory() == null && rawMeta.category() != null) {
                    jd.setJobCategory(rawMeta.category().name());
                }
                if (jd.getAcceptedLevels() == null && rawMeta.acceptedLevels() != null) {
                    List<String> lvlStrings = rawMeta.acceptedLevels().stream().map(Enum::name).toList();
                    jd.setAcceptedLevels(objectMapper != null ? objectMapper.writeValueAsString(lvlStrings) : lvlStrings.toString());
                }
                log.info("[INGESTION] Auto-extracted JD Category: {}, Accepted Levels: {}", jd.getJobCategory(), jd.getAcceptedLevels());
            } catch (Exception e) {
                log.warn("[INGESTION] Warning auto-extracting JD metadata: {}", e.getMessage());
            }
        }

        jd = jobDescriptionRepository.save(jd);
        session.setJobDescription(jd);

        sessionRepository.save(session);

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
    }
}
