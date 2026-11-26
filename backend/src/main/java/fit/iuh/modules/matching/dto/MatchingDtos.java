package fit.iuh.modules.matching.dto;

import com.fasterxml.jackson.annotation.JsonIgnoreProperties;
import com.fasterxml.jackson.annotation.JsonProperty;

import java.util.List;

/**
 * DTOs for Contribution 1: Semantic Similarity Metric (Sentence-BERT + GNN Skill Dependency Graph).
 * Mirrors ai-service `module1_matcher.schemas` and `src.domain.models`.
 */
public final class MatchingDtos {

    private MatchingDtos() {}

    /** Input: raw CV + JD text (PDF files are sent to the AI service as multipart instead). */
    @JsonIgnoreProperties(ignoreUnknown = true)
    public record MatchRequestDto(
            @JsonProperty("cv_text") String cvText,
            @JsonProperty("jd_text") String jdText,
            @JsonProperty("analysis_id") String analysisId
    ) {}

    @JsonIgnoreProperties(ignoreUnknown = true)
    public record ExtractedSkillDto(
            @JsonProperty("skill_id") String skillId,
            @JsonProperty("type") String type,
            @JsonProperty("confidence") double confidence,
            @JsonProperty("evidence_spans") List<String> evidenceSpans
    ) {}

    /** soft_match comes from SBERT; w_j (JD skill importance) comes from the GNN. */
    @JsonIgnoreProperties(ignoreUnknown = true)
    public record MatchResultDto(
            @JsonProperty("jd_skill_id") String jdSkillId,
            @JsonProperty("w_j") double wJ,
            @JsonProperty("matched_cv_skill_id") String matchedCvSkillId,
            @JsonProperty("soft_match") double softMatch
    ) {}

    @JsonIgnoreProperties(ignoreUnknown = true)
    public record Module1OutputDto(
            @JsonProperty("cv_skills") List<ExtractedSkillDto> cvSkills,
            @JsonProperty("jd_skills") List<ExtractedSkillDto> jdSkills,
            @JsonProperty("match_results") List<MatchResultDto> matchResults
    ) {}
}
