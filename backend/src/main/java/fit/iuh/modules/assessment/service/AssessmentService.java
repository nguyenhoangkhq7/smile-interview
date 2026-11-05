package fit.iuh.modules.assessment.service;

import fit.iuh.modules.assessment.dto.AssessmentResponse;

public interface AssessmentService {
    AssessmentResponse assessResumeBlocking(String sessionId, boolean forceRefresh, String fromSessionId);
}
