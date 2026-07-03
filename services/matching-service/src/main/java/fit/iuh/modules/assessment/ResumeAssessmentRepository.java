package fit.iuh.modules.assessment;

import fit.iuh.modules.assessment.ResumeAssessment;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

import java.util.Optional;
import java.util.UUID;

/**
 * Spring Data JPA repository for {@link ResumeAssessment} entities.
 *
 * <p>Provides standard CRUD operations via {@link JpaRepository} plus a
 * session-scoped lookup used by the Cache-Aside pattern in
 * {@code AssessmentService} to avoid redundant LLM API calls.
 */
@Repository
public interface ResumeAssessmentRepository extends JpaRepository<ResumeAssessment, UUID> {

    /**
     * Finds a previously persisted assessment for the given interview session.
     *
     * <p>Used by the Cache-Aside pattern: if a result already exists for this
     * {@code sessionId}, it is returned immediately without calling the LLM API.
     *
     * @param sessionId the unique interview session identifier
     * @return an {@link Optional} containing the cached assessment, or empty if none
     */
    Optional<ResumeAssessment> findBySessionId(String sessionId);

    /**
     * Checks whether an assessment result already exists for the given session.
     *
     * @param sessionId the unique interview session identifier
     * @return {@code true} if a cached assessment exists
     */
    boolean existsBySessionId(String sessionId);

    /**
     * Deletes the cached assessment for a session, allowing re-assessment.
     *
     * @param sessionId the unique interview session identifier
     */
    void deleteBySessionId(String sessionId);
}
