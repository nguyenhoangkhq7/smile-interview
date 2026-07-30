package fit.iuh.modules.assessment.entity;

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
        name = "resume_assessments",
        indexes = {
                @Index(name = "idx_assessment_session_id", columnList = "session_id")
        }
)
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class ResumeAssessment {

    @Id
    @GeneratedValue(strategy = GenerationType.UUID)
    @Column(name = "id", updatable = false, nullable = false)
    private UUID id;

    @Column(name = "session_id", nullable = false, length = 128)
    private String sessionId;

    @Enumerated(EnumType.STRING)
    @Column(name = "job_category", nullable = false, length = 50)
    private JobCategory jobCategory;

    @Enumerated(EnumType.STRING)
    @Column(name = "seniority_level", nullable = false, length = 20)
    private SeniorityLevel seniorityLevel;

    @Column(name = "overall_match_score", nullable = false)
    private Integer overallMatchScore;

    @Enumerated(EnumType.STRING)
    @Column(name = "eligibility", length = 50)
    private EligibilityStatus eligibility;

    @OneToMany(mappedBy = "assessment", cascade = CascadeType.ALL, orphanRemoval = true)
    @Builder.Default
    private List<EvidenceItem> evidenceItems = new ArrayList<>();

    @OneToMany(mappedBy = "assessment", cascade = CascadeType.ALL, orphanRemoval = true)
    @Builder.Default
    private List<ScoreBreakdown> scoreBreakdowns = new ArrayList<>();

    @OneToMany(mappedBy = "assessment", cascade = CascadeType.ALL, orphanRemoval = true)
    @Builder.Default
    private List<Improvement> improvements = new ArrayList<>();

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
