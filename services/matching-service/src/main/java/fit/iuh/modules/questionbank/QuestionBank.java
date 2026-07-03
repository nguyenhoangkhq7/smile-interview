package fit.iuh.modules.questionbank;

import fit.iuh.modules.questionbank.CandidateContextDto;
import fit.iuh.modules.questionbank.QuestionBankMetadataDto;
import fit.iuh.modules.questionbank.QuestionConfigDto;
import fit.iuh.modules.questionbank.QuestionDto;
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
 * Persisted question bank generated from a candidate's CV, JD, and assessment.
 *
 * <p>All structured data (metadata, questions, config, context) is stored as
 * JSONB columns in PostgreSQL for flexible schema and efficient read access.
 */
@Entity
@Table(
        name = "question_banks",
        indexes = {
                @Index(name = "idx_qb_session_id", columnList = "session_id")
        }
)
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class QuestionBank {

    @Id
    @GeneratedValue(strategy = GenerationType.UUID)
    @Column(name = "id", updatable = false, nullable = false)
    private UUID id;

    @Column(name = "session_id", nullable = false, length = 128)
    private String sessionId;

    /** Full metadata object describing candidate profile and generation params. */
    @JdbcTypeCode(SqlTypes.JSON)
    @Column(name = "metadata", columnDefinition = "jsonb")
    private QuestionBankMetadataDto metadata;

    /** Full list of generated questions. */
    @JdbcTypeCode(SqlTypes.JSON)
    @Column(name = "question_bank_json", nullable = false, columnDefinition = "jsonb")
    private List<QuestionDto> questionBankJson;

    /** The question config that was used for generation (for reference). */
    @JdbcTypeCode(SqlTypes.JSON)
    @Column(name = "question_config", columnDefinition = "jsonb")
    private QuestionConfigDto questionConfig;

    /** Cached candidate context extracted by LLM (used for single-question regeneration). */
    @JdbcTypeCode(SqlTypes.JSON)
    @Column(name = "candidate_context", columnDefinition = "jsonb")
    private CandidateContextDto candidateContext;

    @Column(name = "total_questions")
    private Integer totalQuestions;

    @Column(name = "created_at", nullable = false, updatable = false)
    private LocalDateTime createdAt;

    @Column(name = "updated_at")
    private LocalDateTime updatedAt;

    @PrePersist
    void onPrePersist() {
        this.createdAt = LocalDateTime.now();
        this.updatedAt = this.createdAt;
    }

    @PreUpdate
    void onPreUpdate() {
        this.updatedAt = LocalDateTime.now();
    }
}
