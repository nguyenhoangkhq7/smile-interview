package fit.iuh.modules.skillgap.dto;

import com.fasterxml.jackson.annotation.JsonIgnoreProperties;
import com.fasterxml.jackson.annotation.JsonInclude;
import com.fasterxml.jackson.annotation.JsonProperty;

import fit.iuh.modules.matching.dto.MatchingDtos.ExtractedSkillDto;
import fit.iuh.modules.matching.dto.EligibilityReportDto;

import java.util.List;
import java.util.Map;

/**
 * DTOs for Contribution 2: Skill-Gap Detection Algorithm.
 */
public final class SkillGapDtos {

    private SkillGapDtos() {}

    @JsonIgnoreProperties(ignoreUnknown = true)
    public record SkillGapResultDto(
            @JsonProperty("jd_skill_id") String jdSkillId,
            @JsonProperty("jd_skill_name") String jdSkillName,
            @JsonProperty("matched_cv_skill_name") String matchedCvSkillName,
            @JsonProperty("semantic_alignment") String semanticAlignment,
            @JsonProperty("matched_cv_skill_id") String matchedCvSkillId,
            @JsonProperty("priority") double priority,
            @JsonProperty("required_proficiency") double requiredProficiency,
            @JsonProperty("cv_evidence_spans") List<String> cvEvidenceSpans,
            @JsonProperty("context_job") String contextJob,
            @JsonProperty("importance_weight") double importanceWeight,
            @JsonInclude(JsonInclude.Include.NON_EMPTY)
            @JsonProperty("jd_evidence_spans") List<String> jdEvidenceSpans,
            // Keep HTTP DTOs independent of Jackson 2/3 tree implementations.
            @JsonProperty("job_tasks") List<Map<String, Object>> jobTasks
    ) {}

    @JsonIgnoreProperties(ignoreUnknown = true)
    public record SkillGapReportDto(
            @JsonProperty("matching_score") Double matchingScore,
            @JsonProperty("degraded") boolean degraded,
            @JsonInclude(JsonInclude.Include.NON_NULL)
            @JsonProperty("cv_skills") List<ExtractedSkillDto> cvSkills,
            @JsonInclude(JsonInclude.Include.NON_NULL)
            @JsonProperty("eligibility") EligibilityReportDto eligibility
    ) {}

    @JsonIgnoreProperties(ignoreUnknown = true)
    public record AnalyzeWithReportResponseDto(
            @JsonProperty("analysis_id") String analysisId,
            @JsonProperty("skills") List<SkillGapResultDto> skills,
            @JsonProperty("report") SkillGapReportDto report
    ) {}
}
