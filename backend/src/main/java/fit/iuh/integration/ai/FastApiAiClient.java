package fit.iuh.integration.ai;

import fit.iuh.exception.LlmApiException;
import fit.iuh.modules.assessment.dto.AssessmentResponse;
import fit.iuh.modules.assessment.dto.AssessmentResponseDto;
import fit.iuh.modules.assessment.dto.ImprovementResponseDto;
import fit.iuh.modules.assessment.dto.InterviewEvaluationRequest;
import fit.iuh.modules.assessment.entity.EligibilityStatus;
import fit.iuh.modules.assessment.entity.EvidenceItem;
import fit.iuh.modules.assessment.entity.Improvement;
import fit.iuh.modules.assessment.entity.JobCategory;
import fit.iuh.modules.assessment.entity.ResumeAssessment;
import fit.iuh.modules.assessment.entity.ScoreBreakdown;
import fit.iuh.modules.assessment.entity.SeniorityLevel;
import fit.iuh.modules.assessment.mapper.AssessmentMapper;
import fit.iuh.modules.assessment.repository.ResumeAssessmentRepository;
import fit.iuh.modules.chunking.repository.DocumentChunkRepository;
import fit.iuh.modules.questionbank.dto.CandidateContextDto;
import fit.iuh.modules.questionbank.dto.EvidenceItemPair;
import fit.iuh.modules.questionbank.dto.QuestionAssignment;
import fit.iuh.modules.questionbank.dto.QuestionConfigDto;
import fit.iuh.modules.questionbank.dto.QuestionDto;
import fit.iuh.modules.session.entity.Session;
import fit.iuh.modules.session.repository.SessionRepository;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.core.ParameterizedTypeReference;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.client.RestClient;

import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Optional;
import java.util.stream.Collectors;

/**
 * Client invoking external Python FastAPI AI service via REST JSON.
 * Active when app.ai.provider=fastapi.
 */
@Slf4j
@Service
@ConditionalOnProperty(name = "app.ai.provider", havingValue = "fastapi")
public class FastApiAiClient implements AiServicePort {

    private static final String IMPORTANCE_REQUIRED = "REQUIRED";
    private static final String IMPORTANCE_PREFERRED = "PREFERRED";
    private static final String IMPORTANCE_GATE = "GATE";
    private static final String PREFIX_QUICK_WIN = "[QW] ";
    private static final String PREFIX_SKILL_GAP = "[SG] ";

    private final RestClient restClient;
    private final SessionRepository sessionRepository;
    private final DocumentChunkRepository documentChunkRepository;
    private final ResumeAssessmentRepository resumeAssessmentRepository;

    public FastApiAiClient(
            @Value("${app.ai.fastapi.base-url:http://localhost:8000}") String baseUrl,
            SessionRepository sessionRepository,
            DocumentChunkRepository documentChunkRepository,
            ResumeAssessmentRepository resumeAssessmentRepository) {
        log.info("[FastApiAiClient] Initialized with Python AI base URL: {}", baseUrl);
        this.restClient = RestClient.builder().baseUrl(baseUrl).build();
        this.sessionRepository = sessionRepository;
        this.documentChunkRepository = documentChunkRepository;
        this.resumeAssessmentRepository = resumeAssessmentRepository;
    }

