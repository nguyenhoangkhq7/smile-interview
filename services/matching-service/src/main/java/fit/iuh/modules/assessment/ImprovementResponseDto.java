package fit.iuh.modules.assessment;

import com.fasterxml.jackson.annotation.JsonProperty;
import java.util.List;

/**
 * DTO for the Improvement Advisor (Phase 2) of the Assessment pipeline.
 */
public record ImprovementResponseDto(
        @JsonProperty("top_priority_improvements")
        List<ImprovementItem> topPriorityImprovements
) {
    public record ImprovementItem(
            @JsonProperty("criteria_id")
            Long criteriaId,

            @JsonProperty("criteria_name")
            String criteriaName,

            @JsonProperty("suggestion")
            String suggestion,

            @JsonProperty("priority_rank")
            int priorityRank
    ) {}
}
