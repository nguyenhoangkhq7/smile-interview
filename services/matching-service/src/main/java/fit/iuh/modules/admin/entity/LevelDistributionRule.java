package fit.iuh.modules.admin.entity;

import jakarta.persistence.*;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

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

    @Column(name = "level", nullable = false, unique = true, length = 20)
    private String level;

    @Column(name = "behavioral_pct", nullable = false)
    private Double behavioralPct;

    @Column(name = "technical_pct", nullable = false)
    private Double technicalPct;

    @Column(name = "coding_pct", nullable = false)
    private Double codingPct;

    @Column(name = "system_design_pct", nullable = false)
    private Double systemDesignPct;

    @Column(name = "total_questions")
    private Integer totalQuestions;
}
