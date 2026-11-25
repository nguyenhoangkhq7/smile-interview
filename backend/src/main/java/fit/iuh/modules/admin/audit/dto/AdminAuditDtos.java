package fit.iuh.modules.admin.audit.dto;

import fit.iuh.modules.admin.audit.model.AuditAction;
import fit.iuh.modules.admin.audit.model.AuditAction.Target;

import java.time.Instant;
import java.time.LocalDate;
import java.util.List;
import java.util.Map;
import java.util.UUID;

public final class AdminAuditDtos {
    private AdminAuditDtos() {}

    public record Filter(String search, UUID actorId, AuditAction action, LocalDate from, LocalDate to) {
        public Filter(String search, UUID actorId, AuditAction action) {
            this(search, actorId, action, null, null);
        }
    }
    public record Row(String id, Instant occurredAt, UUID actorId, String actorName, AuditAction action,
                      Target targetType, String targetCode, String summary) {}
    public record Change(String field, String oldValue, String newValue) {}
    public record Detail(Row event, String peerAddress, List<Change> changes, Map<String, Object> details) {}
    public record Stats(long total, long today, long admins) {}
    public record Actor(UUID id, String name) {}
    public record Page(List<Row> rows, long total, int page, int size, Stats stats, List<Actor> actors) {}
}
