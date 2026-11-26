package fit.iuh.modules.auth;

import com.fasterxml.jackson.databind.JsonNode;
import fit.iuh.modules.application.ApplicationProfileRepository;
import fit.iuh.modules.application.ApplicationProfileService;
import fit.iuh.modules.auth.entity.Role;
import fit.iuh.modules.auth.entity.User;
import fit.iuh.modules.auth.repository.UserRepository;
import fit.iuh.modules.auth.security.JwtService;
import fit.iuh.modules.evidence.EvidenceJson;
import fit.iuh.modules.session.entity.JobDescription;
import fit.iuh.modules.session.entity.Resume;
import fit.iuh.modules.session.entity.Session;
import fit.iuh.modules.session.repository.JobDescriptionRepository;
import fit.iuh.modules.session.repository.ResumeRepository;
import fit.iuh.modules.session.repository.SessionRepository;
import fit.iuh.modules.session.repository.SessionTurnRepository;
import fit.iuh.modules.study.dto.StudyPlanDtos;
import fit.iuh.modules.study.service.StudyPlanService;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.test.web.server.LocalServerPort;
import org.springframework.jdbc.core.simple.JdbcClient;
import org.springframework.mock.web.MockMultipartFile;

import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.nio.charset.StandardCharsets;
import java.time.Duration;
import java.time.LocalDateTime;
import java.util.Map;
import java.util.UUID;

import static org.assertj.core.api.Assertions.assertThat;

/**
 * End-to-end two-account (User A vs User B) authorization tests covering CV, JD,
 * Session, ApplicationProfile documents, Study resource download, and Auth profile endpoints.
 */
@SpringBootTest(webEnvironment = SpringBootTest.WebEnvironment.RANDOM_PORT)
class AuthorizationSecurityTest {

    @LocalServerPort int port;
    @Autowired UserRepository users;
    @Autowired ResumeRepository resumes;
    @Autowired JobDescriptionRepository descriptions;
    @Autowired SessionRepository sessions;
    @Autowired SessionTurnRepository turns;
    @Autowired ApplicationProfileService profileService;
    @Autowired ApplicationProfileRepository profiles;
    @Autowired StudyPlanService studyPlanService;
    @Autowired JwtService jwt;
    @Autowired EvidenceJson json;
    @Autowired JdbcClient jdbc;

    private final HttpClient http = HttpClient.newHttpClient();
    private User userA;
    private User userB;
    private String tokenA;
    private String tokenB;
    private Resume resumeA;
    private Resume standaloneResumeA;
    private JobDescription jdA;
    private JobDescription standaloneJdA;
    private Session sessionA;
    private Session profileSourceSessionA;
    private UUID profileIdA;

