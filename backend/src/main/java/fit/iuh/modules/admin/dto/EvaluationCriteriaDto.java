package fit.iuh.modules.admin.dto;

import com.fasterxml.jackson.annotation.JsonProperty;
import jakarta.validation.constraints.NotBlank;

import java.util.Set;

public record EvaluationCriteriaDto(
        @JsonProperty("id") Long id,
        @NotBlank(message = "name is required") @JsonProperty("name") String name,
        @JsonProperty("category") String category,
        @JsonProperty("question_type") String questionType,
        @JsonProperty("prompt_instruction") String promptInstruction,
        @JsonProperty("mapped_levels") Set<String> mappedLevels
) {}
