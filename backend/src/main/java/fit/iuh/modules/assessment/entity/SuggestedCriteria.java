package fit.iuh.modules.assessment.entity;

import jakarta.persistence.*;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.time.LocalDateTime;

@Entity
@Table(
        name = "suggested_criteria",
        uniqueConstraints = {
                @UniqueConstraint(columnNames = {"job_category", "criteria_name"})
        }
)
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class SuggestedCriteria {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Enumerated(EnumType.STRING)
    @Column(name = "job_category", nullable = false)
    private JobCategory jobCategory;

    @Column(name = "criteria_name", nullable = false)
    private String criteriaName;

    @Column(name = "occurrence_count", nullable = false)
    private Integer occurrenceCount;

    @Column(name = "last_seen_at", nullable = false)
    private LocalDateTime lastSeenAt;

    @Column(name = "sample_jd_text", columnDefinition = "TEXT")
    private String sampleJdText;

    @Column(name = "promoted", nullable = false)
    private Boolean promoted;

    @PrePersist
    void prePersist() {
        if (occurrenceCount == null) occurrenceCount = 1;
        if (lastSeenAt == null) lastSeenAt = LocalDateTime.now();
        if (promoted == null) promoted = false;
    }
}