    @BeforeEach
    void setUp() {
        String suffix = UUID.randomUUID().toString().substring(0, 8);
        userA = users.save(User.builder()
                .username("User A")
                .email("user-a-" + suffix + "@smile.test")
                .password("$2a$10$8.UnVuG9HHgffUDAlk8qfOUVGkqRzgVymGe07xd00DMxs.AQubh4a")
                .role(Role.USER)
                .build());
        userB = users.save(User.builder()
                .username("User B")
                .email("user-b-" + suffix + "@smile.test")
                .password("$2a$10$8.UnVuG9HHgffUDAlk8qfOUVGkqRzgVymGe07xd00DMxs.AQubh4a")
                .role(Role.USER)
                .build());
        tokenA = jwt.generateToken(userA);
        tokenB = jwt.generateToken(userB);

        resumeA = resumes.save(Resume.builder()
                .id(UUID.randomUUID())
                .userId(userA.getId())
                .fileName("cv-secret-a.pdf")
                .fileUrl("/uploads/resumes/cv-secret-a.pdf")
                .rawText("Secret CV contents for User A - Java 21, Spring Boot, PostgreSQL")
                .createdAt(LocalDateTime.now())
                .build());
        standaloneResumeA = resumes.save(Resume.builder()
                .id(UUID.randomUUID())
                .userId(userA.getId())
                .fileName("cv-standalone-a.pdf")
                .rawText("Standalone CV for User A")
                .createdAt(LocalDateTime.now())
                .build());

        jdA = descriptions.save(JobDescription.builder()
                .id(UUID.randomUUID())
                .userId(userA.getId())
                .title("Senior Backend Engineer A")
                .fileUrl("/uploads/jds/jd-secret-a.pdf")
                .rawText("Secret JD contents for User A - Microservices and SQL tuning")
                .createdAt(LocalDateTime.now())
                .build());
        standaloneJdA = descriptions.save(JobDescription.builder()
                .id(UUID.randomUUID())
                .userId(userA.getId())
                .title("Standalone JD A")
                .rawText("Standalone JD for User A")
                .createdAt(LocalDateTime.now())
                .build());

        sessionA = sessions.save(Session.builder()
                .id("authz-session-" + suffix)
                .userId(userA.getId())
                .resume(standaloneResumeA)
                .jobDescription(standaloneJdA)
                .roleTitle("Backend Engineer")
                .interviewType("Technical")
                .status("Not started")
                .startedAt(LocalDateTime.now())
                .build());

        profileSourceSessionA = sessions.save(Session.builder()
                .id("authz-profile-session-" + suffix)
                .userId(userA.getId())
                .resume(resumeA)
                .jobDescription(jdA)
                .roleTitle("Senior Backend Engineer")
                .interviewType("Technical")
                .status("Not started")
                .skillGapJson("""
                        [{"jd_skill_id":"sql","semantic_alignment":"PARTIAL","priority":0.9,
                          "importance_weight":0.8,"required_proficiency":3,"cv_evidence_spans":["PostgreSQL"],
                          "job_tasks":[{"task_id":"t1","description":"Tune SQL queries","evidence_spans":["SQL tuning"],
                          "required_level":3,"requirement_kind":"REQUIRED","level_basis":"EXPLICIT"}]}]
                        """)
                .gapReportJson("{\"matching_score\":0.75,\"degraded\":false}")
                .startedAt(LocalDateTime.now())
                .build());

        profileIdA = profileService.create(userA,
                new ApplicationProfileService.Create(profileSourceSessionA.getId(), "Profile A", "Acme Corp")).id();
    }

    @AfterEach
    void tearDown() {
        jdbc.sql("DELETE FROM study_plans WHERE application_profile_id = :id").param("id", profileIdA).update();
        jdbc.sql("DELETE FROM sessions WHERE user_id IN (:a, :b)")
                .param("a", userA.getId()).param("b", userB.getId()).update();
        if (profiles.existsById(profileIdA)) {
            profiles.deleteById(profileIdA);
        }
        jdbc.sql("UPDATE users SET default_resume_id = NULL WHERE id IN (:a, :b)")
                .param("a", userA.getId()).param("b", userB.getId()).update();
        jdbc.sql("DELETE FROM resumes WHERE user_id IN (:a, :b)")
                .param("a", userA.getId()).param("b", userB.getId()).update();
        jdbc.sql("DELETE FROM job_descriptions WHERE user_id IN (:a, :b)")
                .param("a", userA.getId()).param("b", userB.getId()).update();
        users.deleteById(userA.getId());
        users.deleteById(userB.getId());
    }

