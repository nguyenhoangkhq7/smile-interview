package fit.iuh.modules.assessment.service;

import fit.iuh.modules.assessment.entity.JobCategory;
import fit.iuh.modules.assessment.entity.SeniorityLevel;

public interface MetadataExtractionService {

    record ExtractionResult(
            JobCategory category,
            SeniorityLevel level
    ) {}

    ExtractionResult extract(String jdMarkdown);
}
