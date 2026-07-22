package fit.iuh.modules.admin.service;

import fit.iuh.modules.admin.dto.*;
import java.util.List;

public interface RuleAdminService {

    List<JobCategoryDto> getAllCategories();
    JobCategoryDto createCategory(JobCategoryDto dto);
    JobCategoryDto updateCategory(Long id, JobCategoryDto dto);
    boolean deleteCategory(Long id);

    List<EvaluationCriteriaDto> getAllCriteria();
    EvaluationCriteriaDto createCriteria(EvaluationCriteriaDto dto);
    EvaluationCriteriaDto updateCriteria(Long id, EvaluationCriteriaDto dto);
    boolean deleteCriteria(Long id);

    List<CategoryCriteriaMappingDto> getAllMappings();
    CategoryCriteriaMappingDto createMapping(CategoryCriteriaMappingDto dto);
    CategoryCriteriaMappingDto updateMapping(Long categoryId, Long criteriaId, String level, CategoryCriteriaMappingDto dto);
    boolean deleteMapping(Long categoryId, Long criteriaId, String level);

    List<LevelDistributionRuleDto> getAllLevelRules();
    LevelDistributionRuleDto updateLevelRule(String level, LevelDistributionRuleDto dto);

    List<SystemSettingDto> getAllSettings();
    SystemSettingDto updateSetting(String key, SystemSettingDto dto);
}
