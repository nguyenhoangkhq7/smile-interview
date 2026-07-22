package fit.iuh.modules.questionbank.service;

import fit.iuh.modules.questionbank.dto.*;

import java.util.List;

public interface QuestionGenerationService {

    List<QuestionDto> generateForCategory(
            String type,
            CandidateContextDto context,
            List<QuestionAssignment> assignments,
            QuestionConfigDto config);

    QuestionDto regenerateSingle(
            String type,
            String difficulty,
            CandidateContextDto context,
            List<EvidenceItemPair> allEvidenceItems,
            List<QuestionDto> existingQuestions);
}
