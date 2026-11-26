package fit.iuh.modules.admin.users.controller;

import fit.iuh.modules.admin.users.dto.AdminUserDtos.*;
import fit.iuh.modules.admin.users.model.UserCatalogFilter;
import fit.iuh.modules.admin.users.service.AdminUsersService;
import fit.iuh.modules.auth.dto.PasswordSetupDtos.Link;
import fit.iuh.modules.auth.entity.Role;
import fit.iuh.modules.auth.entity.User;
import jakarta.validation.Valid;
import jakarta.validation.constraints.Max;
import jakarta.validation.constraints.Min;
import jakarta.validation.constraints.Size;
import lombok.RequiredArgsConstructor;
import org.springframework.http.*;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.method.annotation.HandlerMethodValidationException;
import org.springframework.web.method.annotation.MethodArgumentTypeMismatchException;

import java.nio.charset.StandardCharsets;
import java.util.UUID;

@RestController
@RequestMapping("/api/v1/admin/users")
@RequiredArgsConstructor
public class AdminUsersController {
    private final AdminUsersService service;

    @ExceptionHandler({HandlerMethodValidationException.class, MethodArgumentTypeMismatchException.class})
    public ResponseEntity<java.util.Map<String, String>> invalidParameters() {
        return ResponseEntity.badRequest().body(java.util.Map.of("message", "Tham số quản lý người dùng không hợp lệ."));
    }

    @GetMapping
    public Page list(@AuthenticationPrincipal User actor, @RequestParam(defaultValue = "") @Size(max = 200) String search,
                     @RequestParam(required = false) Role role, @RequestParam(required = false) Status status,
                     @RequestParam(defaultValue = "1") @Min(1) int page,
                     @RequestParam(defaultValue = "6") @Min(1) @Max(100) int size) {
        return service.list(actor.getId(), new UserCatalogFilter(search, role, status), page, size);
    }

    @GetMapping("/{id}")
    public Detail detail(@AuthenticationPrincipal User actor, @PathVariable UUID id) {
        return service.detail(actor.getId(), id);
    }

    @GetMapping(value = "/export", produces = "text/csv")
    public ResponseEntity<byte[]> export(@AuthenticationPrincipal User actor,
                                         @RequestParam(defaultValue = "") @Size(max = 200) String search,
                                         @RequestParam(required = false) Role role,
                                         @RequestParam(required = false) Status status) {
        byte[] csv = service.export(actor.getId(), new UserCatalogFilter(search, role, status))
                .getBytes(StandardCharsets.UTF_8);
        return ResponseEntity.ok().cacheControl(CacheControl.noStore())
                .contentType(new MediaType("text", "csv", StandardCharsets.UTF_8))
                .header(HttpHeaders.CONTENT_DISPOSITION, "attachment; filename=\"users.csv\"")
                .body(csv);
    }

    @PostMapping
    public ResponseEntity<Link> create(@AuthenticationPrincipal User actor, @Valid @RequestBody Create request) {
        return ResponseEntity.status(HttpStatus.CREATED).cacheControl(CacheControl.noStore())
                .body(service.create(actor.getId(), request));
    }

    @PatchMapping("/{id}/status")
    @ResponseStatus(HttpStatus.NO_CONTENT)
    public void changeStatus(@AuthenticationPrincipal User actor, @PathVariable UUID id,
                             @Valid @RequestBody ChangeStatus request) {
        service.changeStatus(actor.getId(), id, request);
    }

    @PostMapping("/{id}/password-setup")
    public ResponseEntity<Link> passwordSetup(@AuthenticationPrincipal User actor, @PathVariable UUID id) {
        return ResponseEntity.ok().cacheControl(CacheControl.noStore()).body(service.resetPassword(actor.getId(), id));
    }
}
