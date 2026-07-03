package fit.iuh.dto;

import java.util.List;

public record InterviewEvaluationRequest(
    String sessionId,
    String roleTitle,
    String interviewType,
    List<QuestionAnswerDto> turns
) {}
