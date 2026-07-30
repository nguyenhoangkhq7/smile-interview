package fit.iuh.modules.hrevaluation.service;

import fit.iuh.modules.hrevaluation.dto.HrEvaluationRequestDto;
import fit.iuh.modules.hrevaluation.dto.HrEvaluationResponseDto;

/**
 * Service contract for managing HR evaluations of AI-generated question banks.
 */
public interface HrEvaluationService {

    /**
     * Validates and persists an HR evaluation for a given interview session.
     *
     * @param dto the evaluation payload from the HR portal frontend
     * @return a response containing the saved record's {@code id} and confirmation message
     */
    HrEvaluationResponseDto saveEvaluation(HrEvaluationRequestDto dto);

    /**
     * Retrieves all evaluations submitted by all HRs (Admin only).
     *
     * @return list of all evaluation response DTOs
     */
    java.util.List<HrEvaluationResponseDto> getAllEvaluations();
}
