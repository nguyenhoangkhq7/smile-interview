package fit.iuh.modules.application;

import fit.iuh.modules.auth.entity.User;
import fit.iuh.modules.evidence.InterviewRunRepository;
import fit.iuh.modules.session.repository.SessionRepository;
import lombok.RequiredArgsConstructor;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.server.ResponseStatusException;
import java.util.Objects;
import java.util.UUID;

@Service @RequiredArgsConstructor
public class ApplicationCompetencyService {
    private final ApplicationProfileRepository profiles;
    private final SessionRepository sessions;
    private final InterviewRunRepository runs;
    private final CompetencyProjection projection;

    @Transactional(readOnly = true)
    public CompetencyProjection.View get(UUID id, User user) {
        var profile = profiles.findById(id).orElseThrow(() -> new ResponseStatusException(HttpStatus.NOT_FOUND, "Application profile not found"));
        if (user == null || !Objects.equals(profile.getUserId(), user.getId()))
            throw new ResponseStatusException(HttpStatus.FORBIDDEN, "This application profile belongs to another user");
        var attempts = sessions.findByApplicationProfileIdOrderByAttemptNumberDesc(id);
        return projection.project(profile, attempts, runs.findAllById(attempts.stream().map(s -> s.getId()).toList()));
    }
}
