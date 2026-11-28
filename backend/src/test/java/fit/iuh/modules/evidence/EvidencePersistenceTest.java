package fit.iuh.modules.evidence;

import com.fasterxml.jackson.databind.JsonNode;
import fit.iuh.modules.session.entity.Session;
import fit.iuh.modules.session.repository.SessionRepository;
import fit.iuh.modules.session.repository.SessionTurnRepository;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.web.server.ResponseStatusException;
import java.time.LocalDateTime;
import java.util.Map;
import java.util.UUID;
import java.util.concurrent.*;
import static org.assertj.core.api.Assertions.*;

/** Requires a disposable PostgreSQL database; see scripts/verify-evidence-backend.ps1. */
@SpringBootTest
class EvidencePersistenceTest {
    @Autowired private EvidenceStore store;
    @Autowired private EvidenceJson json;
    @Autowired private SessionRepository sessions;
    @Autowired private InterviewRunRepository runs;
    @Autowired private InterviewCommandRepository commands;
    @Autowired private SessionTurnRepository turns;
    @Autowired private fit.iuh.config.AppProperties properties;
    @Autowired private org.springframework.web.servlet.mvc.method.annotation.RequestMappingHandlerAdapter mvc;
    private String sessionId;

    @BeforeEach void createSession() {
        sessionId = "test-evidence-" + UUID.randomUUID();
        sessions.save(Session.builder().id(sessionId).status("Not started").startedAt(LocalDateTime.now()).build());
        store.commit(input(0, null));
    }

    @AfterEach void removeSession() { sessions.deleteById(sessionId); }

    private EvidenceStore.Commit input(long version, UUID requestId) {
        var visible = json.tree(Map.of("schema_version", 2, "session_id", sessionId,
                "state_version", version + 1, "is_finished", false, "turns", java.util.List.of(),
                "pending_turn", Map.of("turn_id", "turn-1", "objective_id", "obj-1", "question", "Explain the query"),
                "report", Map.of("objectives", java.util.List.of(Map.of("objective_id", "obj-1", "skill_id", "sql")))));
        return new EvidenceStore.Commit(sessionId, version, requestId, "hash", json.read("{}"),
                json.tree(Map.of("snapshot", visible, "public", visible)));
    }

    @Test void snapshotAndReceiptSurviveSeparateTransactions() {
        var command = input(1, UUID.randomUUID());
        JsonNode response = store.commit(command);
        assertThat(store.commit(command)).isEqualTo(response);
        assertThat(runs.findById(sessionId).orElseThrow().getStateVersion()).isEqualTo(2);
        assertThat(commands.findBySessionIdAndRequestId(sessionId, command.requestId())).isPresent();
        assertThat(turns.findBySessionIdOrderByIdAsc(sessionId)).hasSize(1);
    }

    @Test void acceptedAnswerSurvivesReloadRetryAndAnExpiredWorkerLease() {
        var received = java.time.Instant.now();
        deadline(received.plusSeconds(5));
        var answer = new EvidenceDtos.Answer(UUID.randomUUID(), "turn-1", 1, "saved answer");
        var ack = store.acceptAnswer(sessionId, answer, received);
        assertThat(ack.path("submission").path("status").asText()).isEqualTo("QUEUED");
        assertThat(ack.path("paused_remaining_seconds").asDouble()).isEqualTo(5.0);
        assertThat(json.read(runs.findById(sessionId).orElseThrow().getPublicJson())).isEqualTo(ack);
        assertThat(store.acceptAnswer(sessionId, answer, received.plusSeconds(20))).isEqualTo(ack);
        assertThatThrownBy(() -> store.acceptAnswer(sessionId,
                new EvidenceDtos.Answer(UUID.randomUUID(), "turn-1", 1, "different"), received))
                .isInstanceOf(ResponseStatusException.class);
        var first = store.claimAnswer(java.time.Duration.ZERO);
        var second = store.claimAnswer(java.time.Duration.ofMinutes(1));
        assertThat(second.payload().path("candidate_response").asText()).isEqualTo("saved answer");
        assertThat(second.payload().path("received_at").asText()).isEqualTo(received.toString());
        assertThat(second.attempt()).isEqualTo(2);
        assertThat(store.claimAnswer(java.time.Duration.ofMinutes(1))).isNull();
        var transition = input(2, null).result();
        store.completeGrading(first, transition);
        assertThat(runs.findById(sessionId).orElseThrow().getStateVersion()).isEqualTo(2);
        store.completeGrading(second, transition);
        assertThat(runs.findById(sessionId).orElseThrow().getStateVersion()).isEqualTo(3);
        assertThat(store.acceptAnswer(sessionId, answer, received).hasNonNull("submission")).isFalse();
    }

    private void deadline(java.time.Instant at) {
        var run = runs.findById(sessionId).orElseThrow();
        var snapshot = (com.fasterxml.jackson.databind.node.ObjectNode) json.read(run.getSnapshotJson());
        snapshot.put("deadline_at", at.toString());
        run.setSnapshotJson(snapshot.toString());
        runs.saveAndFlush(run);
    }

