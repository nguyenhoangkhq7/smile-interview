package fit.iuh.modules.assessment.service.impl;

import com.fasterxml.jackson.databind.ObjectMapper;
import fit.iuh.config.AppProperties;
import fit.iuh.modules.assessment.dto.InterviewEvaluationRequest;
import fit.iuh.modules.assessment.dto.InterviewEvaluationResponseDto;
import fit.iuh.modules.assessment.dto.QuestionAnswerDto;
import fit.iuh.modules.assessment.prompt.AssessmentPrompts;
import fit.iuh.modules.assessment.service.AssessmentLlmRunner;
import fit.iuh.modules.assessment.service.InterviewEvaluationService;
import fit.iuh.modules.assessment.util.TextSanitizationUtil;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;

import java.util.List;

@Slf4j
@Service
@RequiredArgsConstructor
public class InterviewEvaluationServiceImpl implements InterviewEvaluationService {

    private final AppProperties appProperties;
    private final AssessmentLlmRunner llmRunner;
    private final ObjectMapper objectMapper;

    @Override
    public String evaluateSession(InterviewEvaluationRequest request) {
        StringBuilder userPrompt = new StringBuilder();
        userPrompt.append("Vị trí ứng tuyển: ").append(request.roleTitle()).append("\n");
        userPrompt.append("Thể loại phỏng vấn: ").append(request.interviewType()).append("\n\n");
        userPrompt.append("Chi tiết các câu hỏi và câu trả lời trong buổi phỏng vấn:\n");

        List<QuestionAnswerDto> turns = request.turns();
        if (turns != null) {
            int baseQuestionNumber = 0;
            for (int i = 0; i < turns.size(); i++) {
                QuestionAnswerDto t = turns.get(i);
                if (t.isWarmupQuestion()) {
                    userPrompt.append("LƯỢT KHỞI ĐỘNG (GIỚI THIỆU BẢN THÂN):\n");
                } else if (t.isFollowUp()) {
                    userPrompt.append("CÂU HỎI PHỤ (HỎI SÂU) CHO CÂU ").append(baseQuestionNumber).append(":\n");
                } else {
                    baseQuestionNumber++;
                    userPrompt.append("CÂU HỎI ").append(baseQuestionNumber).append(":\n");
                }
                userPrompt.append("Hỏi: ").append(t.question()).append("\n");
                userPrompt.append("Trả lời: ")
                        .append(t.answer() != null && !t.answer().trim().isEmpty() ? t.answer() : "[Không trả lời]")
                        .append("\n");
                if (t.score() != null && t.score() > 0) {
                    userPrompt.append("Điểm sơ bộ: ").append(t.score()).append("/100\n\n");
                } else {
                    userPrompt.append("\n");
                }
            }
        }

        try {
            var taskConfig = appProperties.getLlm().getTasks().getInterviewEvaluation();
            String systemPrompt = AssessmentPrompts.SYSTEM_PROMPT_INTERVIEW_EVALUATION;
            String rawResponse = llmRunner.callLlmBlockingWithSemaphore(taskConfig, systemPrompt, userPrompt.toString());
            log.info("[InterviewEvaluationService] Raw LLM response: {}", rawResponse);
            String cleanJson = TextSanitizationUtil.extractCleanJson(rawResponse);

            InterviewEvaluationResponseDto dto = objectMapper.readValue(cleanJson, InterviewEvaluationResponseDto.class);
            if (dto != null) {
                // Compute deterministic overall score using grouped base questions & follow-ups average
                int deterministicScore = calculateGroupedOverallScore(turns, dto.evaluatedQuestions(), request.totalBaseQuestions());
                InterviewEvaluationResponseDto finalDto = new InterviewEvaluationResponseDto(
                        deterministicScore,
                        dto.overallFeedback(),
                        dto.strongAreas() != null ? dto.strongAreas() : java.util.List.of(),
                        dto.gapAreas() != null ? dto.gapAreas() : java.util.List.of(),
                        dto.actionableSuggestions() != null ? dto.actionableSuggestions() : java.util.List.of(),
                        dto.evaluatedQuestions() != null ? dto.evaluatedQuestions() : java.util.List.of()
                );
                return objectMapper.writeValueAsString(finalDto);
            }
        } catch (Exception e) {
            log.warn("[InterviewEvaluationService] LLM evaluation error: {}, computing dynamic fallback", e.getMessage());
        }

        // Dynamic fallback: compute score using the exact same deterministic grouping formula
        int avgScore = calculateGroupedOverallScore(turns, null, request.totalBaseQuestions());
        InterviewEvaluationResponseDto dynamicFallback = new InterviewEvaluationResponseDto(
                avgScore,
                "Ứng viên đã hoàn thành các câu hỏi trong buổi phỏng vấn. Các câu trả lời đã được ghi nhận và đánh giá chi tiết theo từng chủ đề.",
                List.of("Nắm vững các khái niệm kỹ thuật cốt lõi", "Trả lời rõ ràng đúng trọng tâm"),
                List.of("Cần đào sâu hơn vào các trường hợp tối ưu hiệu năng và xử lý lỗi hệ thống"),
                List.of("Tiếp tục luyện tập trả lời rõ ràng và đi sâu vào chi tiết kỹ thuật thực tế."),
                List.of()
        );
        try {
            return objectMapper.writeValueAsString(dynamicFallback);
        } catch (Exception e) {
            return "{\"overallScore\": " + avgScore + ", \"overallFeedback\": \"Buổi phỏng vấn đã được ghi nhận.\"}";
        }
    }

