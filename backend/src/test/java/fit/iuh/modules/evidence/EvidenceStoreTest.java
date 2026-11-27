package fit.iuh.modules.evidence;

import com.fasterxml.jackson.databind.ObjectMapper;
import fit.iuh.modules.session.entity.Session;
import fit.iuh.modules.session.repository.SessionRepository;
import fit.iuh.modules.session.repository.SessionTurnRepository;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.web.server.ResponseStatusException;
import java.util.Map;
import java.util.Optional;
import java.util.UUID;
import static org.assertj.core.api.Assertions.*;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.*;

class EvidenceStoreTest {
    private final InterviewRunRepository runs = mock(InterviewRunRepository.class);
    private final InterviewCommandRepository commands = mock(InterviewCommandRepository.class);
    private final SessionRepository sessions = mock(SessionRepository.class);
    private final SessionTurnRepository turns = mock(SessionTurnRepository.class);
    private final EvidenceJson json = new EvidenceJson(new ObjectMapper());
    private final EvidenceStore store = new EvidenceStore(runs, commands, sessions, turns, json,
            mock(EvidenceAdmission.class));

    @BeforeEach
    void setup() {
        when(sessions.lockById("session")).thenReturn(Optional.of(Session.builder().id("session").build()));
    }

    private InterviewRun existing(long version) {
        InterviewRun run = new InterviewRun();
        run.setStateVersion(version);
        run.setConfigJson("{}");
        run.setPublicJson("{\"state_version\":" + version + "}");
        return run;
    }

    private EvidenceStore.Commit commit(long expected, long actual) {
        var visible = json.read("{\"schema_version\":2,\"session_id\":\"session\",\"state_version\":" + actual
                + ",\"is_finished\":true,\"turns\":[],\"pending_turn\":null}");
        var result = json.tree(Map.of("snapshot", visible, "public", visible));
        return new EvidenceStore.Commit("session", expected, UUID.randomUUID(), "hash", json.read("{}"), result);
    }

    @Test
    void duplicateRequestReturnsPersistedResponseWithoutSaving() {
        var input = commit(1, 2);
        InterviewCommand command = new InterviewCommand();
        command.setRequestHash("hash"); command.setResponseJson("{\"state_version\":2}");
        when(commands.findBySessionIdAndRequestId("session", input.requestId())).thenReturn(Optional.of(command));
        assertThat(store.commit(input).path("state_version").asInt()).isEqualTo(2);
        verify(runs, never()).save(any());
    }

    @Test
    void reusingRequestIdForDifferentAnswerIsConflict() {
        UUID id = UUID.randomUUID();
        InterviewCommand command = new InterviewCommand(); command.setRequestHash("original");
        when(commands.findBySessionIdAndRequestId("session", id)).thenReturn(Optional.of(command));
        assertThatThrownBy(() -> store.replay("session", id, "different")).isInstanceOf(ResponseStatusException.class);
    }

    @Test
    void staleCommitCannotOverwriteNewerSnapshot() {
        when(runs.findById("session")).thenReturn(Optional.of(existing(2)));
        assertThatThrownBy(() -> store.commit(commit(1, 2))).isInstanceOf(ResponseStatusException.class);
        verify(runs, never()).save(any());
    }

    @Test
    void invalidAiVersionIsRejected() {
        when(runs.findById("session")).thenReturn(Optional.of(existing(1)));
        assertThatThrownBy(() -> store.commit(commit(1, 99))).isInstanceOf(ResponseStatusException.class);
        verify(commands, never()).save(any());
    }

    @Test
    void commitStoresSnapshotReceiptAndSessionStatus() {
        when(runs.findById("session")).thenReturn(Optional.of(existing(1)));
        assertThat(store.commit(commit(1, 2)).path("state_version").asInt()).isEqualTo(2);
        verify(runs).save(any()); verify(commands).save(any()); verify(sessions).save(any());
    }

    @Test
    void startLocksConfiguration() {
        var run = existing(1);
        run.setConfigJson("""
                {"mode":"FOCUSED","focused_question_mode":"DEBUGGING","max_questions":10,
                 "duration_seconds":900,"max_questions_per_objective":3}
                """);
        var matching = json.tree(new EvidenceDtos.Config(null, "DEBUGGING", 10, 900, 3));
        assertThat(store.sameStart(run, matching).path("state_version").asInt()).isEqualTo(1);
        var otherFocus = json.tree(new EvidenceDtos.Config(null, "DESIGN", 10, 900, 3));
        var otherCap = json.tree(new EvidenceDtos.Config(null, "DEBUGGING", 10, 900, 8));
        for (var changed : java.util.List.of(otherFocus, otherCap)) {
            assertThatThrownBy(() -> store.sameStart(run, changed))
                    .isInstanceOfSatisfying(ResponseStatusException.class,
                            ex -> assertThat(ex.getStatusCode().value()).isEqualTo(409));
        }
    }

