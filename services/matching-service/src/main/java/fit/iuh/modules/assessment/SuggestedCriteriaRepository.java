package fit.iuh.modules.assessment;

import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

import java.util.Optional;

@Repository
public interface SuggestedCriteriaRepository extends JpaRepository<SuggestedCriteria, Long> {
    Optional<SuggestedCriteria> findByJobCategoryAndCriteriaNameIgnoreCase(JobCategory jobCategory, String criteriaName);
}
