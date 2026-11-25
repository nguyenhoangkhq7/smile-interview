package fit.iuh.modules.admin.users.repository;

import fit.iuh.modules.admin.users.dto.AdminUserDtos.*;
import fit.iuh.modules.admin.users.model.UserCatalogFilter;
import fit.iuh.modules.auth.entity.Role;
import lombok.RequiredArgsConstructor;
import org.springframework.jdbc.core.RowMapper;
import org.springframework.jdbc.core.namedparam.MapSqlParameterSource;
import org.springframework.jdbc.core.namedparam.NamedParameterJdbcTemplate;
import org.springframework.stereotype.Repository;

import java.time.LocalDateTime;
import java.util.List;
import java.util.Optional;
import java.util.UUID;

@Repository
@RequiredArgsConstructor
public class AdminUserReadRepository {
    private static final String USER_ACCOUNTS = "u.role IN ('USER', 'CANDIDATE')";
    private static final String FILTER = """
            WHERE %s
              AND (CAST(:role AS text) IS NULL OR u.role = :role)
              AND (CAST(:locked AS boolean) IS NULL OR (u.locked_at IS NOT NULL) = :locked)
              AND (strpos(lower(u.username), :search) > 0 OR strpos(lower(u.email), :search) > 0
                   OR strpos(coalesce(u.phone_number, ''), :search) > 0)
            """.formatted(USER_ACCOUNTS);
    private static final String INTERVIEW_EXISTS = """
            AND (s.ai_interview_session_id IS NOT NULL OR s.status IN ('In progress', 'Completed', 'Stopped early', 'Cancelled')
                 OR EXISTS (SELECT 1 FROM interview_runs r WHERE r.session_id = s.id))
            """;
    private static final String SUMMARY = """
            SELECT u.id, u.username, u.email, u.phone_number, u.role, u.locked_at IS NOT NULL AS locked,
                   u.created_at, u.lock_reason, u.id = :actor AS self,
                   (SELECT count(*) FROM application_profiles p WHERE p.user_id = u.id AND p.deleted_at IS NULL) AS profiles,
                   (SELECT count(*) FROM sessions s WHERE s.user_id = u.id
            """ + INTERVIEW_EXISTS + ") AS interviews FROM users u ";
    private static final String ORDER = " ORDER BY u.created_at DESC, u.id DESC ";
    private static final RowMapper<Summary> SUMMARY_ROW = (rs, row) -> new Summary(
            rs.getObject("id", UUID.class), rs.getString("username"), rs.getString("email"),
            rs.getString("phone_number"), Role.valueOf(rs.getString("role")),
            rs.getBoolean("locked") ? Status.LOCKED : Status.ACTIVE, rs.getObject("created_at", LocalDateTime.class),
            rs.getLong("profiles"), rs.getLong("interviews"), rs.getBoolean("self"), rs.getString("lock_reason"));

    private final NamedParameterJdbcTemplate jdbc;

    public Stats stats() {
        return jdbc.getJdbcTemplate().queryForObject("""
                SELECT count(*) AS total, count(*) FILTER (WHERE locked_at IS NULL) AS active,
                       count(*) FILTER (WHERE locked_at IS NOT NULL) AS locked,
                       count(*) FILTER (WHERE created_at >= CURRENT_DATE - 29) AS registered_recently
                FROM users u WHERE %s
                """.formatted(USER_ACCOUNTS), (rs, row) -> new Stats(rs.getLong("total"), rs.getLong("active"),
                rs.getLong("locked"), rs.getLong("registered_recently")));
    }

    public long count(UserCatalogFilter filter) {
        return jdbc.queryForObject("SELECT count(*) FROM users u " + FILTER, parameters(filter), Long.class);
    }

    public List<Summary> page(UserCatalogFilter filter, UUID actor, int page, int size) {
        var params = parameters(filter).addValue("actor", actor).addValue("size", size)
                .addValue("offset", (page - 1L) * size);
        return jdbc.query(SUMMARY + FILTER + ORDER + " LIMIT :size OFFSET :offset", params, SUMMARY_ROW);
    }

    public List<Summary> export(UserCatalogFilter filter, UUID actor) {
        return jdbc.query(SUMMARY + FILTER + ORDER, parameters(filter).addValue("actor", actor), SUMMARY_ROW);
    }

    public Optional<Summary> summary(UUID user, UUID actor) {
        return jdbc.query(SUMMARY + "WHERE u.id = :user",
                new MapSqlParameterSource("user", user).addValue("actor", actor), SUMMARY_ROW).stream().findFirst();
    }

    public List<Interview> recentInterviews(UUID user) {
        return jdbc.query("""
                SELECT id, role_title, status, overall_score, started_at, ended_at
                FROM sessions s WHERE s.user_id = :user
                """ + INTERVIEW_EXISTS + " ORDER BY started_at DESC, id DESC LIMIT 10",
                new MapSqlParameterSource("user", user), (rs, row) -> new Interview(rs.getString("id"),
                        rs.getString("role_title"), rs.getString("status"), rs.getObject("overall_score", Integer.class),
                        rs.getObject("started_at", LocalDateTime.class), rs.getObject("ended_at", LocalDateTime.class)));
    }

    public List<Profile> recentProfiles(UUID user) {
        return jdbc.query("""
                SELECT id, title, role_title, created_at FROM application_profiles
                WHERE user_id = :user AND deleted_at IS NULL ORDER BY created_at DESC, id DESC LIMIT 10
                """, new MapSqlParameterSource("user", user), (rs, row) -> new Profile(rs.getObject("id", UUID.class),
                rs.getString("title"), rs.getString("role_title"), rs.getObject("created_at", LocalDateTime.class)));
    }

    public List<Plan> activePlans(UUID user) {
        return jdbc.query("""
                SELECT p.id, p.title, count(t.id) AS total, count(t.id) FILTER (WHERE t.status = 'DONE') AS completed
                FROM study_plans p JOIN application_profiles a ON a.id = p.application_profile_id
                LEFT JOIN study_tasks t ON t.plan_id = p.id
                WHERE a.user_id = :user AND a.deleted_at IS NULL AND p.status = 'ACTIVE'
                GROUP BY p.id ORDER BY p.updated_at DESC, p.id DESC LIMIT 10
                """, new MapSqlParameterSource("user", user), (rs, row) ->
                new Plan(rs.getLong("id"), rs.getString("title"), rs.getLong("total"), rs.getLong("completed")));
    }

    private static MapSqlParameterSource parameters(UserCatalogFilter filter) {
        return new MapSqlParameterSource("search", filter.search())
                .addValue("role", filter.role() == null ? null : filter.role().name(), java.sql.Types.VARCHAR)
                .addValue("locked", filter.status() == null ? null : filter.status() == Status.LOCKED, java.sql.Types.BOOLEAN);
    }
}
