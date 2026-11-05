package fit.iuh.modules.ontology.dto;

import com.fasterxml.jackson.annotation.JsonProperty;

public record SkillRelationDto(
        @JsonProperty("source")
        String source,

        @JsonProperty("target")
        String target,

        @JsonProperty("relation")
        String relation,

        @JsonProperty("weight")
        double weight
) {}
