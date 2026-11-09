package fit.iuh.modules.evidence;

import com.fasterxml.jackson.databind.ObjectMapper;
import fit.iuh.modules.adaptive.controller.AdaptiveInterviewController;
import fit.iuh.modules.session.entity.Session;
import fit.iuh.modules.session.repository.SessionRepository;
import org.junit.jupiter.api.Test;
import org.springframework.web.server.ResponseStatusException;
import java.util.Optional;
import static org.assertj.core.api.Assertions.*;
import static org.mockito.Mockito.*;

class RetiredInterviewTest {
    @Test void executionIsGoneWithoutCallingRepositoriesOrAi() {
        var sessions = mock(SessionRepository.class);
        var runs = mock(InterviewRunRepository.class);
        var controller = new AdaptiveInterviewController(sessions, new ObjectMapper(), runs);
        assertThatThrownBy(() -> controller.retired("old"))
                .isInstanceOfSatisfying(ResponseStatusException.class, error ->
                        assertThat(error.getStatusCode().value()).isEqualTo(410));
        verifyNoInteractions(sessions, runs);
    }

    @Test void archivedReportRemainsReadableWithoutAnAiCall() {
        var sessions = mock(SessionRepository.class);
        var runs = mock(InterviewRunRepository.class);
        var session = new Session();
        session.setInterviewReportJson("{\"session_id\":\"old\",\"total_turns\":3}");
        when(sessions.findById("old")).thenReturn(Optional.of(session));
        var controller = new AdaptiveInterviewController(sessions, new ObjectMapper(), runs);
        assertThat(controller.archivedReport("old").getBody()).containsEntry("total_turns", 3);
    }
}
