package fit.iuh.modules.application;

import fit.iuh.modules.session.repository.SessionRepository;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Component;
import org.springframework.transaction.annotation.Transactional;
import java.time.LocalDateTime;

@Component
@RequiredArgsConstructor
@Slf4j
public class ApplicationProfilePurgeJob {
    private final ApplicationProfileRepository profiles;
    private final SessionRepository sessions;

    @Scheduled(fixedDelayString = "${app.application-profile.purge-ms:3600000}")
    @Transactional
    public void purgeExpiredProfiles() {
        var expired = profiles.findExpired(LocalDateTime.now().minusDays(30));
        if (expired.isEmpty()) return;

        for (var profile : expired) {
            sessions.deleteByApplicationProfileId(profile.getId());
        }
        profiles.deleteByIds(expired.stream().map(ApplicationProfile::getId).toList());
        log.info("Permanently deleted {} expired application profiles", expired.size());
    }
}
