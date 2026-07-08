package fit.iuh.modules.questionbank;

/**
 * Represents a planned question assignment before generation.
 *
 * @param item       The evidence item this question targets (can be null for generic questions)
 * @param category   The category of the question (behavioural, technical, coding, system_design)
 * @param difficulty The target difficulty (easy, medium, hard) - relative to candidate level
 * @param isFollowUp Whether this is a secondary follow-up question for the same item
 */
public record QuestionAssignment(
        EvidenceItemPair item,
        String category,
        String difficulty,
        boolean isFollowUp
) {
}
