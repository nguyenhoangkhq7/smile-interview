package fit.iuh.modules.evidence;

import com.fasterxml.jackson.databind.ObjectMapper;
import fit.iuh.modules.auth.entity.User;
import fit.iuh.modules.session.entity.Session;
import fit.iuh.modules.session.repository.SessionRepository;
import fit.iuh.modules.session.repository.SessionTurnRepository;
import org.junit.jupiter.api.Test;
import org.springframework.web.server.ResponseStatusException;
import java.util.Optional;
import java.util.UUID;
import static org.assertj.core.api.Assertions.*;
import static org.mockito.Mockito.*;

class EvidenceServiceTest {
    private final SessionRepository sessions = mock(SessionRepository.class);
    private final SessionTurnRepository turns = mock(SessionTurnRepository.class);
    private final InterviewRunRepository runs = mock(InterviewRunRepository.class);
    private final EvidenceStore store = mock(EvidenceStore.class);
    private final EvidenceAiClient ai = mock(EvidenceAiClient.class);
    private final EvidenceInputs inputs = mock(EvidenceInputs.class);
    private final EvidenceJson json = new EvidenceJson(new ObjectMapper());
    private final EvidenceService service = new EvidenceService(sessions, turns, runs, store, ai, inputs, json);
    private final User owner = User.builder().id(UUID.randomUUID()).build();

    private void session() {
        when(sessions.findById("s")).thenReturn(Optional.of(Session.builder().id("s").userId(owner.getId()).build()));
    }

    @Test void ownerIsCheckedBeforeReturningAReplay() {
        session();
        var answer = new EvidenceDtos.Answer(UUID.randomUUID(), "turn", 1, "answer");
        assertThatThrownBy(() -> service.respond("s", User.builder().id(UUID.randomUUID()).build(), answer))
                .isInstanceOfSatisfying(ResponseStatusException.class, ex -> assertThat(ex.getStatusCode().value()).isEqualTo(403));
        verifyNoInteractions(store, ai);
    }

    @Test void repeatedAnswerReturnsReceiptWithoutCallingAi() {
        session();
        var answer = new EvidenceDtos.Answer(UUID.randomUUID(), "turn", 1, "answer");
        var saved = json.read("{\"state_version\":2}");
        when(store.replay("s", answer.requestId(), json.hash(answer))).thenReturn(saved);
        assertThat(service.respond("s", owner, answer)).isEqualTo(saved);
        verifyNoInteractions(ai, runs);
    }

    @Test void staleAnswerIsRejectedBeforeModelCall() {
        session();
        InterviewRun run = new InterviewRun(); run.setStateVersion(2);
        when(runs.findById("s")).thenReturn(Optional.of(run));
        var answer = new EvidenceDtos.Answer(UUID.randomUUID(), "turn", 1, "answer");
        assertThatThrownBy(() -> service.respond("s", owner, answer)).isInstanceOf(ResponseStatusException.class);
        verifyNoInteractions(ai);
    }

    @Test void repeatedStartReusesFrozenConfigurationAndPlan() {
        session();
        InterviewRun run = new InterviewRun();
        when(runs.findById("s")).thenReturn(Optional.of(run));
        var config = EvidenceDtos.Config.defaults();
        service.start("s", owner, config);
        verify(store).sameStart(run, json.tree(config));
        verifyNoInteractions(ai, inputs);
    }
}
