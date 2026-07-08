package fit.iuh.modules.rulengine;

import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;
import org.springframework.stereotype.Repository;

import java.util.List;

/**
 * Repository for fetching evaluation criteria via a PostgreSQL {@code WITH RECURSIVE} CTE.
 *
 * <h2>Algorithm</h2>
 * <pre>
 *   1. Start at the leaf node matching {@code categoryName} (e.g., "BACKEND").
 *   2. Walk UP the adjacency-list tree to the root (e.g., "SOFTWARE_ENGINEERING").
 *   3. For each node in the path, collect all criteria mapped to it for the
 *      given {@code seniorityLevel} (or the fallback 'ALL' level).
 *   4. Return a flat list of {@link CriteriaWeightProjection} objects.
 * </pre>
 *
 * <h2>Deduplication Strategy</h2>
 * If a criterion appears in BOTH a specific seniority mapping AND an 'ALL' mapping,
 * the specific seniority mapping takes precedence (higher weight row wins via
 * {@code MAX(ccm.weight_percentage)} in the aggregate).
 *
 * <h2>Usage</h2>
 * <pre>{@code
 * List<CriteriaWeightProjection> criteria =
 *     jobCriteriaRepository.findCriteriaTreeByCategory("BACKEND", "FRESHER");
 * }</pre>
 */
@Repository
public interface JobCriteriaRepository extends JpaRepository<JobCategoryEntity, Long> {

    /**
     * Executes the recursive criteria lookup for a given job category and seniority level.
     *
     * <p>The query traverses the {@code job_categories} adjacency-list tree from
     * {@code categoryName} up to the root, then joins to
     * {@code category_criteria_mapping} filtering for rows where
     * {@code seniority_level = :seniorityLevel OR seniority_level = 'ALL'}.
     *
     * <p>Deduplication: if a criterion is mapped at multiple levels of the tree,
     * the row with the highest {@code weight_percentage} is kept (it represents
     * the most specific, most relevant override).
     *
     * @param categoryName   the {@link fit.iuh.modules.assessment.JobCategory} enum name (e.g., "BACKEND")
     * @param seniorityLevel the {@link fit.iuh.modules.assessment.SeniorityLevel} enum name (e.g., "FRESHER")
     * @return ordered list of criteria + weights, highest weight first
     */
    @Query(value = """
            WITH RECURSIVE category_tree AS (
                -- Anchor: start at the exact leaf node matching categoryName
                SELECT id, name, parent_id, 0 AS depth
                FROM job_categories
                WHERE name = :categoryName

                UNION ALL

                -- Recursive: walk up to each parent node
                SELECT jc.id, jc.name, jc.parent_id, ct.depth + 1
                FROM job_categories jc
                INNER JOIN category_tree ct ON jc.id = ct.parent_id
            ),
            mapped_criteria AS (
                SELECT
                    ec.id                  AS criteriaId,
                    ec.criteria_name       AS criteriaName,
                    ec.prompt_instruction  AS promptInstruction,
                    ccm.weight_percentage  AS weightPercentage,
                    ROW_NUMBER() OVER(
                        PARTITION BY ec.id
                        ORDER BY 
                            CASE WHEN ccm.seniority_level = :seniorityLevel THEN 1 ELSE 2 END ASC,
                            ct.depth ASC,
                            ccm.weight_percentage DESC
                    ) as rn
                FROM category_tree ct
                JOIN category_criteria_mapping ccm
                    ON ccm.job_category_id = ct.id
                    AND (ccm.seniority_level = :seniorityLevel OR ccm.seniority_level = 'ALL')
                JOIN evaluation_criteria ec
                    ON ec.id = ccm.criteria_id
            )
            SELECT criteriaId, criteriaName, promptInstruction, weightPercentage
            FROM mapped_criteria
            WHERE rn = 1
            ORDER BY weightPercentage DESC
            """,
            nativeQuery = true)
    List<CriteriaWeightProjection> findCriteriaTreeByCategory(
            @Param("categoryName") String categoryName,
            @Param("seniorityLevel") String seniorityLevel
    );

    /**
     * Spring Data JPA projection interface for the native query result set.
     * Maps directly to the aliases defined in the SELECT clause of the CTE query.
     */
    interface CriteriaWeightProjection {
        Long getCriteriaId();
        String getCriteriaName();
        String getPromptInstruction();
        Double getWeightPercentage();
    }
}
