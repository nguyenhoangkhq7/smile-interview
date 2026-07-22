package fit.iuh.modules.questionbank.dto;

import com.fasterxml.jackson.annotation.JsonProperty;
import jakarta.validation.Valid;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class GenerateQuestionBankRequest {

    @NotBlank
    @JsonProperty("sessionId")
    private String sessionId;

    @NotNull
    @Valid
    @JsonProperty("questionConfig")
    private QuestionConfigDto questionConfig;
}
