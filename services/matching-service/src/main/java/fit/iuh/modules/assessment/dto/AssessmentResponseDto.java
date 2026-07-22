package fit.iuh.modules.assessment.dto;

import com.fasterxml.jackson.annotation.JsonIgnoreProperties;
import com.fasterxml.jackson.annotation.JsonProperty;

import java.util.List;
import java.util.Map;

@JsonIgnoreProperties(ignoreUnknown = true)
public record AssessmentResponseDto(
        @JsonProperty("evidence_items")
        List<EvidenceItem> evidenceItems,

        @JsonProperty("additional_evidence_items")
        List<AdHocEvidenceItem> additionalEvidenceItems
) {

    @JsonIgnoreProperties(ignoreUnknown = true)
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

            @JsonProperty("status")
            String status,

            @JsonProperty("reasoning")
            String reasoning,

            @JsonProperty("weight_used")
            Double weightUsed,

            @JsonProperty("score_contribution")
            Double scoreContribution,

            @JsonProperty("source_span")
            String sourceSpan,

            @JsonProperty("grounding_score")
            Double groundingScore,

            @JsonProperty("confidence_votes")
            Map<String, Integer> confidenceVotes,

            @JsonProperty("low_confidence")
            Boolean lowConfidence,

            @JsonProperty("needs_manual_review")
            Boolean needsManualReview
    ) {}

    @JsonIgnoreProperties(ignoreUnknown = true)
    public record AdHocEvidenceItem(
            @JsonProperty("criteria_name")
            String criteriaName,

            @JsonProperty("importance")
            String importance,

            @JsonProperty("jd_requirement")
            String jdRequirement,

            @JsonProperty("cv_evidence")
            String cvEvidence,

            @JsonProperty("status")
            String status,

            @JsonProperty("reasoning")
            String reasoning,

            @JsonProperty("source_span")
            String sourceSpan
    ) {}
}