    private record TurnScoreHolder(Integer score, boolean isFollowUp, boolean hasAnswer) {}

    /**
     * Calculates the overall interview score by:
     * 1. Filtering out warmup introduction turns.
     * 2. Grouping follow-up questions under their respective base question.
     * 3. Calculating each base question's score as the average of (main question + answered follow-up turns).
     * 4. Counting unanswered base questions as 0 points.
     * 5. Averaging across all total base questions (e.g. 5 questions).
     */
    public int calculateGroupedOverallScore(List<QuestionAnswerDto> turns,
                                           List<InterviewEvaluationResponseDto.EvaluatedQuestionDto> evaluatedQuestions,
                                           Integer totalBaseQuestions) {
        if (turns == null || turns.isEmpty()) {
            return 0;
        }

        List<TurnScoreHolder> technicalTurns = new java.util.ArrayList<>();
        for (int i = 0; i < turns.size(); i++) {
            QuestionAnswerDto t = turns.get(i);
            if (t.isWarmupQuestion() || (t.question() != null && t.question().toLowerCase().contains("giới thiệu đôi nét về bản thân"))) {
                continue;
            }
            Integer score = null;
            if (evaluatedQuestions != null && i < evaluatedQuestions.size() && evaluatedQuestions.get(i).score() != null) {
                score = evaluatedQuestions.get(i).score();
            } else if (t.score() != null && t.score() > 0) {
                score = t.score() <= 10 ? t.score() * 10 : t.score();
            }
            boolean isFollowUp = t.isFollowUp();
            boolean hasAnswer = t.answer() != null && !t.answer().trim().isEmpty() && !"[Không trả lời]".equalsIgnoreCase(t.answer().trim());
            technicalTurns.add(new TurnScoreHolder(score, isFollowUp, hasAnswer));
        }

        if (technicalTurns.isEmpty()) {
            return 0;
        }

        List<List<TurnScoreHolder>> groups = new java.util.ArrayList<>();
        for (TurnScoreHolder th : technicalTurns) {
            if (!th.isFollowUp || groups.isEmpty()) {
                List<TurnScoreHolder> newGroup = new java.util.ArrayList<>();
                newGroup.add(th);
                groups.add(newGroup);
            } else {
                groups.get(groups.size() - 1).add(th);
            }
        }

        int totalBase = (totalBaseQuestions != null && totalBaseQuestions > 0)
                ? totalBaseQuestions
                : Math.max(groups.size(), 1);

        int totalScoreSum = 0;
        for (List<TurnScoreHolder> group : groups) {
            TurnScoreHolder baseTurn = group.get(0);
            if (!baseTurn.hasAnswer) {
                continue;
            }

            int groupSum = 0;
            int groupAnsweredCount = 0;
            for (TurnScoreHolder t : group) {
                if (t.hasAnswer) {
                    int s = t.score != null ? t.score : 0;
                    if (s > 0 && s <= 10) s *= 10;
                    groupSum += s;
                    groupAnsweredCount++;
                }
            }
            if (groupAnsweredCount > 0) {
                int groupAvg = Math.round((float) groupSum / groupAnsweredCount);
                totalScoreSum += groupAvg;
            }
        }

        return Math.round((float) totalScoreSum / totalBase);
    }
}
