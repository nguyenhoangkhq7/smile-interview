package fit.iuh.modules.hrevaluation.entity;

import jakarta.persistence.*;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;
import org.hibernate.annotations.CreationTimestamp;

import java.time.LocalDateTime;
import java.util.UUID;

/**
 * JPA entity representing a single HR evaluator's rating
 * of an AI-generated question bank for an interview session.
 *
 * <p>Mapped to the {@code hr_evaluations} table created by {@code V7}.
 */
@Entity
@Table(
        name = "hr_evaluations",
        indexes = {
                @Index(name = "idx_hr_eval_session_id", columnList = "session_id")
        }
)
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class HrEvaluation {

    @Id
    @GeneratedValue(strategy = GenerationType.UUID)
    @Column(name = "id", updatable = false, nullable = false)
    private UUID id;

    /** Interview session this evaluation belongs to. */
    @Column(name = "session_id", nullable = false, length = 128)
    private String sessionId;

    /** ID of the HR user who submitted the evaluation (optional FK to users table). */
    @Column(name = "user_id")
    private UUID userId;

    /** Name or identifier of the HR person submitting the evaluation. */
    @Column(name = "evaluator_name", length = 255)
    private String evaluatorName;

    /**
     * HR score (1–5) for the accuracy of CV-JD matching analysis.
     */
    @Column(name = "rating_matching_accuracy")
    private Integer ratingMatchingAccuracy;

    /**
     * HR score (1–5) for the quality of the AI rationale
     * behind the selected questions.
     */
    @Column(name = "rating_ai_rationale")
    private Integer ratingAiRationale;

    /**
     * HR score (1–5) for the overall quality of the generated questions
     * (relevance, difficulty, clarity).
     */
    @Column(name = "rating_question_quality")
    private Integer ratingQuestionQuality;

    /** Free-text feedback from the HR evaluator. */
    @Column(name = "feedback_notes", columnDefinition = "TEXT")
    private String feedbackNotes;

    /** Automatically populated on insert. */
    @CreationTimestamp
    @Column(name = "created_at", nullable = false, updatable = false)
    private LocalDateTime createdAt;
}
