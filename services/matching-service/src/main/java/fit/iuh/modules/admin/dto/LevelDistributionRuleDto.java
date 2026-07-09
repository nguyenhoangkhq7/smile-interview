package fit.iuh.modules.admin.dto;

import com.fasterxml.jackson.annotation.JsonProperty;
import jakarta.validation.constraints.*;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

/**
 * DTO for {@link fit.iuh.modules.admin.LevelDistributionRule}.
 */
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class LevelDistributionRuleDto {

    @JsonProperty("id")
    private Long id;

    @NotBlank(message = "level is required")
    @JsonProperty("level")
    private String level;

    @NotNull @Min(0) @Max(100)
    @JsonProperty("behavioral_pct")
    private Double behavioralPct;

    @NotNull @Min(0) @Max(100)
    @JsonProperty("technical_pct")
    private Double technicalPct;

    @NotNull @Min(0) @Max(100)
    @JsonProperty("coding_pct")
    private Double codingPct;

    @NotNull @Min(0) @Max(100)
    @JsonProperty("system_design_pct")
    private Double systemDesignPct;
}
