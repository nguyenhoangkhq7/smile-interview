package fit.iuh.modules.assessment.dto;

import com.fasterxml.jackson.annotation.JsonAlias;
import com.fasterxml.jackson.annotation.JsonIgnoreProperties;
import com.fasterxml.jackson.annotation.JsonProperty;

import java.util.List;

@JsonIgnoreProperties(ignoreUnknown = true)
public record ImprovementResponseDto(
        @JsonProperty("quick_wins")
        List<ImprovementItem> quickWins,
        
        @JsonProperty("skill_gaps")
        List<ImprovementItem> skillGaps
) {

    @JsonIgnoreProperties(ignoreUnknown = true)
    public record ImprovementItem(
            @JsonProperty("criteria_name")
            @JsonAlias({"criteriaName"})
            String criteriaName,

            @JsonProperty("actionable_advice")
            @JsonAlias({"suggestion", "actionableAdvice", "actionable_advice"})
            String actionableAdvice,

            @JsonProperty("priority")
            @JsonAlias({"priority_rank", "priorityRank", "priority"})
            String priority
    ) {}
}
