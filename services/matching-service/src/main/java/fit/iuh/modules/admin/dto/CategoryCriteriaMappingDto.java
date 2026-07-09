package fit.iuh.modules.admin.dto;

import com.fasterxml.jackson.annotation.JsonProperty;
import jakarta.validation.constraints.*;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

/**
 * DTO for {@link fit.iuh.modules.rulengine.CategoryCriteriaMapping}.
 * The composite PK is {@code (job_category_id, criteria_id, seniority_level)}.
 */
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class CategoryCriteriaMappingDto {

    @NotNull(message = "job_category_id is required")
    @JsonProperty("job_category_id")
    private Long jobCategoryId;

    /** Human-readable category name (read-only; for display in GET responses). */
    @JsonProperty("job_category_name")
    private String jobCategoryName;

    @NotNull(message = "criteria_id is required")
    @JsonProperty("criteria_id")
    private Long criteriaId;

    /** Human-readable criteria name (read-only; for display in GET responses). */
    @JsonProperty("criteria_name")
    private String criteriaName;

    @NotBlank(message = "seniority_level is required")
    @JsonProperty("seniority_level")
    private String seniorityLevel;

    @NotNull(message = "weight_percentage is required")
    @Positive(message = "weight_percentage must be positive")
    @Max(value = 100, message = "weight_percentage must be ≤ 100")
    @JsonProperty("weight_percentage")
    private Double weightPercentage;
}
