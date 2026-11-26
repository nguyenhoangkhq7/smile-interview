package fit.iuh.modules.application;

import fit.iuh.modules.auth.entity.User;
import fit.iuh.modules.evidence.InterviewRunRepository;
import fit.iuh.modules.session.repository.SessionRepository;
import org.junit.jupiter.api.Test;
import org.springframework.web.server.ResponseStatusException;
import java.util.*;
import static org.assertj.core.api.Assertions.*;
import static org.mockito.Mockito.*;

class ApplicationCompetencyServiceTest {
    @Test void verifiesOwnershipBeforeReadingInterviewEvidence() {
        var profiles = mock(ApplicationProfileRepository.class);
        var sessions = mock(SessionRepository.class);
        var runs = mock(InterviewRunRepository.class);
        var projection = mock(CompetencyProjection.class);
        var service = new ApplicationCompetencyService(profiles, sessions, runs, projection);
        var profile = new ApplicationProfile(); profile.setId(UUID.randomUUID()); profile.setUserId(UUID.randomUUID());
        when(profiles.findById(profile.getId())).thenReturn(Optional.of(profile));
        assertThatThrownBy(() -> service.get(profile.getId(), User.builder().id(UUID.randomUUID()).build()))
                .isInstanceOfSatisfying(ResponseStatusException.class, ex -> assertThat(ex.getStatusCode().value()).isEqualTo(403));
        assertThatThrownBy(() -> service.get(profile.getId(), null)).isInstanceOf(ResponseStatusException.class);
        verifyNoInteractions(sessions, runs, projection);
    }
}
