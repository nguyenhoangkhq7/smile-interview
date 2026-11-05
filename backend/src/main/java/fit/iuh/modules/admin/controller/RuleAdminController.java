package fit.iuh.modules.admin.controller;

import fit.iuh.modules.admin.dto.*;
import fit.iuh.modules.admin.service.RuleAdminService;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.security.access.prepost.PreAuthorize;
import org.springframework.web.bind.annotation.*;

import java.util.List;

@RestController
@RequestMapping("/api/admin")
@RequiredArgsConstructor
@PreAuthorize("hasRole('ADMIN')")
public class RuleAdminController {

    private final RuleAdminService ruleAdminService;

    @GetMapping("/job-categories")
    public ResponseEntity<List<JobCategoryDto>> getAllCategories() {
        return ResponseEntity.ok(ruleAdminService.getAllCategories());
    }

    @PostMapping("/job-categories")
    public ResponseEntity<JobCategoryDto> createCategory(@Valid @RequestBody JobCategoryDto dto) {
        JobCategoryDto created = ruleAdminService.createCategory(dto);
        return ResponseEntity.status(HttpStatus.CREATED).body(created);
    }

    @PutMapping("/job-categories/{id}")
    public ResponseEntity<JobCategoryDto> updateCategory(
            @PathVariable Long id,
            @Valid @RequestBody JobCategoryDto dto) {
        return ResponseEntity.ok(ruleAdminService.updateCategory(id, dto));
    }

    @DeleteMapping("/job-categories/{id}")
    public ResponseEntity<Void> deleteCategory(@PathVariable Long id) {
        boolean deleted = ruleAdminService.deleteCategory(id);
        if (!deleted) {
            return ResponseEntity.notFound().build();
        }
        return ResponseEntity.noContent().build();
    }

    @GetMapping("/evaluation-criteria")
    public ResponseEntity<List<EvaluationCriteriaDto>> getAllCriteria() {
        return ResponseEntity.ok(ruleAdminService.getAllCriteria());
    }

    @PostMapping("/evaluation-criteria")
    public ResponseEntity<EvaluationCriteriaDto> createCriteria(
            @Valid @RequestBody EvaluationCriteriaDto dto) {
        EvaluationCriteriaDto created = ruleAdminService.createCriteria(dto);
        return ResponseEntity.status(HttpStatus.CREATED).body(created);
    }

    @PutMapping("/evaluation-criteria/{id}")
    public ResponseEntity<EvaluationCriteriaDto> updateCriteria(
            @PathVariable Long id,
            @Valid @RequestBody EvaluationCriteriaDto dto) {
        return ResponseEntity.ok(ruleAdminService.updateCriteria(id, dto));
    }

    @DeleteMapping("/evaluation-criteria/{id}")
    public ResponseEntity<Void> deleteCriteria(@PathVariable Long id) {
        boolean deleted = ruleAdminService.deleteCriteria(id);
        if (!deleted) {
            return ResponseEntity.notFound().build();
        }
        return ResponseEntity.noContent().build();
    }

    @GetMapping("/category-criteria-mappings")
    public ResponseEntity<List<CategoryCriteriaMappingDto>> getAllMappings() {
        return ResponseEntity.ok(ruleAdminService.getAllMappings());
    }

    @PostMapping("/category-criteria-mappings")
    public ResponseEntity<CategoryCriteriaMappingDto> createMapping(
            @Valid @RequestBody CategoryCriteriaMappingDto dto) {
        CategoryCriteriaMappingDto created = ruleAdminService.createMapping(dto);
        return ResponseEntity.status(HttpStatus.CREATED).body(created);
    }

    @PutMapping("/category-criteria-mappings/{categoryId}/{criteriaId}/{level}")
    public ResponseEntity<CategoryCriteriaMappingDto> updateMapping(
            @PathVariable Long categoryId,
            @PathVariable Long criteriaId,
            @PathVariable String level,
            @Valid @RequestBody CategoryCriteriaMappingDto dto) {
        return ResponseEntity.ok(ruleAdminService.updateMapping(categoryId, criteriaId, level, dto));
    }

    @DeleteMapping("/category-criteria-mappings/{categoryId}/{criteriaId}/{level}")
    public ResponseEntity<Void> deleteMapping(
            @PathVariable Long categoryId,
            @PathVariable Long criteriaId,
            @PathVariable String level) {
        boolean deleted = ruleAdminService.deleteMapping(categoryId, criteriaId, level);
        if (!deleted) {
            return ResponseEntity.notFound().build();
        }
        return ResponseEntity.noContent().build();
    }

    @GetMapping("/level-distribution-rules")
    public ResponseEntity<List<LevelDistributionRuleDto>> getAllLevelRules() {
        return ResponseEntity.ok(ruleAdminService.getAllLevelRules());
    }

    @PutMapping("/level-distribution-rules/{level}")
    public ResponseEntity<LevelDistributionRuleDto> updateLevelRule(
            @PathVariable String level,
            @Valid @RequestBody LevelDistributionRuleDto dto) {
        return ResponseEntity.ok(ruleAdminService.updateLevelRule(level, dto));
    }

    @GetMapping("/system-settings")
    public ResponseEntity<List<SystemSettingDto>> getAllSettings() {
        return ResponseEntity.ok(ruleAdminService.getAllSettings());
    }

    @PutMapping("/system-settings/{key}")
    public ResponseEntity<SystemSettingDto> updateSetting(
            @PathVariable String key,
            @Valid @RequestBody SystemSettingDto dto) {
        return ResponseEntity.ok(ruleAdminService.updateSetting(key, dto));
    }
}
