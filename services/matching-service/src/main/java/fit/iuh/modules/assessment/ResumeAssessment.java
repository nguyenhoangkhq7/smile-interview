package fit.iuh.modules.assessment;

import fit.iuh.modules.assessment.AssessmentResponseDto;
import jakarta.persistence.*;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;
import org.hibernate.annotations.JdbcTypeCode;
import org.hibernate.type.SqlTypes;

import java.time.LocalDateTime;
import java.util.List;
import java.util.UUID;

/**
 * JPA Entity persisting the SimInterview 3-part assessment result for an interview session.
 *
 * <h3>SimInterview Outputs (Academic Paper Alignment)</h3>
 * <ol>
 *   <li><strong>Competency-level fit score</strong> — {@link #competencyFitScore} (integer column,
 *       fast for dashboard sorting and threshold filtering).
 *   <li><strong>Section-wise feedback</strong> — {@link #sectionWiseFeedback} (PostgreSQL {@code jsonb},
 *       allows native JSON operators: {@code section_wise_feedback -> 'skills_evaluation'
 *       -> 'critical_missing_skills'} for Module 3 question generation).
 *   <li><strong>Actionable improvement suggestions</strong> — {@link #actionableSuggestions}
 *       (PostgreSQL {@code jsonb} array of strings).
 * </ol>
 *
 * <h3>Cache-Aside Pattern</h3>
 * The unique index on {@code session_id} ensures that subsequent calls for the same session
 * return the cached record instantly without re-invoking the LLM API.
 *
 * <h3>Schema Note</h3>
 * Hibernate 6's {@link JdbcTypeCode} with {@link SqlTypes#JSON} maps Java objects/collections
 * directly to PostgreSQL {@code jsonb} — no external Hibernate Types library is required.
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
    @GeneratedValue(strategy = GenerationType.UUID)
    @Column(name = "id", updatable = false, nullable = false)
    private UUID id;

    /**
     * Links this assessment to a specific interview session.
     * Must be unique — only one assessment result is stored per session.
     * The unique constraint + index enables O(1) cache-aside lookups.
     */
    @Column(name = "session_id", nullable = false, unique = true, length = 128)
    private String sessionId;

    // -------------------------------------------------------------------------
    // SimInterview Output 1 — Competency-level fit score
    // -------------------------------------------------------------------------

    /**
     * The holistic competency fit score (0–100) from the LLM.
     * Stored as a plain integer column for fast SQL sorting ({@code ORDER BY competency_fit_score DESC})
     * and threshold filtering ({@code WHERE competency_fit_score >= 70}) without parsing JSONB.
     */
    @Column(name = "competency_fit_score")
    private Integer competencyFitScore;

    @Column(name = "technical_depth_score")
    private Integer technicalDepthScore;

    @Column(name = "match_level", length = 64)
    private String matchLevel;

    @Column(name = "role_type_detected", length = 64)
    private String roleTypeDetected;

    @Column(name = "candidate_level", length = 64)
    private String candidateLevel;

    @Column(name = "years_of_experience_estimate", length = 64)
    private String yearsOfExperienceEstimate;

    @JdbcTypeCode(SqlTypes.JSON)
    @Column(name = "strong_areas", columnDefinition = "jsonb")
    private List<String> strongAreas;

    @JdbcTypeCode(SqlTypes.JSON)
    @Column(name = "gap_areas", columnDefinition = "jsonb")
    private List<String> gapAreas;

    @JdbcTypeCode(SqlTypes.JSON)
    @Column(name = "critical_missing_skills", columnDefinition = "jsonb")
    private List<String> criticalMissingSkills;

    // -------------------------------------------------------------------------
    // SimInterview Output 2 — Section-wise feedback (JSONB)
    // -------------------------------------------------------------------------

    /**
     * The structured section-wise feedback object from the LLM, stored as PostgreSQL {@code jsonb}.
     */
    @JdbcTypeCode(SqlTypes.JSON)
    @Column(name = "section_wise_feedback", nullable = false, columnDefinition = "jsonb")
    private AssessmentResponseDto.SectionWiseFeedback sectionWiseFeedback;

    // -------------------------------------------------------------------------
    // SimInterview Output 3 — Actionable improvement suggestions (JSONB)
    // -------------------------------------------------------------------------

    /**
     * The ordered list of actionable improvement suggestions, stored as a PostgreSQL {@code jsonb} array.
     *
     * <p>Stored as JSONB (rather than a {@code text} column with comma-separated values) to preserve
     * proper array semantics and enable future array-level queries (e.g., {@code jsonb_array_length}).
     */
    @JdbcTypeCode(SqlTypes.JSON)
    @Column(name = "actionable_suggestions", nullable = false, columnDefinition = "jsonb")
    private List<String> actionableSuggestions;

    // -------------------------------------------------------------------------
    // Audit field
    // -------------------------------------------------------------------------

    /**
     * Timestamp when this assessment was first persisted.
     * Set automatically in the {@link PrePersist} lifecycle callback; never updated.
     */
    @Column(name = "created_at", nullable = false, updatable = false)
    private LocalDateTime createdAt;

    /** Automatically sets {@link #createdAt} before the initial DB insert. */
    @PrePersist
    void onPrePersist() {
        this.createdAt = LocalDateTime.now();
    }
}
