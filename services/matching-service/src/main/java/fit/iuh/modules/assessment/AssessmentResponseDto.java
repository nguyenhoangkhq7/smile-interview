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
 *   ]
 * }
 * }</pre>
 */
public record AssessmentResponseDto(

        @JsonProperty("evidence_items")
        List<EvidenceItem> evidenceItems,

        @JsonProperty("additional_evidence_items")
        List<AdHocEvidenceItem> additionalEvidenceItems

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
            String status,

            /** MỚI — LLM giải thích lý do kết luận status này. */
            @JsonProperty("reasoning")
            String reasoning,

            /** MỚI — weight từ DB, đính kèm để UI hiển thị. (Populated by Java) */
            @JsonProperty("weight_used")
            Double weightUsed,

            /** MỚI — weight * points, đóng góp vào điểm tổng. (Populated by Java) */
            @JsonProperty("score_contribution")
            Double scoreContribution,

            /** MỚI — Trích đoạn gần-nguyên-văn từ CV Markdown làm căn cứ chứng minh. */
            @JsonProperty("source_span")
            String sourceSpan,

            /** MỚI — Điểm khớp grounding giữa source_span và CV gốc (0.0 - 1.0). */
            @JsonProperty("grounding_score")
            Double groundingScore,

            /** MỚI — Phân bổ số phiếu bầu cho các trạng thái trong Self-Consistency. */
            @JsonProperty("confidence_votes")
            java.util.Map<String, Integer> confidenceVotes,

            /** MỚI — Cờ đánh dấu phân loại có độ tin cậy thấp (khi hòa phiếu). */
            @JsonProperty("low_confidence")
            Boolean lowConfidence,

            /** MỚI — Cờ đánh dấu cần kiểm tra thủ công (khi batch LLM bị lỗi). */
            @JsonProperty("needs_manual_review")
            Boolean needsManualReview

    ) {}

    public record AdHocEvidenceItem(
            @JsonProperty("criteria_name")
            String criteriaName,

            @JsonProperty("jd_requirement")
            String jdRequirement,

            @JsonProperty("cv_evidence")
            String cvEvidence,

            @JsonProperty("status")
            String status,

            @JsonProperty("reasoning")
            String reasoning
    ) {}
}