    @Override
    @Transactional
    public AssessmentResponse evaluateCvJd(String sessionId, boolean forceRefresh, String fromSessionId) {
        Optional<AssessmentResponse> cached = checkOrClearCache(sessionId, forceRefresh);
        if (cached.isPresent()) {
            return cached.get();
        }

        Session session = sessionRepository.findById(sessionId)
                .orElseThrow(() -> new LlmApiException("Session not found: " + sessionId));

        Map<String, Object> requestPayload = buildCvJdPayload(session, sessionId, forceRefresh, fromSessionId);
        log.info("[FastApiAiClient] Forwarding evaluateCvJd to Python FastAPI for sessionId={}", sessionId);

        AssessmentResponse response = restClient.post()
                .uri("/api/ai/cv-jd/match")
                .body(requestPayload)
                .retrieve()
                .body(AssessmentResponse.class);

        if (response == null) {
            throw new LlmApiException("Empty response from Python FastAPI CV-JD matching service.");
        }

        ResumeAssessment saved = persistExternalAssessment(sessionId, response);
        session.setAssessmentId(saved.getId());
        sessionRepository.save(session);

        response.setId(saved.getId());
        response.setSessionId(sessionId);
        response.setCreatedAt(saved.getCreatedAt());
        response.setCached(false);
        return response;
    }

    @Override
    public String evaluateSession(InterviewEvaluationRequest request) {
        log.info("[FastApiAiClient] Forwarding evaluateSession to Python FastAPI for roleTitle={}", request.roleTitle());
        return restClient.post()
                .uri("/api/ai/interview/evaluate")
                .body(request)
                .retrieve()
                .body(String.class);
    }

    @Override
    public List<QuestionDto> generateQuestions(
            String type,
            CandidateContextDto context,
            List<QuestionAssignment> assignments,
            QuestionConfigDto config) {
        log.info("[FastApiAiClient] Forwarding generateQuestions to Python FastAPI for type={}", type);
        Map<String, Object> body = new LinkedHashMap<>();
        body.put("type", type);
        body.put("context", context);
        body.put("assignments", assignments != null ? assignments : List.of());
        body.put("config", config);

        return restClient.post()
                .uri("/api/ai/questions/generate")
                .body(body)
                .retrieve()
                .body(new ParameterizedTypeReference<List<QuestionDto>>() {});
    }

    @Override
    public QuestionDto regenerateSingleQuestion(
            String type,
            String difficulty,
            CandidateContextDto context,
            List<EvidenceItemPair> allEvidenceItems,
            List<QuestionDto> existingQuestions) {
        log.info("[FastApiAiClient] Forwarding regenerateSingleQuestion to Python FastAPI for type={}, difficulty={}", type, difficulty);
        Map<String, Object> body = new LinkedHashMap<>();
        body.put("type", type);
        body.put("difficulty", difficulty);
        body.put("context", context);
        body.put("allEvidenceItems", allEvidenceItems != null ? allEvidenceItems : List.of());
        body.put("existingQuestions", existingQuestions != null ? existingQuestions : List.of());

        return restClient.post()
                .uri("/api/ai/questions/regenerate-single")
                .body(body)
                .retrieve()
                .body(QuestionDto.class);
    }

    private Optional<AssessmentResponse> checkOrClearCache(String sessionId, boolean forceRefresh) {
        if (!forceRefresh) {
            Optional<ResumeAssessment> existing = resumeAssessmentRepository.findBySessionId(sessionId);
            if (existing.isPresent()) {
                log.info("[FastApiAiClient] Returning cached assessment from DB for sessionId={}", sessionId);
                ResumeAssessment entity = existing.get();
                AssessmentResponse resp = AssessmentMapper.toResponse(entity, true);
                resp.setScoreBreakdown(extractScoreBreakdown(entity));
                return Optional.of(resp);
            }
        } else if (resumeAssessmentRepository.existsBySessionId(sessionId)) {
            log.info("[FastApiAiClient] Force refresh requested; clearing cached assessment for sessionId={}", sessionId);
            resumeAssessmentRepository.deleteBySessionId(sessionId);
            resumeAssessmentRepository.flush();
        }
        return Optional.empty();
    }

