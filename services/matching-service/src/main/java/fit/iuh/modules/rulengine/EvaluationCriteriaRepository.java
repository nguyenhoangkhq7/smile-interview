package fit.iuh.modules.rulengine;

import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

/**
 * Spring Data JPA repository for {@link EvaluationCriteria}.
 * Provides standard CRUD operations and a unique-by-name lookup.
 */
@Repository
public interface EvaluationCriteriaRepository extends JpaRepository<EvaluationCriteria, Long> {

    /** Checks whether a criterion with the given name already exists. */
    boolean existsByCriteriaName(String criteriaName);
}
