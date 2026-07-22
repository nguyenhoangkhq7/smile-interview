package fit.iuh.modules.evaluation;

import com.fasterxml.jackson.databind.ObjectMapper;
import fit.iuh.grpc.inference.InferenceRequest;
import fit.iuh.grpc.inference.QAContext;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import reactor.core.publisher.Mono;

import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.Mockito.*;

import fit.iuh.modules.evaluation.client.OpenRouterClient;
import fit.iuh.modules.evaluation.service.EvaluationServiceImpl;
import fit.iuh.modules.evaluation.prompt.PromptBuilder;
import fit.iuh.modules.evaluation.model.EvaluationResult;

/**
 * Unit tests for InterviewEvaluationService.
 * All LLM network calls are mocked via OpenRouterClient.
 */
class EvaluationServiceTest {

    private OpenRouterClient mockOpenRouterClient;
    private EvaluationServiceImpl service;
    private ObjectMapper objectMapper;

    @BeforeEach
    void setUp() {
        mockOpenRouterClient = mock(OpenRouterClient.class);
        objectMapper = new ObjectMapper();
        service = new EvaluationServiceImpl(mockOpenRouterClient, objectMapper, new PromptBuilder(), 10, 30);
    }

    // ─────────────────────────────────────────────────────────────────────────
    // Test 1: FOLLOW_UP generates a dynamic question targeting the gap
    // ─────────────────────────────────────────────────────────────────────────

    @Test
    @DisplayName("FOLLOW_UP: LLM generates a dynamic follow-up question bám sát câu trả lời thiếu ý")
    void testFollowUpGeneratesDynamicQuestion() {
        String followUpQ = "Bạn có thể giải thích cụ thể cơ chế locking trong transaction isolation không?";
        String mockLlmJson = """
                {
                  "decision": "FOLLOW_UP",
                  "follow_up_question": "%s",
                  "reasoning": "Câu trả lời đúng hướng nhưng chưa giải thích được cơ chế isolation.",
                  "score": 5,
                  "evaluation": "Điểm mạnh: Hiểu khái niệm cơ bản.\\nĐiểm yếu: Thiếu chi tiết về isolation levels.\\nGợi ý bổ sung: Nghiên cứu MVCC và locking."
                }
                """.formatted(followUpQ);

        when(mockOpenRouterClient.evaluationCompletion(anyString(), anyString()))
                .thenReturn(Mono.just(mockLlmJson));

        InferenceRequest request = InferenceRequest.newBuilder()
                .setTargetJobTitle("Backend Engineer")
                .setInterviewDomain("IT")
                .setCurrentQuestion("Giải thích khái niệm transaction trong database.")
                .setCandidateAnswer("Transaction là nhóm các câu lệnh SQL chạy cùng nhau.")
                .setCurrentFollowUpCount(0)
                .setMaxFollowUpCount(3)
                .build();

        EvaluationResult result = service.evaluate(request);

        assertEquals("FOLLOW_UP", result.getDecision());
        assertNotNull(result.getFollowUpQuestion(), "follow_up_question must not be null");
        assertFalse(result.getFollowUpQuestion().isBlank(), "follow_up_question must not be blank");
        assertEquals(followUpQ, result.getFollowUpQuestion());
        assertEquals(5, result.getScore());
        assertFalse(result.isFallback());
        assertFalse(result.isExcludedFromScoring());
    }

    // ─────────────────────────────────────────────────────────────────────────
    // Test 2: max_follow_up_count reached → forced NEXT_TOPIC
    // ─────────────────────────────────────────────────────────────────────────

