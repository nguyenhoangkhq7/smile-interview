package fit.iuh.modules.questionbank.entity;

import fit.iuh.modules.questionbank.dto.CandidateContextDto;
import fit.iuh.modules.questionbank.dto.QuestionConfigDto;
import jakarta.persistence.*;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;
import org.hibernate.annotations.JdbcTypeCode;
import org.hibernate.type.SqlTypes;

import java.time.LocalDateTime;
import java.util.ArrayList;
import java.util.List;
import java.util.UUID;

@Entity
@Table(
        name = "session_questions",
        indexes = {
                @Index(name = "idx_sq_session_id", columnList = "session_id")
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

    @OneToMany(mappedBy = "questionBank", cascade = CascadeType.ALL, orphanRemoval = true)
    @Builder.Default
    private List<SessionMetadata> metadataItems = new ArrayList<>();

    @OneToMany(mappedBy = "questionBank", cascade = CascadeType.ALL, orphanRemoval = true)
    @Builder.Default
    private List<Question> questions = new ArrayList<>();

    @JdbcTypeCode(SqlTypes.JSON)
    @Column(name = "question_config", columnDefinition = "text")
    private QuestionConfigDto questionConfig;

    @JdbcTypeCode(SqlTypes.JSON)
    @Column(name = "candidate_context", columnDefinition = "text")
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
