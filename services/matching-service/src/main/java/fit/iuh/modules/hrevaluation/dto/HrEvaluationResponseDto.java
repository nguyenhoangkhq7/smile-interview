package fit.iuh.modules.hrevaluation.dto;

import com.fasterxml.jackson.annotation.JsonInclude;
import com.fasterxml.jackson.annotation.JsonProperty;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.time.LocalDateTime;
import java.util.UUID;

/**
 * Response payload returned for HR evaluation submissions and admin evaluation lists.
 */
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
@JsonInclude(JsonInclude.Include.NON_NULL)
public class HrEvaluationResponseDto {

    /** Auto-generated UUID of the persisted evaluation record. */
    @JsonProperty("id")
    private UUID id;

    /** The interview session this evaluation belongs to. */
    @JsonProperty("session_id")
    private String sessionId;

    /** ID of the HR user who submitted the evaluation (optional). */
    @JsonProperty("user_id")
    private UUID userId;

    /** Evaluator name or display name. */
    @JsonProperty("evaluator_name")
    private String evaluatorName;

    /** Rating for CV-JD matching accuracy (1-5). */
    @JsonProperty("rating_matching_accuracy")
    private Integer ratingMatchingAccuracy;

    /** Rating for AI rationale quality (1-5). */
    @JsonProperty("rating_ai_rationale")
    private Integer ratingAiRationale;

    /** Rating for question quality (1-5). */
    @JsonProperty("rating_question_quality")
    private Integer ratingQuestionQuality;

    /** Free-text feedback notes. */
    @JsonProperty("feedback_notes")
    private String feedbackNotes;

    /** ISO-8601 timestamp of when the evaluation was saved. */
    @JsonProperty("created_at")
    private LocalDateTime createdAt;

    /** Human-readable confirmation message. */
    @JsonProperty("message")
    private String message;
}
