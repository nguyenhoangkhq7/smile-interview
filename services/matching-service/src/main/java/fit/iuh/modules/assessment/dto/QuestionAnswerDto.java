package fit.iuh.modules.assessment.dto;

import com.fasterxml.jackson.annotation.JsonProperty;

public record QuestionAnswerDto(
        @JsonProperty("question") String question,
        @JsonProperty("answer") String answer,
        @JsonProperty("score") Integer score
) {}
