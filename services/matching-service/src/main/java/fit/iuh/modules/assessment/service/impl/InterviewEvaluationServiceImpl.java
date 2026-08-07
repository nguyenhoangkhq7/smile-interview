package fit.iuh.modules.assessment.service.impl;

import fit.iuh.config.AppProperties;
import fit.iuh.dto.chat.LlmChatRequest;
import fit.iuh.dto.chat.LlmChatResponse;
import fit.iuh.exception.LlmApiException;
import fit.iuh.modules.assessment.dto.InterviewEvaluationRequest;
import fit.iuh.modules.assessment.dto.QuestionAnswerDto;
import fit.iuh.modules.assessment.prompt.AssessmentPrompts;
import fit.iuh.modules.assessment.service.InterviewEvaluationService;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Qualifier;
import org.springframework.stereotype.Service;
import org.springframework.web.reactive.function.client.WebClient;

import java.util.List;
import java.util.Map;

@Slf4j
@Service
public class InterviewEvaluationServiceImpl implements InterviewEvaluationService {

    private static final Map<String, String> JSON_RESPONSE_FORMAT = Map.of("type", "json_object");

    private final AppProperties appProperties;
    private final WebClient llmWebClient;

    public InterviewEvaluationServiceImpl(
            AppProperties appProperties,
            @Qualifier("llmWebClient") WebClient llmWebClient) {
        this.appProperties = appProperties;
        this.llmWebClient = llmWebClient;
    }

    @Override
    public String evaluateSession(InterviewEvaluationRequest request) {
        StringBuilder userPrompt = new StringBuilder();
        userPrompt.append("Vị trí ứng tuyển: ").append(request.roleTitle()).append("\n");
        userPrompt.append("Thể loại phỏng vấn: ").append(request.interviewType()).append("\n\n");
        userPrompt.append("Chi tiết các câu hỏi và câu trả lời:\n");

        List<QuestionAnswerDto> turns = request.turns();
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

        var taskConfig = appProperties.getLlm().getTasks().getInterviewEvaluation();
        List<String> models = appProperties.getLlm().resolveModels(taskConfig);
        String model = models.isEmpty() ? appProperties.getLlm().resolveModel(taskConfig) : models.get(0);
        int maxTokens = appProperties.getLlm().resolveMaxTokens(taskConfig);
        double temperature = appProperties.getLlm().resolveTemperature(taskConfig);

        LlmChatRequest llmRequest = LlmChatRequest.builder()
                .model(model)
                .models(models)
                .maxTokens(maxTokens)
                .temperature(temperature)
                .stream(false)
                .responseFormat(JSON_RESPONSE_FORMAT)
                .messages(List.of(
                        LlmChatRequest.Message.system(AssessmentPrompts.SYSTEM_PROMPT_INTERVIEW_EVALUATION),
                        LlmChatRequest.Message.user(userPrompt.toString())
                ))
                .build();

        LlmChatResponse response = llmWebClient.post()
                .uri(appProperties.getLlm().getChatPath())
                .bodyValue(llmRequest)
                .retrieve()
                .bodyToMono(LlmChatResponse.class)
                .block();

        if (response == null || response.getFirstChoiceContent() == null) {
            throw new LlmApiException("LLM returned empty evaluation response.");
        }
        return response.getFirstChoiceContent().strip();
    }
}
