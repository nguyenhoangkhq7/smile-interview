package fit.iuh.modules.session.controller;

import fit.iuh.common.service.S3StorageService;
import fit.iuh.modules.auth.entity.User;
import fit.iuh.modules.session.entity.JobDescription;
import fit.iuh.modules.session.entity.Resume;
import fit.iuh.modules.session.entity.Session;
import fit.iuh.modules.session.repository.JobDescriptionRepository;
import fit.iuh.modules.session.repository.ResumeRepository;
import fit.iuh.modules.session.repository.SessionRepository;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.apache.pdfbox.Loader;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.text.PDFTextStripper;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.multipart.MultipartFile;

import java.time.LocalDateTime;
import java.util.Map;
import java.util.UUID;

/**
 * Lightweight document upload controller.
 * Ingests CV and JD documents (PDF or plain text), extracts text in-memory via PDFBox (~20ms),
 * and persists to PostgreSQL for the NCKH AI Service pipeline.
 */
@Slf4j
@RestController
@RequestMapping("/api/v1/sessions/{sessionId}/documents")
@RequiredArgsConstructor
public class DocumentUploadController {

    private final SessionRepository sessionRepository;
    private final ResumeRepository resumeRepository;
    private final JobDescriptionRepository jobDescriptionRepository;
    private final S3StorageService s3StorageService;

