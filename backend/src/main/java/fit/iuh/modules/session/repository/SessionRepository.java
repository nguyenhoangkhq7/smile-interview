package fit.iuh.modules.session.repository;

import fit.iuh.modules.session.entity.Session;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

@Repository
public interface SessionRepository extends JpaRepository<Session, String> {

    java.util.List<Session> findByUserIdOrderByStartedAtDesc(java.util.UUID userId);

    java.util.List<Session> findAllByOrderByStartedAtDesc();
}
