package fit.iuh.modules.assessment.dto;

import com.fasterxml.jackson.annotation.JsonProperty;
import java.util.List;

public record InterviewEvaluationRequest(
        @JsonProperty("role_title") String roleTitle,
        @JsonProperty("interview_type") String interviewType,
        @JsonProperty("turns") List<QuestionAnswerDto> turns,
        @JsonProperty("total_base_questions") Integer totalBaseQuestions
) {}
