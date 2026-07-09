package fit.iuh.modules.evaluation;

import com.fasterxml.jackson.annotation.JsonIgnoreProperties;
import com.fasterxml.jackson.annotation.JsonProperty;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

/**
 * DTO that maps the JSON output produced by the LLM during per-turn evaluation.
 * score is nullable: a null score indicates the turn was a fallback (system error/timeout)
 * and must NOT be counted toward the candidate's final average score.
 */
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
@JsonIgnoreProperties(ignoreUnknown = true)
public class EvaluationResult {

    /** "FOLLOW_UP" or "NEXT_TOPIC" */
    private String decision;

    /** AI-generated follow-up question targeting the specific gap in the candidate's answer.
     *  Empty string when decision is NEXT_TOPIC. */
    @JsonProperty("follow_up_question")
    private String followUpQuestion;

    /** One-sentence explanation for the decision. */
    private String reasoning;

    /** Score 0-10. Null for fallback turns — excluded from final scoring. */
    private Integer score;

    /** Detailed evaluation in Vietnamese: Điểm mạnh / Điểm yếu / Gợi ý. */
    private String evaluation;

    /** True if this result was produced by the fallback path (timeout or LLM error). */
    @Builder.Default
    private boolean isFallback = false;

    /** True if this turn must be excluded from the final report's scoring calculations. */
    @Builder.Default
    private boolean excludedFromScoring = false;
}
