package fit.iuh.modules.admin;

import fit.iuh.modules.admin.dto.*;
import fit.iuh.modules.rulengine.*;
import jakarta.persistence.EntityNotFoundException;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.security.access.prepost.PreAuthorize;
import org.springframework.web.bind.annotation.*;

import java.util.List;
import java.util.stream.Collectors;

/**
 * REST Controller exposing the Admin Control Center CRUD API.
 *
 * <p><strong>Base path:</strong> {@code /api/admin}
 *
 * <p><strong>Security:</strong> All endpoints require the caller to hold the
 * {@code ADMIN} role (enforced by {@code @PreAuthorize} which requires
 * {@code @EnableMethodSecurity} — already active in {@code SecurityConfig}).
 *
 * <h2>Managed Resources</h2>
 * <ul>
 *   <li>Job Categories ({@code job_categories} table)</li>
 *   <li>Evaluation Criteria ({@code evaluation_criteria} table)</li>
 *   <li>Category↔Criteria Mappings ({@code category_criteria_mapping} table)</li>
 *   <li>Level Distribution Rules ({@code level_distribution_rules} table)</li>
 *   <li>System Settings ({@code system_settings} table)</li>
 * </ul>
 */
@Slf4j
@RestController
@RequestMapping("/api/admin")
@RequiredArgsConstructor
@PreAuthorize("hasRole('ADMIN')")
public class RuleAdminController {

    private final JobCriteriaRepository             jobCriteriaRepository;
    private final EvaluationCriteriaRepository      evaluationCriteriaRepository;
    private final CategoryCriteriaMappingRepository mappingRepository;
    private final LevelDistributionRuleRepository   levelRuleRepository;
    private final SystemSettingRepository           systemSettingRepository;

    // =========================================================================
    // Job Categories
    // =========================================================================

    @GetMapping("/job-categories")
    public ResponseEntity<List<JobCategoryDto>> getAllCategories() {
        List<JobCategoryDto> result = jobCriteriaRepository.findAll().stream()
                .map(this::toJobCategoryDto)
                .collect(Collectors.toList());
        return ResponseEntity.ok(result);
    }

    @PostMapping("/job-categories")
    public ResponseEntity<JobCategoryDto> createCategory(@Valid @RequestBody JobCategoryDto dto) {
        JobCategoryEntity entity = new JobCategoryEntity();
        entity.setName(dto.getName());

        if (dto.getParentId() != null) {
            JobCategoryEntity parent = jobCriteriaRepository.findById(dto.getParentId())
                    .orElseThrow(() -> new EntityNotFoundException("Parent category not found: " + dto.getParentId()));
            entity.setParent(parent);
        }

        JobCategoryEntity saved = jobCriteriaRepository.save(entity);
        log.info("[AdminController] Job category created: id={}, name={}", saved.getId(), saved.getName());
        return ResponseEntity.status(HttpStatus.CREATED).body(toJobCategoryDto(saved));
    }

    @PutMapping("/job-categories/{id}")
    public ResponseEntity<JobCategoryDto> updateCategory(
            @PathVariable Long id,
            @Valid @RequestBody JobCategoryDto dto) {

        JobCategoryEntity entity = jobCriteriaRepository.findById(id)
                .orElseThrow(() -> new EntityNotFoundException("Job category not found: " + id));

        entity.setName(dto.getName());
        if (dto.getParentId() != null) {
            if (dto.getParentId().equals(id)) {
                return ResponseEntity.badRequest().build(); // prevent self-reference
            }
            JobCategoryEntity parent = jobCriteriaRepository.findById(dto.getParentId())
                    .orElseThrow(() -> new EntityNotFoundException("Parent category not found: " + dto.getParentId()));
            entity.setParent(parent);
        } else {
            entity.setParent(null);
        }

        JobCategoryEntity saved = jobCriteriaRepository.save(entity);
        log.info("[AdminController] Job category updated: id={}", id);
        return ResponseEntity.ok(toJobCategoryDto(saved));
    }

    @DeleteMapping("/job-categories/{id}")
    public ResponseEntity<Void> deleteCategory(@PathVariable Long id) {
        if (!jobCriteriaRepository.existsById(id)) {
            return ResponseEntity.notFound().build();
        }
        jobCriteriaRepository.deleteById(id);
        log.info("[AdminController] Job category deleted: id={}", id);
        return ResponseEntity.noContent().build();
    }

    // =========================================================================
    // Evaluation Criteria
    // =========================================================================

    @GetMapping("/evaluation-criteria")
    public ResponseEntity<List<EvaluationCriteriaDto>> getAllCriteria() {
        List<EvaluationCriteriaDto> result = evaluationCriteriaRepository.findAll().stream()
                .map(this::toEvaluationCriteriaDto)
                .collect(Collectors.toList());
        return ResponseEntity.ok(result);
    }

