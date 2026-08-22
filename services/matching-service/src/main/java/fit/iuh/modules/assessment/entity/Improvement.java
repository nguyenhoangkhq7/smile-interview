package fit.iuh.modules.assessment.entity;

import jakarta.persistence.*;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.time.LocalDateTime;
import java.util.UUID;

@Entity
@Table(name = "improvements")
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class Improvement {

    @Id
    @GeneratedValue(strategy = GenerationType.UUID)
    @Column(name = "id", updatable = false, nullable = false)
    private UUID id;

    @ManyToOne(fetch = FetchType.LAZY)
    @JoinColumn(name = "assessment_id", nullable = false)
    @lombok.ToString.Exclude
    @lombok.EqualsAndHashCode.Exclude
    private ResumeAssessment assessment;

    @Column(name = "priority_rank")
    private Integer priorityRank;

    @Column(name = "topic", length = 255)
    private String topic;

    @Column(name = "suggestion_details", columnDefinition = "TEXT")
    private String suggestionDetails;

    @Column(name = "created_at", updatable = false)
    private LocalDateTime createdAt;

    @PrePersist
    void onPrePersist() {
        if (this.createdAt == null) {
            this.createdAt = LocalDateTime.now();
        }
    }
}
