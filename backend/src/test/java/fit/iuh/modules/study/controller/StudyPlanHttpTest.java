package fit.iuh.modules.study.controller;

import com.fasterxml.jackson.databind.JsonNode;
import fit.iuh.modules.application.ApplicationProfileRepository;
import fit.iuh.modules.application.ApplicationProfileService;
import fit.iuh.modules.auth.entity.Role;
import fit.iuh.modules.auth.entity.User;
import fit.iuh.modules.auth.repository.UserRepository;
import fit.iuh.modules.auth.security.JwtService;
import fit.iuh.modules.evidence.EvidenceJson;
import fit.iuh.modules.evidence.InterviewRun;
import fit.iuh.modules.evidence.InterviewRunRepository;
import fit.iuh.modules.session.entity.JobDescription;
import fit.iuh.modules.session.entity.Resume;
import fit.iuh.modules.session.entity.Session;
import fit.iuh.modules.session.repository.JobDescriptionRepository;
import fit.iuh.modules.session.repository.ResumeRepository;
import fit.iuh.modules.session.repository.SessionRepository;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.test.web.server.LocalServerPort;
import org.springframework.jdbc.core.simple.JdbcClient;

import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.time.Duration;
import java.time.LocalDateTime;
import java.util.Map;
import java.util.UUID;
import java.util.concurrent.CompletableFuture;

import static org.assertj.core.api.Assertions.assertThat;

@SpringBootTest(webEnvironment = SpringBootTest.WebEnvironment.RANDOM_PORT)
class StudyPlanHttpTest {
    private static final String OBJECTIVE = """
            {"objective_id":"sql-task","skill_id":"sql","claim":"Inspect SQL queries",
             "rubric_fingerprint":"sql-v1","target_depth":3,
             "criteria":[{"criterion_id":"sql-c1","description":"Inspect execution plan","essential":true}]}
            """;

    @LocalServerPort int port;
    @Autowired UserRepository users;
    @Autowired ResumeRepository resumes;
    @Autowired JobDescriptionRepository descriptions;
    @Autowired SessionRepository sessions;
    @Autowired ApplicationProfileService applicationService;
    @Autowired ApplicationProfileRepository profiles;
    @Autowired InterviewRunRepository runs;
    @Autowired JwtService jwt;
    @Autowired EvidenceJson json;
    @Autowired JdbcClient jdbc;
    private final HttpClient http = HttpClient.newHttpClient();
    private User owner;
    private User stranger;
    private Resume resume;
    private JobDescription jd;
    private UUID profileId;
    private String sessionId;

    @BeforeEach void seedProfile() {
        owner = user();
        stranger = user();
        resume = resumes.save(Resume.builder().id(UUID.randomUUID()).userId(owner.getId()).fileName("cv.pdf")
                .rawText("CV baseline").createdAt(LocalDateTime.now()).build());
        jd = descriptions.save(JobDescription.builder().id(UUID.randomUUID()).userId(owner.getId()).title("Backend")
                .rawText("JD baseline").createdAt(LocalDateTime.now()).build());
        sessionId = UUID.randomUUID().toString();
        sessions.save(Session.builder().id(sessionId).userId(owner.getId()).resume(resume).jobDescription(jd)
                .roleTitle("Backend").status("Not started").startedAt(LocalDateTime.now())
                .skillGapJson("""
                        [{"jd_skill_id":"sql","semantic_alignment":"MISSING","job_tasks":[],"jd_evidence_spans":[],"importance_weight":1},
                         {"jd_skill_id":"java","semantic_alignment":"MISSING","job_tasks":[],"jd_evidence_spans":[],"importance_weight":1}]
                        """).gapReportJson("{}").build());
        profileId = applicationService.create(owner, new ApplicationProfileService.Create(sessionId, "Backend", null)).id();
        var profile = profiles.findById(profileId).orElseThrow();
        profile.setBlueprintJson("{\"objectives\":[" + OBJECTIVE + "]}");
        profiles.save(profile);
    }

