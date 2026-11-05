package fit.iuh.modules.assessment;

import fit.iuh.modules.assessment.dto.InterviewEvaluationResponseDto;
import fit.iuh.modules.assessment.dto.QuestionAnswerDto;
import fit.iuh.modules.assessment.service.impl.InterviewEvaluationServiceImpl;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;

import java.util.List;

import static org.junit.jupiter.api.Assertions.assertEquals;

class InterviewEvaluationServiceTest {

    private InterviewEvaluationServiceImpl service;

    @BeforeEach
    void setUp() {
        service = new InterviewEvaluationServiceImpl(null, null, null);
    }

    @Test
    @DisplayName("Calculate score: 5 base questions, answered 2 (1 with followup), 3 unanswered")
    void testGroupedScoreWithFollowUpAndUnansweredQuestions() {
        // Question 1: main (80) + followup 1 (90) -> avg 85
        // Question 2: main (75) -> avg 75
        // Question 3, 4, 5: unanswered (0)
        // Total base = 5. Expected overall = (85 + 75 + 0 + 0 + 0) / 5 = 32
        List<QuestionAnswerDto> turns = List.of(
                new QuestionAnswerDto("Câu 1: Microservices là gì?", "Microservices chia nhỏ hệ thống...", 80, false, false),
                new QuestionAnswerDto("Hỏi sâu 1: Xử lý distributed transaction thế nào?", "Dùng Saga pattern...", 90, true, false),
                new QuestionAnswerDto("Câu 2: SQL vs NoSQL khác nhau gì?", "SQL là relational, NoSQL là non-relational...", 75, false, false),
                new QuestionAnswerDto("Câu 3: Docker hoạt động thế nào?", "", 0, false, false),
                new QuestionAnswerDto("Câu 4: CI/CD pipeline là gì?", "", 0, false, false),
                new QuestionAnswerDto("Câu 5: Nguyên tắc SOLID là gì?", "", 0, false, false)
        );

        List<InterviewEvaluationResponseDto.EvaluatedQuestionDto> evaluated = List.of(
                new InterviewEvaluationResponseDto.EvaluatedQuestionDto("Câu 1", "Ans", 80, "Tốt", "", ""),
                new InterviewEvaluationResponseDto.EvaluatedQuestionDto("Hỏi sâu 1", "Ans", 90, "Rất tốt", "", ""),
                new InterviewEvaluationResponseDto.EvaluatedQuestionDto("Câu 2", "Ans", 75, "Khá", "", ""),
                new InterviewEvaluationResponseDto.EvaluatedQuestionDto("Câu 3", "", 0, "", "", ""),
                new InterviewEvaluationResponseDto.EvaluatedQuestionDto("Câu 4", "", 0, "", "", ""),
                new InterviewEvaluationResponseDto.EvaluatedQuestionDto("Câu 5", "", 0, "", "", "")
        );

        int score = service.calculateGroupedOverallScore(turns, evaluated, 5);
        assertEquals(32, score, "Score should be 32 (85 + 75 + 0 + 0 + 0) / 5");
    }

    @Test
    @DisplayName("Warmup self-introduction turn is excluded from technical score")
    void testWarmupTurnExcludedFromScore() {
        // Warmup turn (excluded)
        // Question 1: main 80 -> avg 80
        // Question 2: main 80 -> avg 80
        // Questions 3, 4, 5: unanswered (0)
        // Total base = 5. Expected overall = (80 + 80 + 0 + 0 + 0) / 5 = 32
        List<QuestionAnswerDto> turns = List.of(
                new QuestionAnswerDto("Hãy giới thiệu đôi nét về bản thân", "Tôi là Nam, tốt nghiệp ĐH...", 100, false, true),
                new QuestionAnswerDto("Câu 1: Nguyên lý OOP", "Gồm 4 tính chất...", 80, false, false),
                new QuestionAnswerDto("Câu 2: Design pattern Singleton", "Đảm bảo 1 instance...", 80, false, false)
        );

        List<InterviewEvaluationResponseDto.EvaluatedQuestionDto> evaluated = List.of(
                new InterviewEvaluationResponseDto.EvaluatedQuestionDto("Giới thiệu", "Ans", 100, "", "", ""),
                new InterviewEvaluationResponseDto.EvaluatedQuestionDto("Câu 1", "Ans", 80, "", "", ""),
                new InterviewEvaluationResponseDto.EvaluatedQuestionDto("Câu 2", "Ans", 80, "", "", "")
        );

        int score = service.calculateGroupedOverallScore(turns, evaluated, 5);
        assertEquals(32, score, "Warmup turn must not dilute or artificially inflate technical score");
    }

    @Test
    @DisplayName("Calculate score: All 5 base questions answered with multiple followups")
    void testAllQuestionsAnsweredWithMultipleFollowUps() {
        // Q1: (80 + 90) / 2 = 85
        // Q2: 80
        // Q3: (70 + 80) / 2 = 75
        // Q4: 90
        // Q5: 85
        // Overall: (85 + 80 + 75 + 90 + 85) / 5 = 83
        List<QuestionAnswerDto> turns = List.of(
                new QuestionAnswerDto("Q1", "A1", 80, false, false),
                new QuestionAnswerDto("Q1-FU1", "A1-FU1", 90, true, false),
                new QuestionAnswerDto("Q2", "A2", 80, false, false),
                new QuestionAnswerDto("Q3", "A3", 70, false, false),
                new QuestionAnswerDto("Q3-FU1", "A3-FU1", 80, true, false),
                new QuestionAnswerDto("Q4", "A4", 90, false, false),
                new QuestionAnswerDto("Q5", "A5", 85, false, false)
        );

        List<InterviewEvaluationResponseDto.EvaluatedQuestionDto> evaluated = List.of(
                new InterviewEvaluationResponseDto.EvaluatedQuestionDto("Q1", "A1", 80, "", "", ""),
                new InterviewEvaluationResponseDto.EvaluatedQuestionDto("Q1-FU1", "A1-FU1", 90, "", "", ""),
                new InterviewEvaluationResponseDto.EvaluatedQuestionDto("Q2", "A2", 80, "", "", ""),
                new InterviewEvaluationResponseDto.EvaluatedQuestionDto("Q3", "A3", 70, "", "", ""),
                new InterviewEvaluationResponseDto.EvaluatedQuestionDto("Q3-FU1", "A3-FU1", 80, "", "", ""),
                new InterviewEvaluationResponseDto.EvaluatedQuestionDto("Q4", "A4", 90, "", "", ""),
                new InterviewEvaluationResponseDto.EvaluatedQuestionDto("Q5", "A5", 85, "", "", "")
        );

        int score = service.calculateGroupedOverallScore(turns, evaluated, 5);
        assertEquals(83, score, "Score should be 83");
    }

    @Test
    @DisplayName("Calculate score: 0 questions answered returns 0")
    void testZeroQuestionsAnswered() {
        List<QuestionAnswerDto> turns = List.of(
                new QuestionAnswerDto("Q1", "", 0, false, false),
                new QuestionAnswerDto("Q2", "", 0, false, false),
                new QuestionAnswerDto("Q3", "", 0, false, false),
                new QuestionAnswerDto("Q4", "", 0, false, false),
                new QuestionAnswerDto("Q5", "", 0, false, false)
        );

        int score = service.calculateGroupedOverallScore(turns, null, 5);
        assertEquals(0, score, "Score should be 0 when no questions are answered");
    }
}
