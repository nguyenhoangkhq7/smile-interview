package fit.iuh.dto;

public record QuestionAnswerDto(
    String question,
    String answer,
    Integer score,
    String strengths
) {}
