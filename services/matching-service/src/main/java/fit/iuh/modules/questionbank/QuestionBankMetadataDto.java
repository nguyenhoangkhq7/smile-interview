package fit.iuh.modules.questionbank;

import com.fasterxml.jackson.annotation.JsonProperty;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.util.List;
import java.util.Map;

/**
 * Metadata describing the generated question bank: candidate profile,
 * difficulty distribution, total question count, and generation rationale.
 */
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class QuestionBankMetadataDto {

    @JsonProperty("candidate_level")
    private String candidateLevel;

    @JsonProperty("overall_match")
    private String overallMatch;

    @JsonProperty("years_of_experience")
    private String yearsOfExperience;

    @JsonProperty("role_type")
    private String roleType;

    @JsonProperty("target_domain")
    private String targetDomain;

    @JsonProperty("strong_areas")
    private List<String> strongAreas;

    @JsonProperty("gap_areas")
    private List<String> gapAreas;

    @JsonProperty("difficulty_distribution")
    private Map<String, String> difficultyDistribution;

    @JsonProperty("total_questions")
    private int totalQuestions;

    @JsonProperty("generation_rationale")
    private String generationRationale;
}
