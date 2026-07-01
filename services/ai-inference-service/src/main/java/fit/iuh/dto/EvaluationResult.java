package fit.iuh.dto;

public record EvaluationResult(
    String decision,
    String reasoning,
    String followUpQuestion,
    int score
) {}
