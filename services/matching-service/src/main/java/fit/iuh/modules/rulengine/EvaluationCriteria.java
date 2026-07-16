package fit.iuh.modules.rulengine;

import jakarta.persistence.*;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

/**
 * JPA Entity for the {@code evaluation_criteria} table.
 *
 * <p>Each row represents one assessment dimension. The {@code promptInstruction} field is
 * injected <em>verbatim</em> into the LLM assessment prompt via
 * {@link fit.iuh.modules.assessment.AssessmentService}, telling the LLM exactly what
 * evidence to search for when evaluating that criterion.
 *
 * <p>This design (storing instructions in DB, not hardcoded in Java) enables the team
 * to tune, add, or remove criteria without a code deployment.
 */
@Entity
@Table(name = "evaluation_criteria")
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class EvaluationCriteria {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    @Column(name = "id", updatable = false, nullable = false)
    private Long id;

    /**
     * Human-readable criterion name used in the UI and stored in
     * {@code evidence_items} JSONB (e.g., "Tech Stack Alignment").
     */
    @Column(name = "criteria_name", nullable = false, unique = true, length = 200)
    private String criteriaName;

    /**
     * Zero-shot instruction injected into the LLM assessment prompt.
     * Must follow the format:
     * <pre>
     *   [Evaluation focus]
     *   - status="matched" if ...
     *   - status="weak" if ...
     *   - status="missing" if ...
     * </pre>
     */
    @Column(name = "prompt_instruction", nullable = false, columnDefinition = "TEXT")
    private String promptInstruction;

    @Column(name = "question_type", length = 50)
    private String questionType;
}
