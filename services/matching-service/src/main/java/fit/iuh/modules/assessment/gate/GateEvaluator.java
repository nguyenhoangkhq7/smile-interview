package fit.iuh.modules.assessment.gate;

/**
 * Strategy interface for evaluating an eligibility gate against a candidate CV.
 */
public interface GateEvaluator {

    /**
     * Determines whether this evaluator handles the given gate criteria name.
     */
    boolean supports(String criteriaName);

    /**
     * Evaluates candidate CV against the required value for this gate.
     */
    GateEvaluationResult evaluate(String criteriaName, String requiredValue, String cvContent);
}
