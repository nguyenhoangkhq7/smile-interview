package fit.iuh.modules.session.repository;

import fit.iuh.modules.session.entity.Session;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

@Repository
public interface SessionRepository extends JpaRepository<Session, String> {

    java.util.List<Session> findByApplicationProfileIdOrderByAttemptNumberDesc(java.util.UUID profileId);

    @org.springframework.data.jpa.repository.Lock(jakarta.persistence.LockModeType.PESSIMISTIC_WRITE)
    @org.springframework.data.jpa.repository.Query("select s from Session s where s.id = :id")
    java.util.Optional<Session> lockById(@org.springframework.data.repository.query.Param("id") String id);

    java.util.List<Session> findByUserIdOrderByStartedAtDesc(java.util.UUID userId);

    java.util.List<Session> findAllByOrderByStartedAtDesc();
}
