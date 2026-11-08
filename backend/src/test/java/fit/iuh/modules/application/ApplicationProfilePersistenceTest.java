package fit.iuh.modules.application;

import fit.iuh.modules.auth.entity.*;
import fit.iuh.modules.auth.repository.UserRepository;
import fit.iuh.modules.evidence.*;
import fit.iuh.modules.session.entity.*;
import fit.iuh.modules.session.repository.*;
import org.junit.jupiter.api.*;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import java.time.LocalDateTime;
import java.util.*;
import java.util.concurrent.*;
import static org.assertj.core.api.Assertions.*;

/** Runs against disposable PostgreSQL via scripts/verify-evidence-backend.ps1. */
@SpringBootTest
class ApplicationProfilePersistenceTest {
    @Autowired ApplicationProfileService service;
    @Autowired ApplicationProfileRepository profiles;
    @Autowired SessionRepository sessions;
    @Autowired UserRepository users;
    @Autowired ResumeRepository resumes;
    @Autowired JobDescriptionRepository jds;
    @Autowired EvidenceStore store;
    @Autowired EvidenceJson json;
    @Autowired ApplicationCompetencyService competency;
    @Autowired fit.iuh.modules.auth.security.JwtService jwt;
    @Autowired org.springframework.web.context.WebApplicationContext webContext;
    private User user;
    private Resume resume;
    private JobDescription jd;
    private String sourceId;

    @BeforeEach void setup() {
        user = users.save(User.builder().username("Profile test").email(UUID.randomUUID() + "@test.local")
                .password("test").role(Role.USER).build());
        resume = resumes.save(Resume.builder().id(UUID.randomUUID()).userId(user.getId()).fileName("cv.pdf")
                .rawText("CV baseline").createdAt(LocalDateTime.now()).build());
        jd = jds.save(JobDescription.builder().id(UUID.randomUUID()).userId(user.getId()).title("Backend")
                .rawText("JD baseline").createdAt(LocalDateTime.now()).build());
        sourceId = "profile-test-" + UUID.randomUUID();
        sessions.save(Session.builder().id(sourceId).userId(user.getId()).resume(resume).jobDescription(jd)
                .roleTitle("Backend").status("Not started").startedAt(LocalDateTime.now())
                .skillGapJson("[{\"jd_skill_id\":\"sql\",\"job_tasks\":[],\"jd_evidence_spans\":[],\"importance_weight\":1}]")
                .gapReportJson("{}").build());
    }

    @AfterEach void cleanup() {
        var owned = profiles.findByUserIdOrderByCreatedAtDesc(user.getId());
        for (var profile : owned) {
            sessions.deleteAll(sessions.findByApplicationProfileIdOrderByAttemptNumberDesc(profile.getId()));
            profiles.deleteById(profile.getId());
        }
        if (sessions.existsById(sourceId)) sessions.deleteById(sourceId);
        resumes.deleteById(resume.getId()); jds.deleteById(jd.getId()); users.deleteById(user.getId());
    }

    @Test void profileAndFrozenRubricSurviveTransactionsAndConcurrentCreationReturnsOneAttempt() throws Exception {
        var profile = service.create(user, new ApplicationProfileService.Create(sourceId, "Backend · A", "A"));
        assertThat(profile.attempts()).hasSize(1);
        assertThat(service.create(user, new ApplicationProfileService.Create(sourceId, "Backend · A", "A")).id()).isEqualTo(profile.id());
        String payload = "{\"schema_version\":2,\"session_id\":\"" + sourceId
                + "\",\"state_version\":1,\"is_finished\":true,\"turns\":[],\"report\":{\"termination_reason\":\"USER_STOP\"},"
                + "\"objectives\":{\"sql\":{\"objective\":{\"skill_id\":\"sql\",\"criteria\":[]}}},\"policy\":{}}";
        var visible = json.read(payload);
        store.commit(new EvidenceStore.Commit(sourceId, 0, null, null, json.read("{}"),
                json.tree(Map.of("snapshot", visible, "public", visible))));
        var stored = profiles.findById(profile.id()).orElseThrow();
        assertThat(json.read(stored.getBlueprintJson()).path("objectives")).hasSize(1);
        assertThat(stored.getCvText()).isEqualTo("CV baseline");
        assertThat(sessions.findById(sourceId).orElseThrow().getStatus()).isEqualTo("Cancelled");
        assertThat(json.tree(service.get(profile.id(), user)).path("createdAt").isTextual()).isTrue();
        resume.setRawText("Changed CV"); resume.setFileName("new-cv.pdf"); resumes.save(resume);
        assertThat(profiles.findById(profile.id()).orElseThrow().getCvText()).isEqualTo("CV baseline");
        assertThat(service.get(profile.id(), user).cvFilename()).isEqualTo("cv.pdf");

        CountDownLatch gate = new CountDownLatch(1);
        try (ExecutorService executor = Executors.newFixedThreadPool(2)) {
            Callable<String> create = () -> { gate.await(); return service.newAttempt(profile.id(), user).id(); };
            var first = executor.submit(create); var second = executor.submit(create);
            gate.countDown();
            assertThat(first.get(15, TimeUnit.SECONDS)).isEqualTo(second.get(15, TimeUnit.SECONDS));
        }
        var result = service.get(profile.id(), user);
        assertThat(result.attempts()).hasSize(2);
        assertThat(result.attempts().getFirst().number()).isEqualTo(2);
        assertThat(result.attempts().getFirst().answeredCount()).isZero();
        assertThat(result.attempts().getLast().status()).isEqualTo("Cancelled");
    }

