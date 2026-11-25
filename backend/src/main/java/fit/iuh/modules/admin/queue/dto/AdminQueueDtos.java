package fit.iuh.modules.admin.queue.dto;

import jakarta.validation.constraints.NotNull;

import java.time.Instant;
import java.util.List;
import java.util.UUID;

public final class AdminQueueDtos {
    private AdminQueueDtos() {}

    public enum Status { PENDING, RUNNING, SUCCEEDED, FAILED }

    public record Stats(long pendingCount, long runningCount, long succeededCount, long failedCount) {}
    public record Job(UUID id, String candidateName, String roleTitle, String sessionId, Status status,
                      int attempts, Instant createdAt, Instant availableAt, Instant claimedAt, Instant leaseUntil,
                      UUID claimToken, Instant finishedAt, String failureCode, boolean prioritized) {}
    public record Page(List<Job> jobs, Stats stats, long total, int page, int size, int maxAttempts) {}
    public record Detail(Job job, Integer skillCount, Double matchingScore, Boolean degraded) {}
    public record Release(@NotNull UUID claimToken) {}
}
