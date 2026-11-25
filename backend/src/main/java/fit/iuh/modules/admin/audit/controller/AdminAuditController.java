package fit.iuh.modules.admin.audit.controller;

import fit.iuh.modules.admin.audit.dto.AdminAuditDtos.*;
import fit.iuh.modules.admin.audit.model.AuditAction;
import fit.iuh.modules.admin.audit.service.AdminAuditService;
import jakarta.servlet.http.HttpServletResponse;
import jakarta.validation.constraints.Max;
import jakarta.validation.constraints.Min;
import jakarta.validation.constraints.Size;
import lombok.RequiredArgsConstructor;
import org.springframework.http.CacheControl;
import org.springframework.http.ContentDisposition;
import org.springframework.http.HttpHeaders;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.method.annotation.HandlerMethodValidationException;
import org.springframework.web.method.annotation.MethodArgumentTypeMismatchException;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.time.LocalDate;
import java.util.Map;
import java.util.UUID;

import org.springframework.format.annotation.DateTimeFormat;
import org.springframework.http.HttpStatus;
import org.springframework.web.server.ResponseStatusException;

@RestController
@RequestMapping("/api/v1/admin/audit-logs")
@RequiredArgsConstructor
public class AdminAuditController {
    private final AdminAuditService audit;

    @GetMapping
    public ResponseEntity<Page> list(@RequestParam(defaultValue = "") @Size(max = 200) String search,
                                     @RequestParam(required = false) UUID actorId,
                                     @RequestParam(required = false) AuditAction action,
                                     @RequestParam(required = false) @DateTimeFormat(iso = DateTimeFormat.ISO.DATE) LocalDate from,
                                     @RequestParam(required = false) @DateTimeFormat(iso = DateTimeFormat.ISO.DATE) LocalDate to,
                                     @RequestParam(defaultValue = "1") @Min(1) int page,
                                     @RequestParam(defaultValue = "6") @Min(1) @Max(100) int size) {
        validateDateRange(from, to);
        return ResponseEntity.ok().cacheControl(CacheControl.noStore())
                .body(audit.list(new Filter(search, actorId, action, from, to), page, size));
    }

    @GetMapping("/{id}")
    public ResponseEntity<Detail> detail(@PathVariable @Min(1) long id) {
        return ResponseEntity.ok().cacheControl(CacheControl.noStore()).body(audit.detail(id));
    }

    @GetMapping(value = "/export", produces = "text/csv")
    public void export(@RequestParam(defaultValue = "") @Size(max = 200) String search,
                       @RequestParam(required = false) UUID actorId,
                       @RequestParam(required = false) AuditAction action,
                       @RequestParam(required = false) @DateTimeFormat(iso = DateTimeFormat.ISO.DATE) LocalDate from,
                       @RequestParam(required = false) @DateTimeFormat(iso = DateTimeFormat.ISO.DATE) LocalDate to,
                       HttpServletResponse response) throws IOException {
        validateDateRange(from, to);
        response.setContentType("text/csv");
        response.setCharacterEncoding(StandardCharsets.UTF_8.name());
        response.setHeader(HttpHeaders.CACHE_CONTROL, CacheControl.noStore().getHeaderValue());
        response.setHeader(HttpHeaders.CONTENT_DISPOSITION,
                ContentDisposition.attachment().filename("admin-audit-logs.csv").build().toString());
        audit.export(new Filter(search, actorId, action, from, to), response.getOutputStream());
    }

    private static void validateDateRange(LocalDate from, LocalDate to) {
        if (from != null && to != null && from.isAfter(to)) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "Khoảng ngày lọc nhật ký không hợp lệ.");
        }
    }

    @ExceptionHandler({HandlerMethodValidationException.class, MethodArgumentTypeMismatchException.class})
    public ResponseEntity<Map<String, String>> invalidParameters() {
        return ResponseEntity.badRequest().body(Map.of("message", "Tham số nhật ký quản trị không hợp lệ."));
    }
}
