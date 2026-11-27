package fit.iuh.modules.admin.interviews.controller;

import fit.iuh.modules.admin.interviews.dto.AdminInterviewDtos.Detail;
import fit.iuh.modules.admin.interviews.dto.AdminInterviewDtos.DocumentKind;
import fit.iuh.modules.admin.interviews.dto.AdminInterviewDtos.DocumentView;
import fit.iuh.modules.admin.interviews.dto.AdminInterviewDtos.MatchingDetail;
import fit.iuh.modules.admin.interviews.dto.AdminInterviewDtos.Page;
import fit.iuh.modules.admin.interviews.dto.AdminInterviewDtos.QualityReview;
import fit.iuh.modules.admin.interviews.model.InterviewStatus;
import fit.iuh.modules.admin.interviews.service.AdminAiQualityService;
import fit.iuh.modules.admin.interviews.service.AdminInterviewDocuments;
import fit.iuh.modules.admin.interviews.service.AdminInterviewService;
import jakarta.validation.constraints.Max;
import jakarta.validation.constraints.Min;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Size;
import lombok.RequiredArgsConstructor;
import org.springframework.core.io.Resource;
import org.springframework.http.CacheControl;
import org.springframework.http.ContentDisposition;
import org.springframework.http.HttpHeaders;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.bind.MissingServletRequestParameterException;
import org.springframework.web.method.annotation.HandlerMethodValidationException;
import org.springframework.web.method.annotation.MethodArgumentTypeMismatchException;

import java.nio.charset.StandardCharsets;
import java.util.Map;

@RestController
@RequestMapping("/api/v1/admin/interview-sessions")
@RequiredArgsConstructor
public class AdminInterviewController {
    private final AdminInterviewService interviews;
    private final AdminAiQualityService quality;
    private final AdminInterviewDocuments documents;

    @GetMapping
    public ResponseEntity<Page> list(@RequestParam(defaultValue = "") @Size(max = 200) String search,
                                     @RequestParam(required = false) InterviewStatus status,
                                     @RequestParam(defaultValue = "1") @Min(1) int page,
                                     @RequestParam(defaultValue = "10") @Min(1) @Max(100) int size) {
        return ResponseEntity.ok().cacheControl(CacheControl.noStore()).body(interviews.list(search, status, page, size));
    }

    @GetMapping("/detail")
    public ResponseEntity<Detail> detail(@RequestParam @NotBlank @Size(max = 128) String id) {
        return ResponseEntity.ok().cacheControl(CacheControl.noStore()).body(interviews.detail(id));
    }

    @GetMapping("/quality")
    public ResponseEntity<QualityReview> quality(@RequestParam @NotBlank @Size(max = 128) String id) {
        return ResponseEntity.ok().cacheControl(CacheControl.noStore()).body(quality.review(id));
    }

    @GetMapping("/matching")
    public ResponseEntity<MatchingDetail> matching(@RequestParam @NotBlank @Size(max = 128) String id) {
        return ResponseEntity.ok().cacheControl(CacheControl.noStore()).body(interviews.matching(id));
    }

    @GetMapping("/document")
    public ResponseEntity<DocumentView> document(@RequestParam @NotBlank @Size(max = 128) String id,
                                                  @RequestParam DocumentKind kind,
                                                  @RequestParam(defaultValue = "true") boolean preview) {
        return ResponseEntity.ok().cacheControl(CacheControl.noStore()).body(documents.view(id, kind, preview));
    }

    @GetMapping("/document-file")
    public ResponseEntity<Resource> original(@RequestParam @NotBlank @Size(max = 128) String id,
                                              @RequestParam DocumentKind kind) {
        var file = documents.original(id, kind);
        return ResponseEntity.ok().cacheControl(CacheControl.noStore()).contentType(MediaType.APPLICATION_OCTET_STREAM)
                .header(HttpHeaders.CONTENT_DISPOSITION, ContentDisposition.attachment()
                        .filename(file.name(), StandardCharsets.UTF_8).build().toString())
                .body(file.resource());
    }

    @ExceptionHandler({HandlerMethodValidationException.class, MethodArgumentTypeMismatchException.class,
            MissingServletRequestParameterException.class})
    public ResponseEntity<Map<String, String>> badParameters() {
        return ResponseEntity.badRequest().body(Map.of("message", "Tham số phiên phỏng vấn không hợp lệ."));
    }
}
