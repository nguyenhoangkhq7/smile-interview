package fit.iuh.modules.session.controller;

import fit.iuh.common.service.S3StorageService;
import fit.iuh.exception.ResourceNotFoundException;
import fit.iuh.modules.application.ApplicationProfileRepository;
import fit.iuh.modules.auth.entity.Role;
import fit.iuh.modules.auth.entity.User;
import fit.iuh.modules.session.entity.Resume;
import fit.iuh.modules.session.repository.ResumeRepository;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.apache.pdfbox.Loader;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.text.PDFTextStripper;
import org.springframework.http.HttpStatus;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.multipart.MultipartFile;
import org.springframework.web.server.ResponseStatusException;

import java.time.LocalDateTime;
import java.util.List;
import java.util.Map;
import java.util.Objects;
import java.util.UUID;

@Slf4j
@RestController
@RequestMapping("/api/v1/resumes")
@RequiredArgsConstructor
public class ResumeController {

    private final ResumeRepository resumeRepository;
    private final ApplicationProfileRepository applicationProfileRepository;
    private final S3StorageService s3StorageService;

    @GetMapping
    public ResponseEntity<List<Resume>> getResumes(@AuthenticationPrincipal User currentUser) {
        User user = requireUser(currentUser);
        if (!isAdmin(user)) {
            return ResponseEntity.ok(resumeRepository.findByUserIdOrderByCreatedAtDesc(user.getId()));
        }
        return ResponseEntity.ok(resumeRepository.findAllByOrderByCreatedAtDesc());
    }

    @GetMapping("/{id}")
    public ResponseEntity<Resume> getResume(
            @PathVariable UUID id,
            @AuthenticationPrincipal User currentUser) {
        return ResponseEntity.ok(requireOwnedResume(id, currentUser));
    }

    @GetMapping("/{id}/raw")
    public ResponseEntity<Map<String, String>> getResumeRaw(
            @PathVariable UUID id,
            @AuthenticationPrincipal User currentUser) {
        Resume resume = requireOwnedResume(id, currentUser);
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

        User user = requireUser(currentUser);
        UUID userId = user.getId();
        String fileName = file.getOriginalFilename() != null ? file.getOriginalFilename() : "cv.pdf";
        String fileUrl;

        if ((parsedContent == null || parsedContent.isBlank()) && fileName.toLowerCase().endsWith(".pdf")) {
            try (PDDocument document = Loader.loadPDF(file.getBytes())) {
                parsedContent = new PDFTextStripper().getText(document).trim();
            } catch (Exception e) {
                log.warn("[ResumeController] Could not extract text from {}: {}", fileName, e.getMessage());
            }
        }

        try {
            String s3Key = "resumes/" + userId + "/" + System.currentTimeMillis() + "_" + fileName;
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

        User user = requireUser(currentUser);
        String fileName = (String) body.getOrDefault("file_name", "CV.pdf");
        String parsedContent = (String) body.getOrDefault("parsed_content", body.get("extracted_text"));
        String rawText = (String) body.get("raw_text");
        if (rawText == null || rawText.isBlank()) rawText = parsedContent;

        Resume resume = Resume.builder()
                .id(UUID.randomUUID())
                .userId(user.getId())
                .fileName(fileName)
                .fileUrl(null)
                .rawText(rawText)
                .createdAt(LocalDateTime.now())
                .build();

        Resume saved = resumeRepository.save(resume);
        return ResponseEntity.status(HttpStatus.CREATED).body(saved);
    }

    @DeleteMapping("/{id}")
    public ResponseEntity<Map<String, Object>> deleteResume(
            @PathVariable UUID id,
            @AuthenticationPrincipal User currentUser) {
        Resume resume = requireOwnedResume(id, currentUser);
        if (applicationProfileRepository.existsByResumeId(resume.getId())) {
            throw new ResponseStatusException(HttpStatus.CONFLICT,
                    "CV đang được sử dụng bởi hồ sơ ứng tuyển và không thể xóa.");
        }
        resumeRepository.delete(resume);
        return ResponseEntity.ok(Map.of("success", true, "message", "Resume deleted successfully"));
    }

    private Resume requireOwnedResume(UUID id, User currentUser) {
        User user = requireUser(currentUser);
        Resume resume = resumeRepository.findById(id)
                .orElseThrow(() -> new ResourceNotFoundException("Resume not found with id: " + id));
        if (!isAdmin(user) && !Objects.equals(resume.getUserId(), user.getId())) {
            throw new ResponseStatusException(HttpStatus.FORBIDDEN, "This resume belongs to another user");
        }
        return resume;
    }

    private User requireUser(User currentUser) {
        if (currentUser == null) {
            throw new ResponseStatusException(HttpStatus.UNAUTHORIZED, "Authentication required");
        }
        return currentUser;
    }

    private boolean isAdmin(User user) {
        return user.getRole() == Role.ADMIN;
    }
}
