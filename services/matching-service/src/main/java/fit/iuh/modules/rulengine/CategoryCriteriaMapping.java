package fit.iuh.modules.rulengine;

import jakarta.persistence.*;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.io.Serializable;

/**
 * JPA Entity for the {@code category_criteria_mapping} junction table.
 *
 * <p>Maps an {@link EvaluationCriteria} to a {@link JobCategoryEntity} with a specific
 * {@code weightPercentage} and {@code seniorityLevel}. The composite primary key
 * {@code (job_category_id, criteria_id, seniority_level)} ensures a category can have
 * different weight sets for different experience levels.
 *
 * <p>The special value {@code seniority_level = 'ALL'} applies to every seniority level
 * unless a more specific row exists for that level.
 */
@Entity
@Table(name = "category_criteria_mapping")
@IdClass(CategoryCriteriaMapping.CategoryCriteriaMappingId.class)
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class CategoryCriteriaMapping {

    @Id
    @Column(name = "job_category_id", nullable = false)
    private Long jobCategoryId;

    @Id
    @Column(name = "criteria_id", nullable = false)
    private Long criteriaId;

    @Id
    @Column(name = "seniority_level", nullable = false, length = 20)
    private String seniorityLevel;

    /**
     * Relative weight of this criterion within the category+level combination (0-100).
     * {@link fit.iuh.modules.assessment.ScoringService} normalises these weights
     * so they do not need to sum to exactly 100.
     */
    @Column(name = "weight_percentage", nullable = false)
    private Double weightPercentage;

    /**
     * Composite primary key class for {@link CategoryCriteriaMapping}.
     */
    @Data
    @NoArgsConstructor
    @AllArgsConstructor
    public static class CategoryCriteriaMappingId implements Serializable {
        private Long jobCategoryId;
        private Long criteriaId;
        private String seniorityLevel;
    }
}
