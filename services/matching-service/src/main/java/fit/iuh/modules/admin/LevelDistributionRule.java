package fit.iuh.modules.admin;

import jakarta.persistence.*;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

/**
 * JPA Entity for the {@code level_distribution_rules} table.
 *
 * <p>Each row represents the base question-category percentage distribution
 * for one {@link fit.iuh.modules.assessment.SeniorityLevel}. This entity
 * replaces the hardcoded {@code switch-case} in
 * {@link fit.iuh.modules.questionbank.DifficultyDistributor}.
 *
 * <h3>Runtime Semantics</h3>
 * The four percentage fields ({@code behavioralPct}, {@code technicalPct},
 * {@code codingPct}, {@code systemDesignPct}) are <em>relative weights</em>,
 * not strict totals. {@code DifficultyDistributor} normalises them at runtime,
 * so they do not need to sum to exactly 100.
 */
@Entity
@Table(name = "level_distribution_rules")
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class LevelDistributionRule {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    @Column(name = "id", updatable = false, nullable = false)
    private Long id;

    /**
     * Maps to {@link fit.iuh.modules.assessment.SeniorityLevel} enum name.
     * Unique constraint enforces one row per seniority level.
     */
    @Column(name = "level", nullable = false, unique = true, length = 20)
    private String level;

    /** Base percentage for behavioral questions (0–100). */
    @Column(name = "behavioral_pct", nullable = false)
    private Double behavioralPct;

    /** Base percentage for technical questions (0–100). */
    @Column(name = "technical_pct", nullable = false)
    private Double technicalPct;

    /** Base percentage for coding questions (0–100). */
    @Column(name = "coding_pct", nullable = false)
    private Double codingPct;

    /** Base percentage for system design questions (0–100). */
    @Column(name = "system_design_pct", nullable = false)
    private Double systemDesignPct;
}
