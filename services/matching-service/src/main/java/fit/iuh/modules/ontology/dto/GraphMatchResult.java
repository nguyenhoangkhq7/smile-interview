package fit.iuh.modules.ontology.dto;

import com.fasterxml.jackson.annotation.JsonProperty;

public record GraphMatchResult(
        @JsonProperty("required_skill")
        String requiredSkill,

        @JsonProperty("candidate_evidence")
        String candidateEvidence,

        @JsonProperty("matched_skill")
        String matchedSkill,

        @JsonProperty("similarity_score")
        double similarityScore,

        @JsonProperty("match_status")
        String matchStatus,

        @JsonProperty("relation_path")
        String relationPath,

        @JsonProperty("explanation")
        String explanation
) {}
