package fit.iuh.modules.assessment.dto;

import com.fasterxml.jackson.annotation.JsonProperty;

public record QuestionAnswerDto(
        @JsonProperty("question") String question,
        @JsonProperty("answer") String answer,
        @JsonProperty("score") Integer score,
        @JsonProperty("is_deep_dive") Boolean isDeepDive,
        @JsonProperty("is_warmup") Boolean isWarmup
) {
    public boolean isFollowUp() {
        return Boolean.TRUE.equals(isDeepDive);
    }

    public boolean isWarmupQuestion() {
        return Boolean.TRUE.equals(isWarmup);
    }
}
