package fit.iuh.modules.admin.service.impl;

import fit.iuh.modules.admin.dto.*;
import fit.iuh.modules.admin.entity.LevelDistributionRule;
import fit.iuh.modules.admin.entity.SystemSetting;
import fit.iuh.modules.admin.repository.LevelDistributionRuleRepository;
import fit.iuh.modules.admin.repository.SystemSettingRepository;
import fit.iuh.modules.admin.service.RuleAdminService;
import fit.iuh.modules.assessment.service.CriteriaEmbeddingInitializer;
import fit.iuh.modules.rulengine.entity.CategoryCriteriaMapping;
import fit.iuh.modules.rulengine.entity.EvaluationCriteria;
import fit.iuh.modules.rulengine.entity.JobCategoryEntity;
import fit.iuh.modules.rulengine.repository.CategoryCriteriaMappingRepository;
import fit.iuh.modules.rulengine.repository.EvaluationCriteriaRepository;
import fit.iuh.modules.rulengine.repository.JobCategoryEntityRepository;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.cache.annotation.CacheEvict;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.HashMap;
import java.util.HashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.stream.Collectors;

@Slf4j
@Service
public class RuleAdminServiceImpl implements RuleAdminService {

    private final JobCategoryEntityRepository jobCategoryRepository;
    private final EvaluationCriteriaRepository criteriaRepository;
    private final CategoryCriteriaMappingRepository mappingRepository;
    private final LevelDistributionRuleRepository levelRuleRepository;
    private final SystemSettingRepository settingRepository;
    private final CriteriaEmbeddingInitializer criteriaEmbeddingInitializer;

    @Autowired
    public RuleAdminServiceImpl(
            JobCategoryEntityRepository jobCategoryRepository,
            EvaluationCriteriaRepository criteriaRepository,
            CategoryCriteriaMappingRepository mappingRepository,
            LevelDistributionRuleRepository levelRuleRepository,
            SystemSettingRepository settingRepository,
            @Autowired(required = false) CriteriaEmbeddingInitializer criteriaEmbeddingInitializer) {
        this.jobCategoryRepository = jobCategoryRepository;
        this.criteriaRepository = criteriaRepository;
        this.mappingRepository = mappingRepository;
        this.levelRuleRepository = levelRuleRepository;
        this.settingRepository = settingRepository;
        this.criteriaEmbeddingInitializer = criteriaEmbeddingInitializer;
    }

    @Override
    @Transactional(readOnly = true)
    public List<JobCategoryDto> getAllCategories() {
        return jobCategoryRepository.findAll().stream()
                .map(this::toCategoryDto)
                .collect(Collectors.toList());
    }

    @Override
    @Transactional
    @CacheEvict(value = "criteria_prompts", allEntries = true)
    public JobCategoryDto createCategory(JobCategoryDto dto) {
        validateNoCycle(null, dto.parentId());

        JobCategoryEntity parent = null;
        if (dto.parentId() != null) {
            parent = jobCategoryRepository.findById(dto.parentId())
                    .orElseThrow(() -> new IllegalArgumentException("Parent category not found with id: " + dto.parentId()));
        }

        JobCategoryEntity entity = JobCategoryEntity.builder()
                .code(dto.code().toUpperCase().strip())
                .name(dto.name().strip())
                .parent(parent)
                .build();

        JobCategoryEntity saved = jobCategoryRepository.save(entity);
        log.info("[AdminService] Created JobCategory id={}, code={}", saved.getId(), saved.getCode());
        return toCategoryDto(saved);
    }

    @Override
    @Transactional
    @CacheEvict(value = "criteria_prompts", allEntries = true)
    public JobCategoryDto updateCategory(Long id, JobCategoryDto dto) {
        JobCategoryEntity entity = jobCategoryRepository.findById(id)
                .orElseThrow(() -> new IllegalArgumentException("Category not found with id: " + id));

        validateNoCycle(id, dto.parentId());

        JobCategoryEntity parent = null;
        if (dto.parentId() != null) {
            parent = jobCategoryRepository.findById(dto.parentId())
                    .orElseThrow(() -> new IllegalArgumentException("Parent category not found with id: " + dto.parentId()));
        }

        entity.setCode(dto.code().toUpperCase().strip());
        entity.setName(dto.name().strip());
        entity.setParent(parent);

        JobCategoryEntity updated = jobCategoryRepository.save(entity);
        log.info("[AdminService] Updated JobCategory id={}, code={}", updated.getId(), updated.getCode());
        return toCategoryDto(updated);
    }

