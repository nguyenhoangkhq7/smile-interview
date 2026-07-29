package fit.iuh.modules.rulengine.entity;

import jakarta.persistence.*;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

@Entity
@Table(
        name = "category_criteria_mapping",
        uniqueConstraints = {
                @UniqueConstraint(
                        name = "uk_cat_crit_level",
                        columnNames = {"job_category_id", "evaluation_criteria_id", "level"}
                )
        }
)
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class CategoryCriteriaMapping {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    @Column(name = "id", updatable = false, nullable = false)
    private Long id;

    @ManyToOne(fetch = FetchType.LAZY, optional = false)
    @JoinColumn(name = "job_category_id", nullable = false)
    private JobCategoryEntity jobCategory;

    @ManyToOne(fetch = FetchType.LAZY, optional = false)
    @JoinColumn(name = "evaluation_criteria_id", nullable = false)
    private EvaluationCriteria evaluationCriteria;

    @Column(name = "level", nullable = false, length = 20)
    private String level;

    @Column(name = "weight_percentage", nullable = false)
    private Double weightPercentage;

    @Column(name = "level_prompt_instruction", columnDefinition = "TEXT")
    private String levelPromptInstruction;
}
