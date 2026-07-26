package fit.iuh.modules.assessment.entity;

import fit.iuh.modules.assessment.dto.AssessmentResponseDto;
import fit.iuh.modules.assessment.dto.ImprovementResponseDto;
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

    @JdbcTypeCode(SqlTypes.JSON)
    @Column(name = "eligibility_json", columnDefinition = "jsonb")
    private Eligibility eligibility;

    @JdbcTypeCode(SqlTypes.JSON)
    @Column(name = "evidence_items_json", nullable = false, columnDefinition = "jsonb")
    private List<AssessmentResponseDto.EvidenceItem> mustHaveEvidenceItems;

    @JdbcTypeCode(SqlTypes.JSON)
    @Column(name = "additional_evidence_items_json", columnDefinition = "jsonb")
    private List<AssessmentResponseDto.AdHocEvidenceItem> preferToHaveEvidenceItems;

    public List<AssessmentResponseDto.EvidenceItem> getEvidenceItems() {
        return mustHaveEvidenceItems;
    }

    public List<AssessmentResponseDto.AdHocEvidenceItem> getAdditionalEvidenceItems() {
        return preferToHaveEvidenceItems;
    }


    @JdbcTypeCode(SqlTypes.JSON)
    @Column(name = "top_priority_improvements_json", columnDefinition = "jsonb")
    private List<ImprovementResponseDto.ImprovementItem> topPriorityImprovements;

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
