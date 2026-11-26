package fit.iuh.modules.admin.overview;

import fit.iuh.modules.admin.overview.dto.AdminOverviewResponse.Distribution;
import fit.iuh.modules.admin.overview.dto.AdminOverviewResponse.KnowledgeGap;
import fit.iuh.modules.admin.overview.dto.AdminOverviewResponse.TelemetryPoint;
import fit.iuh.modules.admin.overview.service.AdminOverviewService;
import fit.iuh.modules.admin.overview.model.OverviewRange;
import fit.iuh.modules.auth.repository.UserRepository;
import fit.iuh.modules.auth.security.JwtService;
import jakarta.servlet.Filter;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.test.web.servlet.setup.MockMvcBuilders;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.context.WebApplicationContext;

import java.time.LocalDateTime;
import java.time.ZoneId;
import java.util.UUID;

import static org.assertj.core.api.Assertions.assertThat;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.header;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

@SpringBootTest
@Transactional
class AdminOverviewTest {
    private static final String PATH = "/api/v1/admin/overview";

    @Autowired AdminOverviewService overview;
    @Autowired JdbcTemplate db;
    @Autowired WebApplicationContext context;
    @Autowired UserRepository users;
    @Autowired JwtService jwt;

    private final LocalDateTime today = LocalDateTime.now().toLocalDate().atTime(12, 0);

    @Test
    void aggregatesRangeDataAcrossJobsAndEvidenceWithoutCountingCandidatesTwice() {
        var baseline = overview.load(OverviewRange.WEEK);
        UUID candidate = account("USER");
        UUID another = account("USER");
        String current = session(candidate, today, "Completed", "Platform Engineer");
        String stopped = session(candidate, today, "Stopped early", "platform engineer");
        String legacy = session(another, today, "Completed", "Legacy Engineer");
        session(another, today.minusDays(7), "Completed", "Platform Engineer");
        session(another, today, "Not started", "Unstarted Engineer");

        db.update("UPDATE sessions SET interview_report_json = 'legacy malformed' WHERE id = ?", legacy);
        db.update("UPDATE sessions SET skill_gap_json = ?, gap_report_json = '{}' WHERE id = ?", """
                [{"jd_skill_id":"sql","jd_skill_name":"SQL","semantic_alignment":"MISSING"},
                 {"jd_skill_id":"git","jd_skill_name":"Git","semantic_alignment":"MATCH"}]
                """, current);
        run(current, "VOICE", "QUESTION_BUDGET", """
                [{"skill_id":"sql","assessment":"DEMONSTRATED_BELOW_TARGET"},
                 {"skill_id":"git","assessment":"DEMONSTRATED_AT_TARGET"}]
                """);
        run(stopped, "TEXT", "USER_STOP", "[{\"skill_id\":\"sql\",\"assessment\":\"NOT_DEMONSTRATED\"}]");
        db.update("UPDATE sessions SET skill_gap_json = '[]', gap_report_json = '{}' WHERE id = ?", legacy);

        job(candidate, current, "SUCCEEDED");
        job(candidate, stopped, "FAILED");
        var result = overview.load(OverviewRange.WEEK);
        assertThat(result.kpis().interviews()).isEqualTo(baseline.kpis().interviews() + 3);
        assertThat(result.kpis().completedInterviews()).isEqualTo(baseline.kpis().completedInterviews() + 2);
        assertThat(result.kpis().textInterviews()).isEqualTo(baseline.kpis().textInterviews() + 1);
        assertThat(result.kpis().voiceInterviews()).isEqualTo(baseline.kpis().voiceInterviews() + 1);
        assertThat(result.kpis().skillGapJobs()).isEqualTo(baseline.kpis().skillGapJobs() + 2);
        assertThat(result.telemetry().stream().mapToLong(TelemetryPoint::analyses).sum())
                .isEqualTo(baseline.telemetry().stream().mapToLong(TelemetryPoint::analyses).sum() + 2);
        assertThat(result.termination()).extracting(Distribution::code).contains("QUESTION_BUDGET", "USER_STOP", "OTHER");
        assertThat(result.termination()).filteredOn(item -> item.code().equals("QUESTION_BUDGET"))
                .extracting(Distribution::count).containsExactly(1L);
        assertThat(result.assessments()).filteredOn(item -> item.code().equals("DEMONSTRATED_BELOW_TARGET"))
                .extracting(Distribution::count).containsExactly(1L);
        assertThat(result.knowledgeGaps()).contains(new KnowledgeGap("SQL", 1, 100));
        assertThat(result.popularRoles()).filteredOn(role -> role.title().equalsIgnoreCase("Platform Engineer"))
                .singleElement().satisfies(role -> {
                    assertThat(role.interviews()).isEqualTo(2);
                    assertThat(role.growth()).isEqualTo(100.0);
                });
        assertThat(result.popularRoles()).noneMatch(role -> role.title().equals("Unstarted Engineer"));
        assertThat(overview.load(OverviewRange.ALL).kpis().interviewsGrowth()).isNull();
    }

    @Test
    void requiresAdminAndValidatesTheRequestedRange() throws Exception {
        var mvc = MockMvcBuilders.webAppContextSetup(context)
                .addFilters(context.getBean("springSecurityFilterChain", Filter.class)).build();
        String candidate = token(account("USER"));
        String admin = token(account("ADMIN"));

        mvc.perform(get(PATH)).andExpect(status().isUnauthorized());
        mvc.perform(get(PATH).header("Authorization", candidate)).andExpect(status().isForbidden());
        mvc.perform(get(PATH).param("range", "8d").header("Authorization", admin)).andExpect(status().isBadRequest());
        mvc.perform(get(PATH).param("range", "90d").header("Authorization", admin))
                .andExpect(status().isOk())
                .andExpect(header().string("Cache-Control", "no-store"))
                .andExpect(jsonPath("$.kpis.users").isNumber())
                .andExpect(jsonPath("$.telemetry[0].from").isString())
                .andExpect(jsonPath("$.assessments.length()").value(6));
    }

    private UUID account(String role) {
        UUID id = UUID.randomUUID();
        db.update("INSERT INTO users(id, username, email, password_hash, role, created_at) VALUES (?,?,?,?,?,?)",
                id, "Admin metrics fixture", id + "@example.test", "unused", role, today);
        return id;
    }

    private String token(UUID id) {
        return "Bearer " + jwt.generateToken(users.findById(id).orElseThrow());
    }

    private String session(UUID owner, LocalDateTime started, String status, String roleTitle) {
        String id = UUID.randomUUID().toString();
        db.update("INSERT INTO sessions(id,user_id,status,role_title,started_at,ended_at) VALUES (?,?,?,?,?,?)",
                id, owner, status, roleTitle, started, "Not started".equals(status) ? null : started.plusMinutes(5));
        return id;
    }

    private void run(String session, String mode, String reason, String objectives) {
        db.update("""
                INSERT INTO interview_runs(session_id, state_version, config_json, snapshot_json, public_json)
                VALUES (?,1,?,'{}',?)
                """, session, "{\"interaction_mode\":\"" + mode + "\"}", """
                {"report":{"termination_reason":"%s","objectives":%s}}
                """.formatted(reason, objectives));
    }

    private void job(UUID owner, String session, String status) {
        db.update("INSERT INTO skill_gap_jobs(id,session_id,owner_id,input_key,status,created_at) VALUES (?,?,?,?,?,?)",
                UUID.randomUUID(), session, owner, "fixture", status,
                today.atZone(ZoneId.systemDefault()).toOffsetDateTime());
    }
}
