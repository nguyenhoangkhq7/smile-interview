package fit.iuh.modules.assessment.gate;

public record GateEvaluationResult(
        boolean evaluated,
        boolean passed,
        String cvEvidence,
        String reasoning
) {}