    private Map<String, Object> buildCvJdPayload(Session session, String sessionId, boolean forceRefresh, String fromSessionId) {
        String cvText = extractDocumentText(
                session.getResume() != null ? session.getResume().getParsedContent() : null,
                session.getResume() != null ? session.getResume().getRawText() : null,
                sessionId,
                "cv"
        );
        String jdText = extractDocumentText(
                session.getJobDescription() != null ? session.getJobDescription().getParsedContent() : null,
                session.getJobDescription() != null ? session.getJobDescription().getRawText() : null,
                sessionId,
                "jd"
        );

        Map<String, Object> payload = new LinkedHashMap<>();
        payload.put("sessionId", sessionId);
        payload.put("forceRefresh", forceRefresh);
        payload.put("fromSessionId", fromSessionId != null ? fromSessionId : "");
        payload.put("cvText", cvText);
        payload.put("jdText", jdText);
        payload.put("roleTitle", session.getRoleTitle() != null ? session.getRoleTitle() : "");
        payload.put("jobCategory", session.getJobDescription() != null && session.getJobDescription().getJobCategory() != null
                ? session.getJobDescription().getJobCategory() : "BACKEND");
        payload.put("seniorityLevel", session.getResume() != null && session.getResume().getSeniorityLevel() != null
                ? session.getResume().getSeniorityLevel() : "MID");
        return payload;
    }

    private String extractDocumentText(String parsedContent, String rawText, String sessionId, String docType) {
        if (parsedContent != null && !parsedContent.isBlank()) {
            return parsedContent;
        }
        if (rawText != null && !rawText.isBlank()) {
            return rawText;
        }
        var chunks = documentChunkRepository.findBySessionIdAndDocType(sessionId, docType);
        if (chunks != null && !chunks.isEmpty()) {
            return chunks.stream().map(c -> c.getContent()).collect(Collectors.joining("\n"));
        }
        return "";
    }

    private ResumeAssessment persistExternalAssessment(String sessionId, AssessmentResponse response) {
        ResumeAssessment entity = ResumeAssessment.builder()
                .sessionId(sessionId)
                .jobCategory(response.getJobCategory() != null ? response.getJobCategory() : JobCategory.BACKEND)
                .seniorityLevel(response.getSeniorityLevel() != null ? response.getSeniorityLevel() : SeniorityLevel.MID)
                .overallMatchScore(response.getOverallMatchScore() != null ? response.getOverallMatchScore() : 0)
                .eligibility(response.getEligibility() != null ? response.getEligibility() : EligibilityStatus.ELIGIBILITY)
                .build();

        entity.setEvidenceItems(buildEvidenceEntities(entity, response));
        entity.setScoreBreakdowns(buildScoreBreakdownEntities(entity, response));
        entity.setImprovements(buildImprovementEntities(entity, response));

        return resumeAssessmentRepository.save(entity);
    }

    private List<EvidenceItem> buildEvidenceEntities(ResumeAssessment entity, AssessmentResponse response) {
        List<EvidenceItem> list = new ArrayList<>();
        if (response.getMustHaveEvidenceItems() != null) {
            for (AssessmentResponseDto.EvidenceItem item : response.getMustHaveEvidenceItems()) {
                list.add(toEvidenceEntity(entity, item.criteriaId(), item.criteriaName(),
                        item.importance() != null ? item.importance() : IMPORTANCE_REQUIRED,
                        item.jdRequirement(), item.cvEvidence(), item.status(), item.reasoning()));
            }
        }
        if (response.getPreferToHaveEvidenceItems() != null) {
            for (AssessmentResponseDto.AdHocEvidenceItem item : response.getPreferToHaveEvidenceItems()) {
                list.add(toEvidenceEntity(entity, item.criteriaId(), item.criteriaName(),
                        IMPORTANCE_PREFERRED, item.jdRequirement(), item.cvEvidence(), item.status(), item.reasoning()));
            }
        }
        if (response.getGateEvidenceItems() != null) {
            for (AssessmentResponseDto.EvidenceItem item : response.getGateEvidenceItems()) {
                list.add(toEvidenceEntity(entity, item.criteriaId(), item.criteriaName(),
                        IMPORTANCE_GATE, item.jdRequirement(), item.cvEvidence(), item.status(), item.reasoning()));
            }
        }
        return list;
    }