    @AfterEach void cleanFixture() {
        sessions.deleteAll(sessions.findByApplicationProfileIdOrderByAttemptNumberDesc(profileId));
        profiles.deleteById(profileId);
        resumes.deleteById(resume.getId());
        descriptions.deleteById(jd.getId());
        users.deleteAll(java.util.List.of(owner, stranger));
    }

    @Test void ownerCanManageTasksChecklistLinksAndFilesWithPersistentProgress() throws Exception {
        assertThat(send("GET", "", null, null).statusCode()).isEqualTo(401);
        assertThat(send("GET", "", stranger, null).statusCode()).isEqualTo(403);
        var empty = body(send("GET", "", owner, null), 200);
        assertThat(empty.at("/plan/id").isNull()).isTrue();
        assertThat(empty.at("/plan/targetCompletionPercent").asInt()).isEqualTo(80);
        assertThat(empty.at("/progress/percent").isNull()).isTrue();

        body(send("POST", "/tasks", owner, task("unknown-skill", "TODO")), 400);
        body(send("POST", "/tasks", owner, task("sql", "InProg")), 400);
        assertThat(body(send("GET", "", owner, null), 200).at("/plan/id").isNull()).isTrue();
        long taskId = body(send("POST", "/tasks", owner, task("sql", "TODO")), 201).path("id").asLong();
        long otherId = body(send("POST", "/tasks", owner, task(null, "TODO")), 201).path("id").asLong();
        String task = "/tasks/" + taskId;
        assertThat(send("PUT", task, stranger, task("sql", "DONE")).statusCode()).isEqualTo(403);
        var checklist = body(send("POST", task + "/checklist", owner, Map.of("content", "Read EXPLAIN")), 201);
        long itemId = checklist.path("id").asLong();
        String item = task + "/checklist/" + itemId;
        assertThat(body(send("PUT", item, owner, Map.of("content", "Read EXPLAIN", "isCompleted", true)), 200)
                .path("completedAt").isTextual()).isTrue();
        assertThat(body(send("GET", "", owner, null), 200).at("/progress/percent").asInt()).isZero();
        assertThat(send("DELETE", "/tasks/" + otherId + "/checklist/" + itemId, owner, null).statusCode()).isEqualTo(404);

        body(send("POST", task + "/resources", owner, Map.of("title", "Invalid", "url", "javascript:alert(1)")), 400);
        var link = body(send("POST", task + "/resources", owner, Map.of("title", "Docs", "url", "https://example.org/docs")), 201);
        String linkPath = task + "/resources/" + link.path("id").asLong();
        assertThat(body(send("PUT", linkPath, owner, Map.of("title", "Updated docs", "url", "https://example.org/sql")), 200)
                .path("url").asText()).endsWith("/sql");
        assertThat(send("DELETE", linkPath, owner, null).statusCode()).isEqualTo(204);

        String multipart = "--fixture\r\nContent-Disposition: form-data; name=\"file\"; filename=\"notes.txt\"\r\n"
                + "Content-Type: text/plain\r\n\r\nSQL notes\r\n--fixture--\r\n";
        var resource = body(http.send(request(task + "/resources/upload", owner)
                        .header("Content-Type", "multipart/form-data; boundary=fixture")
                        .POST(HttpRequest.BodyPublishers.ofString(multipart)).build(), HttpResponse.BodyHandlers.ofString()), 201);
        String filePath = task + "/resources/" + resource.path("id").asLong() + "/file";
        assertThat(send("GET", filePath, stranger, null).statusCode()).isEqualTo(403);
        var file = send("GET", filePath, owner, null);
        assertThat(file.statusCode()).isEqualTo(200);
        assertThat(file.body()).isEqualTo("SQL notes");
        assertThat(file.headers().firstValue("Content-Disposition")).hasValueSatisfying(value -> assertThat(value).startsWith("attachment"));

        assertThat(body(send("PUT", task, owner, task("sql", "IN_PROGRESS")), 200).path("completedAt").isNull()).isTrue();
        var finished = body(send("PUT", task, owner, task("sql", "DONE")), 200);
        assertThat(finished.path("completedAt").isTextual()).isTrue();
        var plan = body(send("GET", "", owner, null), 200);
        assertThat(plan.at("/tasks/0/task/notes").asText()).isEqualTo("Review the execution plan");
        assertThat(plan.at("/tasks/0/checklist/0/isCompleted").asBoolean()).isTrue();
        assertThat(plan.at("/tasks/0/resources/0/fileName").asText()).isEqualTo("notes.txt");
        assertThat(plan.at("/progress/percent").asInt()).isEqualTo(50);
        assertThat(plan.at("/progress/meetsTarget").asBoolean()).isFalse();
        assertThat(body(send("PUT", "", owner, Map.of("title", "SQL plan", "targetCompletionPercent", 50,
                "targetDate", "2027-01-01")), 200).at("/progress/meetsTarget").asBoolean()).isTrue();
        assertThat(body(send("PUT", task, owner, task("sql", "TODO")), 200).path("completedAt").isNull()).isTrue();
        assertThat(send("DELETE", task, owner, null).statusCode()).isEqualTo(204);
        assertThat(send("GET", filePath, owner, null).statusCode()).isEqualTo(404);
        assertThat(jdbc.sql("SELECT count(*) FROM study_task_checklist_items WHERE task_id = :id")
                .param("id", taskId).query(Long.class).single()).isZero();
    }

