package fit.iuh.integration.ai;

import fit.iuh.modules.assessment.dto.AssessmentResponse;
import fit.iuh.modules.assessment.dto.InterviewEvaluationRequest;
import fit.iuh.modules.questionbank.dto.CandidateContextDto;
import fit.iuh.modules.questionbank.dto.EvidenceItemPair;
import fit.iuh.modules.questionbank.dto.QuestionAssignment;
import fit.iuh.modules.questionbank.dto.QuestionConfigDto;
import fit.iuh.modules.questionbank.dto.QuestionDto;

import java.util.List;

/**
 * Port interface for all AI operations.
 * Allows seamless switching between local Spring Boot AI implementation
 * and external Python FastAPI AI service via application configuration.
 */
public interface AiServicePort {

    AssessmentResponse evaluateCvJd(String sessionId, boolean forceRefresh, String fromSessionId);

    String evaluateSession(InterviewEvaluationRequest request);

    List<QuestionDto> generateQuestions(String type, CandidateContextDto context, List<QuestionAssignment> assignments, QuestionConfigDto config);

    QuestionDto regenerateSingleQuestion(
            String type,
            String difficulty,
            CandidateContextDto context,
            List<EvidenceItemPair> allEvidenceItems,
            List<QuestionDto> existingQuestions);
}
