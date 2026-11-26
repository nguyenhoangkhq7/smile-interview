package fit.iuh.modules.admin.storage.dto;

import jakarta.validation.constraints.NotEmpty;
import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.Size;

import java.time.Instant;
import java.util.List;
import java.util.UUID;

public final class AdminStorageDtos {
    private AdminStorageDtos() {}

    public static final int CLEANUP_BATCH_SIZE = 6;

    public record Segment(String code, long bytes) {}
    public record Orphans(List<UUID> ids, long bytes, int minimumAgeHours) {}
    public record Overview(List<Segment> segments, long totalBytes, Long quotaBytes,
                           boolean s3Available, boolean complete, Orphans orphans, int cleanupBatchSize, Instant measuredAt) {}
    public record CleanupRequest(@NotEmpty @Size(max = CLEANUP_BATCH_SIZE) List<@NotNull UUID> ids) {}
    public record CleanupResult(int deleted, int skipped, int failed) {}
}
