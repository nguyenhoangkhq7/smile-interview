package fit.iuh.modules.evaluation.model;

import com.fasterxml.jackson.annotation.JsonIgnoreProperties;
import com.fasterxml.jackson.annotation.JsonProperty;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Getter;
import lombok.NoArgsConstructor;

import java.util.List;

/**
 * Internal model that maps the JSON output produced by the LLM during Final Synthesis
 * ({@code GenerateFinalReport} RPC). The LLM has access to the full transcript + resume/JD
 * to produce a holistic hiring recommendation.
 * <p>
 * Immutability note: {@code @Getter} (no {@code @Setter}) is intentional — instances are
 * created exclusively via the Builder or Jackson deserialization and must not be mutated afterwards.
 */
@Getter
@Builder
@NoArgsConstructor
@AllArgsConstructor
@JsonIgnoreProperties(ignoreUnknown = true)
public class FinalReportResult {

    /**
     * Holistic overall score (0-10). Not a simple arithmetic mean — the LLM weighs core
     * questions more heavily than follow-up probes.
     */
    @JsonProperty("overall_score")
    private int overallScore;

    /** Executive summary of the candidate's performance across all topics. */
    @JsonProperty("overall_summary")
    private String overallSummary;

    /** Key strengths demonstrated throughout the interview. */
    private List<String> strengths;

    /** Key weaknesses or gaps, including any resume/JD contradictions detected. */
    private List<String> weaknesses;

    /** Concrete, actionable improvement recommendations for the candidate. */
    private List<String> recommendations;

    /**
     * High-level hiring recommendation.
     * One of: {@code "Strong Hire"} | {@code "Hire"} | {@code "No Hire"} | {@code "Strong No Hire"}.
     */
    @JsonProperty("hiring_recommendation")
    private String hiringRecommendation;
}
