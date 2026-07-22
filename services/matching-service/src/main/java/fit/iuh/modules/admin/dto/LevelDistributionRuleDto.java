package fit.iuh.modules.admin.dto;

import com.fasterxml.jackson.annotation.JsonProperty;

public record LevelDistributionRuleDto(
        @JsonProperty("id") Long id,
        @JsonProperty("level") String level,
        @JsonProperty("behavioral_pct") Double behavioralPct,
        @JsonProperty("technical_pct") Double technicalPct,
        @JsonProperty("coding_pct") Double codingPct,
        @JsonProperty("system_design_pct") Double systemDesignPct
) {}