    @PostMapping("/evaluation-criteria")
    public ResponseEntity<EvaluationCriteriaDto> createCriteria(
            @Valid @RequestBody EvaluationCriteriaDto dto) {

        EvaluationCriteria entity = new EvaluationCriteria();
        entity.setCriteriaName(dto.getCriteriaName());
        entity.setPromptInstruction(dto.getPromptInstruction());

        EvaluationCriteria saved = evaluationCriteriaRepository.save(entity);
        log.info("[AdminController] Evaluation criteria created: id={}, name={}", saved.getId(), saved.getCriteriaName());
        return ResponseEntity.status(HttpStatus.CREATED).body(toEvaluationCriteriaDto(saved));
    }

    @PutMapping("/evaluation-criteria/{id}")
    public ResponseEntity<EvaluationCriteriaDto> updateCriteria(
            @PathVariable Long id,
            @Valid @RequestBody EvaluationCriteriaDto dto) {

        EvaluationCriteria entity = evaluationCriteriaRepository.findById(id)
                .orElseThrow(() -> new EntityNotFoundException("Evaluation criteria not found: " + id));

        entity.setCriteriaName(dto.getCriteriaName());
        entity.setPromptInstruction(dto.getPromptInstruction());

        EvaluationCriteria saved = evaluationCriteriaRepository.save(entity);
        log.info("[AdminController] Evaluation criteria updated: id={}", id);
        return ResponseEntity.ok(toEvaluationCriteriaDto(saved));
    }

    @DeleteMapping("/evaluation-criteria/{id}")
    public ResponseEntity<Void> deleteCriteria(@PathVariable Long id) {
        if (!evaluationCriteriaRepository.existsById(id)) {
            return ResponseEntity.notFound().build();
        }
        evaluationCriteriaRepository.deleteById(id);
        log.info("[AdminController] Evaluation criteria deleted: id={}", id);
        return ResponseEntity.noContent().build();
    }

    // =========================================================================
    // Category–Criteria Mappings
    // =========================================================================

    @GetMapping("/category-criteria-mappings")
    public ResponseEntity<List<CategoryCriteriaMappingDto>> getAllMappings() {
        List<CategoryCriteriaMappingDto> result = mappingRepository.findAll().stream()
                .map(this::toMappingDto)
                .collect(Collectors.toList());
        return ResponseEntity.ok(result);
    }

    @PostMapping("/category-criteria-mappings")
    public ResponseEntity<CategoryCriteriaMappingDto> createMapping(
            @Valid @RequestBody CategoryCriteriaMappingDto dto) {

        CategoryCriteriaMapping entity = new CategoryCriteriaMapping();
        entity.setJobCategoryId(dto.getJobCategoryId());
        entity.setCriteriaId(dto.getCriteriaId());
        entity.setSeniorityLevel(dto.getSeniorityLevel());
        entity.setWeightPercentage(dto.getWeightPercentage());

        CategoryCriteriaMapping saved = mappingRepository.save(entity);
        log.info("[AdminController] Mapping created: cat={}, crit={}, level={}",
                saved.getJobCategoryId(), saved.getCriteriaId(), saved.getSeniorityLevel());
        return ResponseEntity.status(HttpStatus.CREATED).body(toMappingDto(saved));
    }

    @PutMapping("/category-criteria-mappings/{categoryId}/{criteriaId}/{level}")
    public ResponseEntity<CategoryCriteriaMappingDto> updateMapping(
            @PathVariable Long categoryId,
            @PathVariable Long criteriaId,
            @PathVariable String level,
            @Valid @RequestBody CategoryCriteriaMappingDto dto) {

        CategoryCriteriaMapping.CategoryCriteriaMappingId pk =
                new CategoryCriteriaMapping.CategoryCriteriaMappingId(categoryId, criteriaId, level);

        CategoryCriteriaMapping entity = mappingRepository.findById(pk)
                .orElseThrow(() -> new EntityNotFoundException(
                        "Mapping not found: cat=" + categoryId + ", crit=" + criteriaId + ", level=" + level));

        entity.setWeightPercentage(dto.getWeightPercentage());

        CategoryCriteriaMapping saved = mappingRepository.save(entity);
        log.info("[AdminController] Mapping updated: weight={}", saved.getWeightPercentage());
        return ResponseEntity.ok(toMappingDto(saved));
    }