    @Test void knowledgeGapsOnlyUseFinalizedInterviewEvidence() throws Exception {
        String path = "/knowledge-gaps";
        assertThat(send("GET", path, stranger, null).statusCode()).isEqualTo(403);
        var baseline = body(send("GET", path, owner, null), 200);
        assertThat(baseline.path("weak")).isEmpty();
        assertThat(baseline.path("reportWeaknesses")).isEmpty();
        assertThat(baseline.path("notAssessedSkillIds").toString()).isEqualTo("[\"sql\",\"java\"]");
        var plan = Map.of("title", "Interview practice", "targetCompletionPercent", 80, "sourceSessionId", sessionId);
        body(send("PUT", "", owner, plan), 400);

        saveInterview(false);
        var running = body(send("GET", path, owner, null), 200);
        assertThat(running.path("weak")).isEmpty();
        assertThat(running.path("reportWeaknesses")).isEmpty();
        saveInterview(true);
        var result = body(send("GET", path, owner, null), 200);
        assertThat(result.path("completedAttempts").asInt()).isEqualTo(1);
        assertThat(result.path("weak").size()).isEqualTo(1);
        assertThat(result.at("/weak/0/skillId").asText()).isEqualTo("sql");
        var evidence = result.at("/weak/0/objectives/0/criteria/0/evidence/0");
        assertThat(evidence.at("/source/sessionId").asText()).isEqualTo(sessionId);
        assertThat(evidence.path("rationale").asText()).isEqualTo("Cannot explain the execution plan");
        var finding = result.at("/reportWeaknesses/0");
        assertThat(finding.path("skillId").asText()).isEqualTo("sql");
        assertThat(finding.path("sessionId").asText()).isEqualTo(sessionId);
        assertThat(finding.path("attemptNumber").asInt()).isEqualTo(1);
        assertThat(finding.path("weaknesses")).hasSize(1);
        assertThat(finding.at("/weaknesses/0").asText()).isEqualTo("Needs practice interpreting an execution plan");
        assertThat(result.path("notAssessedSkillIds").toString()).isEqualTo("[\"java\"]");
        assertThat(body(send("PUT", "", owner, plan), 200).at("/plan/sourceSessionId").asText()).isEqualTo(sessionId);
        body(send("PUT", "", owner, Map.of("title", "SQL plan", "targetCompletionPercent", 80,
                "sourceSessionId", "unrelated-session")), 400);
    }

