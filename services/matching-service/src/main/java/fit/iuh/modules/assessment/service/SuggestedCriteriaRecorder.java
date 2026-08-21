package fit.iuh.modules.assessment.service;

import fit.iuh.modules.assessment.dto.AssessmentResponseDto;
import fit.iuh.modules.assessment.entity.JobCategory;
import fit.iuh.modules.assessment.entity.SuggestedCriteria;
import fit.iuh.modules.assessment.repository.SuggestedCriteriaRepository;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.LocalDateTime;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

@Slf4j
@Service
@RequiredArgsConstructor
public class SuggestedCriteriaRecorder {

    private final SuggestedCriteriaRepository suggestedCriteriaRepository;

    @Transactional
    public void recordAdHocCriteria(JobCategory jobCategory, List<AssessmentResponseDto.AdHocEvidenceItem> adHocItems) {
        if (adHocItems == null || adHocItems.isEmpty()) return;

        Map<String, AssessmentResponseDto.AdHocEvidenceItem> uniqueItems = new LinkedHashMap<>();
        for (AssessmentResponseDto.AdHocEvidenceItem item : adHocItems) {
            if (item != null && item.criteriaName() != null && !item.criteriaName().isBlank()) {
                uniqueItems.putIfAbsent(item.criteriaName().trim().toLowerCase(), item);
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
                                }
                        );
            } catch (Exception e) {
                log.warn("[SuggestedCriteriaRecorder] Duplicate conflict recording ad-hoc criteria '{}': {}", cleanName, e.getMessage());
            }
        }
    }
}