    @Test void legacyConfigDefaultsToTextButCannotSwitchToVoice() {
        assertThat(store.sameStart(existing(1), json.read("{\"interaction_mode\":\"TEXT\"}"))
                .path("state_version").asInt()).isEqualTo(1);
        assertThatThrownBy(() -> store.sameStart(existing(1), json.read("{\"interaction_mode\":\"VOICE\"}")))
                .isInstanceOf(ResponseStatusException.class);
    }

    @Test void checklistReferencesSurviveJsonRoundTripAndRemainLocked() {
        var config = json.tree(Map.of("recheck", new EvidenceDtos.ChecklistRef(1L, 2L)));
        var run = existing(1);
        run.setConfigJson(config.toString());
        assertThat(store.sameStart(run, config).path("state_version").asInt()).isEqualTo(1);

        var base = commit(1, 2);
        var result = (com.fasterxml.jackson.databind.node.ObjectNode) base.result();
        var snapshot = (com.fasterxml.jackson.databind.node.ObjectNode) result.path("snapshot");
        var visible = (com.fasterxml.jackson.databind.node.ObjectNode) result.path("public");
        snapshot.set("config", json.read(config.toString()));
        visible.set("config", json.read(config.toString()));
        snapshot.putObject("recheck_target").put("criterion_id", "criterion");
        when(runs.findById("session")).thenReturn(Optional.of(run));
        var input = new EvidenceStore.Commit("session", 1, null, null, config, result);
        assertThat(store.commit(input).path("state_version").intValue()).isEqualTo(2);
        run.setStateVersion(1);
        visible.set("config", json.tree(Map.of("recheck", new EvidenceDtos.ChecklistRef(1L, 3L))));
        assertThatThrownBy(() -> store.commit(input)).isInstanceOfSatisfying(ResponseStatusException.class,
                ex -> assertThat(ex.getStatusCode().value()).isEqualTo(502));
    }

    @Test void aiCannotChangeTheFrozenInteractionMode() {
        when(runs.findById("session")).thenReturn(Optional.of(existing(1)));
        var original = commit(1, 2);
        var voiceCommit = new EvidenceStore.Commit(original.sessionId(), original.expectedVersion(), original.requestId(),
                original.requestHash(), json.read("{\"interaction_mode\":\"VOICE\"}"), original.result());
        assertThatThrownBy(() -> store.commit(voiceCommit)).isInstanceOf(ResponseStatusException.class);
        verify(runs, never()).save(any());
    }

    @Test void projectSessionLoadsTurnsOnceAndSkipsUnchangedTurnSaves() {
        when(runs.findById("session")).thenReturn(Optional.of(existing(1)));
        var unchanged = new fit.iuh.modules.session.entity.SessionTurn();
        unchanged.setId(10L);
        unchanged.setSessionId("session");
        unchanged.setExternalTurnId("t-1");
        unchanged.setQuestion("Q1");
        unchanged.setAnswer("A1");
        unchanged.setTopicTag("sql");
        unchanged.setIsDeepDive(false);
        when(turns.findBySessionIdOrderByIdAsc("session")).thenReturn(java.util.List.of(unchanged));

        var visible = json.read("""
            {"schema_version":2,"session_id":"session","state_version":2,"is_finished":false,
             "report":{"objectives":[{"objective_id":"obj-1","skill_id":"sql"}]},
             "turns":[{"turn_id":"t-1","objective_id":"obj-1","question":"Q1","answer":"A1"}],
             "pending_turn":{"turn_id":"t-2","objective_id":"obj-1","question":"Q2"}}
            """);
        var result = json.tree(Map.of("snapshot", visible, "public", visible));
        store.commit(new EvidenceStore.Commit("session", 1, UUID.randomUUID(), "hash", json.read("{}"), result));

        verify(turns, times(1)).findBySessionIdOrderByIdAsc("session");
        verify(turns, never()).findBySessionIdAndExternalTurnId(any(), any());
        var savedCaptor = org.mockito.ArgumentCaptor.forClass(fit.iuh.modules.session.entity.SessionTurn.class);
        verify(turns, times(1)).save(savedCaptor.capture());
        assertThat(savedCaptor.getValue().getExternalTurnId()).isEqualTo("t-2");
    }
}
