package fit.iuh.modules.admin.dto;

import com.fasterxml.jackson.annotation.JsonProperty;
import jakarta.validation.constraints.NotNull;

public record CategoryCriteriaMappingDto(
        @NotNull(message = "category_id is required") @JsonProperty("category_id") Long categoryId,
        @NotNull(message = "criteria_id is required") @JsonProperty("criteria_id") Long criteriaId,
        @JsonProperty("level") String level,
        @NotNull(message = "weight_percentage is required") @JsonProperty("weight_percentage") Double weightPercentage
) {}