    private EvidenceItem toEvidenceEntity(
            ResumeAssessment entity,
            Long criteriaId,
            String criteriaName,
            String importance,
            String jdRequirement,
            String cvEvidence,
            String status,
            String reasoning) {
        return EvidenceItem.builder()
                .assessment(entity)
                .criteriaId(criteriaId != null ? criteriaId.intValue() : null)
                .criteriaName(criteriaName)
                .importance(importance)
                .jdRequirement(jdRequirement)
                .cvEvidence(cvEvidence)
                .status(status != null ? status : "matched")
                .reasoning(reasoning)
                .build();
    }

    private List<ScoreBreakdown> buildScoreBreakdownEntities(ResumeAssessment entity, AssessmentResponse response) {
        int overall = response.getOverallMatchScore() != null ? response.getOverallMatchScore() : 0;
        AssessmentResponse.ScoreBreakdown sb = response.getScoreBreakdown();
        int mustScore = sb != null ? sb.rawMustHaveScore() : overall;
        double mustRatio = sb != null ? sb.mustHaveWeightRatio() : 0.8;
        int preferScore = sb != null ? sb.rawPreferToHaveScore() : overall;
        double preferRatio = sb != null ? sb.preferToHaveWeightRatio() : 0.2;
        int finalScore = sb != null ? sb.finalScore() : overall;

        return List.of(
                ScoreBreakdown.builder().assessment(entity).category("Must-Have").score(mustScore).maxScore(100).feedback("Weight: " + mustRatio).build(),
                ScoreBreakdown.builder().assessment(entity).category("Prefer-To-Have").score(preferScore).maxScore(100).feedback("Weight: " + preferRatio).build(),
                ScoreBreakdown.builder().assessment(entity).category("Overall").score(finalScore).maxScore(100).feedback("Final Score").build()
        );
    }

    private List<Improvement> buildImprovementEntities(ResumeAssessment entity, AssessmentResponse response) {
        List<Improvement> list = new ArrayList<>();
        int rank = 1;
        if (response.getQuickWins() != null) {
            for (ImprovementResponseDto.ImprovementItem item : response.getQuickWins()) {
                list.add(Improvement.builder()
                        .assessment(entity)
                        .priorityRank(rank++)
                        .topic(PREFIX_QUICK_WIN + item.criteriaName())
                        .suggestionDetails(item.actionableAdvice())
                        .build());
            }
        }
        if (response.getSkillGaps() != null) {
            for (ImprovementResponseDto.ImprovementItem item : response.getSkillGaps()) {
                list.add(Improvement.builder()
                        .assessment(entity)
                        .priorityRank(rank++)
                        .topic(PREFIX_SKILL_GAP + item.criteriaName())
                        .suggestionDetails(item.actionableAdvice())
                        .build());
            }
        }
        return list;
    }

    private AssessmentResponse.ScoreBreakdown extractScoreBreakdown(ResumeAssessment entity) {
        int overall = entity.getOverallMatchScore() != null ? entity.getOverallMatchScore() : 0;
        if (entity.getScoreBreakdowns() == null || entity.getScoreBreakdowns().isEmpty()) {
            return new AssessmentResponse.ScoreBreakdown(overall, 0.8, overall, 0.2, overall);
        }
        int must = overall;
        int prefer = overall;
        for (ScoreBreakdown b : entity.getScoreBreakdowns()) {
            if ("Must-Have".equalsIgnoreCase(b.getCategory()) && b.getScore() != null) {
                must = b.getScore();
            } else if ("Prefer-To-Have".equalsIgnoreCase(b.getCategory()) && b.getScore() != null) {
                prefer = b.getScore();
            }
        }
        return new AssessmentResponse.ScoreBreakdown(must, 0.8, prefer, 0.2, overall);
    }
}
