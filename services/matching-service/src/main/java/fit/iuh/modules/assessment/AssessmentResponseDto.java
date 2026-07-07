package fit.iuh.modules.assessment;

import com.fasterxml.jackson.annotation.JsonProperty;

import java.util.List;

/**
 * DTO mapping the new LLM assessment output schema.
 *
 * <p>The LLM is now an <strong>Evidence-Matching Engine</strong> only — it does NOT
 * compute scores. It returns a flat list of {@link EvidenceItem} objects, one per
 * evaluation criterion. The {@link ScoringService} then computes the
 * {@code overall_match_score} from these items and their DB weights.
 *
 * <h3>LLM Output Contract</h3>
 * <pre>{@code
 * {
 *   "evidence_items": [
 *     {
 *       "criteria_id": 1,
 *       "criteria_name": "Tech Stack Alignment",
 *       "jd_requirement": "Yêu cầu Java 17+, Spring Boot 3.x",
 *       "cv_evidence": "Sử dụng Java 21 và Spring Boot 3.3 trong dự án SmileInterview",
 *       "status": "matched"
 *     }
 *   ],
 *   "top_priority_improvements": ["Cần thêm kinh nghiệm với Kubernetes"]
 * }
 * }</pre>
 */
public record AssessmentResponseDto(

        @JsonProperty("evidence_items")
        List<EvidenceItem> evidenceItems,

        @JsonProperty("top_priority_improvements")
        List<String> topPriorityImprovements

) {

    /**
     * A single piece of evidence for one evaluation criterion.
     *
     * <p>{@code criteriaId} links back to the {@code evaluation_criteria} table row,
     * enabling {@link ScoringService} to look up the corresponding weight.
     */
    public record EvidenceItem(

            /** Foreign key to {@code evaluation_criteria.id} — used by ScoringService for weight lookup. */
            @JsonProperty("criteria_id")
            Long criteriaId,

            /** Human-readable criterion name (e.g., "Tech Stack Alignment"). */
            @JsonProperty("criteria_name")
            String criteriaName,

            /** The specific JD requirement being evaluated (in Vietnamese per prompt rules). */
            @JsonProperty("jd_requirement")
            String jdRequirement,

            /**
             * Concrete evidence extracted from the CV, or {@code null} if the requirement
             * is missing from the CV entirely.
             */
            @JsonProperty("cv_evidence")
            String cvEvidence,

            /**
             * Matching result:
             * <ul>
             *   <li>{@code "matched"} — strong, direct, or semantically equivalent evidence found</li>
             *   <li>{@code "weak"} — partial evidence (skills-list only, or below expected depth)</li>
             *   <li>{@code "missing"} — requirement completely absent from CV</li>
             * </ul>
             */
            @JsonProperty("status")
            String status

    ) {}
}
