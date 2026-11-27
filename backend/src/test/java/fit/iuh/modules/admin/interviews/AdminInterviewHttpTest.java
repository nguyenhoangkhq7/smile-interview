package fit.iuh.modules.admin.interviews;

import fit.iuh.modules.admin.aipolicy.service.AiPolicySources;
import fit.iuh.modules.admin.interviews.dto.AdminInterviewDtos.*;
import fit.iuh.modules.auth.repository.UserRepository;
import fit.iuh.modules.auth.security.JwtService;
import jakarta.servlet.Filter;
import org.junit.jupiter.api.Test;
import org.mockito.ArgumentCaptor;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.test.context.bean.override.mockito.MockitoBean;
import org.springframework.test.web.servlet.setup.MockMvcBuilders;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.context.WebApplicationContext;
import software.amazon.awssdk.core.ResponseInputStream;
import software.amazon.awssdk.services.s3.S3Client;
import software.amazon.awssdk.services.s3.model.GetObjectRequest;
import software.amazon.awssdk.services.s3.model.GetObjectResponse;

import java.io.ByteArrayInputStream;
import java.util.List;
import java.util.UUID;

import static org.assertj.core.api.Assertions.assertThat;
import static org.hamcrest.Matchers.containsString;
import static org.hamcrest.Matchers.not;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.verifyNoInteractions;
import static org.mockito.Mockito.when;
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
    @MockitoBean AiPolicySources ai;
    @MockitoBean S3Client s3;

    @Test
    void exposesSavedDocumentsAndMatchingOnlyThroughAdminEndpoints() throws Exception {
        var mvc = MockMvcBuilders.webAppContextSetup(context)
                .addFilters(context.getBean("springSecurityFilterChain", Filter.class)).build();
        UUID owner = account("USER");
        String id = session(owner, "Document test", "Completed", true);
        String admin = authorization(account("ADMIN"));
        String candidate = authorization(owner);
        UUID cv = UUID.randomUUID(), jd = UUID.randomUUID(), profile = UUID.randomUUID();
        String cvUrl = "https://smile-interview.s3.ap-southeast-1.amazonaws.com/resumes/archive/cv.pdf";
        String jdText = "Nhiệm vụ JD đã lưu.";
        String cvText = "CV đã lưu " + "a".repeat(1800) + " phần cuối.";
        db.update("INSERT INTO resumes(id,user_id,file_name,raw_text,file_url) VALUES (?,?,?,?,?)",
                cv, owner, "cv.pdf", "CURRENT CV", cvUrl);
        db.update("INSERT INTO job_descriptions(id,user_id,title,raw_text) VALUES (?,?,?,?)", jd, owner, "Backend", "CURRENT JD");
        String skills = """
                [{"jd_skill_id":"java","jd_skill_name":"Java","semantic_alignment":"PARTIAL","matched_cv_skill_id":"kotlin",
                  "required_proficiency":3,"cv_evidence_spans":["Đã dùng Kotlin"],
                  "job_tasks":[{"description":"Vận hành API","requirement_kind":"REQUIRED","evidence_spans":["Nhiệm vụ JD đã lưu."]}]}]
                """;
        db.update("""
                INSERT INTO application_profiles(id, user_id, title, role_title, resume_id, jd_id, cv_filename, jd_title,
                    cv_text, jd_text, skill_gap_json, gap_report_json, created_at)
                VALUES (?, ?, 'Profile', 'Backend', ?, ?, 'Bản CV.pdf', 'JD lưu', ?, ?, ?, ?, now())
                """, profile, owner, cv, jd, cvText, jdText, skills, "{\"matching_score\":0.19,\"degraded\":true}");
        db.update("UPDATE sessions SET resume_id=?, jd_id=?, application_profile_id=?, skill_gap_json='[]' WHERE id=?",
                cv, jd, profile, id);

        for (String endpoint : List.of("/document", "/document-file", "/matching")) {
            mvc.perform(get(PATH + endpoint).param("id", id).param("kind", "CV")
                    .header("Authorization", candidate)).andExpect(status().isForbidden());
        }
        mvc.perform(get(PATH + "/document").param("id", id).param("kind", "CV").header("Authorization", admin))
                .andExpect(status().isOk()).andExpect(header().string("Cache-Control", "no-store"))
                .andExpect(jsonPath("$.name").value("Bản CV.pdf")).andExpect(jsonPath("$.originalAvailable").value(true))
                .andExpect(jsonPath("$.text").value(cvText.substring(0, 1600) + "…"));
        mvc.perform(get(PATH + "/document").param("id", id).param("kind", "CV").param("preview", "false")
                .header("Authorization", admin)).andExpect(status().isOk()).andExpect(jsonPath("$.text").value(cvText));
        mvc.perform(get(PATH + "/document").param("id", id).param("kind", "JD").header("Authorization", admin))
                .andExpect(status().isOk()).andExpect(jsonPath("$.text").value(jdText))
                .andExpect(jsonPath("$.originalAvailable").value(false));
        mvc.perform(get(PATH + "/matching").param("id", id).header("Authorization", admin))
                .andExpect(status().isOk()).andExpect(jsonPath("$.score").value(0.19))
                .andExpect(jsonPath("$.degraded").value(true))
                .andExpect(jsonPath("$.skills[0].alignment").value("PARTIAL"))
                .andExpect(jsonPath("$.skills[0].cvEvidence[0]").value("Đã dùng Kotlin"))
                .andExpect(jsonPath("$.skills[0].tasks[0].evidence[0]").value(jdText))
                .andExpect(content().string(not(containsString("CV đã lưu"))));

        byte[] file = {1, 2, 3};
        when(s3.getObject(any(GetObjectRequest.class))).thenReturn(new ResponseInputStream<>(
                GetObjectResponse.builder().build(), new ByteArrayInputStream(file)));
        mvc.perform(get(PATH + "/document-file").param("id", id).param("kind", "CV").header("Authorization", admin))
                .andExpect(status().isOk()).andExpect(header().string("Content-Disposition", containsString("attachment")))
                .andExpect(content().bytes(file));
        var request = ArgumentCaptor.forClass(GetObjectRequest.class);
        verify(s3).getObject(request.capture());
        assertThat(request.getValue().key()).isEqualTo("resumes/archive/cv.pdf");
    }

    @Test
    void reviewsStoredSessionAsAdminWithoutReturningRawDocuments() throws Exception {
        var mvc = MockMvcBuilders.webAppContextSetup(context)
                .addFilters(context.getBean("springSecurityFilterChain", Filter.class)).build();
        UUID candidate = account("USER");
        String id = session(candidate, "Quality test", "Completed", true);
        insertRun(id, true, "SENSITIVE ANSWER");
        UUID cv = UUID.randomUUID(), jd = UUID.randomUUID();
        db.update("INSERT INTO resumes(id, file_name, raw_text) VALUES (?,?,?)", cv, "cv.pdf", "SENSITIVE CV");
        db.update("INSERT INTO job_descriptions(id, title, raw_text) VALUES (?,?,?)", jd, "Job", "SENSITIVE JD");
        db.update("UPDATE sessions SET resume_id=?, jd_id=?, skill_gap_json=?, gap_report_json=? WHERE id=?",
                cv, jd, "[]", "{\"matching_score\":0.4}", id);

        String endpoint = PATH + "/quality";
        mvc.perform(get(endpoint).param("id", id)).andExpect(status().isUnauthorized());
        mvc.perform(get(endpoint).param("id", id).header("Authorization", authorization(candidate)))
                .andExpect(status().isForbidden());
        verifyNoInteractions(ai);

        when(ai.quality(any())).thenReturn(new QualityReview(new QualitySection(0, List.of()),
                new QualitySection(1, List.of(new QualityFinding("REVIEW", "MISSING_CODE", "Thiếu đoạn mã",
                        "Java", 1, "Question")))));
        mvc.perform(get(endpoint).param("id", id).header("Authorization", authorization(account("ADMIN"))))
                .andExpect(status().isOk()).andExpect(header().string("Cache-Control", "no-store"))
                .andExpect(jsonPath("$.questions.findings[0].code").value("MISSING_CODE"))
                .andExpect(content().string(not(containsString("SENSITIVE"))))
                .andExpect(content().string(not(containsString("PRIVATE SNAPSHOT"))));

        var captured = ArgumentCaptor.forClass(QualityInput.class);
        verify(ai).quality(captured.capture());
        assertThat(captured.getValue()).isEqualTo(new QualityInput("SENSITIVE CV", "SENSITIVE JD",
                "[]", "{\"matching_score\":0.4}", "VOICE", List.of(new QualityQuestion("Question", "Java"))));
    }

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
