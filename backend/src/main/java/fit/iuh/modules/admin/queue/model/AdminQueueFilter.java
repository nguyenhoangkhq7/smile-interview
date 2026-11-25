package fit.iuh.modules.admin.queue.model;

import fit.iuh.modules.admin.queue.dto.AdminQueueDtos.Status;

import java.util.Locale;

public record AdminQueueFilter(String search, Status status) {
    public AdminQueueFilter {
        search = search == null ? "" : search.strip().toLowerCase(Locale.ROOT);
    }
}
