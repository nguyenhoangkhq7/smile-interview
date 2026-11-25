package fit.iuh.modules.session.controller;

import fit.iuh.common.service.S3StorageService;
import fit.iuh.exception.ResourceNotFoundException;
import fit.iuh.modules.application.ApplicationProfileRepository;
import fit.iuh.modules.auth.entity.Role;
import fit.iuh.modules.auth.entity.User;
import fit.iuh.modules.session.entity.JobDescription;
import fit.iuh.modules.session.repository.JobDescriptionRepository;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
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
@RequestMapping("/api/v1/job-descriptions")
@RequiredArgsConstructor
public class JobDescriptionController {

    private final JobDescriptionRepository jobDescriptionRepository;
    private final ApplicationProfileRepository applicationProfileRepository;
    private final S3StorageService s3StorageService;

    @GetMapping
    public ResponseEntity<List<JobDescription>> getJobDescriptions(@AuthenticationPrincipal User currentUser) {
        User user = requireUser(currentUser);
        if (!isAdmin(user)) {
            return ResponseEntity.ok(jobDescriptionRepository.findByUserIdOrderByCreatedAtDesc(user.getId()));
        }
        return ResponseEntity.ok(jobDescriptionRepository.findAllByOrderByCreatedAtDesc());
    }

    @GetMapping("/{id}")
    public ResponseEntity<JobDescription> getJobDescription(
            @PathVariable UUID id,
            @AuthenticationPrincipal User currentUser) {
        return ResponseEntity.ok(requireOwnedJd(id, currentUser));
    }

    @GetMapping("/{id}/raw")
    public ResponseEntity<Map<String, String>> getJobDescriptionRaw(
            @PathVariable UUID id,
            @AuthenticationPrincipal User currentUser) {
        JobDescription jd = requireOwnedJd(id, currentUser);
        String rawText = jd.getRawText();
        return ResponseEntity.ok(Map.of(
                "title", jd.getTitle(),
                "rawText", rawText != null ? rawText : ""
        ));
    }

    @PostMapping(consumes = MediaType.MULTIPART_FORM_DATA_VALUE)
    public ResponseEntity<JobDescription> uploadJobDescription(
            @AuthenticationPrincipal User currentUser,
            @RequestParam("file") MultipartFile file,
            @RequestParam(value = "parsed_content", required = false) String parsedContent) {

        User user = requireUser(currentUser);
        UUID userId = user.getId();
        String title = file.getOriginalFilename() != null ? file.getOriginalFilename() : "JD.pdf";
        String fileUrl;

        try {
            String s3Key = "jds/" + userId + "/" + System.currentTimeMillis() + "_" + title;
            fileUrl = s3StorageService.uploadFile(s3Key, file.getBytes(), file.getContentType());
        } catch (Exception e) {
            log.warn("[JobDescriptionController] S3 upload skipped or failed: {}", e.getMessage());
            fileUrl = "/uploads/jds/" + title;
        }

        JobDescription jd = JobDescription.builder()
                .id(UUID.randomUUID())
                .userId(userId)
                .title(title)
                .fileUrl(fileUrl)
                .rawText(parsedContent)
                .createdAt(LocalDateTime.now())
                .build();

        JobDescription saved = jobDescriptionRepository.save(jd);
        return ResponseEntity.status(HttpStatus.CREATED).body(saved);
    }

    @PostMapping(consumes = MediaType.APPLICATION_JSON_VALUE)
    public ResponseEntity<JobDescription> createJobDescriptionJson(
            @AuthenticationPrincipal User currentUser,
            @RequestBody Map<String, Object> body) {

        User user = requireUser(currentUser);
        String title = (String) body.getOrDefault("title", body.getOrDefault("file_name", "JD_" + System.currentTimeMillis()));
        String parsedContent = (String) body.getOrDefault("parsed_content", body.get("extracted_text"));
        String rawText = (String) body.get("raw_text");
        if (rawText == null || rawText.isBlank()) rawText = parsedContent;

        JobDescription jd = JobDescription.builder()
                .id(UUID.randomUUID())
                .userId(user.getId())
                .title(title)
                .fileUrl(null)
                .rawText(rawText)
                .createdAt(LocalDateTime.now())
                .build();

        JobDescription saved = jobDescriptionRepository.save(jd);
        return ResponseEntity.status(HttpStatus.CREATED).body(saved);
    }

    @DeleteMapping("/{id}")
    public ResponseEntity<Map<String, Object>> deleteJobDescription(
            @PathVariable UUID id,
            @AuthenticationPrincipal User currentUser) {
        JobDescription jd = requireOwnedJd(id, currentUser);
        if (applicationProfileRepository.existsByJobDescriptionId(jd.getId())) {
            throw new ResponseStatusException(HttpStatus.CONFLICT,
                    "JD đang được sử dụng bởi hồ sơ ứng tuyển và không thể xóa.");
        }
        jobDescriptionRepository.delete(jd);
        return ResponseEntity.ok(Map.of("success", true, "message", "Job description deleted successfully"));
    }

    private JobDescription requireOwnedJd(UUID id, User currentUser) {
        User user = requireUser(currentUser);
        JobDescription jd = jobDescriptionRepository.findById(id)
                .orElseThrow(() -> new ResourceNotFoundException("Job description not found with id: " + id));
        if (!isAdmin(user) && !Objects.equals(jd.getUserId(), user.getId())) {
            throw new ResponseStatusException(HttpStatus.FORBIDDEN, "This job description belongs to another user");
        }
        return jd;
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
