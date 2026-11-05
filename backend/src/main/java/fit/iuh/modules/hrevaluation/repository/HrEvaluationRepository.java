package fit.iuh.modules.hrevaluation.repository;

import fit.iuh.modules.hrevaluation.entity.HrEvaluation;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

import java.util.List;
import java.util.UUID;

/**
 * Spring Data JPA repository for {@link HrEvaluation} entities.
 *
 * <p>All CRUD operations are inherited from {@link JpaRepository}.
 * Custom queries are added here as the feature grows.
 */
@Repository
public interface HrEvaluationRepository extends JpaRepository<HrEvaluation, UUID> {

    /**
     * Returns all evaluations for a given session, ordered by submission time descending.
     *
     * @param sessionId the interview session identifier
     * @return list of evaluations (may be empty)
     */
    List<HrEvaluation> findBySessionIdOrderByCreatedAtDesc(String sessionId);

    /**
     * Returns all evaluations submitted by all HRs, ordered by submission time descending.
     *
     * @return list of all evaluations
     */
    List<HrEvaluation> findAllByOrderByCreatedAtDesc();
}
