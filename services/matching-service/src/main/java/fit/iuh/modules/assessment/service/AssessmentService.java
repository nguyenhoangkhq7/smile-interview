package fit.iuh.modules.assessment.service;

import fit.iuh.modules.assessment.dto.AssessmentResponse;
import fit.iuh.modules.assessment.dto.AssessmentResponseDto;
import fit.iuh.modules.assessment.dto.InterviewEvaluationRequest;
import fit.iuh.modules.rulengine.repository.JobCriteriaRepository.CriteriaWeightProjection;

import java.util.List;

public interface AssessmentService {

    AssessmentResponse assessResumeBlocking(String sessionId, boolean forceRefresh);

    AssessmentResponse assessResumeBlocking(String sessionId, boolean forceRefresh, String fromSessionId);

    AssessmentResponse assessResumeBlocking(String sessionId, boolean forceRefresh, String fromSessionId, Boolean includeNotApplicable);

    String evaluateSession(InterviewEvaluationRequest request);

    AssessmentResponseDto runBatchedAssessmentWithSelfConsistency(
            String sessionId,
            String fullCvMarkdown,
            String fullJdMarkdown,
            List<CriteriaWeightProjection> criteriaList);
}
