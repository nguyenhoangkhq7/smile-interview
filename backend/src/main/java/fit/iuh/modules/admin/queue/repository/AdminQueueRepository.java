package fit.iuh.modules.admin.queue.repository;

import fit.iuh.modules.admin.queue.dto.AdminQueueDtos.*;
import fit.iuh.modules.admin.queue.model.AdminQueueFilter;
import lombok.RequiredArgsConstructor;
import org.springframework.jdbc.core.RowMapper;
import org.springframework.jdbc.core.namedparam.MapSqlParameterSource;
import org.springframework.jdbc.core.namedparam.NamedParameterJdbcTemplate;
import org.springframework.stereotype.Repository;

import java.sql.ResultSet;
import java.sql.SQLException;
import java.sql.Types;
import java.time.Instant;
import java.time.OffsetDateTime;
import java.util.List;
import java.util.Optional;
import java.util.UUID;

@Repository
@RequiredArgsConstructor
public class AdminQueueRepository {
    private static final String JOIN = """
            FROM skill_gap_jobs j JOIN users u ON u.id = j.owner_id JOIN sessions s ON s.id = j.session_id
            """;
    private static final String FILTER = """
            WHERE (CAST(:status AS text) IS NULL OR j.status = :status)
              AND (strpos(j.id::text, :search) > 0 OR strpos(lower(u.username), :search) > 0
                   OR strpos(lower(coalesce(s.role_title, '')), :search) > 0)
            """;
    private static final String SELECT_JOB = "SELECT j.*, u.username, s.role_title ";
    private static final RowMapper<Job> JOB = (rs, row) -> new Job(
            rs.getObject("id", UUID.class), rs.getString("username"), rs.getString("role_title"),
            rs.getString("session_id"), Status.valueOf(rs.getString("status")), rs.getInt("attempts"),
            instant(rs, "created_at"), instant(rs, "available_at"), instant(rs, "claimed_at"), instant(rs, "lease_until"),
            rs.getObject("claim_token", UUID.class), instant(rs, "finished_at"), rs.getString("failure_code"),
            instant(rs, "priority_at") != null);

    private final NamedParameterJdbcTemplate jdbc;

    public Stats stats() {
        return jdbc.getJdbcTemplate().queryForObject("""
                SELECT count(*) FILTER (WHERE status = 'PENDING') AS pending,
                       count(*) FILTER (WHERE status = 'RUNNING') AS running,
                       count(*) FILTER (WHERE status = 'SUCCEEDED') AS succeeded,
                       count(*) FILTER (WHERE status = 'FAILED') AS failed
                FROM skill_gap_jobs
                """, (rs, row) -> new Stats(rs.getLong("pending"), rs.getLong("running"),
                rs.getLong("succeeded"), rs.getLong("failed")));
    }

    public long count(AdminQueueFilter filter) {
        return jdbc.queryForObject("SELECT count(*) " + JOIN + FILTER, params(filter), Long.class);
    }

    public List<Job> page(AdminQueueFilter filter, long offset, int size) {
        return jdbc.query(SELECT_JOB + JOIN + FILTER + " ORDER BY j.created_at DESC, j.id DESC LIMIT :size OFFSET :offset",
                params(filter).addValue("size", size).addValue("offset", offset), JOB);
    }

    public Optional<JobResult> detail(UUID id) {
        return jdbc.query(SELECT_JOB + JOIN + " WHERE j.id = :id", new MapSqlParameterSource("id", id),
                (row, index) -> new JobResult(JOB.mapRow(row, index), row.getString("result_json")))
                .stream().findFirst();
    }

    public int prioritize(UUID id) {
        return jdbc.update("""
                UPDATE skill_gap_jobs SET priority_at = coalesce(priority_at, clock_timestamp()),
                    available_at = least(available_at, clock_timestamp())
                WHERE id = :id AND status = 'PENDING'
                """, idParam(id));
    }

    public int release(UUID id, UUID token) {
        return jdbc.update("""
                UPDATE skill_gap_jobs SET status = 'PENDING', attempts = greatest(attempts - 1, 0),
                    available_at = clock_timestamp(), lease_until = NULL, claim_token = NULL, claimed_at = NULL,
                    priority_at = NULL, failure_code = NULL
                WHERE id = :id AND status = 'RUNNING' AND claim_token = :token
                """, idParam(id).addValue("token", token));
    }

    public boolean exists(UUID id) {
        return Boolean.TRUE.equals(jdbc.queryForObject("SELECT EXISTS (SELECT 1 FROM skill_gap_jobs WHERE id = :id)",
                idParam(id), Boolean.class));
    }

    private static Instant instant(ResultSet rs, String column) throws SQLException {
        var value = rs.getObject(column, OffsetDateTime.class);
        return value == null ? null : value.toInstant();
    }

    private static MapSqlParameterSource idParam(UUID id) {
        return new MapSqlParameterSource().addValue("id", id, Types.OTHER);
    }

    private static MapSqlParameterSource params(AdminQueueFilter filter) {
        return new MapSqlParameterSource("search", filter.search())
                .addValue("status", filter.status() == null ? null : filter.status().name(), Types.VARCHAR);
    }

    public record JobResult(Job job, String resultJson) {}
}
