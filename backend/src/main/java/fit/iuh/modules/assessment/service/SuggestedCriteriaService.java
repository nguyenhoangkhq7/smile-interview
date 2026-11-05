package fit.iuh.modules.assessment.service;

import fit.iuh.modules.assessment.dto.SuggestedCriteriaDto;

import java.util.List;
import java.util.Map;

public interface SuggestedCriteriaService {

    List<SuggestedCriteriaDto> getSuggestedCriteria();

    Map<String, Object> promoteCriteria(Long id, String categoryCode, String level, Double weightPercentage, String questionType, String category);

    void deleteSuggestedCriteria(Long id);
}
