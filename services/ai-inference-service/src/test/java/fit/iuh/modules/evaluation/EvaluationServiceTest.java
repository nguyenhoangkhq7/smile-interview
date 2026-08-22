package fit.iuh.modules.evaluation;

import com.fasterxml.jackson.databind.ObjectMapper;
import fit.iuh.common.exception.LlmInferenceException;
import fit.iuh.grpc.inference.FinalReportRequest;
import fit.iuh.grpc.inference.InferenceRequest;
import fit.iuh.grpc.inference.TurnRecord;
import fit.iuh.modules.evaluation.client.OpenRouterClient;
import fit.iuh.modules.evaluation.model.EvaluationResult;
import fit.iuh.modules.evaluation.model.FinalReportResult;
import fit.iuh.modules.evaluation.prompt.PromptBuilder;
import fit.iuh.modules.evaluation.service.EvaluationServiceImpl;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;

import java.util.List;

import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.Mockito.*;

/**
 * Comprehensive Unit tests for EvaluationServiceImpl.
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
        service = new EvaluationServiceImpl(mockOpenRouterClient, objectMapper, new PromptBuilder());
    }

    // ─────────────────────────────────────────────────────────────────────────
    // Test 1: FOLLOW_UP generates dynamic question
    // ─────────────────────────────────────────────────────────────────────────

    @Test
    @DisplayName("FOLLOW_UP: LLM generates a dynamic follow-up question")
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
                .thenReturn(mockLlmJson);

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
    // Test 2: Programmatic Enforcement overrides LLM when limit reached
    // ─────────────────────────────────────────────────────────────────────────

    @Test
    @DisplayName("Programmatic Rule Enforcement: Ép NEXT_TOPIC khi đạt max follow-up ngay cả khi LLM trả FOLLOW_UP")
    void testMaxFollowUpEnforcedProgrammatically() {
        // LLM mistakenly returned FOLLOW_UP even though limit is reached
        String mockLlmJson = """
                {
                  "decision": "FOLLOW_UP",
                  "follow_up_question": "Can you elaborate more?",
                  "reasoning": "Needs more detail.",
                  "score": 6,
                  "evaluation": "Good understanding."
                }
                """;

        when(mockOpenRouterClient.evaluationCompletion(anyString(), anyString()))
                .thenReturn(mockLlmJson);

        // current_follow_up_count (3) == max_follow_up_count (3)
        InferenceRequest request = InferenceRequest.newBuilder()
                .setTargetJobTitle("Backend Engineer")
                .setInterviewDomain("IT")
                .setCurrentQuestion("Giải thích SOLID principles.")
                .setCandidateAnswer("SOLID là 5 nguyên tắc lập trình hướng đối tượng.")
                .setCurrentFollowUpCount(3)
                .setMaxFollowUpCount(3)
                .build();

        EvaluationResult result = service.evaluate(request);

        // Must be overridden to NEXT_TOPIC with empty follow-up question
        assertEquals("NEXT_TOPIC", result.getDecision());
        assertEquals("", result.getFollowUpQuestion());
        assertEquals(6, result.getScore());
        assertFalse(result.isFallback());
    }

    @Test
    @DisplayName("Programmatic Rule Enforcement: Ép NEXT_TOPIC khi điểm cao (>= 8) ngay cả khi LLM trả FOLLOW_UP")
    void testHighScoreEnforcesNextTopicProgrammatically() {
        // LLM returned high score (8) but mistakenly returned FOLLOW_UP
        String mockLlmJson = """
                {
                  "decision": "FOLLOW_UP",
                  "follow_up_question": "Bạn có thể nói thêm về trade-off không?",
                  "reasoning": "Câu trả lời rất tốt nhưng muốn hỏi thêm trade-off.",
                  "score": 8,
                  "evaluation": "Điểm mạnh: Hiểu sâu kiến thức."
                }
                """;

        when(mockOpenRouterClient.evaluationCompletion(anyString(), anyString()))
                .thenReturn(mockLlmJson);

        InferenceRequest request = InferenceRequest.newBuilder()
                .setTargetJobTitle("Backend Engineer")
                .setInterviewDomain("IT")
                .setCurrentQuestion("Giải thích cơ chế Index trong PostgreSQL.")
                .setCandidateAnswer("PostgreSQL sử dụng B-tree index cho các phép so sánh =, <, >...")
                .setCurrentFollowUpCount(0)
                .setMaxFollowUpCount(3)
                .build();

        EvaluationResult result = service.evaluate(request);

        // Must be overridden to NEXT_TOPIC with empty follow-up question
        assertEquals("NEXT_TOPIC", result.getDecision());
        assertEquals("", result.getFollowUpQuestion());
        assertEquals(8, result.getScore());
        assertFalse(result.isFallback());
    }

    @Test
    @DisplayName("Programmatic Rule Enforcement: Ép NEXT_TOPIC khi điểm quá thấp (<= 2) ngay cả khi LLM trả FOLLOW_UP")
    void testLowScoreEnforcesNextTopicProgrammatically() {
        // LLM returned low score (1) but mistakenly returned FOLLOW_UP
        String mockLlmJson = """
                {
                  "decision": "FOLLOW_UP",
                  "follow_up_question": "Bạn có biết thêm gì không?",
                  "reasoning": "Câu trả lời sai hoàn toàn.",
                  "score": 1,
                  "evaluation": "Điểm yếu: Sai kiến thức căn bản."
                }
                """;

        when(mockOpenRouterClient.evaluationCompletion(anyString(), anyString()))
                .thenReturn(mockLlmJson);

        InferenceRequest request = InferenceRequest.newBuilder()
                .setTargetJobTitle("Backend Engineer")
                .setInterviewDomain("IT")
                .setCurrentQuestion("Giải thích cơ chế Index trong PostgreSQL.")
                .setCandidateAnswer("Index là để xóa dữ liệu nhanh hơn.")
                .setCurrentFollowUpCount(0)
                .setMaxFollowUpCount(3)
                .build();

        EvaluationResult result = service.evaluate(request);

        // Must be overridden to NEXT_TOPIC with empty follow-up question
        assertEquals("NEXT_TOPIC", result.getDecision());
        assertEquals("", result.getFollowUpQuestion());
        assertEquals(1, result.getScore());
        assertFalse(result.isFallback());
    }

    // ─────────────────────────────────────────────────────────────────────────
    // Test 3: Markdown-wrapped JSON response sanitized & parsed successfully
    // ─────────────────────────────────────────────────────────────────────────

    @Test
    @DisplayName("Markdown codeblock wrapped JSON is sanitized and parsed successfully")
    void testMarkdownWrappedJsonParsedSuccessfully() {
        String markdownLlmResponse = """
                ```json
                {
                  "decision": "NEXT_TOPIC",
                  "follow_up_question": "",
                  "reasoning": "Câu trả lời xuất sắc và toàn diện.",
                  "score": 10,
                  "evaluation": "Điểm mạnh: Nắm rất vững kiến thức.\\nĐiểm yếu: Không có.\\nGợi ý: Giữ vững phong độ."
                }
                ```
                """;

        when(mockOpenRouterClient.evaluationCompletion(anyString(), anyString()))
                .thenReturn(markdownLlmResponse);

        InferenceRequest request = InferenceRequest.newBuilder()
                .setTargetJobTitle("Backend Engineer")
                .setInterviewDomain("IT")
                .setCurrentQuestion("Explain indexing in SQL.")
                .setCandidateAnswer("B-Tree index allows O(log N) lookup time.")
                .setCurrentFollowUpCount(0)
                .setMaxFollowUpCount(3)
                .build();

        EvaluationResult result = service.evaluate(request);

        assertEquals("NEXT_TOPIC", result.getDecision());
        assertEquals(10, result.getScore());
        assertFalse(result.isFallback());
    }

    // ─────────────────────────────────────────────────────────────────────────
    // Test 4: LLM exception → fallback does NOT pollute scoring
    // ─────────────────────────────────────────────────────────────────────────

    @Test
    @DisplayName("LLM error → fallback result has null score and is excluded from scoring")
    void testFallbackExcludedFromScoring() {
        when(mockOpenRouterClient.evaluationCompletion(anyString(), anyString()))
                .thenThrow(new LlmInferenceException("Simulated API failure"));

        InferenceRequest request = InferenceRequest.newBuilder()
                .setTargetJobTitle("Backend Engineer")
                .setInterviewDomain("IT")
                .setCurrentQuestion("Giải thích microservices.")
                .setCandidateAnswer("Microservices là kiến trúc chia nhỏ service.")
                .setCurrentFollowUpCount(0)
                .setMaxFollowUpCount(3)
                .build();

        EvaluationResult result = service.evaluate(request);

        assertEquals("NEXT_TOPIC", result.getDecision());
        assertNull(result.getScore(), "Fallback score must be null — not 0 — to avoid polluting averages");
        assertTrue(result.isFallback(), "isFallback must be true");
        assertTrue(result.isExcludedFromScoring(), "excludedFromScoring must be true");
    }

    // ─────────────────────────────────────────────────────────────────────────
    // Test 5: invalid JSON → retry → fallback if retry also fails
    // ─────────────────────────────────────────────────────────────────────────

    @Test
    @DisplayName("JSON parse lỗi → retry 1 lần → fallback nếu retry vẫn lỗi")
    void testJsonParseErrorRetryThenFallback() {
        // Both attempts return invalid JSON
        when(mockOpenRouterClient.evaluationCompletion(anyString(), anyString()))
                .thenReturn("This is completely invalid non-JSON output");

        InferenceRequest request = InferenceRequest.newBuilder()
                .setTargetJobTitle("Backend Engineer")
                .setInterviewDomain("IT")
                .setCurrentQuestion("What is REST?")
                .setCandidateAnswer("REST is an architectural style.")
                .setCurrentFollowUpCount(0)
                .setMaxFollowUpCount(3)
                .build();

        EvaluationResult result = service.evaluate(request);

        assertTrue(result.isFallback());
        assertTrue(result.isExcludedFromScoring());
        assertNull(result.getScore());
        verify(mockOpenRouterClient, times(2)).evaluationCompletion(anyString(), anyString());
    }

    // ─────────────────────────────────────────────────────────────────────────
    // Test 6: Final report synthesis success
    // ─────────────────────────────────────────────────────────────────────────

    @Test
    @DisplayName("GenerateFinalReport parses holistic synthesis response correctly")
    void testFinalReportSuccess() {
        String mockFinalReportJson = """
                ```json
                {
                  "overall_score": 8,
                  "overall_summary": "Ứng viên có kiến thức vững chắc về backend và database.",
                  "strengths": ["Hiểu rõ transaction", "Kinh nghiệm thực tế tốt"],
                  "weaknesses": ["Chưa tối ưu distributed caching"],
                  "recommendations": ["Tìm hiểu thêm về Redis Cluster"],
                  "hiring_recommendation": "Hire"
                }
                ```
                """;

        when(mockOpenRouterClient.finalReportCompletion(anyString(), anyString()))
                .thenReturn(mockFinalReportJson);

        FinalReportRequest request = FinalReportRequest.newBuilder()
                .setSessionId("session-123")
                .setTargetJobTitle("Senior Backend Engineer")
                .addTurns(TurnRecord.newBuilder()
                        .setQuestion("Explain ACID")
                        .setAnswer("Atomicity, Consistency, Isolation, Durability")
                        .setScore(8)
                        .setEvaluation("Good")
                        .setWasFollowUp(false)
                        .build())
                .build();

        FinalReportResult result = service.generateFinalReport(request);

        assertNotNull(result);
        assertEquals(8, result.getOverallScore());
        assertEquals("Hire", result.getHiringRecommendation());
        assertEquals(2, result.getStrengths().size());
        assertEquals(1, result.getWeaknesses().size());
        assertEquals(1, result.getRecommendations().size());
    }

    // ─────────────────────────────────────────────────────────────────────────
    // Test 7: Final report failure throws LlmInferenceException (No fake No Hire)
    // ─────────────────────────────────────────────────────────────────────────

    @Test
    @DisplayName("GenerateFinalReport failure throws LlmInferenceException instead of fake No Hire")
    void testFinalReportFailureThrowsException() {
        when(mockOpenRouterClient.finalReportCompletion(anyString(), anyString()))
                .thenThrow(new LlmInferenceException("LLM service unavailable"));

        FinalReportRequest request = FinalReportRequest.newBuilder()
                .setSessionId("session-123")
                .setTargetJobTitle("Senior Backend Engineer")
                .build();

        assertThrows(LlmInferenceException.class, () -> service.generateFinalReport(request));
    }

    // ─────────────────────────────────────────────────────────────────────────
    // Test 8: Candidate profile (name, age, gender) included in evaluation prompt
    // ─────────────────────────────────────────────────────────────────────────

    @Test
    @DisplayName("Candidate profile (name, age, gender) is included in evaluation prompt")
    void testCandidateProfileIncludedInPrompt() {
        String mockLlmJson = """
                {
                  "decision": "FOLLOW_UP",
                  "follow_up_question": "Cảm ơn em An đã chia sẻ. Em có thể giải thích thêm về connection pool không?",
                  "reasoning": "Câu trả lời đúng hướng.",
                  "score": 6,
                  "evaluation": "Điểm mạnh: Nắm cơ bản."
                }
                """;

        when(mockOpenRouterClient.evaluationCompletion(anyString(), anyString()))
                .thenReturn(mockLlmJson);

        InferenceRequest request = InferenceRequest.newBuilder()
                .setTargetJobTitle("Backend Engineer")
                .setInterviewDomain("IT")
                .setCandidateName("Nguyễn Văn An")
                .setCandidateAge(23)
                .setCandidateGender("male")
                .setCurrentQuestion("Giải thích connection pooling.")
                .setCandidateAnswer("Connection pool duy trì các connection có sẵn để tái sử dụng.")
                .setCurrentFollowUpCount(0)
                .setMaxFollowUpCount(3)
                .build();

        EvaluationResult result = service.evaluate(request);

        assertNotNull(result);
        assertEquals("FOLLOW_UP", result.getDecision());
        assertTrue(result.getFollowUpQuestion().contains("em An") || result.getFollowUpQuestion().contains("em"));
        verify(mockOpenRouterClient).evaluationCompletion(anyString(), org.mockito.ArgumentMatchers.contains("name=\"Nguyễn Văn An\""));
    }

    // ─────────────────────────────────────────────────────────────────────────
    // Test 9: Repetitive question forces NEXT_TOPIC
    // ─────────────────────────────────────────────────────────────────────────

    @Test
    @DisplayName("Repetitive follow-up question forces NEXT_TOPIC")
    void testRepetitiveFollowUpQuestionForcesNextTopic() {
        String mockLlmJson = """
                {
                  "decision": "FOLLOW_UP",
                  "follow_up_question": "Em hãy giải thích lại về transaction isolation levels trong database cho anh nghe nhé.",
                  "reasoning": "Muốn hỏi lại.",
                  "score": 6,
                  "evaluation": "Điểm mạnh: Nắm cơ bản."
                }
                """;

        when(mockOpenRouterClient.evaluationCompletion(anyString(), anyString()))
                .thenReturn(mockLlmJson);

        InferenceRequest request = InferenceRequest.newBuilder()
                .setTargetJobTitle("Backend Engineer")
                .setInterviewDomain("IT")
                .setCurrentQuestion("Giải thích transaction isolation levels trong database.")
                .setCandidateAnswer("Transaction isolation có Read Uncommitted, Read Committed, Repeatable Read, Serializable.")
                .setCurrentFollowUpCount(0)
                .setMaxFollowUpCount(3)
                .build();

        EvaluationResult result = service.evaluate(request);

        assertNotNull(result);
        assertEquals("NEXT_TOPIC", result.getDecision());
        assertEquals("", result.getFollowUpQuestion());
    }
}
