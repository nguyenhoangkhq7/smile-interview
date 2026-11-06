package fit.iuh.modules.skillgap.dto;

import com.fasterxml.jackson.annotation.JsonIgnoreProperties;
import com.fasterxml.jackson.annotation.JsonProperty;

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
            @JsonProperty("semantic_alignment") String semanticAlignment,
            @JsonProperty("matched_cv_skill_id") String matchedCvSkillId,
            @JsonProperty("is_substituted") boolean isSubstituted,
            @JsonProperty("gap_magnitude") double gapMagnitude,
            @JsonProperty("severity") double severity,
            @JsonProperty("priority") double priority,
            @JsonProperty("required_proficiency") double requiredProficiency,
            @JsonProperty("candidate_proficiency") double candidateProficiency,
            @JsonProperty("cv_evidence_spans") List<String> cvEvidenceSpans,
            @JsonProperty("context_job") String contextJob,
            @JsonProperty("suggested_strategy") String suggestedStrategy,
            @JsonProperty("degraded") boolean degraded,
            @JsonProperty("flags") List<String> flags
    ) {}

    @JsonIgnoreProperties(ignoreUnknown = true)
    public record AnalyzeWithReportResponseDto(
            @JsonProperty("analysis_id") String analysisId,
            @JsonProperty("skills") List<SkillGapResultDto> skills,
            @JsonProperty("report") Map<String, Object> report
    ) {}
}