    /**
     * Prevents cyclic reference in the Job Category tree hierarchy.
     *
     * @param targetCategoryId the ID of the category being updated (null if creating new)
     * @param newParentId      the proposed new parent ID
     */
    private void validateNoCycle(Long targetCategoryId, Long newParentId) {
        if (newParentId == null) {
            return;
        }

        if (targetCategoryId != null && targetCategoryId.equals(newParentId)) {
            throw new IllegalArgumentException("Không thể tự gán danh mục làm cha của chính nó.");
        }

        Long currentParentId = newParentId;
        Set<Long> visited = new HashSet<>();
        if (targetCategoryId != null) {
            visited.add(targetCategoryId);
        }

        while (currentParentId != null) {
            if (!visited.add(currentParentId)) {
                if (targetCategoryId != null && targetCategoryId.equals(currentParentId)) {
                    throw new IllegalArgumentException("Lỗi tham chiếu vòng: Không thể gán danh mục này làm con của một danh mục thuộc nhánh con của chính nó.");
                }
                break;
            }

            JobCategoryEntity parentEntity = jobCategoryRepository.findById(currentParentId)
                    .orElseThrow(() -> new IllegalArgumentException("Parent category not found with id: " + newParentId));

            currentParentId = (parentEntity.getParent() != null) ? parentEntity.getParent().getId() : null;
        }
    }

    @Override
    @Transactional
    @CacheEvict(value = "criteria_prompts", allEntries = true)
    public boolean deleteCategory(Long id) {
        if (!jobCategoryRepository.existsById(id)) {
            return false;
        }
        jobCategoryRepository.deleteById(id);
        log.info("[AdminService] Deleted JobCategory id={}", id);
        return true;
    }

    @Override
    @Transactional(readOnly = true)
    public List<EvaluationCriteriaDto> getAllCriteria() {
        // 1. Fetch all (criteriaId, level) pairs from the mapping table in one query.
        List<Object[]> rows = criteriaRepository.findAllCriteriaIdAndLevel();
        Map<Long, Set<String>> levelsByCriteriaId = new HashMap<>();
        for (Object[] row : rows) {
            Long criteriaId = ((Number) row[0]).longValue();
            String level = (String) row[1];
            levelsByCriteriaId
                    .computeIfAbsent(criteriaId, k -> new HashSet<>())
                    .add(level);
        }
        // 2. Map each criteria entity to a DTO with its collected mapped levels.
        return criteriaRepository.findAll().stream()
                .map(e -> toCriteriaDto(e, levelsByCriteriaId.getOrDefault(e.getId(), Set.of())))
                .collect(Collectors.toList());
    }

    @Override
    @Transactional
    @CacheEvict(value = "criteria_prompts", allEntries = true)
    public EvaluationCriteriaDto createCriteria(EvaluationCriteriaDto dto) {
        EvaluationCriteria entity = EvaluationCriteria.builder()
                .name(dto.name().strip())
                .category(dto.category() != null ? dto.category().strip() : "technical")
                .questionType(dto.questionType() != null ? dto.questionType().strip() : "technical")
                .promptInstruction(dto.promptInstruction() != null ? dto.promptInstruction().strip() : "")
                .build();

        EvaluationCriteria saved = criteriaRepository.save(entity);
        log.info("[AdminService] Created EvaluationCriteria id={}, name={}", saved.getId(), saved.getName());

        // Asynchronously compute and persist embedding for the new criteria
        if (criteriaEmbeddingInitializer != null) {
            criteriaEmbeddingInitializer.computeAndPersistEmbedding(saved);
        }

        return toCriteriaDto(saved, Set.of());
    }

