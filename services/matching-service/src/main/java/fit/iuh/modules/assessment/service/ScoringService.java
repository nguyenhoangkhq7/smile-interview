package fit.iuh.modules.assessment.service;

import fit.iuh.modules.assessment.dto.AssessmentResponse;
import fit.iuh.modules.assessment.dto.AssessmentResponseDto;
import fit.iuh.modules.assessment.entity.SeniorityLevel;
import fit.iuh.modules.rulengine.repository.JobCriteriaRepository.CriteriaWeightProjection;

import java.util.List;

public interface ScoringService {

    record ScoringResult(
            int score,
            AssessmentResponse.ScoreBreakdown breakdown,
            List<AssessmentResponseDto.EvidenceItem> evidenceItems
    ) {}

    ScoringResult calculateWithBreakdown(
            List<AssessmentResponseDto.EvidenceItem> evidenceItems,
            List<AssessmentResponseDto.AdHocEvidenceItem> adHocItems,
            List<CriteriaWeightProjection> criteriaWeights,
            SeniorityLevel seniorityLevel);
}
