package fit.iuh.modules.session.repository;

import fit.iuh.modules.session.entity.Session;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;
import org.springframework.stereotype.Repository;

import java.util.Optional;

@Repository
public interface SessionRepository extends JpaRepository<Session, String> {

    @Query("SELECT s.id FROM Session s " +
           "WHERE s.resume.id = :resumeId " +
           "AND s.jobDescription.id = :jdId " +
           "AND s.id != :sessionId " +
           "AND s.assessmentId IS NOT NULL " +
           "ORDER BY s.startedAt DESC LIMIT 1")
    Optional<String> findSessionByResumeIdAndJdId(
            @Param("resumeId") java.util.UUID resumeId,
            @Param("jdId") java.util.UUID jdId,
            @Param("sessionId") String sessionId
    );

    @Query("SELECT s.id FROM Session s " +
           "WHERE s.resume.parsedContent = :cvContent " +
           "AND s.jobDescription.parsedContent = :jdContent " +
           "AND s.id != :sessionId " +
           "AND s.assessmentId IS NOT NULL " +
           "ORDER BY s.startedAt DESC LIMIT 1")
    Optional<String> findSessionWithSameContentAndAssessment(
            @Param("cvContent") String cvContent,
            @Param("jdContent") String jdContent,
            @Param("sessionId") String sessionId
    );
    java.util.List<Session> findByUserIdOrderByStartedAtDesc(java.util.UUID userId);

    java.util.List<Session> findAllByOrderByStartedAtDesc();
}