    @Override
    @Transactional
    @CacheEvict(value = "criteria_prompts", allEntries = true)
    public EvaluationCriteriaDto updateCriteria(Long id, EvaluationCriteriaDto dto) {
        EvaluationCriteria entity = criteriaRepository.findById(id)
                .orElseThrow(() -> new IllegalArgumentException("Criteria not found with id: " + id));

        entity.setName(dto.name().strip());
        entity.setCategory(dto.category() != null ? dto.category().strip() : entity.getCategory());
        entity.setQuestionType(dto.questionType() != null ? dto.questionType().strip() : entity.getQuestionType());
        entity.setPromptInstruction(dto.promptInstruction() != null ? dto.promptInstruction().strip() : entity.getPromptInstruction());

        // Nullify existing embedding so computeAndPersistEmbedding will recompute it
        entity.setEmbedding(null);

        EvaluationCriteria updated = criteriaRepository.save(entity);
        log.info("[AdminService] Updated EvaluationCriteria id={}", updated.getId());

        // Recompute embedding for updated text
        if (criteriaEmbeddingInitializer != null) {
            criteriaEmbeddingInitializer.computeAndPersistEmbedding(updated);
        }

        return toCriteriaDto(updated, Set.of());
    }

    @Override
    @Transactional
    @CacheEvict(value = "criteria_prompts", allEntries = true)
    public boolean deleteCriteria(Long id) {
        if (!criteriaRepository.existsById(id)) {
            return false;
        }
        criteriaRepository.deleteById(id);
        log.info("[AdminService] Deleted EvaluationCriteria id={}", id);
        return true;
    }

    @Override
    @Transactional(readOnly = true)
    public List<CategoryCriteriaMappingDto> getAllMappings() {
        return mappingRepository.findAll().stream()
                .map(this::toMappingDto)
                .collect(Collectors.toList());
    }

    @Override
    @Transactional
    @CacheEvict(value = "criteria_prompts", allEntries = true)
    public CategoryCriteriaMappingDto createMapping(CategoryCriteriaMappingDto dto) {
        JobCategoryEntity category = jobCategoryRepository.findById(dto.categoryId())
                .orElseThrow(() -> new IllegalArgumentException("Category not found with id: " + dto.categoryId()));

        EvaluationCriteria criteria = criteriaRepository.findById(dto.criteriaId())
                .orElseThrow(() -> new IllegalArgumentException("Criteria not found with id: " + dto.criteriaId()));

        String level = dto.level() != null ? dto.level().toUpperCase().strip() : "ALL";

        CategoryCriteriaMapping entity = CategoryCriteriaMapping.builder()
                .jobCategory(category)
                .evaluationCriteria(criteria)
                .level(level)
                .weightPercentage(dto.weightPercentage())
                .levelPromptInstruction(dto.levelPromptInstruction())
                .build();

        CategoryCriteriaMapping saved = mappingRepository.save(entity);
        log.info("[AdminService] Created Mapping categoryId={}, criteriaId={}, level={}, weight={}",
                category.getId(), criteria.getId(), level, saved.getWeightPercentage());
        return toMappingDto(saved);
    }

    @Override
    @Transactional
    @CacheEvict(value = "criteria_prompts", allEntries = true)
    public CategoryCriteriaMappingDto updateMapping(Long categoryId, Long criteriaId, String level, CategoryCriteriaMappingDto dto) {
        CategoryCriteriaMapping entity = mappingRepository
                .findByJobCategoryIdAndEvaluationCriteriaIdAndLevel(categoryId, criteriaId, level.toUpperCase().strip())
                .orElseThrow(() -> new IllegalArgumentException(
                        String.format("Mapping not found for categoryId=%d, criteriaId=%d, level=%s", categoryId, criteriaId, level)));

        entity.setWeightPercentage(dto.weightPercentage());
        if (dto.levelPromptInstruction() != null) {
            entity.setLevelPromptInstruction(dto.levelPromptInstruction());
        }
        CategoryCriteriaMapping updated = mappingRepository.save(entity);
        log.info("[AdminService] Updated Mapping weight to {} for categoryId={}, criteriaId={}, level={}",
                updated.getWeightPercentage(), categoryId, criteriaId, level);
        return toMappingDto(updated);
    }

