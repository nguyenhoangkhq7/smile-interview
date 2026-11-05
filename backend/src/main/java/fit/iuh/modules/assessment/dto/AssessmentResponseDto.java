package fit.iuh.modules.assessment.dto;

import com.fasterxml.jackson.annotation.JsonAlias;
import com.fasterxml.jackson.annotation.JsonIgnoreProperties;
import com.fasterxml.jackson.annotation.JsonInclude;
import com.fasterxml.jackson.annotation.JsonProperty;

import java.util.List;
import java.util.Map;

@JsonIgnoreProperties(ignoreUnknown = true)
@JsonInclude(JsonInclude.Include.NON_NULL)
public record AssessmentResponseDto(
        @JsonProperty("must_have_evidence_items")
        @JsonAlias({"must_have_evidence_items", "evidence_items"})
        List<EvidenceItem> mustHaveEvidenceItems,

        @JsonProperty("prefer_to_have_evidence_items")
        @JsonAlias({"prefer_to_have_evidence_items", "additional_evidence_items"})
        List<AdHocEvidenceItem> preferToHaveEvidenceItems
) {

    @JsonIgnoreProperties(ignoreUnknown = true)
    @JsonInclude(JsonInclude.Include.NON_NULL)
    public record MatchMetadata(
            @JsonProperty("source_type") String sourceType,
            @JsonProperty("badge_label") String badgeLabel,
            @JsonProperty("badge_color") String badgeColor
    ) {}

    @JsonIgnoreProperties(ignoreUnknown = true)
    @JsonInclude(JsonInclude.Include.NON_NULL)
    public record EvidenceItem(
            @JsonProperty("criteria_id")
            Long criteriaId,

            @JsonProperty("criteria_name")
            String criteriaName,

            @JsonProperty("importance")
            String importance,

            @JsonProperty("jd_requirement")
            String jdRequirement,

            @JsonProperty("cv_evidence")
            String cvEvidence,

            @JsonProperty(value = "cv_quote", access = JsonProperty.Access.WRITE_ONLY)
            String cvQuote,

            @JsonProperty("status")
            String status,

            @JsonProperty("reasoning")
            String reasoning,

            @JsonProperty(value = "weight_used", access = JsonProperty.Access.WRITE_ONLY)
            Double weightUsed,

            @JsonProperty(value = "score_contribution", access = JsonProperty.Access.WRITE_ONLY)
            Double scoreContribution,

            @JsonProperty(value = "grounding_score", access = JsonProperty.Access.WRITE_ONLY)
            Double groundingScore,

            @JsonProperty(value = "confidence_votes", access = JsonProperty.Access.WRITE_ONLY)
            Map<String, Integer> confidenceVotes,

            @JsonProperty(value = "low_confidence", access = JsonProperty.Access.WRITE_ONLY)
            Boolean lowConfidence,

            @JsonProperty(value = "needs_manual_review", access = JsonProperty.Access.WRITE_ONLY)
            Boolean needsManualReview,
            
            @JsonProperty("match_metadata")
            MatchMetadata matchMetadata
    ) {}

    @JsonIgnoreProperties(ignoreUnknown = true)
    @JsonInclude(JsonInclude.Include.NON_NULL)
    public record AdHocEvidenceItem(
            @JsonProperty("criteria_id")
            Long criteriaId,

            @JsonProperty("criteria_name")
            String criteriaName,

            @JsonProperty("importance")
            String importance,

            @JsonProperty("jd_requirement")
            String jdRequirement,

            @JsonProperty("cv_evidence")
            String cvEvidence,

            @JsonProperty(value = "cv_quote", access = JsonProperty.Access.WRITE_ONLY)
            String cvQuote,

            @JsonProperty("status")
            String status,

            @JsonProperty("reasoning")
            String reasoning,

            @JsonProperty("match_metadata")
            MatchMetadata matchMetadata
    ) {}
}
