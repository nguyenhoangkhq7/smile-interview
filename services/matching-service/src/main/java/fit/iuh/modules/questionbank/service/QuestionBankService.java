package fit.iuh.modules.questionbank.service;

import fit.iuh.modules.questionbank.dto.GenerateQuestionBankRequest;
import fit.iuh.modules.questionbank.dto.QuestionBankResponseDto;

import java.util.List;
import java.util.UUID;

public interface QuestionBankService {

    QuestionBankResponseDto generate(GenerateQuestionBankRequest request);

    List<QuestionBankResponseDto> getBySessionId(String sessionId);

    /**
     * Retrieves the most recently generated {@link QuestionBankResponseDto} for the
     * given {@code sessionId}.
     *
     * @param sessionId the interview session identifier
     * @return the latest question bank record
     * @throws fit.iuh.exception.ResourceNotFoundException if no question bank exists for this session
     */
    QuestionBankResponseDto getQuestionBankBySessionId(String sessionId);

    QuestionBankResponseDto getById(UUID id);

    QuestionBankResponseDto regenerateQuestion(UUID questionBankId, String questionId);
}
