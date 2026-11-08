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
    private final EvidenceStore store = new EvidenceStore(runs, commands, sessions, turns, json);

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
        assertThat(store.sameStart(existing(1), json.read("{}")).path("state_version").asInt()).isEqualTo(1);
        assertThatThrownBy(() -> store.sameStart(existing(1), json.read("{\"mode\":\"FOCUSED\"}")))
                .isInstanceOf(ResponseStatusException.class);
    }

    @Test void legacyConfigDefaultsToTextButCannotSwitchToVoice() {
        assertThat(store.sameStart(existing(1), json.read("{\"interaction_mode\":\"TEXT\"}"))
                .path("state_version").asInt()).isEqualTo(1);
        assertThatThrownBy(() -> store.sameStart(existing(1), json.read("{\"interaction_mode\":\"VOICE\"}")))
                .isInstanceOf(ResponseStatusException.class);
    }

    @Test void aiCannotChangeTheFrozenInteractionMode() {
        when(runs.findById("session")).thenReturn(Optional.of(existing(1)));
        var original = commit(1, 2);
        var voiceCommit = new EvidenceStore.Commit(original.sessionId(), original.expectedVersion(), original.requestId(),
                original.requestHash(), json.read("{\"interaction_mode\":\"VOICE\"}"), original.result());
        assertThatThrownBy(() -> store.commit(voiceCommit)).isInstanceOf(ResponseStatusException.class);
        verify(runs, never()).save(any());
    }
}