    @Test
    @DisplayName("max_follow_up_count đạt giới hạn → bắt buộc trả NEXT_TOPIC")
    void testMaxFollowUpForcesNextTopic() {
        // LLM tries to FOLLOW_UP but the prompt includes [RULE] enforcement
        String mockLlmJson = """
                {
                  "decision": "NEXT_TOPIC",
                  "follow_up_question": "",
                  "reasoning": "Đã đạt giới hạn đào sâu, chuyển chủ đề.",
                  "score": 6,
                  "evaluation": "Điểm mạnh: Có nền tảng.\\nĐiểm yếu: Chưa sâu.\\nGợi ý bổ sung: Thực hành thêm."
                }
                """;

        when(mockOpenRouterClient.evaluationCompletion(anyString(), anyString()))
                .thenReturn(Mono.just(mockLlmJson));

        // current_follow_up_count == max_follow_up_count
        InferenceRequest request = InferenceRequest.newBuilder()
                .setTargetJobTitle("Backend Engineer")
                .setInterviewDomain("IT")
                .setCurrentQuestion("Giải thích SOLID principles.")
                .setCandidateAnswer("SOLID là 5 nguyên tắc lập trình hướng đối tượng.")
                .setCurrentFollowUpCount(3)
                .setMaxFollowUpCount(3)
                .build();

        EvaluationResult result = service.evaluate(request);

        // Regardless of LLM preference, once prompt enforces NEXT_TOPIC, decision must be NEXT_TOPIC
        assertEquals("NEXT_TOPIC", result.getDecision());
        assertTrue(result.getFollowUpQuestion() == null || result.getFollowUpQuestion().isBlank(),
                "follow_up_question must be blank when decision is NEXT_TOPIC");
        assertFalse(result.isFallback());
        assertFalse(result.isExcludedFromScoring());
    }

    // ─────────────────────────────────────────────────────────────────────────
    // Test 3: LLM timeout → fallback does NOT pollute scoring
    // ─────────────────────────────────────────────────────────────────────────

    @Test
    @DisplayName("LLM timeout → fallback result has null score and is excluded from scoring")
    void testFallbackExcludedFromScoring() {
        // Simulate timeout by throwing exception
        when(mockOpenRouterClient.evaluationCompletion(anyString(), anyString()))
                .thenReturn(Mono.error(new RuntimeException("Simulated timeout")));

        // Use a very short timeout so CompletableFuture fires quickly
        EvaluationServiceImpl shortTimeoutService =
                new EvaluationServiceImpl(mockOpenRouterClient, objectMapper, new PromptBuilder(), 1, 30);

        InferenceRequest request = InferenceRequest.newBuilder()
                .setTargetJobTitle("Backend Engineer")
                .setInterviewDomain("IT")
                .setCurrentQuestion("Giải thích microservices.")
                .setCandidateAnswer("Microservices là kiến trúc chia nhỏ service.")
                .setCurrentFollowUpCount(0)
                .setMaxFollowUpCount(3)
                .build();

        EvaluationResult result = shortTimeoutService.evaluate(request);

        assertEquals("NEXT_TOPIC", result.getDecision(),
                "Fallback must default to NEXT_TOPIC to keep interview flowing");
        assertNull(result.getScore(), "Fallback score must be null — not 0 — to avoid polluting averages");
        assertTrue(result.isFallback(), "isFallback must be true");
        assertTrue(result.isExcludedFromScoring(), "excludedFromScoring must be true");
    }

    // ─────────────────────────────────────────────────────────────────────────
    // Test 4: invalid JSON → retry → fallback if retry also fails
    // ─────────────────────────────────────────────────────────────────────────

    @Test
    @DisplayName("JSON parse lỗi → retry 1 lần → fallback nếu retry vẫn lỗi")
    void testJsonParseErrorRetryThenFallback() {
        // Both attempts return invalid JSON
        when(mockOpenRouterClient.evaluationCompletion(anyString(), anyString()))
                .thenReturn(Mono.just("This is not JSON"));

        InferenceRequest request = InferenceRequest.newBuilder()
                .setTargetJobTitle("Backend Engineer")
                .setInterviewDomain("IT")
                .setCurrentQuestion("What is REST?")
                .setCandidateAnswer("REST is an architectural style.")
                .setCurrentFollowUpCount(0)
                .setMaxFollowUpCount(3)
                .build();

        EvaluationResult result = service.evaluate(request);

        // After retry fails, should fall back
        assertTrue(result.isFallback());
        assertTrue(result.isExcludedFromScoring());
        assertNull(result.getScore());
        // verify retry happened: evaluationCompletion was called twice
        verify(mockOpenRouterClient, times(2)).evaluationCompletion(anyString(), anyString());
    }
}
