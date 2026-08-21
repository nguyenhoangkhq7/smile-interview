package fit.iuh.modules.assessment.dto;

import com.fasterxml.jackson.annotation.JsonIgnoreProperties;
import com.fasterxml.jackson.annotation.JsonProperty;
import fit.iuh.modules.assessment.entity.JobCategory;
import fit.iuh.modules.assessment.entity.SeniorityLevel;
import fit.iuh.modules.assessment.gate.EligibilityGateService.GateCheckDto;
import fit.iuh.modules.rulengine.repository.JobCriteriaRepository.CriteriaWeightProjection;

import java.io.Serializable;
import java.util.List;

@JsonIgnoreProperties(ignoreUnknown = true)
public record PreparedJdContext(
        @JsonProperty("category")
        JobCategory category,

        @JsonProperty("target_level")
        SeniorityLevel targetLevel,

        @JsonProperty("accepted_levels")
        List<SeniorityLevel> acceptedLevels,

        @JsonProperty("bundle")
        ClassifiedCriteriaBundle bundle,

        @JsonProperty("criteria_list")
        List<CriteriaWeightDto> criteriaList,

        @JsonProperty("gate_requirements")
        List<GateCheckDto> gateRequirements
) implements Serializable {

    @JsonIgnoreProperties(ignoreUnknown = true)
    public record JdBaseProfile(
            @JsonProperty("category")
            JobCategory category,

            @JsonProperty("accepted_levels")
            List<SeniorityLevel> acceptedLevels,

            @JsonProperty("gate_requirements")
            List<GateCheckDto> gateRequirements,

            @JsonProperty("raw_bundle")
            ClassifiedCriteriaBundle rawBundle
    ) implements Serializable {}

    @JsonIgnoreProperties(ignoreUnknown = true)
    public record CriteriaWeightDto(
            @JsonProperty("criteria_id")
            Long criteriaId,

            @JsonProperty("criteria_name")
            String criteriaName,

            @JsonProperty("prompt_instruction")
            String promptInstruction,

            @JsonProperty("level_prompt_instruction")
            String levelPromptInstruction,

            @JsonProperty("weight_percentage")
            Double weightPercentage,

            @JsonProperty("embedding")
            String embedding
    ) implements CriteriaWeightProjection, Serializable {
        @java.io.Serial
        private static final long serialVersionUID = 1L;

        @Override public Long getCriteriaId() { return criteriaId; }
        @Override public String getCriteriaName() { return criteriaName; }
        @Override public String getPromptInstruction() { return promptInstruction; }
        @Override public String getLevelPromptInstruction() { return levelPromptInstruction; }
        @Override public Double getWeightPercentage() { return weightPercentage; }
        @Override public String getEmbedding() { return embedding; }
        @Override public Integer getSourceDepth() { return null; }
    }
}