    @Test
    void protectedAuthEndpointsRequireJwtAndProfileRejectsForeignDefaultResume() throws Exception {
        assertThat(send("GET", "/api/auth/me", null, null).statusCode()).isEqualTo(401);
        assertThat(send("PUT", "/api/auth/profile", null, Map.of("username", "Anon")).statusCode()).isEqualTo(401);

        assertThat(send("GET", "/api/auth/me", tokenA, null).statusCode()).isEqualTo(200);

        // User B must not be able to bind User A's resume as defaultResumeId
        var hijackDefault = send("PUT", "/api/auth/profile", tokenB,
                Map.of("defaultResumeId", resumeA.getId().toString()));
        assertThat(hijackDefault.statusCode()).isEqualTo(403);
        assertThat(users.findById(userB.getId()).orElseThrow().getDefaultResumeId()).isNull();

        // User A can bind their own resume as defaultResumeId
        var ownDefault = send("PUT", "/api/auth/profile", tokenA,
                Map.of("defaultResumeId", resumeA.getId().toString()));
        assertThat(ownDefault.statusCode()).isEqualTo(200);
        assertThat(users.findById(userA.getId()).orElseThrow().getDefaultResumeId()).isEqualTo(resumeA.getId());
    }

    @Test
    void strangerCannotReadRawTextDownloadOrDeleteAnotherUsersResumeAndJd() throws Exception {
        // User B cannot list User A's resumes or JDs
        var listResumesB = send("GET", "/api/v1/resumes", tokenB, null);
        assertThat(listResumesB.statusCode()).isEqualTo(200);
        assertThat(listResumesB.body()).doesNotContain(resumeA.getId().toString());

        var listJdsB = send("GET", "/api/v1/job-descriptions", tokenB, null);
        assertThat(listJdsB.statusCode()).isEqualTo(200);
        assertThat(listJdsB.body()).doesNotContain(jdA.getId().toString());

        // User B cannot read, extract raw text, or delete User A's Resume
        assertThat(send("GET", "/api/v1/resumes/" + standaloneResumeA.getId(), tokenB, null).statusCode()).isEqualTo(403);
        assertThat(send("GET", "/api/v1/resumes/" + standaloneResumeA.getId() + "/raw", tokenB, null).statusCode()).isEqualTo(403);
        assertThat(send("DELETE", "/api/v1/resumes/" + standaloneResumeA.getId(), tokenB, null).statusCode()).isEqualTo(403);
        assertThat(resumes.existsById(standaloneResumeA.getId())).isTrue();

        // User B cannot read, extract raw text, or delete User A's JD
        assertThat(send("GET", "/api/v1/job-descriptions/" + standaloneJdA.getId(), tokenB, null).statusCode()).isEqualTo(403);
        assertThat(send("GET", "/api/v1/job-descriptions/" + standaloneJdA.getId() + "/raw", tokenB, null).statusCode()).isEqualTo(403);
        assertThat(send("DELETE", "/api/v1/job-descriptions/" + standaloneJdA.getId(), tokenB, null).statusCode()).isEqualTo(403);
        assertThat(descriptions.existsById(standaloneJdA.getId())).isTrue();

        // User A can read own resume/JD and cannot delete one bound to an ApplicationProfile (409)
        assertThat(send("GET", "/api/v1/resumes/" + resumeA.getId(), tokenA, null).statusCode()).isEqualTo(200);
        assertThat(send("GET", "/api/v1/resumes/" + resumeA.getId() + "/raw", tokenA, null).statusCode()).isEqualTo(200);
        assertThat(send("DELETE", "/api/v1/resumes/" + resumeA.getId(), tokenA, null).statusCode()).isEqualTo(409);
        assertThat(send("DELETE", "/api/v1/job-descriptions/" + jdA.getId(), tokenA, null).statusCode()).isEqualTo(409);

        // User A can delete standalone CV and JD
        assertThat(send("DELETE", "/api/v1/resumes/" + standaloneResumeA.getId(), tokenA, null).statusCode()).isEqualTo(200);
        assertThat(send("DELETE", "/api/v1/job-descriptions/" + standaloneJdA.getId(), tokenA, null).statusCode()).isEqualTo(200);
        assertThat(resumes.existsById(standaloneResumeA.getId())).isFalse();
        assertThat(descriptions.existsById(standaloneJdA.getId())).isFalse();
    }

