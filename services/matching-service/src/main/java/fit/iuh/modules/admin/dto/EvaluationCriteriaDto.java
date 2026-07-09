package fit.iuh.modules.admin.dto;

import com.fasterxml.jackson.annotation.JsonProperty;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Size;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

/**
 * DTO for {@link fit.iuh.modules.rulengine.EvaluationCriteria}.
 */
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class EvaluationCriteriaDto {

    @JsonProperty("id")
    private Long id;

    @NotBlank(message = "criteria_name is required")
    @Size(max = 200, message = "criteria_name must be ≤ 200 characters")
    @JsonProperty("criteria_name")
    private String criteriaName;

    @NotBlank(message = "prompt_instruction is required")
    @JsonProperty("prompt_instruction")
    private String promptInstruction;
}
