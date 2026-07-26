package fit.iuh.modules.assessment.service;

import fit.iuh.modules.assessment.dto.ClassifiedCriteriaBundle;
import fit.iuh.modules.rulengine.repository.JobCriteriaRepository.CriteriaWeightProjection;

import java.util.List;

public interface JdCriteriaClassifierService {

    /**
     * Classifies database criteria against the JD and extracts any extra JD criteria
     * not covered by the DB list.
     *
     * @param jdMarkdown     full Job Description text
     * @param dbCriteria     criteria loaded from the rule-engine database
     * @param seniorityLevel candidate seniority level (INTERN, FRESHER, JUNIOR, MID, SENIOR, LEAD)
     *                       used to apply lenient classification rules for junior candidates
     */
    ClassifiedCriteriaBundle classify(String jdMarkdown, List<CriteriaWeightProjection> dbCriteria, String seniorityLevel);

    /** Backward-compatible overload — defaults seniorityLevel to null (no leniency adjustments). */
    default ClassifiedCriteriaBundle classify(String jdMarkdown, List<CriteriaWeightProjection> dbCriteria) {
        return classify(jdMarkdown, dbCriteria, null);
    }
}
