package fit.iuh.modules.evaluation;

public record EvaluationResult(
    String decision,
    String reasoning,
    String followUpQuestion,
    int score,
    String evaluation
) {}