    @Test void simultaneousFirstTasksShareOneActivePlan() throws Exception {
        var request = request("/tasks", owner).header("Content-Type", "application/json")
                .POST(HttpRequest.BodyPublishers.ofString(json.tree(task(null, "TODO")).toString())).build();
        var first = http.sendAsync(request, HttpResponse.BodyHandlers.ofString());
        var second = http.sendAsync(request, HttpResponse.BodyHandlers.ofString());
        CompletableFuture.allOf(first, second).join();
        var firstTask = body(first.join(), 201);
        var secondTask = body(second.join(), 201);
        assertThat(firstTask.path("planId").asLong()).isEqualTo(secondTask.path("planId").asLong());
        assertThat(firstTask.path("id").asLong()).isNotEqualTo(secondTask.path("id").asLong());
        assertThat(body(send("GET", "", owner, null), 200).at("/progress/total").asInt()).isEqualTo(2);
    }

    @Test void taskCreationPersistsInitialDetailsAndListProgressIsScopedToOwner() throws Exception {
        var input = new java.util.HashMap<String, Object>(task("sql", "DONE"));
        input.put("checklist", java.util.List.of(Map.of("content", "Read the query plan", "sortOrder", 0)));
        input.put("resource", Map.of("title", "SQL guide", "url", "javascript:alert(1)"));
        body(send("POST", "/tasks", owner, input), 400);
        assertThat(body(send("GET", "", owner, null), 200).at("/plan/id").isNull()).isTrue();

        input.put("resource", Map.of("title", "SQL guide", "url", "https://example.org/sql"));
        body(send("POST", "/tasks", owner, input), 201);
        var plan = body(send("GET", "", owner, null), 200);
        assertThat(plan.at("/tasks/0/checklist/0/content").asText()).isEqualTo("Read the query plan");
        assertThat(plan.at("/tasks/0/resources/0/title").asText()).isEqualTo("SQL guide");
        var summary = body(sendProgress(owner), 200);
        assertThat(summary.at("/0/applicationProfileId").asText()).isEqualTo(profileId.toString());
        assertThat(summary.at("/0/progress/percent").asInt()).isEqualTo(100);
        assertThat(body(sendProgress(stranger), 200)).isEmpty();
    }

    @Test void movingTasksPersistsOrderAndStatus() throws Exception {
        long first = body(send("POST", "/tasks", owner, task("sql", "TODO")), 201).path("id").asLong();
        long second = body(send("POST", "/tasks", owner, task("sql", "TODO")), 201).path("id").asLong();
        String position = "/tasks/" + second + "/position";
        assertThat(send("PUT", position, owner, Map.of("status", "TODO", "beforeTaskId", first)).statusCode()).isEqualTo(204);
        var ordered = body(send("GET", "", owner, null), 200);
        assertThat(ordered.at("/tasks/0/task/id").asLong()).isEqualTo(second);
        assertThat(ordered.at("/tasks/1/task/id").asLong()).isEqualTo(first);

        body(send("PUT", position, owner, Map.of("status", "DONE", "beforeTaskId", first)), 404);
        assertThat(send("PUT", position, owner, Map.of("status", "DONE")).statusCode()).isEqualTo(204);
        var finished = body(send("GET", "", owner, null), 200);
        assertThat(finished.at("/progress/done").asInt()).isEqualTo(1);
        assertThat(finished.at("/tasks/0/task/completedAt").isTextual()).isTrue();
    }

    @Test void childTasksKeepTheirParentAndSurviveParentDeletion() throws Exception {
        long parentId = body(send("POST", "/tasks", owner, task("sql", "TODO")), 201).path("id").asLong();
        var input = new java.util.HashMap<String, Object>(task("sql", "TODO"));
        input.put("parentTaskId", Long.MAX_VALUE);
        body(send("POST", "/tasks", owner, input), 404);
        input.put("parentTaskId", parentId);
        var child = body(send("POST", "/tasks", owner, input), 201);
        assertThat(child.path("parentTaskId").asLong()).isEqualTo(parentId);
        String childPath = "/tasks/" + child.path("id").asLong();
        assertThat(body(send("PUT", childPath, owner, task("sql", "DONE")), 200)
                .path("parentTaskId").asLong()).isEqualTo(parentId);
        assertThat(body(send("GET", "", owner, null), 200).at("/tasks/1/task/parentTaskId").asLong()).isEqualTo(parentId);

        assertThat(send("DELETE", "/tasks/" + parentId, owner, null).statusCode()).isEqualTo(204);
        var remaining = body(send("GET", "", owner, null), 200);
        assertThat(remaining.at("/tasks/0/task/id").asLong()).isEqualTo(child.path("id").asLong());
        assertThat(remaining.at("/tasks/0/task/parentTaskId").isNull()).isTrue();
    }

