package fit.iuh.modules.evaluation;

import com.fasterxml.jackson.annotation.JsonIgnoreProperties;
import com.fasterxml.jackson.annotation.JsonProperty;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.util.List;

/**
 * DTO that maps the JSON output produced by the LLM during Final Synthesis
 * (GenerateFinalReport RPC). The LLM has access to the full transcript + resume/JD
 * to produce a holistic hiring recommendation.
 */
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
@JsonIgnoreProperties(ignoreUnknown = true)
public class FinalReportResult {

    /** Holistic overall score (0-10). Not a simple arithmetic mean — LLM weighs core
     *  questions more heavily than follow-up probes. */
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

    /** High-level hiring recommendation.
     *  One of: "Strong Hire" | "Hire" | "No Hire" | "Strong No Hire" */
    @JsonProperty("hiring_recommendation")
    private String hiringRecommendation;
}
