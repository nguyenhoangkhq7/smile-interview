package fit.iuh.modules.questionbank.entity;

import fit.iuh.modules.questionbank.dto.CandidateContextDto;
import fit.iuh.modules.questionbank.dto.QuestionBankMetadataDto;
import fit.iuh.modules.questionbank.dto.QuestionConfigDto;
import fit.iuh.modules.questionbank.dto.QuestionDto;
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

    @JdbcTypeCode(SqlTypes.JSON)
    @Column(name = "metadata", columnDefinition = "jsonb")
    private QuestionBankMetadataDto metadata;

    @JdbcTypeCode(SqlTypes.JSON)
    @Column(name = "question_bank_json", nullable = false, columnDefinition = "jsonb")
    private List<QuestionDto> questionBankJson;

    @JdbcTypeCode(SqlTypes.JSON)
    @Column(name = "question_config", columnDefinition = "jsonb")
    private QuestionConfigDto questionConfig;

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
