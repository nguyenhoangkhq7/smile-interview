package fit.iuh.modules.assessment.gate;

import fit.iuh.modules.assessment.util.ResumeHeuristicsUtil;
import org.springframework.stereotype.Component;

import java.util.Locale;

@Component
public class YoeGateEvaluator implements GateEvaluator {

    @Override
    public boolean supports(String criteriaName) {
        if (criteriaName == null) return false;
        String lower = criteriaName.toLowerCase(Locale.ROOT);
        return lower.contains("experience") || lower.contains("yoe") || lower.contains("kinh nghiệm");
    }

    @Override
    public GateEvaluationResult evaluate(String criteriaName, String requiredValue, String cvContent) {
        double candidateYoe = ResumeHeuristicsUtil.calculateCandidateYoe(cvContent);
        double reqYoe = ResumeHeuristicsUtil.parseRequiredYoe(requiredValue);
        boolean pass = candidateYoe >= reqYoe;

        String cvEvidence = candidateYoe > 0
                ? candidateYoe + " years of experience"
                : (pass ? "0 YOE (Fresher/Entry-level requirement met)" : "No quantifiable experience found");

        String reasoning = pass
                ? "Candidate meets the required experience duration."
                : "Candidate experience duration does not meet the minimum requirement (" + reqYoe + " years required vs " + candidateYoe + " years found).";

        return new GateEvaluationResult(true, pass, cvEvidence, reasoning);
    }
}