    @Override
    @Transactional
    @CacheEvict(value = "criteria_prompts", allEntries = true)
    public boolean deleteMapping(Long categoryId, Long criteriaId, String level) {
        var opt = mappingRepository.findByJobCategoryIdAndEvaluationCriteriaIdAndLevel(
                categoryId, criteriaId, level.toUpperCase().strip());
        if (opt.isEmpty()) {
            return false;
        }
        mappingRepository.delete(opt.get());
        log.info("[AdminService] Deleted Mapping categoryId={}, criteriaId={}, level={}", categoryId, criteriaId, level);
        return true;
    }

    @Override
    @Transactional(readOnly = true)
    public List<LevelDistributionRuleDto> getAllLevelRules() {
        return levelRuleRepository.findAll().stream()
                .map(this::toLevelRuleDto)
                .collect(Collectors.toList());
    }

    @Override
    @Transactional
    public LevelDistributionRuleDto updateLevelRule(String level, LevelDistributionRuleDto dto) {
        LevelDistributionRule entity = levelRuleRepository.findByLevel(level.toUpperCase().strip())
                .orElseThrow(() -> new IllegalArgumentException("Level rule not found for level: " + level));

        entity.setBehavioralPct(dto.behavioralPct());
        entity.setTechnicalPct(dto.technicalPct());
        entity.setCodingPct(dto.codingPct());
        entity.setSystemDesignPct(dto.systemDesignPct());

        LevelDistributionRule updated = levelRuleRepository.save(entity);
        log.info("[AdminService] Updated LevelRule level={}", updated.getLevel());
        return toLevelRuleDto(updated);
    }

    @Override
    @Transactional(readOnly = true)
    public List<SystemSettingDto> getAllSettings() {
        return settingRepository.findAll().stream()
                .map(this::toSettingDto)
                .collect(Collectors.toList());
    }

    @Override
    @Transactional
    public SystemSettingDto updateSetting(String key, SystemSettingDto dto) {
        SystemSetting entity = settingRepository.findBySettingKey(key.strip())
                .orElseThrow(() -> new IllegalArgumentException("System setting not found for key: " + key));

        entity.setSettingValue(dto.settingValue().strip());
        if (dto.description() != null) {
            entity.setDescription(dto.description().strip());
        }

        SystemSetting updated = settingRepository.save(entity);
        log.info("[AdminService] Updated SystemSetting key={}, value={}", updated.getSettingKey(), updated.getSettingValue());
        return toSettingDto(updated);
    }

    private JobCategoryDto toCategoryDto(JobCategoryEntity e) {
        Long parentId = e.getParent() != null ? e.getParent().getId() : null;
        return new JobCategoryDto(e.getId(), e.getCode(), e.getName(), parentId);
    }

    private EvaluationCriteriaDto toCriteriaDto(EvaluationCriteria e, Set<String> mappedLevels) {
        return new EvaluationCriteriaDto(e.getId(), e.getName(), e.getCategory(), e.getQuestionType(), e.getPromptInstruction(), mappedLevels);
    }

    private CategoryCriteriaMappingDto toMappingDto(CategoryCriteriaMapping e) {
        return new CategoryCriteriaMappingDto(
                e.getJobCategory().getId(),
                e.getEvaluationCriteria().getId(),
                e.getLevel(),
                e.getWeightPercentage(),
                e.getLevelPromptInstruction()
        );
    }

    private LevelDistributionRuleDto toLevelRuleDto(LevelDistributionRule e) {
        return new LevelDistributionRuleDto(
                e.getId(), e.getLevel(),
                e.getBehavioralPct(), e.getTechnicalPct(),
                e.getCodingPct(), e.getSystemDesignPct()
        );
    }

    private SystemSettingDto toSettingDto(SystemSetting e) {
        return new SystemSettingDto(e.getId(), e.getSettingKey(), e.getSettingValue(), e.getDescription(), e.getUpdatedAt());
    }
}
