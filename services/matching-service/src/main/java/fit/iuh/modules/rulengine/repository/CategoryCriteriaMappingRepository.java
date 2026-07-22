package fit.iuh.modules.rulengine.repository;

import fit.iuh.modules.rulengine.entity.CategoryCriteriaMapping;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

import java.util.Optional;

@Repository
public interface CategoryCriteriaMappingRepository extends JpaRepository<CategoryCriteriaMapping, Long> {

    Optional<CategoryCriteriaMapping> findByJobCategoryIdAndEvaluationCriteriaIdAndLevel(
            Long jobCategoryId,
            Long evaluationCriteriaId,
            String level
    );
}
