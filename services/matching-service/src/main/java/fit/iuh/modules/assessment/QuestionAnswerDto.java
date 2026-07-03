package fit.iuh.modules.assessment;

public record QuestionAnswerDto(
    String question,
    String answer,
    Integer score,
    String strengths
) {}
