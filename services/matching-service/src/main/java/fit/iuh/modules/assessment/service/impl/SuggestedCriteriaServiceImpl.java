package fit.iuh.modules.assessment.service.impl;

import fit.iuh.modules.assessment.dto.AssessmentResponseDto;
import fit.iuh.modules.assessment.entity.JobCategory;
import fit.iuh.modules.assessment.entity.SuggestedCriteria;
import fit.iuh.modules.assessment.repository.SuggestedCriteriaRepository;
import fit.iuh.modules.assessment.service.SuggestedCriteriaService;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.LocalDateTime;
import java.util.List;

@Slf4j
@Service
@RequiredArgsConstructor
public class SuggestedCriteriaServiceImpl implements SuggestedCriteriaService {

    private final SuggestedCriteriaRepository suggestedCriteriaRepository;

    @Override
    @Transactional
    public void recordAdHocCriteria(JobCategory jobCategory, List<AssessmentResponseDto.AdHocEvidenceItem> adHocItems) {
        if (adHocItems == null || adHocItems.isEmpty()) {
            return;
        }

        // Deduplicate items within the input list by trimmed lower-case criteria name
        java.util.Map<String, AssessmentResponseDto.AdHocEvidenceItem> uniqueItems = new java.util.LinkedHashMap<>();
        for (AssessmentResponseDto.AdHocEvidenceItem item : adHocItems) {
            if (item != null && item.criteriaName() != null && !item.criteriaName().isBlank()) {
                String cleanName = item.criteriaName().trim();
                uniqueItems.putIfAbsent(cleanName.toLowerCase(), item);
            }
        }

        for (AssessmentResponseDto.AdHocEvidenceItem item : uniqueItems.values()) {
            String cleanName = item.criteriaName().trim();
            try {
                suggestedCriteriaRepository.findByJobCategoryAndCriteriaNameIgnoreCase(jobCategory, cleanName)
                        .ifPresentOrElse(
                                existing -> {
                                    existing.setOccurrenceCount(existing.getOccurrenceCount() + 1);
                                    existing.setLastSeenAt(LocalDateTime.now());
                                    if (item.jdRequirement() != null &&
                                        (existing.getSampleJdText() == null || item.jdRequirement().length() > existing.getSampleJdText().length())) {
                                        existing.setSampleJdText(item.jdRequirement());
                                    }
                                    suggestedCriteriaRepository.save(existing);
                                    log.debug("[SuggestedCriteria] Incremented occurrence for: {}", cleanName);
                                },
                                () -> {
                                    SuggestedCriteria newCriteria = SuggestedCriteria.builder()
                                            .jobCategory(jobCategory)
                                            .criteriaName(cleanName)
                                            .occurrenceCount(1)
                                            .lastSeenAt(LocalDateTime.now())
                                            .sampleJdText(item.jdRequirement())
                                            .promoted(false)
                                            .build();
                                    suggestedCriteriaRepository.saveAndFlush(newCriteria);
                                    log.info("[SuggestedCriteria] New ad-hoc criteria recorded: {}", cleanName);
                                }
                        );
            } catch (Exception e) {
                log.warn("[SuggestedCriteria] Duplicate constraint conflict recording ad-hoc criteria '{}': {}", cleanName, e.getMessage());
            }
        }
    }
}
