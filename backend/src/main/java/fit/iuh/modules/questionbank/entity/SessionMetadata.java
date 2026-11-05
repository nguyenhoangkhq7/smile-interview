package fit.iuh.modules.questionbank.entity;

import jakarta.persistence.*;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.util.UUID;

@Entity
@Table(name = "session_metadata")
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class SessionMetadata {

    @Id
    @GeneratedValue(strategy = GenerationType.UUID)
    @Column(name = "id", updatable = false, nullable = false)
    private UUID id;

    @ManyToOne(fetch = FetchType.LAZY)
    @JoinColumn(name = "session_question_id", nullable = false)
    private QuestionBank questionBank;

    @Column(name = "metadata_key", length = 100)
    private String metadataKey;

    @Column(name = "metadata_value", columnDefinition = "TEXT")
    private String metadataValue;
}
