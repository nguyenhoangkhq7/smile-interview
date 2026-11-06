package fit.iuh.modules.session.controller;

import fit.iuh.common.service.S3StorageService;
import fit.iuh.exception.ResourceNotFoundException;
import fit.iuh.modules.auth.entity.User;
import fit.iuh.modules.session.entity.Resume;
import fit.iuh.modules.session.repository.ResumeRepository;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.http.HttpStatus;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.multipart.MultipartFile;
import org.apache.pdfbox.Loader;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.text.PDFTextStripper;

import java.time.LocalDateTime;
import java.util.List;
import java.util.Map;
import java.util.UUID;

@Slf4j
@RestController
@RequestMapping("/api/v1/resumes")
@RequiredArgsConstructor
public class ResumeController {

    private final ResumeRepository resumeRepository;
    private final S3StorageService s3StorageService;

    @GetMapping
    public ResponseEntity<List<Resume>> getResumes(@AuthenticationPrincipal User currentUser) {
        if (currentUser != null && !"ADMIN".equalsIgnoreCase(currentUser.getRole().name())) {
            return ResponseEntity.ok(resumeRepository.findByUserIdOrderByCreatedAtDesc(currentUser.getId()));
        }
        return ResponseEntity.ok(resumeRepository.findAllByOrderByCreatedAtDesc());
    }

    @GetMapping("/{id}")
    public ResponseEntity<Resume> getResume(@PathVariable UUID id) {
        return ResponseEntity.ok(resumeRepository.findById(id)
                .orElseThrow(() -> new ResourceNotFoundException("Resume not found with id: " + id)));
    }

    @GetMapping("/{id}/raw")
    public ResponseEntity<Map<String, String>> getResumeRaw(@PathVariable UUID id) {
        Resume resume = resumeRepository.findById(id)
                .orElseThrow(() -> new ResourceNotFoundException("Resume not found with id: " + id));
        String rawText = resume.getRawText();
        return ResponseEntity.ok(Map.of(
                "fileName", resume.getFileName(),
                "rawText", rawText != null ? rawText : ""
        ));
    }

    @PostMapping(consumes = MediaType.MULTIPART_FORM_DATA_VALUE)
    public ResponseEntity<Resume> uploadResume(
            @AuthenticationPrincipal User currentUser,
            @RequestParam("file") MultipartFile file,
            @RequestParam(value = "parsed_content", required = false) String parsedContent) {

        UUID userId = (currentUser != null) ? currentUser.getId() : null;
        String fileName = file.getOriginalFilename() != null ? file.getOriginalFilename() : "cv.pdf";
        String fileUrl = null;

        if ((parsedContent == null || parsedContent.isBlank()) && fileName.toLowerCase().endsWith(".pdf")) {
            try (PDDocument document = Loader.loadPDF(file.getBytes())) {
                parsedContent = new PDFTextStripper().getText(document).trim();
            } catch (Exception e) {
                log.warn("[ResumeController] Could not extract text from {}: {}", fileName, e.getMessage());
            }
        }

        try {
            String s3Key = "resumes/" + (userId != null ? userId : "guest") + "/" + System.currentTimeMillis() + "_" + fileName;
            fileUrl = s3StorageService.uploadFile(s3Key, file.getBytes(), file.getContentType());
        } catch (Exception e) {
            log.warn("[ResumeController] S3 upload skipped or failed: {}", e.getMessage());
            fileUrl = "/uploads/resumes/" + fileName;
        }

        Resume resume = Resume.builder()
                .id(UUID.randomUUID())
                .userId(userId)
                .fileName(fileName)
                .fileUrl(fileUrl)
                .rawText(parsedContent)
                .createdAt(LocalDateTime.now())
                .build();

        Resume saved = resumeRepository.save(resume);
        return ResponseEntity.status(HttpStatus.CREATED).body(saved);
    }

    @PostMapping(consumes = MediaType.APPLICATION_JSON_VALUE)
    public ResponseEntity<Resume> createResumeJson(
            @AuthenticationPrincipal User currentUser,
            @RequestBody Map<String, Object> body) {

        UUID userId = (currentUser != null) ? currentUser.getId() : null;
        String fileName = (String) body.getOrDefault("file_name", "CV.pdf");
        String parsedContent = (String) body.getOrDefault("parsed_content", body.get("extracted_text"));
        String rawText = (String) body.get("raw_text");
        if (rawText == null || rawText.isBlank()) rawText = parsedContent;
        String fileUrl = (String) body.get("file_url");

        Resume resume = Resume.builder()
                .id(UUID.randomUUID())
                .userId(userId)
                .fileName(fileName)
                .fileUrl(fileUrl)
                .rawText(rawText)
                .createdAt(LocalDateTime.now())
                .build();

        Resume saved = resumeRepository.save(resume);
        return ResponseEntity.status(HttpStatus.CREATED).body(saved);
    }

    @DeleteMapping("/{id}")
    public ResponseEntity<Map<String, Object>> deleteResume(@PathVariable UUID id) {
        if (!resumeRepository.existsById(id)) {
            throw new ResourceNotFoundException("Resume not found with id: " + id);
        }
        resumeRepository.deleteById(id);
        return ResponseEntity.ok(Map.of("success", true, "message", "Resume deleted successfully"));
    }
}