    @Test
    void jsonCreationIgnoresUntrustedClientFileUrl() throws Exception {
        var createdResume = send("POST", "/api/v1/resumes", tokenB, Map.of(
                "file_name", "pasted.txt",
                "raw_text", "Pasted CV content",
                "file_url", "https://evil.example.com/spoofed.pdf"
        ));
        assertThat(createdResume.statusCode()).isEqualTo(201);
        JsonNode resumeNode = json.read(createdResume.body());
        assertThat(resumeNode.path("fileUrl").isNull()).isTrue();

        var createdJd = send("POST", "/api/v1/job-descriptions", tokenB, Map.of(
                "title", "Pasted JD",
                "raw_text", "Pasted JD content",
                "file_url", "/uploads/resumes/cv-secret-a.pdf"
        ));
        assertThat(createdJd.statusCode()).isEqualTo(201);
        JsonNode jdNode = json.read(createdJd.body());
        assertThat(jdNode.path("fileUrl").isNull()).isTrue();
    }

    @Test
    void strangerCannotAccessAnotherUsersSessionRawTextsTurnsCloneOrDocuments() throws Exception {
        // /api/v1/sessions/raw-texts must enforce ownership
        assertThat(send("GET", "/api/v1/sessions/raw-texts?resumeId=" + resumeA.getId(), tokenB, null).statusCode()).isEqualTo(403);
        assertThat(send("GET", "/api/v1/sessions/raw-texts?jdId=" + jdA.getId(), tokenB, null).statusCode()).isEqualTo(403);
        var ownRawTexts = send("GET", "/api/v1/sessions/raw-texts?resumeId=" + resumeA.getId() + "&jdId=" + jdA.getId(), tokenA, null);
        assertThat(ownRawTexts.statusCode()).isEqualTo(200);
        assertThat(ownRawTexts.body()).contains("Secret CV contents for User A");

        // Session read/update/delete/turns/clone
        assertThat(send("GET", "/api/v1/sessions/" + sessionA.getId(), tokenB, null).statusCode()).isEqualTo(403);
        assertThat(send("PUT", "/api/v1/sessions/" + sessionA.getId(), tokenB, Map.of("roleTitle", "Hacked")).statusCode()).isEqualTo(403);
        assertThat(send("DELETE", "/api/v1/sessions/" + sessionA.getId(), tokenB, null).statusCode()).isEqualTo(403);
        assertThat(send("GET", "/api/v1/sessions/" + sessionA.getId() + "/turns", tokenB, null).statusCode()).isEqualTo(403);
        assertThat(send("POST", "/api/v1/sessions/" + sessionA.getId() + "/turns", tokenB, Map.of("question", "Hijack?")).statusCode()).isEqualTo(403);
        assertThat(send("POST", "/api/v1/sessions/" + sessionA.getId() + "/clone", tokenB, null).statusCode()).isEqualTo(403);

        // User B cannot create a session referencing User A's sessionId, resumeId, or jdId
        assertThat(send("POST", "/api/v1/sessions", tokenB, Map.of("id", sessionA.getId(), "roleTitle", "Hijack")).statusCode()).isEqualTo(403);
        assertThat(send("POST", "/api/v1/sessions", tokenB, Map.of("resumeId", resumeA.getId().toString())).statusCode()).isEqualTo(403);
        assertThat(send("POST", "/api/v1/sessions", tokenB, Map.of("jdId", jdA.getId().toString())).statusCode()).isEqualTo(403);

        // User B cannot attach User A's CV/JD via DocumentUploadController or overwrite User A's session
        assertThat(sendMultipart("POST", "/api/v1/sessions/" + sessionA.getId() + "/documents", tokenB,
                Map.of("cvText", "Evil", "jdText", "Evil")).statusCode()).isEqualTo(403);
        assertThat(sendMultipart("POST", "/api/v1/sessions/new-session-b-" + UUID.randomUUID() + "/documents?resumeId=" + resumeA.getId(),
                tokenB, Map.of("jdText", "JD for B")).statusCode()).isEqualTo(403);

        // ApplicationProfile documents & StudyPlan resource download remain protected
        assertThat(send("GET", "/api/v1/application-profiles/" + profileIdA + "/documents", tokenB, null).statusCode()).isEqualTo(403);
        assertThat(send("GET", "/api/v1/application-profiles/" + profileIdA + "/documents", tokenA, null).statusCode()).isEqualTo(200);

        // User A can access own session and clone it cleanly
        assertThat(send("GET", "/api/v1/sessions/" + sessionA.getId(), tokenA, null).statusCode()).isEqualTo(200);
        var cloned = send("POST", "/api/v1/sessions/" + sessionA.getId() + "/clone", tokenA, null);
        assertThat(cloned.statusCode()).isEqualTo(200);
        assertThat(sessions.existsById(sessionA.getId())).isTrue();
    }

