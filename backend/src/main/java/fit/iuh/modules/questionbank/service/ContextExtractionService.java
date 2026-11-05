package fit.iuh.modules.questionbank.service;

import fit.iuh.modules.questionbank.dto.CandidateContextDto;

public interface ContextExtractionService {

    CandidateContextDto extractContext(String cvMarkdown, String jdMarkdown, String assessmentJson);
}