    @PostMapping(consumes = MediaType.MULTIPART_FORM_DATA_VALUE, produces = MediaType.APPLICATION_JSON_VALUE)
    @Transactional
    public ResponseEntity<Map<String, Object>> uploadDocuments(
            @PathVariable String sessionId,
            @RequestPart(value = "cvFile", required = false) MultipartFile cvFile,
            @RequestPart(value = "jdFile", required = false) MultipartFile jdFile,
            @RequestPart(value = "cvText", required = false) String cvText,
            @RequestPart(value = "jdText", required = false) String jdText,
            @RequestParam(value = "resumeId", required = false) UUID resumeId,
            @RequestParam(value = "jdId", required = false) UUID jdId,
            @RequestParam(value = "roleTitle", required = false) String roleTitle,
            @RequestParam(value = "interviewType", required = false) String interviewType,
            @AuthenticationPrincipal User currentUser) {

        log.info("[DocumentUpload] Uploading documents for sessionId={}", sessionId);
        UUID userId = currentUser != null ? currentUser.getId() : null;

        Session session = sessionRepository.findById(sessionId)
                .orElseGet(() -> {
                    Session newSession = Session.builder()
                            .id(sessionId)
                            .userId(userId)
                            .status("In progress")
                            .roleTitle(roleTitle != null ? roleTitle : "Software Engineer")
                            .interviewType(interviewType != null ? interviewType : "Technical")
                            .startedAt(LocalDateTime.now())
                            .build();
                    return sessionRepository.save(newSession);
                });

        if (session.getApplicationProfile() != null) {
            throw new org.springframework.web.server.ResponseStatusException(org.springframework.http.HttpStatus.CONFLICT,
                    "Application profile documents are fixed; prepare a new profile to change CV/JD");
        }
        if (roleTitle != null && !roleTitle.isBlank()) {
            session.setRoleTitle(roleTitle);
        }
        if (interviewType != null && !interviewType.isBlank()) {
            session.setInterviewType(interviewType);
        }
        if (userId != null && session.getUserId() == null) {
            session.setUserId(userId);
        }

        if (resumeId != null && session.getResume() == null) {
            resumeRepository.findById(resumeId).ifPresent(session::setResume);
        }
        if (jdId != null && session.getJobDescription() == null) {
            jobDescriptionRepository.findById(jdId).ifPresent(session::setJobDescription);
        }

        // Process CV
        String resolvedCvText = cvText != null ? cvText : "";
        String cvFileName = session.getResume() != null ? session.getResume().getFileName() : "cv_text.txt";
        String cvFileUrl = null;
        if (cvFile != null && !cvFile.isEmpty()) {
            cvFileName = cvFile.getOriginalFilename() != null ? cvFile.getOriginalFilename() : "uploaded_cv.pdf";
            String extracted = extractTextFromFile(cvFile);
            if (!extracted.isBlank()) {
                resolvedCvText = extracted;
            }
            try {
                String s3Key = "resumes/" + (userId != null ? userId : "guest") + "/" + System.currentTimeMillis() + "_" + cvFileName;
                cvFileUrl = s3StorageService.uploadFile(s3Key, cvFile.getBytes(), cvFile.getContentType());
            } catch (Exception e) {
                log.warn("[DocumentUpload] S3 upload for CV skipped or failed: {}", e.getMessage());
                cvFileUrl = "/uploads/resumes/" + cvFileName;
            }
        }

        Resume resume = session.getResume();
        boolean hasNewCv = (cvFile != null && !cvFile.isEmpty()) || (cvText != null && !cvText.isBlank());
        boolean hasNewJd = (jdFile != null && !jdFile.isEmpty()) || (jdText != null && !jdText.isBlank());
        if (!hasNewCv && (resume == null || (resume.getRawText() == null || resume.getRawText().isBlank()))) {
            throw new IllegalArgumentException("CV chưa có nội dung trích xuất. Vui lòng tải lại CV.");
        }
        JobDescription existingJd = session.getJobDescription();
        if (!hasNewJd && (existingJd == null || (existingJd.getRawText() == null || existingJd.getRawText().isBlank()))) {
            throw new IllegalArgumentException("JD chưa có nội dung trích xuất. Vui lòng tải lại JD.");
        }
        if (hasNewCv && resolvedCvText.isBlank()) throw new IllegalArgumentException("Không thể trích xuất nội dung CV.");
        if (resume == null) {
            resume = Resume.builder()
                    .id(UUID.randomUUID())
                    .userId(userId)
                    .fileName(cvFileName)
                    .fileUrl(cvFileUrl)
                    .rawText(resolvedCvText)
                    .createdAt(LocalDateTime.now())
                    .build();
        } else if (hasNewCv) {
            resume.setFileName(cvFileName);
            if (cvFileUrl != null) {
                resume.setFileUrl(cvFileUrl);
            }
            resume.setRawText(resolvedCvText);
        } else {
            resolvedCvText = resume.getRawText() != null ? resume.getRawText() : "";
            cvFileName = resume.getFileName();
        }
        resume = resumeRepository.save(resume);
        session.setResume(resume);

        // Process JD
        String resolvedJdText = jdText != null ? jdText : "";
        String jdFileName = session.getJobDescription() != null ? session.getJobDescription().getTitle() : "jd_text.txt";
        String jdFileUrl = null;
        if (jdFile != null && !jdFile.isEmpty()) {
            jdFileName = jdFile.getOriginalFilename() != null ? jdFile.getOriginalFilename() : "uploaded_jd.pdf";
            String extracted = extractTextFromFile(jdFile);
            if (!extracted.isBlank()) {
                resolvedJdText = extracted;
            }
            try {
                String s3Key = "jds/" + (userId != null ? userId : "guest") + "/" + System.currentTimeMillis() + "_" + jdFileName;
                jdFileUrl = s3StorageService.uploadFile(s3Key, jdFile.getBytes(), jdFile.getContentType());
            } catch (Exception e) {
                log.warn("[DocumentUpload] S3 upload for JD skipped or failed: {}", e.getMessage());
                jdFileUrl = "/uploads/jds/" + jdFileName;
            }
        }

        if (hasNewJd && resolvedJdText.isBlank()) throw new IllegalArgumentException("Không thể trích xuất nội dung JD.");
        JobDescription jd = session.getJobDescription();
        if (jd == null) {
            jd = JobDescription.builder()
                    .id(UUID.randomUUID())
                    .userId(userId)
                    .title(roleTitle != null && !roleTitle.isBlank() ? roleTitle : jdFileName)
                    .fileUrl(jdFileUrl)
                    .rawText(resolvedJdText)
                    .createdAt(LocalDateTime.now())
                    .build();
        } else if (hasNewJd) {
            if (roleTitle != null && !roleTitle.isBlank()) {
                jd.setTitle(roleTitle);
            }
            if (jdFileUrl != null) {
                jd.setFileUrl(jdFileUrl);
            }
            jd.setRawText(resolvedJdText);
        } else {
            resolvedJdText = jd.getRawText() != null ? jd.getRawText() : "";
            jdFileName = jd.getTitle();
        }
        jd = jobDescriptionRepository.save(jd);
        session.setJobDescription(jd);

        sessionRepository.save(session);

        log.info("[DocumentUpload] Success for sessionId={}: CV len={}, JD len={}",
                sessionId, resolvedCvText.length(), resolvedJdText.length());

        return ResponseEntity.ok(Map.of(
                "sessionId", sessionId,
                "success", true,
                "cvFilename", cvFileName,
                "jdFilename", jdFileName,
                "cvTextLength", resolvedCvText.length(),
                "jdTextLength", resolvedJdText.length()
        ));
    }

    private String extractTextFromFile(MultipartFile file) {
        if (file == null || file.isEmpty()) return "";
        String name = file.getOriginalFilename() != null ? file.getOriginalFilename().toLowerCase() : "";
        try {
            byte[] bytes = file.getBytes();
            if (name.endsWith(".pdf") || (file.getContentType() != null && file.getContentType().contains("pdf"))) {
                try (PDDocument doc = Loader.loadPDF(bytes)) {
                    PDFTextStripper stripper = new PDFTextStripper();
                    return stripper.getText(doc).trim();
                }
            }
            return new String(bytes, java.nio.charset.StandardCharsets.UTF_8).trim();
        } catch (Exception e) {
            log.warn("[DocumentUpload] Failed to parse file {}: {}", name, e.getMessage());
            return "";
        }
    }
}
