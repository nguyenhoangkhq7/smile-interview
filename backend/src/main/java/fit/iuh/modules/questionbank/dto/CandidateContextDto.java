package fit.iuh.modules.questionbank.dto;

import com.fasterxml.jackson.annotation.JsonIgnoreProperties;
import com.fasterxml.jackson.annotation.JsonProperty;
import fit.iuh.modules.assessment.entity.JobCategory;
import fit.iuh.modules.assessment.entity.SeniorityLevel;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.util.List;

@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
@JsonIgnoreProperties(ignoreUnknown = true)
public class CandidateContextDto {

    @JsonProperty("candidate_level")
    private SeniorityLevel candidateLevel;

    @JsonProperty("overall_match")
    private String overallMatch;

    @JsonProperty("years_of_experience")
    private Integer yearsOfExperience;

    @JsonProperty("strong_areas")
    private List<String> strongAreas;

    @JsonProperty("gap_areas")
    private List<String> gapAreas;

    @JsonProperty("tech_stack_required")
    private List<String> techStackRequired;

    @JsonProperty("tech_stack_possessed")
    private List<String> techStackPossessed;

    @JsonProperty("target_domain")
    private String targetDomain;

    @JsonProperty("role_type")
    private JobCategory roleType;

    @JsonProperty("cv_project_highlights")
    private List<String> cvProjectHighlights;
}
