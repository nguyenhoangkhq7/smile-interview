package fit.iuh.modules.admin.interviews.controller;

import fit.iuh.modules.admin.interviews.dto.AdminInterviewDtos.Detail;
import fit.iuh.modules.admin.interviews.dto.AdminInterviewDtos.Page;
import fit.iuh.modules.admin.interviews.model.InterviewStatus;
import fit.iuh.modules.admin.interviews.service.AdminInterviewService;
import jakarta.validation.constraints.Max;
import jakarta.validation.constraints.Min;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Size;
import lombok.RequiredArgsConstructor;
import org.springframework.http.CacheControl;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.bind.MissingServletRequestParameterException;
import org.springframework.web.method.annotation.HandlerMethodValidationException;
import org.springframework.web.method.annotation.MethodArgumentTypeMismatchException;

import java.util.Map;

@RestController
@RequestMapping("/api/v1/admin/interview-sessions")
@RequiredArgsConstructor
public class AdminInterviewController {
    private final AdminInterviewService interviews;

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

    @ExceptionHandler({HandlerMethodValidationException.class, MethodArgumentTypeMismatchException.class,
            MissingServletRequestParameterException.class})
    public ResponseEntity<Map<String, String>> badParameters() {
        return ResponseEntity.badRequest().body(Map.of("message", "Tham số phiên phỏng vấn không hợp lệ."));
    }
}