    @Test void competencyUpdatesFromCommittedInterviewAndIsAvailableThroughAuthenticatedHttp() throws Exception {
        var profile = service.create(user, new ApplicationProfileService.Create(sourceId, "SQL preparation", "A"));
        assertThat(competency.get(profile.id(), user).summary().notAssessed()).isEqualTo(1);
        String baseline = profiles.findById(profile.id()).orElseThrow().getSkillGapJson();
        var snapshot = json.read("""
                {"schema_version":2,"session_id":"%s","state_version":1,"is_finished":true,
                 "report":{"termination_reason":"PLAN_COMPLETE"},"policy":{},
                 "turns":[{"turn_id":"sql-turn","objective_id":"sql-task","answer":"Use EXPLAIN ANALYZE",
                   "question":{"text":"How do you inspect a slow SQL query?","assistance":"NONE"}}],
                 "objectives":{"sql-task":{
                   "objective":{"objective_id":"sql-task","skill_id":"sql","claim":"Inspect SQL queries",
                     "rubric_fingerprint":"sql-v1","target_depth":3,
                     "criteria":[{"criterion_id":"sql-c1","description":"Inspect execution plan","essential":true}]},
                   "assessment":"DEMONSTRATED_AT_TARGET","lifecycle":"CLOSED","turns_spent":1,"contradictions":[],
                   "evidence_history":[{"turn_id":"sql-turn","criterion_id":"sql-c1","independent":true,
                     "question_depth":3,"evidence_scope":"slow-query-a","observation":"SUPPORTS",
                     "performance":"AT_TARGET","response_excerpt":"EXPLAIN ANALYZE","rationale":"Uses a concrete verification tool"}]
                 }}}
                """.formatted(sourceId));
        store.commit(new EvidenceStore.Commit(sourceId, 0, null, null, json.read("{}"),
                json.tree(Map.of("snapshot", snapshot, "public", snapshot))));
        var updated = competency.get(profile.id(), user);
        assertThat(updated.summary().meetingTarget()).isEqualTo(1);
        assertThat(updated.skills().getFirst().objectives().getFirst().criteria().getFirst().evidence().getFirst()
                .source().sessionId()).isEqualTo(sourceId);
        assertThat(profiles.findById(profile.id()).orElseThrow().getSkillGapJson()).isEqualTo(baseline);

        var mvc = org.springframework.test.web.servlet.setup.MockMvcBuilders.webAppContextSetup(webContext)
                .addFilters(webContext.getBean("springSecurityFilterChain", jakarta.servlet.Filter.class)).build();
        String endpoint = "/api/v1/application-profiles/" + profile.id() + "/competency";
        mvc.perform(org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get(endpoint))
                .andExpect(org.springframework.test.web.servlet.result.MockMvcResultMatchers.status().isUnauthorized());
        mvc.perform(org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get(endpoint)
                .header("Authorization", "Bearer " + jwt.generateToken(user)))
                .andExpect(org.springframework.test.web.servlet.result.MockMvcResultMatchers.status().isOk())
                .andExpect(org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath("$.summary.meetingTarget").value(1))
                .andExpect(org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath("$.lastAssessment.sessionId").value(sourceId));
    }
}
