package fit.iuh.modules.rulengine.repository;

import fit.iuh.modules.rulengine.entity.CategoryCriteriaMapping;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;
import org.springframework.stereotype.Repository;

import java.util.List;

@Repository
public interface JobCriteriaRepository extends JpaRepository<CategoryCriteriaMapping, Long> {

    public interface CriteriaWeightProjection {
        Long getCriteriaId();
        String getCriteriaName();
        String getPromptInstruction();
        String getLevelPromptInstruction();
        Double getWeightPercentage();
        /** Pre-computed embedding JSON string from evaluation_criteria.embedding column. May be null. */
        String getEmbedding();
    }

    @Query(value = """
            WITH RECURSIVE category_tree AS (
                SELECT id, parent_id, code
                FROM job_categories
                WHERE code = :categoryCode

                UNION ALL

                SELECT c.id, c.parent_id, c.code
                FROM job_categories c
                INNER JOIN category_tree ct ON c.id = ct.parent_id
            )
            SELECT
                ec.id                     AS criteriaId,
                ec.name                   AS criteriaName,
                ec.prompt_instruction     AS promptInstruction,
                m.level_prompt_instruction AS levelPromptInstruction,
                m.weight_percentage       AS weightPercentage,
                ec.embedding              AS embedding
            FROM category_criteria_mapping m
            JOIN evaluation_criteria ec ON m.evaluation_criteria_id = ec.id
            JOIN category_tree ct ON m.job_category_id = ct.id
            WHERE (m.level = :seniorityLevel OR m.level = 'ALL')
            """, nativeQuery = true)
    List<CriteriaWeightProjection> findCriteriaTreeByCategory(
            @Param("categoryCode") String categoryCode,
            @Param("seniorityLevel") String seniorityLevel
    );
}
