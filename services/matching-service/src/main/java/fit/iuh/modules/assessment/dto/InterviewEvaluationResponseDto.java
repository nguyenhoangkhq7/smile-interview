package fit.iuh.modules.assessment.dto;

import com.fasterxml.jackson.annotation.JsonIgnoreProperties;
import com.fasterxml.jackson.annotation.JsonProperty;

import java.util.List;

@JsonIgnoreProperties(ignoreUnknown = true)
public record InterviewEvaluationResponseDto(
        @JsonProperty("overallScore") Integer overallScore,
        @JsonProperty("overallFeedback") String overallFeedback,
        @JsonProperty("strongAreas") List<String> strongAreas,
        @JsonProperty("gapAreas") List<String> gapAreas,
        @JsonProperty("actionableSuggestions") List<String> actionableSuggestions,
        @JsonProperty("evaluatedQuestions") List<EvaluatedQuestionDto> evaluatedQuestions
) {
    @JsonIgnoreProperties(ignoreUnknown = true)
    public record EvaluatedQuestionDto(
            @JsonProperty("question") String question,
            @JsonProperty("answer") String answer,
            @JsonProperty("score") Integer score,
            @JsonProperty("strengths") String strengths,
            @JsonProperty("improvements") String improvements,
            @JsonProperty("suggestedAnswer") String suggestedAnswer
    ) {}

    public static InterviewEvaluationResponseDto fallback() {
        return new InterviewEvaluationResponseDto(
                50,
                "Buổi phỏng vấn đã được ghi nhận. Hệ thống đang tiến hành phân tích chi tiết.",
                List.of(),
                List.of(),
                List.of("Tiếp tục luyện tập trả lời rõ ràng và đi sâu vào chi tiết kỹ thuật."),
                List.of()
        );
    }
}
