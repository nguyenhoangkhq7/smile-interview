package fit.iuh.modules.assessment.entity;

import jakarta.persistence.*;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.time.LocalDateTime;
import java.util.UUID;

@Entity
@Table(name = "evidence_items")
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class EvidenceItem {

    @Id
    @GeneratedValue(strategy = GenerationType.UUID)
    @Column(name = "id", updatable = false, nullable = false)
    private UUID id;

    @ManyToOne(fetch = FetchType.LAZY)
    @JoinColumn(name = "assessment_id", nullable = false)
    @lombok.ToString.Exclude
    @lombok.EqualsAndHashCode.Exclude
    private ResumeAssessment assessment;

    @Column(name = "criteria_id")
    private Integer criteriaId;

    @Column(name = "criteria_name")
    private String criteriaName;

    @Column(name = "importance", length = 50)
    private String importance;

    @Column(name = "jd_requirement", columnDefinition = "TEXT")
    private String jdRequirement;

    @Column(name = "cv_evidence", columnDefinition = "TEXT")
    private String cvEvidence;

    @Column(name = "status", length = 50)
    private String status;

    @Column(name = "reasoning", columnDefinition = "TEXT")
    private String reasoning;

    @Column(name = "created_at", updatable = false)
    private LocalDateTime createdAt;

    @PrePersist
    void onPrePersist() {
        if (this.createdAt == null) {
            this.createdAt = LocalDateTime.now();
        }
    }
}
