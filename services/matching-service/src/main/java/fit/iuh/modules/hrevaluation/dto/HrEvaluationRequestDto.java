package fit.iuh.modules.hrevaluation.dto;

import com.fasterxml.jackson.annotation.JsonProperty;
import jakarta.validation.constraints.Max;
import jakarta.validation.constraints.Min;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Size;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

/**
 * Request payload for submitting an HR evaluation of an AI-generated question bank.
 *
 * <p>All rating fields are validated at the controller layer via Bean Validation.
 * The {@code sessionId} is required; all other fields are optional to accommodate
 * partial evaluations.
 */
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class HrEvaluationRequestDto {

    /** The interview session whose question bank is being evaluated. */
    @NotBlank(message = "sessionId must not be blank")
    @JsonProperty("session_id")
    private String sessionId;

    /** HR evaluator name or identifier (optional). */
    @Size(max = 255, message = "evaluatorName must not exceed 255 characters")
    @JsonProperty("evaluator_name")
    private String evaluatorName;

    /**
     * Score (1–5) rating the accuracy of the CV-JD matching analysis.
     */
    @Min(value = 1, message = "ratingMatchingAccuracy must be between 1 and 5")
    @Max(value = 5, message = "ratingMatchingAccuracy must be between 1 and 5")
    @JsonProperty("rating_matching_accuracy")
    private Integer ratingMatchingAccuracy;

    /**
     * Score (1–5) rating the quality of the AI's reasoning behind the
     * selected questions.
     */
    @Min(value = 1, message = "ratingAiRationale must be between 1 and 5")
    @Max(value = 5, message = "ratingAiRationale must be between 1 and 5")
    @JsonProperty("rating_ai_rationale")
    private Integer ratingAiRationale;

    /**
     * Score (1–5) rating the overall relevance, difficulty balance, and
     * clarity of the generated questions.
     */
    @Min(value = 1, message = "ratingQuestionQuality must be between 1 and 5")
    @Max(value = 5, message = "ratingQuestionQuality must be between 1 and 5")
    @JsonProperty("rating_question_quality")
    private Integer ratingQuestionQuality;

    /** Open-ended HR feedback about the question bank. */
    @JsonProperty("feedback_notes")
    private String feedbackNotes;
}
