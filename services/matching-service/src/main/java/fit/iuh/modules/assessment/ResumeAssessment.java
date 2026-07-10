package fit.iuh.modules.assessment;

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
 * JPA Entity persisting the refactored assessment result for an interview session.
 *
 * <h3>Architecture Changes (V3 Migration)</h3>
 * <ul>
 *   <li>{@code jobCategory} — replaces free-string {@code roleTypeDetected}; maps to {@link JobCategory} ENUM.</li>
 *   <li>{@code seniorityLevel} — replaces free-string {@code candidateLevel}; maps to {@link SeniorityLevel} ENUM.</li>
 *   <li>{@code overallMatchScore} — computed by {@link ScoringService} (Java math), never set by LLM.</li>
 *   <li>{@code evidenceItems} — flat JSONB array of {@link AssessmentResponseDto.EvidenceItem} objects from LLM.</li>
 *   <li>{@code topPriorityImprovements} — ordered improvement suggestions from LLM.</li>
 *   <li>All old LLM-scored fields ({@code competencyFitScore}, {@code technicalDepthScore},
 *       {@code matchLevel}, {@code sectionWiseFeedback}, etc.) removed.</li>
 * </ul>
 *
 * <h3>Cache-Aside Pattern</h3>
 * The unique index on {@code session_id} ensures that subsequent calls for the same session
 * return the cached result instantly without re-invoking any LLM.
 */
@Entity
@Table(
        name = "resume_assessments",
        indexes = {
                @Index(name = "idx_resume_assessment_session_id", columnList = "session_id", unique = true),
                @Index(name = "idx_ra_job_category",    columnList = "job_category"),
                @Index(name = "idx_ra_seniority_level", columnList = "seniority_level"),
                @Index(name = "idx_ra_overall_score",   columnList = "overall_match_score")
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
     * Unique constraint enables O(1) cache-aside lookups.
     */
    @Column(name = "session_id", nullable = false, unique = true, length = 128)
    private String sessionId;

    // -------------------------------------------------------------------------
    // Metadata — from MetadataExtractionService (Step 2, ENUM-typed)
    // -------------------------------------------------------------------------

    /**
     * Engineering domain of the JD, mapped from {@link JobCategory} ENUM.
     * Extracted by {@code MetadataExtractionService} — never inferred by the assessment LLM.
     */
    @Enumerated(EnumType.STRING)
    @Column(name = "job_category", length = 50)
    private JobCategory jobCategory;

    /**
     * Required seniority level from the JD, mapped from {@link SeniorityLevel} ENUM.
     * Extracted by {@code MetadataExtractionService} — never inferred by the assessment LLM.
     */
    @Enumerated(EnumType.STRING)
    @Column(name = "seniority_level", length = 20)
    private SeniorityLevel seniorityLevel;

    // -------------------------------------------------------------------------
    // Score — computed by ScoringService (Java math, NOT the LLM)
    // -------------------------------------------------------------------------

    /**
     * Overall match score (0–100) calculated by {@link ScoringService} using the formula:
     * <pre>
     *   score = SUM(weight_i * points_i) / SUM(weight_i) * 100
     *   where: matched=1.0, weak=0.5, missing=0.0
     * </pre>
     * Stored as a plain integer for fast SQL sorting and threshold filtering.
     */
    @Column(name = "overall_match_score")
    private Integer overallMatchScore;

    // -------------------------------------------------------------------------
    // LLM Evidence Output (Step 4) — evidence only, no scores
    // -------------------------------------------------------------------------

    /**
     * Flat JSONB array of {@link AssessmentResponseDto.EvidenceItem} objects.
     * Populated entirely by the LLM evidence-matching call. Contains no computed scores.
     * Schema: [{criteria_id, criteria_name, jd_requirement, cv_evidence, status}]
     */
    @JdbcTypeCode(SqlTypes.JSON)
    @Column(name = "evidence_items", columnDefinition = "jsonb")
    private List<AssessmentResponseDto.EvidenceItem> evidenceItems;

    @JdbcTypeCode(SqlTypes.JSON)
    @Column(name = "additional_evidence_items", columnDefinition = "jsonb")
    private List<AssessmentResponseDto.AdHocEvidenceItem> additionalEvidenceItems;

    @JdbcTypeCode(SqlTypes.JSON)
    @Column(name = "eligibility", columnDefinition = "jsonb")
    private Eligibility eligibility;

    /**
     * Ordered list of actionable improvement suggestions returned by the LLM.
     * Stored as a JSONB array for native array semantics and future query support.
     */
    @JdbcTypeCode(SqlTypes.JSON)
    @Column(name = "top_priority_improvements", columnDefinition = "jsonb")
    private List<ImprovementResponseDto.ImprovementItem> topPriorityImprovements;

    // -------------------------------------------------------------------------
    // Audit field
    // -------------------------------------------------------------------------

    /** Timestamp when this assessment was first persisted. Never updated. */
    @Column(name = "created_at", nullable = false, updatable = false)
    private LocalDateTime createdAt;

    /** Automatically sets {@link #createdAt} before the initial DB insert. */
    @PrePersist
    void onPrePersist() {
        this.createdAt = LocalDateTime.now();
    }
}
