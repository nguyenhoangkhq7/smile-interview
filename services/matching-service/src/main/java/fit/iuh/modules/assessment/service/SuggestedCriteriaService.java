package fit.iuh.modules.assessment.service;

import fit.iuh.modules.assessment.dto.AssessmentResponseDto;
import fit.iuh.modules.assessment.entity.JobCategory;

import java.util.List;

public interface SuggestedCriteriaService {
    void recordAdHocCriteria(JobCategory jobCategory, List<AssessmentResponseDto.AdHocEvidenceItem> adHocItems);
}
