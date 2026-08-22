package fit.iuh.modules.assessment.gate;

import fit.iuh.modules.assessment.util.ResumeHeuristicsUtil;
import org.springframework.stereotype.Component;

import java.util.Locale;

@Component
public class DegreeGateEvaluator implements GateEvaluator {

    @Override
    public boolean supports(String criteriaName) {
        if (criteriaName == null) return false;
        String lower = criteriaName.toLowerCase(Locale.ROOT);
        return lower.contains("degree")
                || lower.contains("education")
                || lower.contains("academic")
                || lower.contains("university")
                || lower.contains("bachelor")
                || lower.contains("học vấn")
                || lower.contains("bằng cấp")
                || lower.contains("đại học");
    }

    @Override
    public GateEvaluationResult evaluate(String criteriaName, String requiredValue, String cvContent) {
        String effectiveReq = (requiredValue != null && !requiredValue.isBlank()) ? requiredValue : criteriaName;
        boolean hasDegree = ResumeHeuristicsUtil.checkDegreeInCv(cvContent, effectiveReq);
        String cvEvidence = hasDegree
                ? "Degree/Education requirement met in CV"
                : "No matching higher education degree found in CV for requirement: " + (effectiveReq != null ? effectiveReq : "Degree");

        String reasoning = hasDegree
                ? "Candidate meets the formal education requirement (" + (effectiveReq != null ? effectiveReq : "Degree") + ")."
                : "Candidate CV does not meet the specified degree level qualification (" + (effectiveReq != null ? effectiveReq : "Degree") + ").";

        return new GateEvaluationResult(true, hasDegree, cvEvidence, reasoning);
    }
}
