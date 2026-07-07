package fit.iuh.modules.questionbank;

import com.fasterxml.jackson.annotation.JsonIgnoreProperties;
import com.fasterxml.jackson.annotation.JsonProperty;
import fit.iuh.modules.assessment.JobCategory;
import fit.iuh.modules.assessment.SeniorityLevel;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.util.List;

/**
 * Structured context used to drive interview question generation.
 *
 * <p>Populated programmatically from {@link fit.iuh.modules.assessment.ResumeAssessment}
 * (no extra LLM call required). The fields {@link #candidateLevel} and {@link #roleType}
 * are now typed as {@link SeniorityLevel} and {@link JobCategory} ENUMs respectively,
 * enforcing type safety across the pipeline.
 *
 * <h3>ENUM Serialization</h3>
 * Jackson serializes ENUMs to their {@code .name()} string (e.g., {@code "FRESHER"})
 * when stored as JSONB in the DB. The LLM prompt receives {@code enum.name()} via explicit
 * {@code .name()} calls in {@link QuestionBankService} — ensuring the LLM gets a clean
 * uppercase string rather than an enum reference.
 */
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
@JsonIgnoreProperties(ignoreUnknown = true)
public class CandidateContextDto {

    /**
     * Inferred seniority level from the JD, mapped from {@link SeniorityLevel} ENUM.
     * JSON property kept as "candidate_level" for backward compat with stored JSONB.
     */
    @JsonProperty("candidate_level")
    private SeniorityLevel candidateLevel;

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

    /**
     * Role type mapped from {@link JobCategory} ENUM.
     * JSON property kept as "role_type" for backward compat with stored JSONB.
     */
    @JsonProperty("role_type")
    private JobCategory roleType;
}
