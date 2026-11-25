package fit.iuh.modules.admin.users.dto;

import fit.iuh.modules.auth.entity.Role;
import jakarta.validation.constraints.Email;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.Size;

import java.time.LocalDateTime;
import java.util.List;
import java.util.UUID;

public final class AdminUserDtos {
    private AdminUserDtos() {}

    public enum Status { ACTIVE, LOCKED }

    public record Stats(long totalUsers, long activeUsers, long lockedUsers, long registeredLast30Days) {}

    public record Summary(UUID id, String fullName, String email, String phone, Role role,
                          Status status, LocalDateTime joinedAt, long profilesCount, long sessionsCount,
                          boolean self, String lockReason) {}

    public record Page(List<Summary> users, long total, int page, int size, Stats stats) {}

    public record Interview(String id, String roleTitle, String status, Integer score,
                            LocalDateTime startedAt, LocalDateTime endedAt) {}

    public record Profile(UUID id, String title, String roleTitle, LocalDateTime createdAt) {}

    public record Plan(long id, String title, long totalTasks, long completedTasks) {}

    public record Detail(Summary user, List<Interview> interviews, List<Profile> profiles, List<Plan> plans) {}

    public record Create(@NotBlank @Size(max = 255) String fullName,
                         @NotBlank @Email @Size(max = 255) String email) {}


    public record ChangeStatus(@NotNull Status status, @Size(max = 500) String reason) {}
}
