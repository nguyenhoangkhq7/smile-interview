package fit.iuh.modules.admin.storage.repository;

import lombok.RequiredArgsConstructor;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Repository;
import org.springframework.transaction.annotation.Transactional;

import java.time.Instant;
import java.time.ZoneOffset;
import java.util.List;
import java.util.Optional;
import java.util.UUID;

@Repository
@RequiredArgsConstructor
public class AdminStorageRepository {
    private static final String UNREFERENCED = """
            NOT EXISTS (SELECT 1 FROM resumes WHERE managed_cv_id(file_url) = cv.id)
            AND NOT EXISTS (SELECT 1 FROM job_descriptions WHERE managed_cv_id(file_url) = cv.id)
            AND NOT EXISTS (SELECT 1 FROM users WHERE managed_cv_id(avatar_url) = cv.id)
            AND NOT EXISTS (SELECT 1 FROM study_task_resources WHERE managed_cv_id(url) = cv.id)
            """;
    private final JdbcTemplate jdbc;

    public long databaseBytes() {
        return jdbc.queryForObject("SELECT pg_database_size(current_database())", Long.class);
    }

    public List<ManagedObject> orphans(String bucket, Instant before) {
        return jdbc.query("""
                SELECT id, etag FROM managed_cv_objects cv
                WHERE bucket = ? AND created_at <= ? AND etag IS NOT NULL AND deleted_at IS NULL AND
                """ + UNREFERENCED,
                (rs, row) -> new ManagedObject(rs.getObject("id", UUID.class), rs.getString("etag")),
                bucket, before.atOffset(ZoneOffset.UTC));
    }

    @Transactional
    public Optional<ManagedObject> retire(UUID id, String bucket, Instant before) {
        var objects = jdbc.query("""
                SELECT id, etag FROM managed_cv_objects WHERE id = ? AND bucket = ?
                    AND created_at <= ? AND etag IS NOT NULL AND deleted_at IS NULL FOR UPDATE
                """, (rs, row) -> new ManagedObject(rs.getObject("id", UUID.class), rs.getString("etag")),
                id, bucket, before.atOffset(ZoneOffset.UTC));
        if (objects.isEmpty()) return Optional.empty();
        // Use a separate statement after acquiring the row lock shared by reference inserts.
        int retired = jdbc.update("""
                UPDATE managed_cv_objects cv SET retired_at = coalesce(retired_at, clock_timestamp())
                WHERE id = ? AND
                """ + UNREFERENCED, id);
        return retired == 1 ? Optional.of(objects.getFirst()) : Optional.empty();
    }

    public void acknowledgeDeletion(UUID id) {
        jdbc.update("UPDATE managed_cv_objects SET deleted_at = clock_timestamp() WHERE id = ? AND retired_at IS NOT NULL",
                id);
    }

    public record ManagedObject(UUID id, String etag) {}
}
