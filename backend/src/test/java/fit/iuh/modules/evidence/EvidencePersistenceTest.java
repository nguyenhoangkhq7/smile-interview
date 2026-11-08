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
                "pending_turn", Map.of("turn_id", "turn-1", "question", "Explain the query", "skill_id", "sql")));
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
        ((com.fasterxml.jackson.databind.node.ObjectNode) command.result().path("public").path("pending_turn"))
                .put("skill_id", "x".repeat(101));
        assertThatThrownBy(() -> store.commit(command)).isInstanceOf(RuntimeException.class);
        assertThat(runs.findById(sessionId).orElseThrow().getStateVersion()).isEqualTo(1);
        assertThat(commands.findBySessionIdAndRequestId(sessionId, command.requestId())).isEmpty();
    }
}
