package fit.iuh.modules.assessment.dto;

import com.fasterxml.jackson.annotation.JsonProperty;
import fit.iuh.modules.assessment.entity.EligibilityStatus;
import fit.iuh.modules.assessment.entity.JobCategory;
import fit.iuh.modules.assessment.entity.SeniorityLevel;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.time.LocalDateTime;
import java.util.List;
import java.util.UUID;

@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class AssessmentResponse {

    @JsonProperty("id")
    private UUID id;

    @JsonProperty("session_id")
    private String sessionId;

    @JsonProperty("job_category")
    private JobCategory jobCategory;

    @JsonProperty("seniority_level")
    private SeniorityLevel seniorityLevel;

    @JsonProperty("overall_match_score")
    private Integer overallMatchScore;

    @JsonProperty("eligibility")
    private EligibilityStatus eligibility;

    @JsonProperty("gate_evidence_items")
    private List<AssessmentResponseDto.EvidenceItem> gateEvidenceItems;

    @JsonProperty("must_have_evidence_items")
    private List<AssessmentResponseDto.EvidenceItem> mustHaveEvidenceItems;

    @JsonProperty("prefer_to_have_evidence_items")
    private List<AssessmentResponseDto.AdHocEvidenceItem> preferToHaveEvidenceItems;

    @JsonProperty("score_breakdown")
    private ScoreBreakdown scoreBreakdown;

    @JsonProperty("quick_wins")
    private List<ImprovementResponseDto.ImprovementItem> quickWins;

    @JsonProperty("skill_gaps")
    private List<ImprovementResponseDto.ImprovementItem> skillGaps;

    @JsonProperty("cached")
    private boolean cached;

    @JsonProperty("created_at")
    private LocalDateTime createdAt;

    public record ScoreBreakdown(
            @JsonProperty("raw_must_have_score")
            int rawMustHaveScore,

            @JsonProperty("must_have_weight_ratio")
            double mustHaveWeightRatio,

            @JsonProperty("raw_prefer_to_have_score")
            int rawPreferToHaveScore,

            @JsonProperty("prefer_to_have_weight_ratio")
            double preferToHaveWeightRatio,

            @JsonProperty("final_score")
            int finalScore
    ) {}
}
