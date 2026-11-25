package fit.iuh.modules.admin.queue.service;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import fit.iuh.modules.admin.audit.dto.AdminAuditDtos.Change;
import fit.iuh.modules.admin.audit.service.AdminAuditService;
import fit.iuh.modules.admin.queue.dto.AdminQueueDtos.*;
import fit.iuh.modules.admin.queue.model.AdminQueueFilter;
import fit.iuh.modules.admin.queue.repository.AdminQueueRepository;
import fit.iuh.modules.skillgap.SkillGapJobs;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Isolation;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.server.ResponseStatusException;

import java.util.List;
import java.util.Map;
import java.util.UUID;

import static fit.iuh.modules.admin.audit.model.AuditAction.*;

@Service
@RequiredArgsConstructor
@Slf4j
public class AdminQueueService {
    private final AdminQueueRepository queue;
    private final ObjectMapper json;
    private final AdminAuditService audit;

    @Transactional(readOnly = true, isolation = Isolation.REPEATABLE_READ)
    public Page list(AdminQueueFilter filter, int page, int size) {
        long total = queue.count(filter);
        long last = Math.max(1, (total + size - 1) / size);
        int current = (int) Math.min(page, last);
        return new Page(queue.page(filter, (current - 1L) * size, size), queue.stats(), total,
                current, size, SkillGapJobs.MAX_ATTEMPTS);
    }

    public Detail detail(UUID id) {
        var entry = queue.detail(id).orElseThrow(AdminQueueService::missing);
        if (entry.resultJson() == null) return new Detail(entry.job(), null, null, null);
        try {
            var result = json.readTree(entry.resultJson());
            var skills = result.path("skills");
            var report = result.path("report");
            return new Detail(entry.job(), skills.isArray() ? skills.size() : null,
                    report.path("matching_score").isNumber() ? report.path("matching_score").doubleValue() : null,
                    report.path("degraded").isBoolean() ? report.path("degraded").booleanValue() : null);
        } catch (JsonProcessingException ex) {
            log.warn("Could not read stored result for skill gap job {}", id);
            return new Detail(entry.job(), null, null, null);
        }
    }

    @Transactional
    public void release(UUID actor, UUID id, UUID token) {
        requireChange(id, queue.release(id, token), "Lease đã đổi. Vui lòng làm mới danh sách.");
        audit.record(actor, RELEASE_JOB_LEASE, id, "Giải phóng lease và đưa job trở lại hàng đợi.",
                List.of(new Change("status", "RUNNING", "PENDING")), Map.of());
    }

    @Transactional
    public void prioritize(UUID actor, UUID id) {
        requireChange(id, queue.prioritize(id), "Chỉ có thể ưu tiên job đang chờ.");
        audit.record(actor, PRIORITIZE_JOB, id, "Yêu cầu ưu tiên job đang chờ.");
    }

    private void requireChange(UUID id, int changed, String message) {
        if (changed != 0) return;
        if (!queue.exists(id)) throw missing();
        throw new ResponseStatusException(HttpStatus.CONFLICT, message);
    }

    private static ResponseStatusException missing() {
        return new ResponseStatusException(HttpStatus.NOT_FOUND, "Không tìm thấy job.");
    }
}
