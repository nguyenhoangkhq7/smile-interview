package fit.iuh.modules.admin.queue.controller;

import fit.iuh.modules.admin.queue.dto.AdminQueueDtos.*;
import fit.iuh.modules.admin.queue.model.AdminQueueFilter;
import fit.iuh.modules.admin.queue.service.AdminQueueService;
import fit.iuh.modules.auth.entity.User;
import jakarta.validation.Valid;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import jakarta.validation.constraints.Max;
import jakarta.validation.constraints.Min;
import jakarta.validation.constraints.Size;
import lombok.RequiredArgsConstructor;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.method.annotation.HandlerMethodValidationException;
import org.springframework.web.method.annotation.MethodArgumentTypeMismatchException;

import java.util.Map;
import java.util.UUID;

@RestController
@RequestMapping("/api/v1/admin/queue")
@RequiredArgsConstructor
public class AdminQueueController {
    private final AdminQueueService service;

    @GetMapping("/jobs")
    public Page list(@RequestParam(defaultValue = "") @Size(max = 200) String search,
                     @RequestParam(required = false) Status status,
                     @RequestParam(defaultValue = "1") @Min(1) int page,
                     @RequestParam(defaultValue = "10") @Min(1) @Max(100) int size) {
        return service.list(new AdminQueueFilter(search, status), page, size);
    }

    @GetMapping("/jobs/{id}")
    public Detail detail(@PathVariable UUID id) {
        return service.detail(id);
    }

    @PostMapping("/jobs/{id}/release")
    @ResponseStatus(HttpStatus.NO_CONTENT)
    public void release(@AuthenticationPrincipal User actor, @PathVariable UUID id, @Valid @RequestBody Release request) {
        service.release(actor.getId(), id, request.claimToken());
    }

    @PostMapping("/jobs/{id}/prioritize")
    @ResponseStatus(HttpStatus.NO_CONTENT)
    public void prioritize(@AuthenticationPrincipal User actor, @PathVariable UUID id) {
        service.prioritize(actor.getId(), id);
    }

    @ExceptionHandler({HandlerMethodValidationException.class, MethodArgumentTypeMismatchException.class})
    public ResponseEntity<Map<String, String>> invalidParameters() {
        return ResponseEntity.badRequest().body(Map.of("message", "Tham số hàng đợi không hợp lệ."));
    }
}
