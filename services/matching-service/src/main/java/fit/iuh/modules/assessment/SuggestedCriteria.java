package fit.iuh.modules.assessment;

import jakarta.persistence.*;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.time.LocalDateTime;

@Entity
@Table(name = "suggested_criteria")
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class SuggestedCriteria {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(name = "job_category", length = 50, nullable = false)
    @Enumerated(EnumType.STRING)
    private JobCategory jobCategory;

    @Column(name = "criteria_name", length = 200, nullable = false)
    private String criteriaName;

    @Column(name = "occurrence_count", nullable = false)
    private Integer occurrenceCount;

    @Column(name = "last_seen_at", nullable = false)
    private LocalDateTime lastSeenAt;

    @Column(name = "sample_jd_text", columnDefinition = "text")
    private String sampleJdText;

    @Column(name = "promoted", nullable = false)
    private Boolean promoted;
}
