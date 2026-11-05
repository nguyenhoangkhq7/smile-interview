package fit.iuh.integration.ai;

import fit.iuh.modules.assessment.dto.AssessmentResponse;
import fit.iuh.modules.assessment.dto.InterviewEvaluationRequest;
import fit.iuh.modules.assessment.service.AssessmentService;
import fit.iuh.modules.assessment.service.InterviewEvaluationService;
import fit.iuh.modules.questionbank.dto.CandidateContextDto;
import fit.iuh.modules.questionbank.dto.EvidenceItemPair;
import fit.iuh.modules.questionbank.dto.QuestionAssignment;
import fit.iuh.modules.questionbank.dto.QuestionConfigDto;
import fit.iuh.modules.questionbank.dto.QuestionDto;
import fit.iuh.modules.questionbank.service.QuestionGenerationService;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.stereotype.Service;

import java.util.List;

/**
 * Adapter delegating to existing local Java LangChain4j / Spring AI implementations.
 * Active when app.ai.provider=local or not configured.
 */
@Slf4j
@Service
@RequiredArgsConstructor
@ConditionalOnProperty(name = "app.ai.provider", havingValue = "local", matchIfMissing = true)
public class LocalAiAdapter implements AiServicePort {

    private final AssessmentService assessmentService;
    private final InterviewEvaluationService interviewEvaluationService;
    private final QuestionGenerationService questionGenerationService;

    @Override
    public AssessmentResponse evaluateCvJd(String sessionId, boolean forceRefresh, String fromSessionId) {
        log.info("[LocalAiAdapter] Processing CV-JD assessment locally for sessionId={}", sessionId);
        return assessmentService.assessResumeBlocking(sessionId, forceRefresh, fromSessionId);
    }

    @Override
    public String evaluateSession(InterviewEvaluationRequest request) {
        log.info("[LocalAiAdapter] Processing session evaluation locally for roleTitle={}", request.roleTitle());
        return interviewEvaluationService.evaluateSession(request);
    }

    @Override
    public List<QuestionDto> generateQuestions(String type, CandidateContextDto context, List<QuestionAssignment> assignments, QuestionConfigDto config) {
        log.info("[LocalAiAdapter] Generating questions locally for category={}", type);
        return questionGenerationService.generateForCategory(type, context, assignments, config);
    }

    @Override
    public QuestionDto regenerateSingleQuestion(
            String type,
            String difficulty,
            CandidateContextDto context,
            List<EvidenceItemPair> allEvidenceItems,
            List<QuestionDto> existingQuestions) {
        log.info("[LocalAiAdapter] Regenerating single question locally for category={}, difficulty={}", type, difficulty);
        return questionGenerationService.regenerateSingle(type, difficulty, context, allEvidenceItems, existingQuestions);
    }
}
