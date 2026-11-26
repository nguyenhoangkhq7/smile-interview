package fit.iuh.modules.admin.overview.repository;

import fit.iuh.modules.admin.overview.model.OverviewRange.Window;
import org.springframework.core.io.ClassPathResource;
import org.springframework.jdbc.core.namedparam.MapSqlParameterSource;
import org.springframework.jdbc.core.namedparam.NamedParameterJdbcTemplate;
import org.springframework.stereotype.Repository;

import java.io.IOException;
import java.io.UncheckedIOException;
import java.nio.charset.StandardCharsets;
import java.time.LocalDate;
import java.time.ZoneId;
import java.util.List;

@Repository
public class AdminOverviewRepository {
    private static final String KPIS = sql("kpis");
    private static final String TELEMETRY = sql("telemetry");
    private static final String INTERVIEWS = sql("interviews");
    private static final String KNOWLEDGE_GAPS = sql("knowledge-gaps");

    private final NamedParameterJdbcTemplate jdbc;

    public AdminOverviewRepository(NamedParameterJdbcTemplate jdbc) {
        this.jdbc = jdbc;
    }

    public Counts counts(Window window, ZoneId zone) {
        return jdbc.queryForObject(KPIS, parameters(window, zone), (row, index) -> new Counts(
                row.getLong("users"), row.getLong("previous_users"),
                row.getLong("profiles"), row.getLong("previous_profiles"),
                row.getLong("interviews"), row.getLong("previous_interviews"),
                row.getLong("completed_count"), row.getLong("previous_completed"),
                row.getLong("text_count"), row.getLong("voice_count"),
                row.getLong("jobs"), row.getLong("successful_jobs")));
    }

    public List<DailyCount> telemetry(Window window, ZoneId zone) {
        return jdbc.query(TELEMETRY, parameters(window, zone), (row, index) -> new DailyCount(
                row.getObject("event_day", LocalDate.class), row.getLong("analyses"), row.getLong("completed")));
    }

    public List<InterviewCount> interviewBreakdown(Window window, ZoneId zone) {
        return jdbc.query(INTERVIEWS, parameters(window, zone), (row, index) -> new InterviewCount(
                row.getString("category"), row.getString("code"),
                row.getLong("current_count"), row.getLong("previous_count")));
    }

    public List<GapCount> knowledgeGaps(Window window, ZoneId zone) {
        return jdbc.query(KNOWLEDGE_GAPS, parameters(window, zone), (row, index) -> new GapCount(
                row.getString("title"), row.getLong("candidate_count"), row.getLong("total_candidates")));
    }

    private MapSqlParameterSource parameters(Window window, ZoneId zone) {
        return new MapSqlParameterSource()
                .addValue("previous", window.previousStart().atStartOfDay())
                .addValue("start", window.start().atStartOfDay())
                .addValue("end", window.end().atStartOfDay())
                .addValue("jobStart", window.start().atStartOfDay(zone).toOffsetDateTime())
                .addValue("jobEnd", window.end().atStartOfDay(zone).toOffsetDateTime())
                .addValue("zone", zone.getId());
    }

    private static String sql(String name) {
        try {
            return new ClassPathResource("admin/overview/" + name + ".sql").getContentAsString(StandardCharsets.UTF_8);
        } catch (IOException error) {
            throw new UncheckedIOException("Could not load admin overview query " + name, error);
        }
    }

    public record Counts(long users, long previousUsers, long profiles, long previousProfiles,
                         long interviews, long previousInterviews, long completed, long previousCompleted,
                         long text, long voice, long jobs, long successfulJobs) {}

    public record DailyCount(LocalDate day, long analyses, long completed) {}

    public record InterviewCount(String category, String code, long current, long previous) {}

    public record GapCount(String title, long candidates, long totalCandidates) {}
}
