package fit.iuh.modules.assessment.dto;

import fit.iuh.modules.assessment.entity.SuggestedCriteria;
import java.time.LocalDateTime;

public record SuggestedCriteriaDto(
        Long id,
        String criteriaName,
        String detectedCategory,
        String exampleRequirement,
        int occurrenceCount,
        LocalDateTime firstSeenAt,
        LocalDateTime lastSeenAt,
        Boolean promoted,
        LocalDateTime promotedAt
) {
    public static SuggestedCriteriaDto from(SuggestedCriteria s) {
        if (s == null) return null;
        return new SuggestedCriteriaDto(
                s.getId(),
                s.getCriteriaName(),
                s.getDetectedCategory(),
                s.getExampleRequirement(),
                s.getOccurrenceCount(),
                s.getFirstSeenAt(),
                s.getLastSeenAt(),
                s.getPromoted(),
                s.getPromotedAt()
        );
    }
}
