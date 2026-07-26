package fit.iuh.modules.assessment.dto;

import java.util.List;

public record ClassifiedCriteriaBundle(
        List<ClassifiedCriteria> dbCriteria,
        List<JdExtraCriteria> jdExtras
) {
    public record ClassifiedCriteria(
            Long criteriaId,
            String criteriaName,
            String promptInstruction,
            Double weightPercentage,
            String importance  // "required" | "preferred" | "not_in_jd"
    ) {}

    public record JdExtraCriteria(
            String name,
            String importance,         // "required" | "preferred"
            String promptInstruction
    ) {}

    /**
     * Returns DB criteria to send to the LLM for evaluation.
     *  - comprehensive=true  : ALL criteria (including not_in_jd) — used for full analysis mode
     *  - comprehensive=false : Excludes not_in_jd criteria to save LLM tokens.
     *                         The JdCriteriaClassifier MUST be conservative: only assign
     *                         not_in_jd to criteria completely unrelated to the job domain.
     *                         Anything even tangentially relevant should be "preferred".
     */
    public List<ClassifiedCriteria> dbCriteriaForMode(boolean comprehensive) {
        if (comprehensive) {
            return dbCriteria != null ? dbCriteria : List.of();
        }
        if (dbCriteria == null) return List.of();
        return dbCriteria.stream()
                .filter(c -> !"not_in_jd".equalsIgnoreCase(c.importance()))
                .toList();
    }

    public List<JdExtraCriteria> jdExtras() {
        return jdExtras != null ? jdExtras : List.of();
    }
}
