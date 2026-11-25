package fit.iuh.modules.admin.storage.controller;

import fit.iuh.modules.admin.storage.dto.AdminStorageDtos.*;
import fit.iuh.modules.admin.storage.service.AdminStorageService;
import fit.iuh.modules.admin.audit.model.AuditAction;
import fit.iuh.modules.admin.audit.service.AdminAuditService;
import fit.iuh.modules.auth.entity.User;
import jakarta.validation.Valid;
import org.springframework.security.core.annotation.AuthenticationPrincipal;

import java.util.List;
import java.util.Map;
import java.util.UUID;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.*;

@RestController
@RequestMapping("/api/v1/admin/storage")
@RequiredArgsConstructor
public class AdminStorageController {
    private final AdminStorageService storage;
    private final AdminAuditService audit;

    @GetMapping
    public Overview overview() {
        return storage.overview();
    }

    @PostMapping("/cleanup")
    public CleanupResult cleanup(@AuthenticationPrincipal User actor, @Valid @RequestBody CleanupRequest request) {
        UUID batch = UUID.randomUUID();
        var objects = request.ids().stream().distinct().toList();
        audit.record(actor.getId(), AuditAction.REQUEST_STORAGE_CLEANUP, batch, "Yêu cầu dọn tệp mồ côi.",
                List.of(), Map.of("objectIds", objects));
        var result = storage.cleanup(objects);
        audit.record(actor.getId(), AuditAction.CLEANUP_STORAGE, batch,
                "Dọn tệp mồ côi · " + result.deleted() + " đã xóa, " + result.skipped()
                        + " bỏ qua, " + result.failed() + " lỗi.", List.of(),
                Map.of("deleted", result.deleted(), "skipped", result.skipped(), "failed", result.failed()));
        return result;
    }
}
