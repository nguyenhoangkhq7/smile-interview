package fit.iuh.modules.admin.aipolicy.repository;

import lombok.RequiredArgsConstructor;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Repository;
import java.time.Instant;
import java.time.OffsetDateTime;
import java.util.UUID;

@Repository
@RequiredArgsConstructor
public class AiPolicyRepository {
    private final JdbcTemplate jdbc;

    public Stored active() {
        return jdbc.queryForObject("""
                SELECT revision, settings::text, credentials, updated_at FROM ai_runtime_configuration WHERE id = 1
                """, (row, i) -> {
                    var stamp = row.getObject("updated_at", OffsetDateTime.class);
                    return new Stored(row.getLong("revision"), row.getString("settings"), row.getString("credentials"),
                            stamp == null ? null : stamp.toInstant());
                });
    }

    public int update(long revision, String settings, String credentials, UUID actor) {
        return jdbc.update("""
                UPDATE ai_runtime_configuration SET revision = revision + 1, settings = cast(? as jsonb),
                    credentials = ?, updated_at = clock_timestamp(), updated_by = ?
                WHERE id = 1 AND revision = ?
                """, settings, credentials, actor, revision);
    }

    public record Stored(long revision, String settings, String credentials, Instant updatedAt) {}
}
