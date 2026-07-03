package fit.iuh.modules.evaluation;

import fit.iuh.grpc.inference.InferenceRequest;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.ai.chat.client.ChatClient;
import org.springframework.stereotype.Service;

import java.util.List;
import java.util.concurrent.CompletableFuture;
import java.util.concurrent.TimeUnit;

@Service
public class InterviewEvaluationService {
    
    private static final Logger log = LoggerFactory.getLogger(InterviewEvaluationService.class);
    
    private final ChatClient chatClient;

    public InterviewEvaluationService(ChatClient.Builder chatClientBuilder) {
        this.chatClient = chatClientBuilder.build();
    }

    private static final String SYSTEM_PROMPT = """
        You are an expert IT Interviewer (LLM-as-a-judge). Evaluate the candidate's answer based on:
        1. response_length (conciseness)
        2. keyword_coverage (tech stack matching)
        3. demonstrated_competency (STAR examples)
        
        Provide a real-time SCORE from 1 to 10 for their answer based on the 3 criteria above.
        Provide a detailed EVALUATION explaining your score and pointing out strengths and weaknesses.
        
        DECISION RULES:
        - If the answer is lacking or needs clarification, return "FOLLOW_UP" and generate a follow-up question.
        - If the answer is sufficient or completely off-topic, return "NEXT_TOPIC".
        
        CONTEXT AWARENESS:
        You must look at the 'Previous QA Context' provided by the user. Do NOT ask a follow-up question that is identical or too similar to previously asked questions.
        
        Your output MUST be a JSON object mapping to the following fields: decision, reasoning, followUpQuestion, score, evaluation.
        CRITICAL: Keep your 'reasoning' extremely concise (max 1 sentence) to ensure low latency!
        """;

    public EvaluationResult evaluate(InferenceRequest request) {
        if (request.getCurrentFollowUpCount() >= 2) {
            log.info("Hard limit reached for follow-ups (count: {}). Routing to NEXT_TOPIC.", request.getCurrentFollowUpCount());
            return new EvaluationResult("NEXT_TOPIC", "Hard limit reached for follow-ups.", "", 0, "Candidate reached maximum follow-ups for this question.");
        }

        String userPrompt = buildUserPrompt(request);

        try {
            // Apply strict timeout using CompletableFuture
            return CompletableFuture.supplyAsync(() -> 
                chatClient.prompt()
                    .system(SYSTEM_PROMPT)
                    .user(userPrompt)
                    .call()
                    .entity(EvaluationResult.class)
            ).get(8, TimeUnit.SECONDS);

        } catch (Exception e) {
            log.error("Inference failed or timed out. Falling back to NEXT_TOPIC.", e);
            return new EvaluationResult("NEXT_TOPIC", "Fallback due to inference error or timeout.", "", 0, "Evaluation failed due to timeout.");
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
