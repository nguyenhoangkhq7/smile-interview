package fit.iuh.modules.assessment;

import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.LocalDateTime;
import java.util.List;

@Slf4j
@Service
@RequiredArgsConstructor
public class SuggestedCriteriaService {

    private final SuggestedCriteriaRepository suggestedCriteriaRepository;

    @Transactional
    public void recordAdHocCriteria(JobCategory jobCategory, List<AssessmentResponseDto.AdHocEvidenceItem> adHocItems) {
        if (adHocItems == null || adHocItems.isEmpty()) {
            return;
        }

        for (AssessmentResponseDto.AdHocEvidenceItem item : adHocItems) {
            if (item.criteriaName() == null || item.criteriaName().isBlank()) continue;

            suggestedCriteriaRepository.findByJobCategoryAndCriteriaNameIgnoreCase(jobCategory, item.criteriaName())
                    .ifPresentOrElse(
                            existing -> {
                                existing.setOccurrenceCount(existing.getOccurrenceCount() + 1);
                                existing.setLastSeenAt(LocalDateTime.now());
                                // Update sample text if it's longer/more descriptive
                                if (item.jdRequirement() != null && 
                                    (existing.getSampleJdText() == null || item.jdRequirement().length() > existing.getSampleJdText().length())) {
                                    existing.setSampleJdText(item.jdRequirement());
                                }
                                suggestedCriteriaRepository.save(existing);
                                log.debug("[SuggestedCriteria] Incremented occurrence for: {}", item.criteriaName());
                            },
                            () -> {
                                SuggestedCriteria newCriteria = SuggestedCriteria.builder()
                                        .jobCategory(jobCategory)
                                        .criteriaName(item.criteriaName())
                                        .occurrenceCount(1)
                                        .lastSeenAt(LocalDateTime.now())
                                        .sampleJdText(item.jdRequirement())
                                        .promoted(false)
                                        .build();
                                suggestedCriteriaRepository.save(newCriteria);
                                log.info("[SuggestedCriteria] New ad-hoc criteria recorded: {}", item.criteriaName());
                            }
                    );
        }
    }
}