    @DeleteMapping("/category-criteria-mappings/{categoryId}/{criteriaId}/{level}")
    public ResponseEntity<Void> deleteMapping(
            @PathVariable Long categoryId,
            @PathVariable Long criteriaId,
            @PathVariable String level) {

        CategoryCriteriaMapping.CategoryCriteriaMappingId pk =
                new CategoryCriteriaMapping.CategoryCriteriaMappingId(categoryId, criteriaId, level);

        if (!mappingRepository.existsById(pk)) {
            return ResponseEntity.notFound().build();
        }
        mappingRepository.deleteById(pk);
        log.info("[AdminController] Mapping deleted: cat={}, crit={}, level={}", categoryId, criteriaId, level);
        return ResponseEntity.noContent().build();
    }

    // =========================================================================
    // Level Distribution Rules
    // =========================================================================

    @GetMapping("/level-distribution-rules")
    public ResponseEntity<List<LevelDistributionRuleDto>> getAllLevelRules() {
        List<LevelDistributionRuleDto> result = levelRuleRepository.findAll().stream()
                .map(this::toLevelRuleDto)
                .collect(Collectors.toList());
        return ResponseEntity.ok(result);
    }

    @PutMapping("/level-distribution-rules/{level}")
    public ResponseEntity<LevelDistributionRuleDto> updateLevelRule(
            @PathVariable String level,
            @Valid @RequestBody LevelDistributionRuleDto dto) {

        LevelDistributionRule entity = levelRuleRepository.findByLevel(level)
                .orElseThrow(() -> new EntityNotFoundException("Level rule not found: " + level));

        entity.setBehavioralPct(dto.getBehavioralPct());
        entity.setTechnicalPct(dto.getTechnicalPct());
        entity.setCodingPct(dto.getCodingPct());
        entity.setSystemDesignPct(dto.getSystemDesignPct());

        LevelDistributionRule saved = levelRuleRepository.save(entity);
        log.info("[AdminController] Level rule updated: level={}", level);
        return ResponseEntity.ok(toLevelRuleDto(saved));
    }

    // =========================================================================
    // System Settings
    // =========================================================================

    @GetMapping("/system-settings")
    public ResponseEntity<List<SystemSettingDto>> getAllSettings() {
        List<SystemSettingDto> result = systemSettingRepository.findAll().stream()
                .map(s -> new SystemSettingDto(s.getSettingKey(), s.getSettingValue()))
                .collect(Collectors.toList());
        return ResponseEntity.ok(result);
    }

    @PutMapping("/system-settings/{key}")
    public ResponseEntity<SystemSettingDto> updateSetting(
            @PathVariable String key,
            @Valid @RequestBody SystemSettingDto dto) {

        SystemSetting entity = systemSettingRepository.findBySettingKey(key)
                .orElseThrow(() -> new EntityNotFoundException("System setting not found: " + key));

        entity.setSettingValue(dto.getSettingValue());
        SystemSetting saved = systemSettingRepository.save(entity);
        log.info("[AdminController] System setting updated: key={}, value={}", key, saved.getSettingValue());
        return ResponseEntity.ok(new SystemSettingDto(saved.getSettingKey(), saved.getSettingValue()));
    }

    // =========================================================================
    // Private mappers
    // =========================================================================

    private JobCategoryDto toJobCategoryDto(JobCategoryEntity e) {
        return JobCategoryDto.builder()
                .id(e.getId())
                .name(e.getName())
                .parentId(e.getParent() != null ? e.getParent().getId() : null)
                .parentName(e.getParent() != null ? e.getParent().getName() : null)
                .build();
    }

    private EvaluationCriteriaDto toEvaluationCriteriaDto(EvaluationCriteria e) {
        return EvaluationCriteriaDto.builder()
                .id(e.getId())
                .criteriaName(e.getCriteriaName())
                .promptInstruction(e.getPromptInstruction())
                .build();
    }

    private CategoryCriteriaMappingDto toMappingDto(CategoryCriteriaMapping e) {
        // Enrich with category and criteria names for display
        String catName = jobCriteriaRepository.findById(e.getJobCategoryId())
                .map(JobCategoryEntity::getName).orElse(null);
        String crtName = evaluationCriteriaRepository.findById(e.getCriteriaId())
                .map(EvaluationCriteria::getCriteriaName).orElse(null);

        return CategoryCriteriaMappingDto.builder()
                .jobCategoryId(e.getJobCategoryId())
                .jobCategoryName(catName)
                .criteriaId(e.getCriteriaId())
                .criteriaName(crtName)
                .seniorityLevel(e.getSeniorityLevel())
                .weightPercentage(e.getWeightPercentage())
                .build();
    }

    private LevelDistributionRuleDto toLevelRuleDto(LevelDistributionRule e) {
        return LevelDistributionRuleDto.builder()
                .id(e.getId())
                .level(e.getLevel())
                .behavioralPct(e.getBehavioralPct())
                .technicalPct(e.getTechnicalPct())
                .codingPct(e.getCodingPct())
                .systemDesignPct(e.getSystemDesignPct())
                .build();
    }
}
