package fit.iuh.modules.admin.dto;

import com.fasterxml.jackson.annotation.JsonProperty;
import jakarta.validation.constraints.NotBlank;

public record EvaluationCriteriaDto(
        @JsonProperty("id") Long id,
        @NotBlank(message = "name is required") @JsonProperty("name") String name,
        @JsonProperty("category") String category,
        @JsonProperty("question_type") String questionType,
        @JsonProperty("prompt_instruction") String promptInstruction
) {}
