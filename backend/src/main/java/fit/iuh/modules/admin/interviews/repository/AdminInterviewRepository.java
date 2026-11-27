package fit.iuh.modules.admin.interviews.repository;

import fit.iuh.modules.admin.interviews.model.InterviewStatus;
import lombok.RequiredArgsConstructor;
import org.springframework.jdbc.core.namedparam.MapSqlParameterSource;
import org.springframework.jdbc.core.namedparam.NamedParameterJdbcTemplate;
import org.springframework.stereotype.Repository;

import java.sql.ResultSet;
import java.sql.SQLException;
import java.time.Instant;
import java.time.LocalDateTime;
import java.time.OffsetDateTime;
import java.time.ZoneId;
import java.util.EnumMap;
import java.util.List;
import java.util.Map;
import java.util.Optional;

@Repository
@RequiredArgsConstructor
public class AdminInterviewRepository {
    private static final String CATALOG = """
            WITH catalog AS (
                SELECT s.id, u.username AS candidate_name, s.role_title, s.user_rating,
                       s.started_at AS created_at, s.ended_at, s.status AS raw_status, s.interview_type,
                       r.created_at AS run_started_at, r.config_json,
                       CASE
                           WHEN state.value = 'completed' THEN 'COMPLETED'
                           WHEN state.value IN ('stopped early', 'cancelled', 'canceled', 'failed', 'error', 'timed out', 'timeout')
                               THEN 'ANOMALY'
                           WHEN r.session_id IS NOT NULL AND s.ended_at IS NULL THEN 'IN_PROGRESS'
                           WHEN state.value = 'in progress' AND s.ended_at IS NULL AND (
                               s.ai_interview_session_id IS NOT NULL
                               OR EXISTS (SELECT 1 FROM session_turns t WHERE t.session_id = s.id)
                           ) THEN 'IN_PROGRESS'
                           WHEN state.value IN ('', 'not started', 'pending', 'draft', 'in progress')
                               AND s.ended_at IS NULL THEN 'NOT_STARTED'
                           ELSE 'OTHER'
                       END AS admin_status
                FROM sessions s LEFT JOIN users u ON u.id = s.user_id
                LEFT JOIN interview_runs r ON r.session_id = s.id
                CROSS JOIN LATERAL (
                    SELECT replace(lower(btrim(coalesce(s.status, ''))), '_', ' ') AS value
                ) state
                WHERE :search = '' OR strpos(lower(s.id), lower(:search)) > 0
                   OR strpos(lower(u.username), lower(:search)) > 0
                   OR strpos(lower(s.role_title), lower(:search)) > 0
            )
            """;
    private final NamedParameterJdbcTemplate jdbc;

    public Map<InterviewStatus, Long> counts(String search) {
        var counts = new EnumMap<InterviewStatus, Long>(InterviewStatus.class);
        jdbc.query(CATALOG + "SELECT admin_status, count(*) FROM catalog GROUP BY admin_status",
                new MapSqlParameterSource("search", search),
                (org.springframework.jdbc.core.RowCallbackHandler) row ->
                        counts.put(InterviewStatus.valueOf(row.getString(1)), row.getLong(2)));
        return counts;
    }

    public List<Row> page(String search, InterviewStatus status, long offset, int size) {
        var params = new MapSqlParameterSource("search", search).addValue("offset", offset).addValue("size", size);
        String where = "";
        if (status != null) {
            where = "WHERE admin_status = :status ";
            params.addValue("status", status.name());
        }
        return jdbc.query(CATALOG + "SELECT * FROM catalog " + where
                        + "ORDER BY created_at DESC, id DESC LIMIT :size OFFSET :offset", params,
                (row, index) -> row(row));
    }

    public Optional<DetailRow> detail(String id) {
        return jdbc.query(CATALOG + """
                SELECT c.*, COALESCE(p.cv_filename, cv.file_name) AS cv_name,
                       COALESCE(p.jd_title, jd.title) AS jd_title, p.company,
                       COALESCE(p.gap_report_json, s.gap_report_json) AS gap_report,
                       COALESCE(p.skill_gap_json, s.skill_gap_json) IS NOT NULL AS has_gap,
                       r.public_json, s.interview_report_json, s.overall_score, s.overall_feedback,
                       CASE WHEN pg_input_is_valid(r.snapshot_json, 'jsonb')
                           THEN (r.snapshot_json::jsonb -> 'policy')::text
                       END AS policy_json
                FROM catalog c JOIN sessions s ON s.id = c.id
                LEFT JOIN interview_runs r ON r.session_id = c.id
                LEFT JOIN application_profiles p ON p.id = s.application_profile_id
                LEFT JOIN resumes cv ON cv.id = s.resume_id
                LEFT JOIN job_descriptions jd ON jd.id = s.jd_id
                WHERE c.id = :id
                """, new MapSqlParameterSource("id", id).addValue("search", ""),
                (row, index) -> new DetailRow(row(row), row.getString("cv_name"), row.getString("jd_title"),
                        row.getString("company"), row.getString("gap_report"), row.getBoolean("has_gap"),
                        row.getString("public_json"), row.getString("interview_report_json"),
                        row.getObject("overall_score", Integer.class), row.getString("overall_feedback"),
                        row.getString("policy_json")))
                .stream().findFirst();
    }