    private void saveInterview(boolean finished) {
        String snapshot = """
                {"is_finished":%s,
                 "turns":[{"turn_id":"sql-turn","objective_id":"sql-task","answer":"I do not know",
                   "question":{"text":"How do you inspect a slow SQL query?","assistance":"NONE"}}],
                 "objectives":{"sql-task":{
                   "objective":%s,"assessment":"DEMONSTRATED_BELOW_TARGET","lifecycle":"CLOSED","turns_spent":1,
                   "contradictions":[],
                   "evidence_history":[{"turn_id":"sql-turn","criterion_id":"sql-c1","independent":true,
                     "question_depth":3,"evidence_scope":"slow-query-a","observation":"CONTRADICTS",
                     "performance":"BELOW","response_excerpt":"I do not know","rationale":"Cannot explain the execution plan"}]
                 }}}
                """.formatted(finished, OBJECTIVE);
        var run = new InterviewRun();
        run.setSessionId(sessionId);
        run.setStateVersion(finished ? 2L : 1L);
        run.setConfigJson("{}");
        run.setSnapshotJson(snapshot);
        var publicState = (com.fasterxml.jackson.databind.node.ObjectNode) json.read(snapshot);
        publicState.set("report", json.read("""
                {"objectives":[{"skill_id":"sql","assessment":"DEMONSTRATED_BELOW_TARGET",
                    "weaknesses":["Needs practice interpreting an execution plan","Needs practice interpreting an execution plan"]}]}
                """));
        run.setPublicJson(publicState.toString());
        runs.save(run);
        var session = sessions.findById(sessionId).orElseThrow();
        session.setStatus(finished ? "Completed" : "In progress");
        session.setEndedAt(finished ? LocalDateTime.now() : null);
        sessions.save(session);
    }

    private User user() {
        return users.save(User.builder().username("Study test").email(UUID.randomUUID() + "@test.local")
                .password("test").role(Role.USER).build());
    }

    private HttpRequest.Builder request(String suffix, User user) {
        var request = HttpRequest.newBuilder(URI.create("http://127.0.0.1:" + port
                + "/api/v1/application-profiles/" + profileId + "/study-plan" + suffix)).timeout(Duration.ofSeconds(15));
        return user == null ? request : request.header("Authorization", "Bearer " + jwt.generateToken(user));
    }

    private HttpResponse<String> sendProgress(User user) throws Exception {
        var url = URI.create("http://127.0.0.1:" + port + "/api/v1/application-profiles/study-plan-progress");
        var request = HttpRequest.newBuilder(url).timeout(Duration.ofSeconds(15))
                .header("Authorization", "Bearer " + jwt.generateToken(user)).GET().build();
        return http.send(request, HttpResponse.BodyHandlers.ofString());
    }

    private HttpResponse<String> send(String method, String suffix, User user, Object payload) throws Exception {
        var request = request(suffix, user);
        if (payload != null) request.header("Content-Type", "application/json");
        return http.send(request.method(method, payload == null ? HttpRequest.BodyPublishers.noBody()
                : HttpRequest.BodyPublishers.ofString(json.tree(payload).toString())).build(), HttpResponse.BodyHandlers.ofString());
    }

    private JsonNode body(HttpResponse<String> response, int status) {
        assertThat(response.statusCode()).as("response: %s", response.body()).isEqualTo(status);
        return json.read(response.body());
    }

    private Map<String, String> task(String skill, String status) {
        var task = new java.util.HashMap<>(Map.of("title", "Explain SQL", "notes", "Review the execution plan", "status", status));
        if (skill != null) task.put("skillId", skill);
        return task;
    }
}
