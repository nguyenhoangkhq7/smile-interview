package fit.iuh.modules.rulengine.repository;

import fit.iuh.modules.rulengine.entity.CategoryCriteriaMapping;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;
import org.springframework.stereotype.Repository;

import java.util.List;

@Repository
public interface JobCriteriaRepository extends JpaRepository<CategoryCriteriaMapping, Long> {

    /**
     * Projection of criteria data needed for assessment.
     * <p>
     * {@code sourceDepth} indicates where in the ancestor chain the criterion originates:
     * <ul>
     *   <li>0 = the leaf (most-specific) category requested — tagged [SPECIFIC_SKILLS] in the prompt</li>
     *   <li>≥1 = an ancestor category — tagged [CORE_SKILLS] in the prompt</li>
     * </ul>
     */
    public interface CriteriaWeightProjection {
        Long getCriteriaId();
        String getCriteriaName();
        String getPromptInstruction();
        String getLevelPromptInstruction();
        Double getWeightPercentage();
        /** Pre-computed embedding JSON string from evaluation_criteria.embedding column. May be null. */
        String getEmbedding();
        /**
         * Ancestry depth of the category that owns this criterion.
         * 0 = the target/leaf category, 1 = its parent, 2 = grandparent, etc.
         */
        Integer getSourceDepth();
    }

    @com.fasterxml.jackson.annotation.JsonIgnoreProperties(ignoreUnknown = true)
    public record ConcreteCriteriaWeightDto(
        Long criteriaId,
        String criteriaName,
        String promptInstruction,
        String levelPromptInstruction,
        Double weightPercentage,
        String embedding,
        Integer sourceDepth
    ) implements CriteriaWeightProjection, java.io.Serializable {
        @java.io.Serial
        private static final long serialVersionUID = 1L;

        @Override public Long getCriteriaId() { return criteriaId; }
        @Override public String getCriteriaName() { return criteriaName; }
        @Override public String getPromptInstruction() { return promptInstruction; }
        @Override public String getLevelPromptInstruction() { return levelPromptInstruction; }
        @Override public Double getWeightPercentage() { return weightPercentage; }
        @Override public String getEmbedding() { return embedding; }
        @Override public Integer getSourceDepth() { return sourceDepth; }

        public static ConcreteCriteriaWeightDto from(CriteriaWeightProjection p) {
            if (p == null) return null;
            if (p instanceof ConcreteCriteriaWeightDto dto) return dto;
            return new ConcreteCriteriaWeightDto(
                p.getCriteriaId(),
                p.getCriteriaName(),
                p.getPromptInstruction(),
                p.getLevelPromptInstruction(),
                p.getWeightPercentage(),
                p.getEmbedding(),
                p.getSourceDepth()
            );
        }
    }

    /**
     * Recursive CTE that walks the job_category tree upward from the given category code,
     * collecting ALL criteria (direct + inherited) in a single query.
     *
     * <p>The CTE is seeded at depth=0 (the leaf category) and each parent join increments depth,
     * so child rows appear first in the result set. Combined with {@code putIfAbsent} deduplication
     * in Java, this ensures child criteria override parent criteria for the same criteria_id.</p>
     *
     * @param categoryCode    the leaf job-category code (e.g. "SPRING_BACKEND", "BACKEND")
     * @param seniorityLevel  the candidate seniority level (e.g. "JUNIOR") — also matches "ALL"
     */
    @Query(value = """
            WITH RECURSIVE category_tree AS (
                SELECT id, parent_id, code, 0 AS source_depth
                FROM job_categories
                WHERE code = :categoryCode

                UNION ALL

                SELECT c.id, c.parent_id, c.code, ct.source_depth + 1
                FROM job_categories c
                INNER JOIN category_tree ct ON c.id = ct.parent_id
            )
            SELECT
                ec.id                      AS criteriaId,
                ec.name                    AS criteriaName,
                ec.prompt_instruction      AS promptInstruction,
                m.level_prompt_instruction AS levelPromptInstruction,
                m.weight_percentage        AS weightPercentage,
                ec.embedding               AS embedding,
                ct.source_depth            AS sourceDepth
            FROM category_criteria_mapping m
            JOIN evaluation_criteria ec ON m.evaluation_criteria_id = ec.id
            JOIN category_tree ct       ON m.job_category_id = ct.id
            WHERE (
                m.level = :seniorityLevel
                OR (
                    m.level = 'ALL'
                    AND NOT EXISTS (
                        SELECT 1
                        FROM category_criteria_mapping m2
                        WHERE m2.job_category_id      = m.job_category_id
                          AND m2.evaluation_criteria_id = m.evaluation_criteria_id
                          AND m2.level                  = :seniorityLevel
                    )
                )
            )
            ORDER BY ct.source_depth ASC
            """, nativeQuery = true)
    List<CriteriaWeightProjection> findCriteriaTreeByCategory(
            @Param("categoryCode") String categoryCode,
            @Param("seniorityLevel") String seniorityLevel
    );
}
