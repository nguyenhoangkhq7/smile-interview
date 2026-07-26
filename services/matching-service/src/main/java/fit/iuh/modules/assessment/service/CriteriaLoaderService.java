package fit.iuh.modules.assessment.service;

import fit.iuh.modules.rulengine.repository.JobCriteriaRepository.CriteriaWeightProjection;
import java.util.List;

public interface CriteriaLoaderService {
    List<CriteriaWeightProjection> loadAndFilterCriteria(
            String categoryName,
            String seniorityLevelName,
            String sessionId,
            String fullJdMarkdown,
            boolean shouldIncludeNotApp
    );

    fit.iuh.modules.assessment.dto.ClassifiedCriteriaBundle loadAndClassifyCriteria(
            String categoryName,
            String seniorityLevelName,
            String fullJdMarkdown
    );
}

