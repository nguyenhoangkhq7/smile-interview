package fit.iuh.dto;

import com.fasterxml.jackson.annotation.JsonProperty;

import java.util.List;

/**
 * Structured DTO mapping the exact 3-part JSON schema output by the LLM assessment prompt.
 *
 * <p>This record is used in two ways:
 * <ol>
 *   <li><strong>Deserialization</strong> — parsed from the raw LLM JSON response via
 *       {@code ObjectMapper.readValue(json, AssessmentResponseDto.class)}.
 *   <li><strong>JSONB persistence</strong> — the nested {@link SectionWiseFeedback} record
 *       is stored directly in the {@code section_wise_feedback} JSONB column of the
 *       {@code resume_assessments} table.
 * </ol>
 *
 * <h3>Expected LLM JSON Schema</h3>
 * <pre>{@code
 * {
 *   "competency_fit_score": 78,
 *   "section_wise_feedback": {
 *     "skills_evaluation": {
 *       "analysis": "...",
 *       "critical_missing_skills": ["Docker", "Kubernetes"]
 *     },
 *     "experience_evaluation": "...",
 *     "project_evaluation": "..."
 *   },
 *   "actionable_improvement_suggestions": [
 *     "Add Docker to your projects section.",
 *     "..."
 *   ]
 * }
 * }</pre>
 */
public record AssessmentResponseDto(

        /**
         * Output 1 (SimInterview): Competency-level fit score, 0-100.
         * Represents the overall semantic alignment between the candidate's competencies and JD requirements.
         */
        @JsonProperty("competency_fit_score")
        Integer competencyFitScore,

        /**
         * Output 2 (SimInterview): Section-wise feedback object.
         * Stored as JSONB in the database, enabling native JSON queries on the feedback sub-fields.
         */
        @JsonProperty("section_wise_feedback")
        SectionWiseFeedback sectionWiseFeedback,

        /**
         * Output 3 (SimInterview): Ordered list of actionable improvement suggestions for the candidate.
         * Stored as a JSONB array in the database.
         */
        @JsonProperty("actionable_improvement_suggestions")
        List<String> actionableImprovementSuggestions

) {

    // -------------------------------------------------------------------------
    // Nested Records — mirrors the nested JSON structure
    // -------------------------------------------------------------------------

    /**
     * The structured section-wise feedback object containing skill, experience,
     * and project evaluations.
     *
     * <p>{@code critical_missing_skills} is intentionally nested here (inside
     * {@link SkillsEvaluation}) so that Module 3 (Question Bank Generation) can
     * directly read the missing skills from the JSONB column using the native
     * PostgreSQL JSON operator: {@code section_wise_feedback -> 'skills_evaluation'
     * -> 'critical_missing_skills'}.
     */
    public record SectionWiseFeedback(

            /** Skill match analysis plus the list of required-but-absent skills. */
            @JsonProperty("skills_evaluation")
            SkillsEvaluation skillsEvaluation,

            /** 1-2 sentence analysis of whether the candidate's experience level meets JD expectations. */
            @JsonProperty("experience_evaluation")
            String experienceEvaluation,

            /** 1-2 sentence analysis of the relevance and transferability of the candidate's projects. */
            @JsonProperty("project_evaluation")
            String projectEvaluation

    ) {}

    /**
     * Granular skill evaluation containing a qualitative analysis narrative
     * and a machine-readable list of critical missing skills.
     *
     * <p>The {@code criticalMissingSkills} list is the key input for generating
     * targeted interview questions in Module 3.
     */
    public record SkillsEvaluation(

            /** Short qualitative analysis of the candidate's overall skill alignment with the JD. */
            @JsonProperty("analysis")
            String analysis,

            /** Skills that are explicitly required by the JD but completely absent from the CV. */
            @JsonProperty("critical_missing_skills")
            List<String> criticalMissingSkills

    ) {}
}
