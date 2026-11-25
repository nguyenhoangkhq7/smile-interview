package fit.iuh.modules.admin.interviews;

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

import java.util.UUID;

import static org.hamcrest.Matchers.containsString;
import static org.hamcrest.Matchers.not;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.*;

@SpringBootTest
@Transactional
class AdminInterviewHttpTest {
    private static final String PATH = "/api/v1/admin/interview-sessions";
    @Autowired WebApplicationContext context;
    @Autowired JdbcTemplate db;
    @Autowired UserRepository users;
    @Autowired JwtService tokens;

    @Test
    void filtersAndPaginatesAndOnlyReturnsPersistedFinalTranscript() throws Exception {
        var mvc = MockMvcBuilders.webAppContextSetup(context)
                .addFilters(context.getBean("springSecurityFilterChain", Filter.class)).build();
        String title = "Audit Interview " + UUID.randomUUID();
        UUID candidate = account("USER");
        String admin = authorization(account("ADMIN"));
        String completed = session(candidate, title, "Completed", true);
        String active = session(candidate, title, "In progress", false);
        String draft = session(candidate, title, "In progress", false);
        String stopped = session(candidate, title, "Stopped early", true);
        String stale = session(candidate, title, "Completed", true);
        insertRun(completed, true, "Recorded final answer");
        insertRun(active, false, "Private active answer");
        insertRun(stale, false, "Private stale answer");
        db.update("INSERT INTO session_turns(session_id, question, answer, score) VALUES (?,?,?,?)",
                stopped, "Legacy question", "Legacy answer", 4);

        mvc.perform(get(PATH)).andExpect(status().isUnauthorized());
        mvc.perform(get(PATH).header("Authorization", authorization(candidate))).andExpect(status().isForbidden());
        mvc.perform(get(PATH + "/detail").param("id", completed).header("Authorization", authorization(candidate)))
                .andExpect(status().isForbidden());

        mvc.perform(get(PATH).header("Authorization", admin).param("search", title).param("size", "2").param("page", "2"))
                .andExpect(status().isOk()).andExpect(jsonPath("$.total").value(5))
                .andExpect(jsonPath("$.page").value(2)).andExpect(jsonPath("$.sessions.length()").value(2))
                .andExpect(jsonPath("$.counts.COMPLETED").value(2))
                .andExpect(jsonPath("$.counts.IN_PROGRESS").value(1))
                .andExpect(jsonPath("$.counts.NOT_STARTED").value(1))
                .andExpect(jsonPath("$.counts.ANOMALY").value(1));
        mvc.perform(get(PATH).header("Authorization", admin)
                        .param("search", "#" + completed).param("status", "COMPLETED"))
                .andExpect(status().isOk()).andExpect(jsonPath("$.total").value(1))
                .andExpect(jsonPath("$.sessions[0].id").value(completed)).andExpect(jsonPath("$.sessions[0].mode").value("VOICE"));
        mvc.perform(get(PATH).header("Authorization", admin).param("search", title).param("status", "NOT_STARTED"))
                .andExpect(status().isOk()).andExpect(jsonPath("$.sessions[0].id").value(draft));
        mvc.perform(get(PATH).header("Authorization", admin).param("status", "INVALID")).andExpect(status().isBadRequest());

        mvc.perform(get(PATH + "/detail").param("id", completed).header("Authorization", admin))
                .andExpect(status().isOk()).andExpect(jsonPath("$.finalized").value(true))
                .andExpect(jsonPath("$.session.createdAt").isString())
                .andExpect(jsonPath("$.blueprint.maxQuestions").value(8))
                .andExpect(jsonPath("$.blueprint.policy.fallbackDepth").value(2))
                .andExpect(jsonPath("$.transcript.turns[0].answer").value("Recorded final answer"))
                .andExpect(jsonPath("$.transcript.turns[0].evidence[0].excerpt").value("Recorded final answer"))
                .andExpect(jsonPath("$.report.terminationReason").value("PLAN_COMPLETE"))
                .andExpect(content().string(not(containsString("PRIVATE SNAPSHOT"))));
        for (String id : new String[]{active, stale}) {
            mvc.perform(get(PATH + "/detail").param("id", id).header("Authorization", admin))
                    .andExpect(status().isOk()).andExpect(jsonPath("$.finalized").value(false))
                    .andExpect(jsonPath("$.transcript.turns.length()").value(1))
                    .andExpect(jsonPath("$.report").doesNotExist())
                    .andExpect(content().string(not(containsString("PRIVATE SNAPSHOT"))));
        }
        mvc.perform(get(PATH + "/detail").param("id", stopped).header("Authorization", admin))
                .andExpect(status().isOk()).andExpect(jsonPath("$.transcript.turns[0].answer").value("Legacy answer"));
        mvc.perform(get(PATH + "/detail").param("id", "absent-" + UUID.randomUUID()).header("Authorization", admin))
                .andExpect(status().isNotFound());
    }

    private String session(UUID candidate, String role, String status, boolean ended) {
        String id = "session-" + UUID.randomUUID();
        db.update("INSERT INTO sessions(id,user_id,role_title,status,ended_at) VALUES (?,?,?,?, CASE WHEN ? THEN now() END)",
                id, candidate, role, status, ended);
        return id;
    }

    private void insertRun(String id, boolean finished, String answer) {
        String state = """
                {"is_finished":%s,"turns":[{"turn_id":"t1","objective_id":"o1","question":"Question","answer":"%s"}],
                  "report":{"termination_reason":"PLAN_COMPLETE","objectives":[{"objective_id":"o1","skill_id":"Java",
                    "assessment":"DEMONSTRATED_AT_TARGET","evidence":[{"turn_id":"t1","response_excerpt":"%s"}]}]}}
                """.formatted(finished, answer, answer);
        db.update("INSERT INTO interview_runs(session_id,state_version,config_json,snapshot_json,public_json) VALUES (?,1,?,?,?)",
                id, "{\"interaction_mode\":\"VOICE\",\"max_questions\":8}",
                "{\"policy\":{\"fallback_depth\":2},\"private\":\"PRIVATE SNAPSHOT\"}", state);
    }

    private UUID account(String role) {
        UUID id = UUID.randomUUID();
        db.update("INSERT INTO users(id,username,email,password_hash,role) VALUES (?,?,?,?,?)",
                id, "Interview fixture", id + "@example.test", "unused", role);
        return id;
    }

    private String authorization(UUID id) {
        return "Bearer " + tokens.generateToken(users.findById(id).orElseThrow());
    }
}
