package fit.iuh.modules.session.repository;

import fit.iuh.modules.session.entity.SessionTurn;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

import java.util.List;

@Repository
public interface SessionTurnRepository extends JpaRepository<SessionTurn, Long> {
    java.util.Optional<SessionTurn> findBySessionIdAndExternalTurnId(String sessionId, String externalTurnId);
    List<SessionTurn> findBySessionIdOrderByIdAsc(String sessionId);
    void deleteBySessionId(String sessionId);
}
