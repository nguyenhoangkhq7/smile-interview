package fit.iuh.modules.assessment.service.impl;

import com.fasterxml.jackson.databind.ObjectMapper;
import fit.iuh.modules.assessment.dto.AssessmentResponseDto;
import fit.iuh.modules.assessment.service.AssessmentResponseParser;
import fit.iuh.modules.assessment.util.TextSanitizationUtil;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;

import java.util.List;
import java.util.stream.Collectors;

@Slf4j
@Service
@RequiredArgsConstructor
public class AssessmentResponseParserImpl implements AssessmentResponseParser {

    private final ObjectMapper objectMapper;

    @Override
    public AssessmentResponseDto parseAssessmentDto(String sessionId, String llmJsonResponse) {
        String cleanJson = TextSanitizationUtil.extractCleanJson(llmJsonResponse);
        try {
            AssessmentResponseDto rawDto = objectMapper.readValue(cleanJson, AssessmentResponseDto.class);

            List<AssessmentResponseDto.EvidenceItem> sanitizedEvidence = rawDto.mustHaveEvidenceItems() != null
                    ? rawDto.mustHaveEvidenceItems().stream()
                    .filter(item -> item != null)
                    .map(item -> new AssessmentResponseDto.EvidenceItem(
                            item.criteriaId(),
                            sanitizeCyrillicScript(item.criteriaName()),
                            item.importance(),
                            sanitizeLanguageText(item.jdRequirement()),
                            sanitizeLanguageText(item.cvEvidence()),
                            item.status(),
                            sanitizeLanguageText(item.reasoning()),
                            item.weightUsed(),
                            item.scoreContribution(),
                            item.groundingScore(),
                            item.confidenceVotes(),
                            item.lowConfidence(),
                            item.needsManualReview()
                    ))
                    .collect(Collectors.toList())
                    : List.of();

            List<AssessmentResponseDto.AdHocEvidenceItem> preferToHave = rawDto.preferToHaveEvidenceItems() != null
                    ? rawDto.preferToHaveEvidenceItems() : List.of();

            List<AssessmentResponseDto.AdHocEvidenceItem> sanitizedAdHoc = preferToHave.stream()
                    .filter(item -> item != null)
                    .map(item -> new AssessmentResponseDto.AdHocEvidenceItem(
                            sanitizeCyrillicScript(item.criteriaName()),
                            item.importance(),
                            sanitizeLanguageText(item.jdRequirement()),
                            sanitizeLanguageText(item.cvEvidence()),
                            item.status(),
                            sanitizeLanguageText(item.reasoning())
                    ))
                    .collect(Collectors.toList());

            return new AssessmentResponseDto(sanitizedEvidence, sanitizedAdHoc);

        } catch (Exception e) {
            log.error("[AssessmentParser] JSON parse error for session {}: {}", sessionId, e.getMessage());
            throw new RuntimeException("Failed to parse LLM assessment JSON response", e);
        }
    }

    @Override
    public String sanitizeCyrillicScript(String input) {
        return TextSanitizationUtil.sanitizeCyrillicScript(input);
    }

    @Override
    public String sanitizeLanguageText(String text) {
        return TextSanitizationUtil.sanitizeLanguageText(text);
    }
}
