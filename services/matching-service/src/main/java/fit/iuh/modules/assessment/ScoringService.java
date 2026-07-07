package fit.iuh.modules.assessment;

import fit.iuh.modules.rulengine.JobCriteriaRepository.CriteriaWeightProjection;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;

import java.util.List;
import java.util.Map;
import java.util.function.Function;
import java.util.stream.Collectors;

/**
 * Pure Java service that calculates the {@code overall_match_score} (0–100)
 * from a list of evidence items and their corresponding criterion weights.
 *
 * <h2>Algorithm</h2>
 * <pre>
 *   For each evidence item:
 *     - "matched"  → points = 1.0  (full weight awarded)
 *     - "weak"     → points = 0.5  (half weight awarded)
 *     - "missing"  → points = 0.0  (no weight awarded)
 *
 *   overall_match_score = round(
 *       SUM(weight_i * points_i) / SUM(weight_i) * 100
 *   )
 * </pre>
 *
 * <p>Weights are normalised by dividing by their total sum, so the individual
 * weights in {@code category_criteria_mapping} do NOT need to sum to 100.
 *
 * <h2>Design Philosophy</h2>
 * <ul>
 *   <li>No LLM is involved. This is a deterministic mathematical operation.</li>
 *   <li>Evidence items that reference unknown criteria IDs are ignored with a warning.</li>
 *   <li>If no evidence items are present (empty LLM response), the score is 0.</li>
 * </ul>
 */
@Slf4j
@Service
public class ScoringService {

    /** Points awarded per evidence status. */
    private static final double POINTS_MATCHED = 1.0;
    private static final double POINTS_WEAK    = 0.3;
    private static final double POINTS_MISSING = 0.0;

    /**
     * Calculates the overall match score from evidence items and DB weights.
     *
     * @param evidenceItems  the list of evidence items returned by the LLM (from the assessment prompt)
     * @param criteriaWeights the criteria+weights fetched from the DB by {@code JobCriteriaRepository}
     * @return integer score in range [0, 100]
     */
    public int calculate(
            List<AssessmentResponseDto.EvidenceItem> evidenceItems,
            List<CriteriaWeightProjection> criteriaWeights) {

        if (evidenceItems == null || evidenceItems.isEmpty()) {
            log.warn("[Scoring] No evidence items provided — returning score 0.");
            return 0;
        }
        if (criteriaWeights == null || criteriaWeights.isEmpty()) {
            log.warn("[Scoring] No criteria weights found in DB — returning score 0.");
            return 0;
        }

        // Build a lookup map: criteriaId → weightPercentage
        Map<Long, Double> weightMap = criteriaWeights.stream()
                .collect(Collectors.toMap(
                        CriteriaWeightProjection::getCriteriaId,
                        CriteriaWeightProjection::getWeightPercentage,
                        // If a criteriaId appears multiple times, keep the higher weight
                        (existing, replacement) -> Math.max(existing, replacement)
                ));

        double totalWeightUsed = 0.0;
        double weightedPointsSum = 0.0;

        for (AssessmentResponseDto.EvidenceItem item : evidenceItems) {
            if (item.criteriaId() == null) {
                log.debug("[Scoring] Skipping evidence item with null criteriaId: {}", item.criteriaName());
                continue;
            }

            Double weight = weightMap.get(item.criteriaId());
            if (weight == null) {
                log.debug("[Scoring] No weight found for criteriaId={} ('{}') — skipping.",
                        item.criteriaId(), item.criteriaName());
                continue;
            }

            double points = statusToPoints(item.status());
            weightedPointsSum += weight * points;
            totalWeightUsed += weight;

            log.debug("[Scoring] criteria='{}' weight={} status='{}' points={} contribution={}",
                    item.criteriaName(), weight, item.status(), points, weight * points);
        }

        if (totalWeightUsed == 0.0) {
            log.warn("[Scoring] Total weight used is 0 — no matching criteria found. Returning score 0.");
            return 0;
        }

        int score = (int) Math.round((weightedPointsSum / totalWeightUsed) * 100.0);
        // Clamp to [0, 100] as a safety guard against floating-point edge cases
        score = Math.max(0, Math.min(100, score));

        log.info("[Scoring] overall_match_score={} (weighted_sum={:.2f} / total_weight={:.2f})",
                score, weightedPointsSum, totalWeightUsed);

        return score;
    }

    // -------------------------------------------------------------------------
    // Private helper
    // -------------------------------------------------------------------------

    /**
     * Maps an evidence {@code status} string to a numeric point value.
     * Defaults to 0.0 for any unrecognised or null status.
     */
    private double statusToPoints(String status) {
        if (status == null) return POINTS_MISSING;
        return switch (status.toLowerCase().strip()) {
            case "matched" -> POINTS_MATCHED;
            case "weak"    -> POINTS_WEAK;
            default        -> POINTS_MISSING; // "missing" or unknown
        };
    }
}