    @Test
    void strangerCannotDownloadOrDeleteAnotherUsersStudyResource() throws Exception {
        var task = studyPlanService.createTask(profileIdA, userA,
                new StudyPlanDtos.CreateTaskInput("Study SQL indexing", "sql", null, "TODO", 0, null, null, null, null));
        var file = new MockMultipartFile("file", "notes.txt", "text/plain",
                "Private study notes for User A".getBytes(StandardCharsets.UTF_8));
        var resource = studyPlanService.upload(profileIdA, task.id(), userA, "SQL Notes", file);

        String resourceBase = "/api/v1/application-profiles/" + profileIdA
                + "/study-plan/tasks/" + task.id() + "/resources/" + resource.id();

        assertThat(send("GET", resourceBase + "/file", tokenB, null).statusCode()).isEqualTo(403);
        assertThat(send("DELETE", resourceBase, tokenB, null).statusCode()).isEqualTo(403);

        var downloadA = send("GET", resourceBase + "/file", tokenA, null);
        assertThat(downloadA.statusCode()).isEqualTo(200);
        assertThat(downloadA.body()).isEqualTo("Private study notes for User A");

        assertThat(send("DELETE", resourceBase, tokenA, null).statusCode()).isEqualTo(204);
    }

    private HttpResponse<String> send(String method, String path, String token, Object body) throws Exception {
        var builder = HttpRequest.newBuilder(URI.create("http://localhost:" + port + path))
                .timeout(Duration.ofSeconds(15));
        if (token != null) {
            builder.header("Authorization", "Bearer " + token);
        }
        if (body != null) {
            builder.header("Content-Type", "application/json");
            builder.method(method, HttpRequest.BodyPublishers.ofString(json.tree(body).toString(), StandardCharsets.UTF_8));
        } else {
            builder.method(method, HttpRequest.BodyPublishers.noBody());
        }
        return http.send(builder.build(), HttpResponse.BodyHandlers.ofString(StandardCharsets.UTF_8));
    }

    private HttpResponse<String> sendMultipart(String method, String path, String token, Map<String, String> parts) throws Exception {
        String boundary = "----SmileAuthzTestBoundary" + UUID.randomUUID().toString().replace("-", "");
        StringBuilder sb = new StringBuilder();
        for (var entry : parts.entrySet()) {
            sb.append("--").append(boundary).append("\r\n")
                    .append("Content-Disposition: form-data; name=\"").append(entry.getKey()).append("\"\r\n\r\n")
                    .append(entry.getValue()).append("\r\n");
        }
        sb.append("--").append(boundary).append("--\r\n");
        var builder = HttpRequest.newBuilder(URI.create("http://localhost:" + port + path))
                .timeout(Duration.ofSeconds(15))
                .header("Authorization", "Bearer " + token)
                .header("Content-Type", "multipart/form-data; boundary=" + boundary)
                .method(method, HttpRequest.BodyPublishers.ofString(sb.toString(), StandardCharsets.UTF_8));
        return http.send(builder.build(), HttpResponse.BodyHandlers.ofString(StandardCharsets.UTF_8));
    }
}
