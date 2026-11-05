package fit.iuh.modules.questionbank.dto;

public record QuestionAssignment(
        String category,
        String difficulty,
        EvidenceItemPair item,
        boolean isFollowUp,
        String promptStrategy
) {}
