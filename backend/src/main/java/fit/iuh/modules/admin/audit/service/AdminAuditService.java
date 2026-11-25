package fit.iuh.modules.admin.audit.service;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;
import fit.iuh.modules.admin.audit.dto.AdminAuditDtos.*;
import fit.iuh.modules.admin.audit.model.AuditAction;
import fit.iuh.modules.admin.audit.repository.AdminAuditRepository;
import lombok.RequiredArgsConstructor;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Isolation;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.context.request.RequestContextHolder;
import org.springframework.web.context.request.ServletRequestAttributes;
import org.springframework.web.server.ResponseStatusException;

import java.io.BufferedWriter;
import java.io.IOException;
import java.io.OutputStream;
import java.io.OutputStreamWriter;
import java.io.UncheckedIOException;
import java.nio.charset.StandardCharsets;
import java.util.List;
import java.util.Map;
import java.util.UUID;

import static fit.iuh.common.CsvCell.text;

@Service
@RequiredArgsConstructor
public class AdminAuditService {
    private final AdminAuditRepository audit;
    private final ObjectMapper json;

    public void record(UUID actor, AuditAction action, Object target, String summary) {
        record(actor, action, target, summary, List.of(), Map.of());
    }

    public void record(UUID actor, AuditAction action, Object target, String summary,
                       List<Change> changes, Map<String, ?> details) {
        var request = RequestContextHolder.getRequestAttributes();
        String peer = request instanceof ServletRequestAttributes servlet ? servlet.getRequest().getRemoteAddr() : null;
        try {
            audit.insert(actor, action, target.toString(), peer, summary,
                    json.writeValueAsString(changes), json.writeValueAsString(details));
        } catch (JsonProcessingException ex) {
            throw new IllegalStateException("Cannot serialize audit event", ex);
        }
    }

    @Transactional(readOnly = true, isolation = Isolation.REPEATABLE_READ)
    public Page list(Filter filter, int page, int size) {
        long total = audit.count(filter);
        int current = (int) Math.min(page, Math.max(1, (total + size - 1) / size));
        return new Page(audit.page(filter, (current - 1L) * size, size), total, current, size,
                audit.stats(), audit.actors());
    }

    public Detail detail(long id) {
        var row = audit.detail(id).orElseThrow(() ->
                new ResponseStatusException(HttpStatus.NOT_FOUND, "Không tìm thấy bản ghi nhật ký."));
        try {
            return new Detail(row.event(), row.peerAddress(), json.readValue(row.changes(), new TypeReference<>() {}),
                    json.readValue(row.details(), new TypeReference<>() {}));
        } catch (JsonProcessingException ex) {
            throw new IllegalStateException("Cannot read audit event", ex);
        }
    }

    @Transactional(readOnly = true)
    public void export(Filter filter, OutputStream output) throws IOException {
        var writer = new BufferedWriter(new OutputStreamWriter(output, StandardCharsets.UTF_8));
        writer.write("\uFEFFID,Thời gian (UTC),ID quản trị viên,Quản trị viên,Hành động,Loại đối tượng,Mã đối tượng,Tóm tắt\r\n");
        try {
            audit.export(filter, row -> {
                try {
                    writer.write(String.join(",", row.id(), text(row.occurredAt().toString()), text(row.actorId().toString()),
                            text(row.actorName()), text(row.action().name()), text(row.targetType().name()),
                            text(row.targetCode()), text(row.summary())));
                    writer.write("\r\n");
                } catch (IOException ex) {
                    throw new UncheckedIOException(ex);
                }
            });
        } catch (UncheckedIOException ex) {
            throw ex.getCause();
        }
        writer.flush();
    }
}
