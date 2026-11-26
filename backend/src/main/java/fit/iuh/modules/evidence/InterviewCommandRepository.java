package fit.iuh.modules.evidence;

import org.springframework.data.jpa.repository.JpaRepository;
import java.util.Optional;
import java.util.UUID;

public interface InterviewCommandRepository extends JpaRepository<InterviewCommand, UUID> {
    Optional<InterviewCommand> findBySessionIdAndRequestId(String sessionId, UUID requestId);
}
