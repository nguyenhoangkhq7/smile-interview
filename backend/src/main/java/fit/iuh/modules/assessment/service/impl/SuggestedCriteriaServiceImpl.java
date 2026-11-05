package fit.iuh.modules.assessment.service.impl;

import fit.iuh.exception.ResourceNotFoundException;
import fit.iuh.modules.assessment.dto.SuggestedCriteriaDto;
import fit.iuh.modules.assessment.entity.SuggestedCriteria;
import fit.iuh.modules.assessment.repository.SuggestedCriteriaRepository;
import fit.iuh.modules.assessment.service.SuggestedCriteriaService;
import fit.iuh.modules.rulengine.entity.CategoryCriteriaMapping;
import fit.iuh.modules.rulengine.entity.EvaluationCriteria;
import fit.iuh.modules.rulengine.entity.JobCategoryEntity;
import fit.iuh.modules.rulengine.repository.CategoryCriteriaMappingRepository;
import fit.iuh.modules.rulengine.repository.EvaluationCriteriaRepository;
import fit.iuh.modules.rulengine.repository.JobCategoryEntityRepository;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.cache.Cache;
import org.springframework.cache.CacheManager;
import org.springframework.data.domain.Sort;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.List;
import java.util.Map;

@Slf4j
@Service
@RequiredArgsConstructor
public class SuggestedCriteriaServiceImpl implements SuggestedCriteriaService {

    private final SuggestedCriteriaRepository suggestedCriteriaRepository;
    private final EvaluationCriteriaRepository evaluationCriteriaRepository;
    private final CategoryCriteriaMappingRepository categoryCriteriaMappingRepository;
    private final JobCategoryEntityRepository jobCategoryEntityRepository;
    private final CacheManager cacheManager;

    @Override
    @Transactional(readOnly = true)
    public List<SuggestedCriteriaDto> getSuggestedCriteria() {
        List<SuggestedCriteria> criteria = suggestedCriteriaRepository.findAll(
                Sort.by(Sort.Direction.DESC, "occurrenceCount")
        );
        return criteria.stream()
                .map(SuggestedCriteriaDto::from)
                .toList();
    }

    @Override
    @Transactional
    public Map<String, Object> promoteCriteria(
            Long id,
            String categoryCode,
            String level,
            Double weightPercentage,
            String questionType,
            String category) {

        SuggestedCriteria suggested = suggestedCriteriaRepository.findById(id)
                .orElseThrow(() -> new ResourceNotFoundException("Suggested criteria not found with id: " + id));

        if (Boolean.TRUE.equals(suggested.getPromoted())) {
            throw new IllegalStateException("Already promoted: " + suggested.getCriteriaName());
        }

        if (categoryCode == null || categoryCode.isBlank()) {
            throw new IllegalArgumentException("categoryCode is required");
        }

        String normalizedCategoryCode = categoryCode.toUpperCase().strip();
        JobCategoryEntity jobCategory = jobCategoryEntityRepository.findByCode(normalizedCategoryCode)
                .orElseThrow(() -> new IllegalArgumentException("Job category not found: " + normalizedCategoryCode));

        String normalizedLevel = (level != null && !level.isBlank()) ? level.toUpperCase().strip() : "ALL";
        double weight = (weightPercentage != null) ? weightPercentage : 10.0;
        String qType = (questionType != null && !questionType.isBlank()) ? questionType : "technical";
        String critCategory = (category != null && !category.isBlank()) ? category : "technical";

        EvaluationCriteria newCriteria = EvaluationCriteria.builder()
                .name(suggested.getCriteriaName())
                .category(critCategory)
                .questionType(qType)
                .promptInstruction(suggested.getSampleJdText() != null
                        ? "Evaluate candidate's proficiency in " + suggested.getCriteriaName()
                          + ". Specifically: " + suggested.getSampleJdText()
                        : "Evaluate candidate's proficiency in " + suggested.getCriteriaName() + " based on CV evidence.")
                .build();
        newCriteria = evaluationCriteriaRepository.save(newCriteria);

        CategoryCriteriaMapping mapping = CategoryCriteriaMapping.builder()
                .jobCategory(jobCategory)
                .evaluationCriteria(newCriteria)
                .level(normalizedLevel)
                .weightPercentage(weight)
                .build();
        categoryCriteriaMappingRepository.save(mapping);

        suggested.setPromoted(true);
        suggestedCriteriaRepository.save(suggested);

        if (cacheManager != null) {
            Cache cache = cacheManager.getCache("criteria_prompts");
            if (cache != null) {
                cache.clear();
                log.info("[SuggestedCriteriaService] Evicted 'criteria_prompts' cache on promote.");
            }
        }

        log.info("[SuggestedCriteriaService] Promoted suggested criteria '{}' -> evaluation_criteria id={}, category={}, level={}, weight={}%",
                suggested.getCriteriaName(), newCriteria.getId(), normalizedCategoryCode, normalizedLevel, weight);

        return Map.of(
                "message", "Criteria promoted successfully",
                "criteriaId", newCriteria.getId(),
                "criteriaName", newCriteria.getName(),
                "mappedCategory", normalizedCategoryCode,
                "mappedLevel", normalizedLevel,
                "weightPercentage", weight
        );
    }

    @Override
    @Transactional
    public void deleteSuggestedCriteria(Long id) {
        if (!suggestedCriteriaRepository.existsById(id)) {
            throw new ResourceNotFoundException("Suggested criteria not found with id: " + id);
        }
        suggestedCriteriaRepository.deleteById(id);
        log.info("[SuggestedCriteriaService] Deleted suggested criteria id={}", id);
    }
}
