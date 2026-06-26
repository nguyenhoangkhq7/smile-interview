package fit.iuh.entity;

import jakarta.persistence.*;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;
import org.hibernate.annotations.JdbcTypeCode;
import org.hibernate.annotations.UuidGenerator;
import org.hibernate.type.SqlTypes;

import java.time.LocalDateTime;
import java.util.UUID;

/**
 * JPA Entity that persists the holistic resume assessment result for an
 * interview session.
 *
 * <p>Storing results here enables a <strong>Cache-Aside</strong> pattern:
 * subsequent calls for the same {@code sessionId} return the cached record
 * instantly without triggering another (expensive) LLM API call.
 *
 * <p>The {@code assessmentReport} field is mapped to PostgreSQL {@code jsonb}
 * so that future queries can use native JSON operators (e.g. {@code ->}, {@code @>})
 * directly in SQL if needed.
 */
@Entity
@Table(
        name = "resume_assessments",
        indexes = {
                @Index(name = "idx_resume_assessment_session_id", columnList = "session_id", unique = true)
        }
)
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class ResumeAssessment {

    /** Auto-generated UUID primary key. */
    @Id
    @UuidGenerator
    @Column(name = "id", updatable = false, nullable = false)
    private UUID id;

    /**
     * Links this assessment to a specific interview session.
     * Must be unique — only one assessment result is stored per session
     * (re-assessment overwrites the old record).
     */
    @Column(name = "session_id", nullable = false, unique = true, length = 128)
    private String sessionId;

    /**
     * The extracted overall match score (0-100) from the LLM report.
     * Stored as a plain integer for fast dashboard sorting and filtering
     * without parsing the full JSON.
     */
    @Column(name = "overall_score")
    private Integer overallScore;

    /**
     * The extracted hiring recommendation from the LLM report
     * (e.g. "Strong Fit", "Good Fit", "Partial Fit", "Poor Fit").
     */
    @Column(name = "hiring_recommendation", length = 64)
    private String hiringRecommendation;

    /**
     * The complete assessment report text (Markdown) returned by the LLM.
     * Stored as PostgreSQL {@code jsonb} wrapped in a JSON string envelope
     * ({@code {"report": "..."}}) for future queryability.
     *
     * <p>Hibernate 6's {@link JdbcTypeCode} with {@link SqlTypes#JSON} maps
     * this field to the {@code jsonb} column type automatically — no external
     * Hibernate Types library is required.
     */
    @JdbcTypeCode(SqlTypes.JSON)
    @Column(name = "assessment_data", nullable = false, columnDefinition = "jsonb")
    private String assessmentData;

    /**
     * Timestamp when this assessment was first persisted.
     * Set automatically in the {@link PrePersist} lifecycle callback.
     */
    @Column(name = "created_at", nullable = false, updatable = false)
    private LocalDateTime createdAt;

    /** Automatically sets {@link #createdAt} before initial DB insert. */
    @PrePersist
    void onPrePersist() {
        this.createdAt = LocalDateTime.now();
    }
}
