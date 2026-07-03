package fit.iuh.modules.evaluation;

import fit.iuh.grpc.inference.InferenceRequest;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.ai.chat.client.ChatClient;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;

import java.util.List;
import java.util.concurrent.CompletableFuture;
import java.util.concurrent.TimeUnit;

@Service
public class InterviewEvaluationService {
    
    private static final Logger log = LoggerFactory.getLogger(InterviewEvaluationService.class);
    
    private final ChatClient chatClient;
    private final int timeoutSeconds;

    public InterviewEvaluationService(ChatClient.Builder chatClientBuilder,
                                      @Value("${LLM_TIMEOUT_SECONDS:20}") int timeoutSeconds) {
        this.chatClient = chatClientBuilder.build();
        this.timeoutSeconds = timeoutSeconds;
    }

    private static final String SYSTEM_PROMPT = """
        You are an expert IT Interviewer (LLM-as-a-judge). Your role is to perform a deep, rigorous, and detailed technical evaluation of the candidate's answer.
        
        Evaluate the candidate's answer based on:
        1. Technical Accuracy & Depth: Does the candidate explain concepts correctly? Do they demonstrate deep engineering knowledge or just surface-level definitions?
        2. Relevance & Coverage: How completely does the answer address the question? Are key tech stack keywords covered?
        3. Practical Application: Does the candidate mention real-world scenarios, challenges, best practices, or STAR methodology examples?
        
        OUTPUT FORMAT REQUIREMENTS:
        Your response must be a valid JSON object mapping to these fields:
        - decision: Decide dynamically based on these rules:
          * Output "FOLLOW_UP" if the candidate's answer is partially correct, incomplete, lacking depth, or requires clarification.
          * Output "NEXT_TOPIC" if the candidate's answer is completely correct, sufficient, or if the candidate explicitly states they do not know the answer (e.g. "I don't know", "Tôi không biết", "không biết" - as there is no point in probing further).
        - reasoning: A very concise, 1-sentence technical reason for your decision.
        - followUpQuestion: Always output an empty string "". Do NOT generate any follow-up question text here (the platform will pull from pre-generated follow-up questions).
        - score: An integer score from 1 to 10 based on the quality of their answer.
        - evaluation: A detailed, professional, and thorough analysis of their answer in Vietnamese. 
                      Break it down clearly into:
                      - Điểm mạnh (Strengths: what they got right, key technologies correctly explained).
                      - Điểm yếu/Hạn chế (Weaknesses/Gaps: what they missed, incorrect assumptions, or lack of depth).
                      - Gợi ý bổ sung (Suggestions: how they could improve their answer).
        """;

    public EvaluationResult evaluate(InferenceRequest request) {
        String userPrompt = buildUserPrompt(request);

        try {
            // Apply strict timeout using CompletableFuture
            return CompletableFuture.supplyAsync(() -> 
                chatClient.prompt()
                    .system(SYSTEM_PROMPT)
                    .user(userPrompt)
                    .call()
                    .entity(EvaluationResult.class)
            ).get(timeoutSeconds, TimeUnit.SECONDS);

        } catch (Exception e) {
            log.error("Inference failed or timed out. Falling back to NEXT_TOPIC.", e);
            return new EvaluationResult("NEXT_TOPIC", "Fallback due to inference error or timeout.", "", 0, "Không thể đánh giá câu trả lời do lỗi hệ thống hoặc quá thời gian phản hồi.");
        }
    }

    private String buildUserPrompt(InferenceRequest request) {
        StringBuilder sb = new StringBuilder();
        sb.append("Target Job Title: ").append(request.getTargetJobTitle()).append("\n");
        sb.append("Current Question: ").append(request.getCurrentQuestion()).append("\n");
        sb.append("Candidate Answer: ").append(request.getCandidateAnswer()).append("\n");
        
        List<String> history = request.getPreviousQaContextList();
        if (history != null && !history.isEmpty()) {
            sb.append("Previous QA Context:\n");
            for (int i = 0; i < history.size(); i++) {
                sb.append(i + 1).append(". ").append(history.get(i)).append("\n");
            }
        }
        
        return sb.toString();
    }
}
