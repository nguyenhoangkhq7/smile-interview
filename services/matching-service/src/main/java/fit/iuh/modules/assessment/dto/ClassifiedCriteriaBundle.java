package fit.iuh.modules.assessment.dto;

import java.util.List;

@com.fasterxml.jackson.annotation.JsonIgnoreProperties(ignoreUnknown = true)
public record ClassifiedCriteriaBundle(
        List<ClassifiedCriteria> dbCriteria,
        List<JdExtraCriteria> jdExtras
) {
    @com.fasterxml.jackson.annotation.JsonIgnoreProperties(ignoreUnknown = true)
    public record ClassifiedCriteria(
            Long criteriaId,
            String criteriaName,
            String promptInstruction,
            Double weightPercentage,
            String importance  // "required" | "preferred" | "not_in_jd"
    ) {}

    @com.fasterxml.jackson.annotation.JsonIgnoreProperties(ignoreUnknown = true)
    public record JdExtraCriteria(
            String name,
            String importance,         // "required" | "preferred"
            String promptInstruction
    ) {}

    /**
     * Returns active DB criteria to send to the LLM for evaluation (excludes not_in_jd criteria to save LLM tokens).
     */
    public List<ClassifiedCriteria> activeDbCriteria() {
        if (dbCriteria == null) return List.of();
        return dbCriteria.stream()
                .filter(c -> !"not_in_jd".equalsIgnoreCase(c.importance()))
                .toList();
    }

    public List<JdExtraCriteria> jdExtras() {
        return jdExtras != null ? jdExtras : List.of();
    }
}
