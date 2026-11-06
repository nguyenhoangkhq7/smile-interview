package fit.iuh.modules.adaptive.dto;

import com.fasterxml.jackson.annotation.JsonIgnoreProperties;
import com.fasterxml.jackson.annotation.JsonProperty;

import java.util.List;

/**
 * DTOs for Contribution 3: Prompt-Chaining & Bayesian Adaptive Questioning Framework.
 */
public final class AdaptiveDtos {

    private AdaptiveDtos() {}

    @JsonIgnoreProperties(ignoreUnknown = true)
    public record AbductiveReasoningDto(
            @JsonProperty("surprising_fact_C") String surprisingFactC,
            @JsonProperty("hypothesis_A") String hypothesisA
    ) {}

    @JsonIgnoreProperties(ignoreUnknown = true)
    public record StartInterviewResponseDto(
            @JsonProperty("session_id") String sessionId,
            @JsonProperty("turn") int turn,
            @JsonProperty("active_skill_id") String activeSkillId,
            @JsonProperty("initial_belief") List<Double> initialBelief,
            @JsonProperty("abductive_reasoning") AbductiveReasoningDto abductiveReasoning,
            @JsonProperty("question") String question,
            @JsonProperty("is_finished") boolean isFinished
    ) {}

    @JsonIgnoreProperties(ignoreUnknown = true)
    public record RespondInterviewRequestDto(
            @JsonProperty("candidate_response") String candidateResponse
    ) {}

    @JsonIgnoreProperties(ignoreUnknown = true)
    public record RespondInterviewResponseDto(
            @JsonProperty("session_id") String sessionId,
            @JsonProperty("turn") int turn,
            @JsonProperty("evaluated_skill_id") String evaluatedSkillId,
            @JsonProperty("previous_belief") List<Double> previousBelief,
            @JsonProperty("updated_belief") List<Double> updatedBelief,
            @JsonProperty("tv_delta") double tvDelta,
            @JsonProperty("metamorphic_tag") String metamorphicTag,
            @JsonProperty("reflective_insight") String reflectiveInsight,
            @JsonProperty("skill_verified") boolean skillVerified,
            @JsonProperty("active_skill_id") String activeSkillId,
            @JsonProperty("next_question") String nextQuestion,
            @JsonProperty("completion_rate") double completionRate,
            @JsonProperty("is_finished") boolean isFinished
    ) {}
}
