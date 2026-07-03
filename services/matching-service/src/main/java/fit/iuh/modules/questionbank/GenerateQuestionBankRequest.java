package fit.iuh.modules.questionbank;

import com.fasterxml.jackson.annotation.JsonProperty;
import jakarta.validation.Valid;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

/**
 * Request body for the Question Bank generation endpoint.
 *
 * <p>Requires a valid {@code sessionId} (must already have ingested CV/JD
 * and generated an assessment) and a {@code questionConfig} specifying
 * how many questions of each type to generate.
 */
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class GenerateQuestionBankRequest {

    @NotBlank(message = "sessionId is required")
    @JsonProperty("session_id")
    private String sessionId;

    @NotNull(message = "questionConfig is required")
    @Valid
    @JsonProperty("question_config")
    private QuestionConfigDto questionConfig;
}
