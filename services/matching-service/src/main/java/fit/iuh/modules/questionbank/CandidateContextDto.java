package fit.iuh.modules.questionbank;

import com.fasterxml.jackson.annotation.JsonIgnoreProperties;
import com.fasterxml.jackson.annotation.JsonProperty;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.util.List;

/**
 * Structured context extracted by the LLM from CV + JD + Assessment.
 *
 * <p>Used to determine difficulty distribution and personalize question
 * generation for a specific candidate.
 */
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
@JsonIgnoreProperties(ignoreUnknown = true)
public class CandidateContextDto {

    /** Inferred seniority level: junior | mid | senior | lead */
    @JsonProperty("candidate_level")
    private String candidateLevel;

    /** Overall CV-JD match quality: low | medium | high */
    @JsonProperty("overall_match")
    private String overallMatch;

    /** Years of experience range: 0-1 | 1-3 | 3-5 | 5-10 | 10+ */
    @JsonProperty("years_of_experience")
    private String yearsOfExperience;

    /** Skills/domains the candidate demonstrates well (from CV). */
    @JsonProperty("strong_areas")
    private List<String> strongAreas;

    /** Skills/domains the JD requires but the CV lacks or is weak on. */
    @JsonProperty("gap_areas")
    private List<String> gapAreas;

    /** Technologies explicitly required by the JD. */
    @JsonProperty("tech_stack_required")
    private List<String> techStackRequired;

    /** Technologies the candidate possesses (from CV). */
    @JsonProperty("tech_stack_possessed")
    private List<String> techStackPossessed;

    /** Target business domain: fintech | e-commerce | healthcare | SaaS | enterprise | startup | other */
    @JsonProperty("target_domain")
    private String targetDomain;

    /** Role type: backend | frontend | fullstack | devops | data_engineer | ML_engineer | security | mobile | other */
    @JsonProperty("role_type")
    private String roleType;
}
