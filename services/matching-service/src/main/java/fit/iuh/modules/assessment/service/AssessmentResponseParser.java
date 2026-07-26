package fit.iuh.modules.assessment.service;

import fit.iuh.modules.assessment.dto.AssessmentResponseDto;

public interface AssessmentResponseParser {
    AssessmentResponseDto parseAssessmentDto(String sessionId, String llmJsonResponse);
    String sanitizeCyrillicScript(String input);
    String sanitizeLanguageText(String text);
}