    @Test void workerGradesTheSavedAnswerWithoutAnotherBrowserRequest() {
        var received = java.time.Instant.now();
        deadline(received.plusSeconds(60));
        store.acceptAnswer(sessionId, new EvidenceDtos.Answer(UUID.randomUUID(), "turn-1", 1, "my answer"), received);
        var ai = org.mockito.Mockito.mock(EvidenceAiClient.class);
        org.mockito.Mockito.when(ai.compute(org.mockito.ArgumentMatchers.eq("respond"), org.mockito.ArgumentMatchers.any()))
                .thenAnswer(call -> {
                    JsonNode payload = call.getArgument(1);
                    assertThat(payload.path("candidate_response").asText()).isEqualTo("my answer");
                    JsonNode result = input(2, null).result();
                    for (String view : java.util.List.of("snapshot", "public")) {
                        var state = (com.fasterxml.jackson.databind.node.ObjectNode) result.path(view);
                        state.putNull("pending_turn");
                        var turn = state.putArray("turns").addObject();
                        turn.put("turn_id", "turn-1").put("answer", "my answer");
                        if ("snapshot".equals(view)) {
                            state.put("next_question_action", "FOLLOW_UP");
                            turn.putObject("judgment");
                        } else state.put("awaiting_question", true);
                    }
                    return result;
                });
        var worker = new InterviewGradingWorker(store, ai, properties);
        try {
            worker.poll();
            org.awaitility.Awaitility.await().atMost(java.time.Duration.ofSeconds(10)).untilAsserted(() -> {
                var visible = json.read(runs.findById(sessionId).orElseThrow().getPublicJson());
                assertThat(visible.path("awaiting_question").asBoolean()).isTrue();
                assertThat(visible.hasNonNull("submission")).isFalse();
                assertThat(visible.path("turns").size()).isEqualTo(1);
            });
        } finally { worker.shutdown(); }
    }

    @Test void failedGradingCanRetryOnlyTheSavedAnswerAtTheOriginalTime() {
        var received = java.time.Instant.now().minusSeconds(10);
        deadline(received.plusSeconds(5));
        store.acceptAnswer(sessionId, new EvidenceDtos.Answer(UUID.randomUUID(), "turn-1", 1, "original"), received);
        for (int n = 1; n <= 3; n++) {
            var job = store.claimAnswer(java.time.Duration.ofMinutes(1));
            assertThat(job.attempt()).isEqualTo(n);
            store.gradingFailed(job);
            if (n < 3) {
                var run = runs.findById(sessionId).orElseThrow();
                run.setGradingDueAt(received);
                runs.saveAndFlush(run);
            }
        }
        var failed = json.read(runs.findById(sessionId).orElseThrow().getPublicJson());
        assertThat(failed.path("submission").path("status").asText()).isEqualTo("FAILED");
        assertThatThrownBy(() -> store.acceptAnswer(sessionId,
                new EvidenceDtos.Answer(UUID.randomUUID(), "turn-1", 2, "changed"), java.time.Instant.now()))
                .isInstanceOf(ResponseStatusException.class);
        var retried = store.acceptAnswer(sessionId,
                new EvidenceDtos.Answer(UUID.randomUUID(), "turn-1", 2, "original"), java.time.Instant.now());
        assertThat(retried.path("paused_remaining_seconds").asDouble()).isEqualTo(5.0);
        assertThat(retried.path("state_version").asInt()).isEqualTo(3);
        assertThat(store.claimAnswer(java.time.Duration.ofMinutes(1)).payload().path("received_at").asText())
                .isEqualTo(received.toString());
    }

    @Test @SuppressWarnings("unchecked")
    void publicJsonUsesTheConfiguredMvcConverter() throws Exception {
        JsonNode value = json.read("{\"schema_version\":2,\"session_id\":\"test\"}");
        var service = org.mockito.Mockito.mock(EvidenceService.class);
        org.mockito.Mockito.when(service.read("test", null)).thenReturn(value);
        String body = new EvidenceController(service).read("test", null);
        var converter = (org.springframework.http.converter.HttpMessageConverter<String>) mvc.getMessageConverters().stream()
                .filter(c -> c.canWrite(String.class, org.springframework.http.MediaType.APPLICATION_JSON)).findFirst().orElseThrow();
        var output = new org.springframework.mock.http.MockHttpOutputMessage();
        converter.write(body, org.springframework.http.MediaType.APPLICATION_JSON, output);
        assertThat(json.read(output.getBodyAsString())).isEqualTo(value);
    }

    @Test void concurrentAnswersCommitExactlyOnce() throws Exception {
        CountDownLatch gate = new CountDownLatch(1);
        try (ExecutorService executor = Executors.newFixedThreadPool(2)) {
            Callable<Integer> call = () -> {
                gate.await();
                try { store.commit(input(1, UUID.randomUUID())); return 200; }
                catch (ResponseStatusException ex) { return ex.getStatusCode().value(); }
            };
            Future<Integer> first = executor.submit(call), second = executor.submit(call);
            gate.countDown();
            assertThat(java.util.List.of(first.get(15, TimeUnit.SECONDS), second.get(15, TimeUnit.SECONDS)))
                    .containsExactlyInAnyOrder(200, 409);
        }
        assertThat(runs.findById(sessionId).orElseThrow().getStateVersion()).isEqualTo(2);
    }

    @Test void failedProjectionRollsBackSnapshotAndReceipt() {
        var command = input(1, UUID.randomUUID());
        ((com.fasterxml.jackson.databind.node.ObjectNode) command.result().path("public").path("report")
                .path("objectives").get(0))
                .put("skill_id", "x".repeat(101));
        assertThatThrownBy(() -> store.commit(command)).isInstanceOf(RuntimeException.class);
        assertThat(runs.findById(sessionId).orElseThrow().getStateVersion()).isEqualTo(1);
        assertThat(commands.findBySessionIdAndRequestId(sessionId, command.requestId())).isEmpty();
    }
}
