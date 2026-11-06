package fit.iuh.modules.session.controller;

import fit.iuh.common.service.S3StorageService;
import fit.iuh.exception.ResourceNotFoundException;
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

import java.time.LocalDateTime;
import java.util.List;
import java.util.Map;
import java.util.UUID;

@Slf4j
@RestController
@RequestMapping("/api/v1/job-descriptions")
@RequiredArgsConstructor
public class JobDescriptionController {

    private final JobDescriptionRepository jobDescriptionRepository;
    private final S3StorageService s3StorageService;

    @GetMapping
    public ResponseEntity<List<JobDescription>> getJobDescriptions(@AuthenticationPrincipal User currentUser) {
        if (currentUser != null && !"ADMIN".equalsIgnoreCase(currentUser.getRole().name())) {
            return ResponseEntity.ok(jobDescriptionRepository.findByUserIdOrderByCreatedAtDesc(currentUser.getId()));
        }
        return ResponseEntity.ok(jobDescriptionRepository.findAllByOrderByCreatedAtDesc());
    }

    @GetMapping("/{id}")
    public ResponseEntity<JobDescription> getJobDescription(@PathVariable UUID id) {
        return ResponseEntity.ok(jobDescriptionRepository.findById(id)
                .orElseThrow(() -> new ResourceNotFoundException("Job description not found with id: " + id)));
    }

    @GetMapping("/{id}/raw")
    public ResponseEntity<Map<String, String>> getJobDescriptionRaw(@PathVariable UUID id) {
        JobDescription jd = jobDescriptionRepository.findById(id)
                .orElseThrow(() -> new ResourceNotFoundException("Job description not found with id: " + id));
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

        UUID userId = (currentUser != null) ? currentUser.getId() : null;
        String title = file.getOriginalFilename() != null ? file.getOriginalFilename() : "JD.pdf";
        String fileUrl = null;

        try {
            String s3Key = "jds/" + (userId != null ? userId : "guest") + "/" + System.currentTimeMillis() + "_" + title;
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

        UUID userId = (currentUser != null) ? currentUser.getId() : null;
        String title = (String) body.getOrDefault("title", body.getOrDefault("file_name", "JD_" + System.currentTimeMillis()));
        String parsedContent = (String) body.getOrDefault("parsed_content", body.get("extracted_text"));
        String rawText = (String) body.get("raw_text");
        if (rawText == null || rawText.isBlank()) rawText = parsedContent;
        String fileUrl = (String) body.get("file_url");

        JobDescription jd = JobDescription.builder()
                .id(UUID.randomUUID())
                .userId(userId)
                .title(title)
                .fileUrl(fileUrl)
                .rawText(rawText)
                .createdAt(LocalDateTime.now())
                .build();

        JobDescription saved = jobDescriptionRepository.save(jd);
        return ResponseEntity.status(HttpStatus.CREATED).body(saved);
    }

    @DeleteMapping("/{id}")
    public ResponseEntity<Map<String, Object>> deleteJobDescription(@PathVariable UUID id) {
        if (!jobDescriptionRepository.existsById(id)) {
            throw new ResourceNotFoundException("Job description not found with id: " + id);
        }
        jobDescriptionRepository.deleteById(id);
        return ResponseEntity.ok(Map.of("success", true, "message", "Job description deleted successfully"));
    }
}
