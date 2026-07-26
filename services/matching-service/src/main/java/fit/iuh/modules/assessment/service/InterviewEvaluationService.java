package fit.iuh.modules.assessment.service;

import fit.iuh.modules.assessment.dto.InterviewEvaluationRequest;

public interface InterviewEvaluationService {
    String evaluateSession(InterviewEvaluationRequest request);
}
