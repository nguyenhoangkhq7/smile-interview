package fit.iuh.modules.questionbank.service;

import fit.iuh.modules.questionbank.dto.GenerateQuestionBankRequest;
import fit.iuh.modules.questionbank.dto.QuestionBankResponseDto;

import java.util.List;
import java.util.UUID;

public interface QuestionBankService {

    QuestionBankResponseDto generate(GenerateQuestionBankRequest request);

    List<QuestionBankResponseDto> getBySessionId(String sessionId);

    QuestionBankResponseDto getById(UUID id);

    QuestionBankResponseDto regenerateQuestion(UUID questionBankId, String questionId);
}
