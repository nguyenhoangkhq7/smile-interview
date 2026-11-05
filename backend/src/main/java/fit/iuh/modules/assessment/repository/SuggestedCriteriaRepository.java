package fit.iuh.modules.assessment.repository;

import fit.iuh.modules.assessment.entity.JobCategory;
import fit.iuh.modules.assessment.entity.SuggestedCriteria;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.Optional;

public interface SuggestedCriteriaRepository extends JpaRepository<SuggestedCriteria, Long> {

    Optional<SuggestedCriteria> findByJobCategoryAndCriteriaNameIgnoreCase(
            JobCategory jobCategory,
            String criteriaName
    );
}
