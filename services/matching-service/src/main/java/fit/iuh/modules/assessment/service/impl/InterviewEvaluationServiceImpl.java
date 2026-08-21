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
        userPrompt.append("Chi tiết các câu hỏi và câu trả lời:\n");

        List<QuestionAnswerDto> turns = request.turns();
        if (turns != null) {
            for (int i = 0; i < turns.size(); i++) {
                QuestionAnswerDto t = turns.get(i);
                userPrompt.append("CÂU HỎI ").append(i + 1).append(":\n");
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
            String cleanJson = TextSanitizationUtil.extractCleanJson(rawResponse);

            InterviewEvaluationResponseDto dto = objectMapper.readValue(cleanJson, InterviewEvaluationResponseDto.class);
            if (dto != null && dto.overallScore() != null) {
                return objectMapper.writeValueAsString(dto);
            }
        } catch (Exception e) {
            log.warn("[InterviewEvaluationService] LLM evaluation error: {}, returning structured fallback", e.getMessage());
        }

        try {
            return objectMapper.writeValueAsString(InterviewEvaluationResponseDto.fallback());
        } catch (Exception e) {
            return "{\"overallScore\": 50, \"overallFeedback\": \"Buổi phỏng vấn đã được ghi nhận.\"}";
        }
    }
}
