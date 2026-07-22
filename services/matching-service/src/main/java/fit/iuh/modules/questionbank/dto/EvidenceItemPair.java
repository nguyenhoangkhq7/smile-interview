package fit.iuh.modules.questionbank.dto;

public record EvidenceItemPair(
        Long criteriaId,
        String criteriaName,
        String jdRequirement,
        String cvEvidence,
        String status,
        String reasoning,
        Double weightUsed,
        String questionType
) {}
