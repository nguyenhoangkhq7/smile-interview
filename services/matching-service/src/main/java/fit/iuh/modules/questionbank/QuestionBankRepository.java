package fit.iuh.modules.questionbank;

import fit.iuh.modules.questionbank.QuestionBank;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

import java.util.List;
import java.util.UUID;

/**
 * Spring Data JPA repository for {@link QuestionBank} entities.
 *
 * <p>Supports lookup by session ID for retrieving previously generated
 * question banks, and standard CRUD for regeneration updates.
 */
@Repository
public interface QuestionBankRepository extends JpaRepository<QuestionBank, UUID> {

    /**
     * Finds all question banks generated for a given interview session,
     * ordered by creation time (newest first).
     *
     * @param sessionId the unique interview session identifier
     * @return list of question banks, possibly empty
     */
    List<QuestionBank> findBySessionIdOrderByCreatedAtDesc(String sessionId);

    /**
     * Checks whether any question bank exists for the given session.
     *
     * @param sessionId the unique interview session identifier
     * @return {@code true} if at least one question bank exists
     */
    boolean existsBySessionId(String sessionId);
}
