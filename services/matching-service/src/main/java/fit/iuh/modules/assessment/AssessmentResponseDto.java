package fit.iuh.modules.assessment;

import com.fasterxml.jackson.annotation.JsonProperty;
import java.util.List;

/**
 * Rich DTO mapping the exact 3-part JSON schema output by the LLM assessment prompt.
 */
public record AssessmentResponseDto(

        @JsonProperty("role_type_detected")
        String roleTypeDetected,

        @JsonProperty("candidate_level")
        String candidateLevel,

        @JsonProperty("years_of_experience_estimate")
        String yearsOfExperienceEstimate,

        @JsonProperty("overall_fit")
        OverallFit overallFit,

        @JsonProperty("section_wise_feedback")
        SectionWiseFeedback sectionWiseFeedback,

        @JsonProperty("strong_areas")
        List<String> strongAreas,

        @JsonProperty("gap_areas")
        List<String> gapAreas,

        @JsonProperty("critical_missing_skills")
        List<String> criticalMissingSkills,

        @JsonProperty("actionable_improvement_suggestions")
        List<String> actionableImprovementSuggestions

) {

    public record OverallFit(
            @JsonProperty("competency_fit_score")
            Integer competencyFitScore,

            @JsonProperty("technical_depth_score")
            Integer technicalDepthScore,

            @JsonProperty("match_level")
            String matchLevel
    ) {}

    public record SectionWiseFeedback(
            @JsonProperty("cs_fundamentals")
            CsFundamentals csFundamentals,

            @JsonProperty("tech_stack_alignment")
            TechStackAlignment techStackAlignment,

            @JsonProperty("project_technical_depth")
            ProjectTechnicalDepth projectTechnicalDepth,

            @JsonProperty("engineering_practices")
            EngineeringPractices engineeringPractices,

            @JsonProperty("experience_evaluation")
            String experienceEvaluation,

            @JsonProperty("education_and_certifications")
            String educationAndCertifications
    ) {}

    public record CsFundamentals(
            @JsonProperty("analysis")
            String analysis,

            @JsonProperty("evidenced_topics")
            List<String> evidencedTopics
    ) {}

    public record TechStackAlignment(
            @JsonProperty("analysis")
            String analysis,

            @JsonProperty("matched")
            List<String> matched,

            @JsonProperty("weak_evidence")
            List<String> weakEvidence,

            @JsonProperty("missing")
            List<String> missing
    ) {}

    public record ProjectTechnicalDepth(
            @JsonProperty("analysis")
            String analysis,

            @JsonProperty("complexity_level")
            String complexityLevel,

            @JsonProperty("depth_signals")
            List<String> depthSignals
    ) {}

    public record EngineeringPractices(
            @JsonProperty("analysis")
            String analysis,

            @JsonProperty("evidenced")
            List<String> evidenced
    ) {}
}