    public Optional<QualityRow> quality(String id) {
        return jdbc.query("""
                SELECT coalesce(p.cv_text, cv.raw_text) AS cv,
                       coalesce(p.jd_text, jd.raw_text) AS jd,
                       coalesce(p.skill_gap_json, s.skill_gap_json) AS skills_json,
                       coalesce(p.gap_report_json, s.gap_report_json) AS report_json,
                       s.interview_type, r.config_json, r.public_json
                FROM sessions s
                LEFT JOIN application_profiles p ON p.id = s.application_profile_id
                LEFT JOIN resumes cv ON cv.id = s.resume_id
                LEFT JOIN job_descriptions jd ON jd.id = s.jd_id
                LEFT JOIN interview_runs r ON r.session_id = s.id
                WHERE s.id = :id
                """, new MapSqlParameterSource("id", id), (row, index) -> new QualityRow(
                row.getString("cv"), row.getString("jd"), row.getString("skills_json"), row.getString("report_json"),
                row.getString("interview_type"), row.getString("config_json"), row.getString("public_json")))
                .stream().findFirst();
    }

    public Optional<DocumentsRow> documents(String id) {
        return jdbc.query("""
                SELECT coalesce(p.cv_filename, cv.file_name) AS cv_name, coalesce(p.cv_text, cv.raw_text) AS cv_text,
                       cv.file_url AS cv_file, coalesce(p.jd_title, jd.title) AS jd_title,
                       coalesce(p.jd_text, jd.raw_text) AS jd_text, jd.file_url AS jd_file
                FROM sessions s
                LEFT JOIN application_profiles p ON p.id = s.application_profile_id
                LEFT JOIN resumes cv ON cv.id = coalesce(p.resume_id, s.resume_id)
                LEFT JOIN job_descriptions jd ON jd.id = coalesce(p.jd_id, s.jd_id)
                WHERE s.id = :id
                """, new MapSqlParameterSource("id", id), (row, index) -> new DocumentsRow(
                new DocumentRow(row.getString("cv_name"), row.getString("cv_text"), row.getString("cv_file")),
                new DocumentRow(row.getString("jd_title"), row.getString("jd_text"), row.getString("jd_file"))))
                .stream().findFirst();
    }

    public Optional<MatchingRow> matching(String id) {
        return jdbc.query("""
                SELECT coalesce(p.skill_gap_json, s.skill_gap_json) AS skills,
                       coalesce(p.gap_report_json, s.gap_report_json) AS report
                FROM sessions s LEFT JOIN application_profiles p ON p.id = s.application_profile_id
                WHERE s.id = :id
                """, new MapSqlParameterSource("id", id),
                (row, index) -> new MatchingRow(row.getString("skills"), row.getString("report"))).stream().findFirst();
    }

    private static Row row(ResultSet result) throws SQLException {
        var runStart = result.getObject("run_started_at", OffsetDateTime.class);
        return new Row(result.getString("id"), result.getString("candidate_name"), result.getString("role_title"),
                InterviewStatus.valueOf(result.getString("admin_status")), result.getString("raw_status"),
                result.getString("interview_type"), localTime(result, "created_at"),
                runStart == null ? null : runStart.toInstant(), localTime(result, "ended_at"),
                result.getObject("user_rating", Integer.class), result.getString("config_json"));
    }

    private static Instant localTime(ResultSet result, String column) throws SQLException {
        // The sessions table stores LocalDateTime values written in the backend's time zone.
        var local = result.getObject(column, LocalDateTime.class);
        return local == null ? null : local.atZone(ZoneId.systemDefault()).toInstant();
    }

    public record Row(String id, String candidateName, String roleTitle, InterviewStatus status, String rawStatus,
                      String interviewType, Instant createdAt, Instant runStartedAt, Instant endedAt,
                      Integer userRating, String configJson) {}
    public record DetailRow(Row session, String cvName, String jdTitle, String company, String gapReport,
                            boolean hasGap, String publicJson, String legacyReport, Integer overallScore,
                            String overallFeedback, String policyJson) {}
    public record QualityRow(String cv, String jd, String skillsJson, String reportJson,
                             String interviewType, String configJson, String publicJson) {
        @Override public String toString() { return "QualityRow[redacted]"; }
    }
    public record DocumentsRow(DocumentRow cv, DocumentRow jd) {}
    public record DocumentRow(String name, String text, String locator) {
        @Override public String toString() { return "DocumentRow[redacted]"; }
    }
    public record MatchingRow(String skillsJson, String reportJson) {}
}
