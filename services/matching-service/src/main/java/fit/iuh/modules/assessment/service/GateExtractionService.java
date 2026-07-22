package fit.iuh.modules.assessment.service;

import fit.iuh.modules.assessment.entity.Eligibility;

public interface GateExtractionService {
    Eligibility evaluateEligibility(String jdContent, String cvContent);
}
