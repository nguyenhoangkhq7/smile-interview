package fit.iuh.modules.rulengine;

import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;
import org.springframework.stereotype.Repository;

import java.util.List;

/**
 * Spring Data JPA repository for {@link CategoryCriteriaMapping}.
 * Uses the composite PK class {@link CategoryCriteriaMapping.CategoryCriteriaMappingId}.
 */
@Repository
public interface CategoryCriteriaMappingRepository
        extends JpaRepository<CategoryCriteriaMapping, CategoryCriteriaMapping.CategoryCriteriaMappingId> {

    /** Returns all mappings for a given job category. */
    List<CategoryCriteriaMapping> findByJobCategoryId(Long jobCategoryId);

    /** Returns all mappings for a given evaluation criterion. */
    List<CategoryCriteriaMapping> findByCriteriaId(Long criteriaId);

    /** Checks if a specific triple already exists. */
    boolean existsByJobCategoryIdAndCriteriaIdAndSeniorityLevel(
            Long jobCategoryId, Long criteriaId, String seniorityLevel);

    /** Deletes a specific mapping by its composite key. */
    @Query("DELETE FROM CategoryCriteriaMapping c WHERE c.jobCategoryId = :catId AND c.criteriaId = :crtId AND c.seniorityLevel = :level")
    @org.springframework.data.jpa.repository.Modifying
    @org.springframework.transaction.annotation.Transactional
    void deleteByCompositeKey(
            @Param("catId")  Long catId,
            @Param("crtId")  Long crtId,
            @Param("level")  String level);
}
