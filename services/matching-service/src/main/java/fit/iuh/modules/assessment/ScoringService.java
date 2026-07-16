package fit.iuh.modules.assessment;

import fit.iuh.modules.admin.SystemSettingRepository;
import fit.iuh.modules.rulengine.JobCriteriaRepository.CriteriaWeightProjection;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;

import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.stream.Collectors;

/**
 * Pure Java service that calculates the {@code overall_match_score} (0–100)
 * from a list of evidence items and their corresponding criterion weights.
 *
 * <h2>Algorithm</h2>
 * <pre>
 *   For each evidence item:
 *     - "matched"  → points = 1.0              (full weight awarded)
 *     - "weak"     → points = STATUS_WEAK_COEFF (from system_settings, default 0.3)
 *     - "missing"  → points = 0.0              (no weight awarded)
 *
 *   overall_match_score = round(
 *       SUM(weight_i * points_i) / SUM(weight_i) * 100
 *   )
 * </pre>
 *
 * <p>Weights are normalised by dividing by their total sum, so the individual
 * weights in {@code category_criteria_mapping} do NOT need to sum to 100.
 *
 * <h2>Dynamic Configuration</h2>
 * {@code STATUS_WEAK_COEFF} is now read from the {@code system_settings} table
 * via {@link SystemSettingRepository}. If the key is absent, the service falls
 * back to {@code 0.3} (the original hardcoded value) to preserve existing behaviour.
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
@RequiredArgsConstructor
public class ScoringService {

    /** Fallback coefficient used when system_settings is not yet seeded. */
    private static final double DEFAULT_WEAK_COEFF = 0.3;

    /** Points awarded for a fully matched criterion — always 1.0. */
    private static final double POINTS_MATCHED = 1.0;

    /** Points awarded for a fully missing criterion — always 0.0. */
    private static final double POINTS_MISSING = 0.0;

    private final SystemSettingRepository systemSettingRepository;

    public record ScoringResult(
            int score,
            AssessmentResponse.ScoreBreakdown breakdown,
            List<AssessmentResponseDto.EvidenceItem> evidenceItems
    ) {}

    /**
     * Calculates the overall match score from evidence items and DB weights.
     *
     * @param evidenceItems   the list of evidence items returned by the LLM
     * @param adHocItems      the list of ad-hoc evidence items returned by the LLM (prefer-to-have)
     * @param criteriaWeights the criteria+weights fetched from the DB
     * @param seniorityLevel  the expected seniority level of the JD
     * @return a {@link ScoringResult} containing the integer score and breakdown
     */
    public ScoringResult calculateWithBreakdown(
            List<AssessmentResponseDto.EvidenceItem> evidenceItems,
            List<AssessmentResponseDto.AdHocEvidenceItem> adHocItems,
            List<CriteriaWeightProjection> criteriaWeights,
            SeniorityLevel seniorityLevel) {

        // Determine seniority-based pointsWeak dynamically from DB settings
        double pointsWeak;
        if (seniorityLevel == SeniorityLevel.INTERN || seniorityLevel == SeniorityLevel.FRESHER) {
            pointsWeak = systemSettingRepository.getDouble("WEAK_COEFF_INTERN_FRESHER", 0.5);
            log.info("[Scoring] Intern/Fresher seniority level detected. pointsWeak={}", pointsWeak);
        } else if (seniorityLevel == SeniorityLevel.SENIOR || seniorityLevel == SeniorityLevel.LEAD) {
            pointsWeak = systemSettingRepository.getDouble("WEAK_COEFF_SENIOR_LEAD", 0.1);
            log.info("[Scoring] Senior/Lead seniority level detected. pointsWeak={}", pointsWeak);
        } else {
            pointsWeak = systemSettingRepository.getDouble("STATUS_WEAK_COEFF", DEFAULT_WEAK_COEFF);
            log.info("[Scoring] Standard seniority level detected. pointsWeak={}", pointsWeak);
        }

        double totalWeightUsed = 0.0;
        double weightedPointsSum = 0.0;
        List<AssessmentResponseDto.EvidenceItem> updatedItems = new ArrayList<>();

        if (evidenceItems != null && criteriaWeights != null && !criteriaWeights.isEmpty()) {
            // Build a lookup map: criteriaId → weightPercentage
            Map<Long, Double> weightMap = criteriaWeights.stream()
                    .collect(Collectors.toMap(
                            CriteriaWeightProjection::getCriteriaId,
                            CriteriaWeightProjection::getWeightPercentage,
                            // If a criteriaId appears multiple times, keep the higher weight
                            (existing, replacement) -> Math.max(existing, replacement)
                    ));

            for (AssessmentResponseDto.EvidenceItem item : evidenceItems) {
                if (item.criteriaId() == null) {
                    log.debug("[Scoring] Skipping evidence item with null criteriaId: {}", item.criteriaName());
                    updatedItems.add(item);
                    continue;
                }

                Double weight = weightMap.get(item.criteriaId());
                if (weight == null) {
                    log.debug("[Scoring] No weight found for criteriaId={} ('{}') — skipping.",
                            item.criteriaId(), item.criteriaName());
                    updatedItems.add(item);
                    continue;
                }

                double points = statusToPoints(item.status(), pointsWeak);
                double scoreContribution = weight * points;

                if ("not_applicable".equalsIgnoreCase(item.status())) {
                    log.debug("[Scoring] JD-Driven logic: criteria='{}' is not_applicable. Excluding weight.", item.criteriaName());
                } else {
                    weightedPointsSum += scoreContribution;
                    totalWeightUsed += weight;
                }

                log.debug("[Scoring] criteria='{}' weight={} status='{}' points={} contribution={}",
                        item.criteriaName(), weight, item.status(), points, scoreContribution);

                AssessmentResponseDto.EvidenceItem updated = new AssessmentResponseDto.EvidenceItem(
                        item.criteriaId(),
                        item.criteriaName(),
                        item.jdRequirement(),
                        item.cvEvidence(),
                        item.status(),
                        item.reasoning(),
                        weight,
                        scoreContribution
                );
                updatedItems.add(updated);
            }
        }

        // 2. Calculate ad-hoc (prefer-to-have) criteria score contribution
        double adHocPointsSum = 0.0;
        int adHocCount = 0;
        if (adHocItems != null && !adHocItems.isEmpty()) {
            for (AssessmentResponseDto.AdHocEvidenceItem item : adHocItems) {
                if ("not_applicable".equalsIgnoreCase(item.status())) {
                    continue;
                }
                double points = statusToPoints(item.status(), pointsWeak);
                adHocPointsSum += points;
                adHocCount++;
            }
        }

        // 3. Overall match score synthesis using configurable must-have & prefer-to-have weight ratios
        double mustHaveRatioSetting = systemSettingRepository.getDouble("MUST_HAVE_WEIGHT_RATIO", 0.8);
        double preferToHaveRatioSetting = systemSettingRepository.getDouble("PREFER_TO_HAVE_WEIGHT_RATIO", 0.2);

        int score = 0;
        double normMustHave = 0.0;
        double normPreferToHave = 0.0;
        double mustHaveScorePercentage = 0.0;
        double preferToHaveScorePercentage = 0.0;

        boolean hasMustHave = totalWeightUsed > 0.0;
        boolean hasPreferToHave = adHocCount > 0;

        if (hasMustHave && hasPreferToHave) {
            double totalRatio = mustHaveRatioSetting + preferToHaveRatioSetting;
            if (totalRatio > 0.0) {
                normMustHave = mustHaveRatioSetting / totalRatio;
                normPreferToHave = preferToHaveRatioSetting / totalRatio;
            } else {
                normMustHave = 0.8;
                normPreferToHave = 0.2;
            }

            mustHaveScorePercentage = (weightedPointsSum / totalWeightUsed) * 100.0;
            preferToHaveScorePercentage = (adHocPointsSum / adHocCount) * 100.0;

            score = (int) Math.round((normMustHave * mustHaveScorePercentage) + (normPreferToHave * preferToHaveScorePercentage));
        } else if (hasMustHave) {
            mustHaveScorePercentage = (weightedPointsSum / totalWeightUsed) * 100.0;
            score = (int) Math.round(mustHaveScorePercentage);
        } else if (hasPreferToHave) {
            preferToHaveScorePercentage = (adHocPointsSum / adHocCount) * 100.0;
            score = (int) Math.round(preferToHaveScorePercentage);
        }

        score = Math.max(0, Math.min(100, score));

        // Construct dynamic ScoreBreakdown formula and points configuration
        Map<String, Double> pointsConfig = Map.of(
                "matched", POINTS_MATCHED,
                "weak", pointsWeak,
                "missing", POINTS_MISSING,
                "must_have_ratio", hasMustHave && hasPreferToHave ? normMustHave : (hasMustHave ? 1.0 : 0.0),
                "prefer_to_have_ratio", hasMustHave && hasPreferToHave ? normPreferToHave : (hasPreferToHave ? 1.0 : 0.0)
        );

        String formula = hasMustHave && hasPreferToHave
                ? String.format("Formula: %.2f * (MustHaveScore) + %.2f * (PreferToHaveScore)", normMustHave, normPreferToHave)
                : (hasMustHave ? "MustHaveScore" : "PreferToHaveScore");

        AssessmentResponse.ScoreBreakdown breakdown = new AssessmentResponse.ScoreBreakdown(
                weightedPointsSum,
                totalWeightUsed,
                formula,
                pointsConfig
        );

        log.info("[Scoring] overall_match_score={} (Must-Have: {}% (normWeight={}); Prefer-To-Have: {}% (normWeight={}))",
                score, mustHaveScorePercentage, hasMustHave && hasPreferToHave ? normMustHave : (hasMustHave ? 1.0 : 0.0),
                preferToHaveScorePercentage, hasMustHave && hasPreferToHave ? normPreferToHave : (hasPreferToHave ? 1.0 : 0.0));

        return new ScoringResult(score, breakdown, updatedItems);
    }

    public int calculate(
            List<AssessmentResponseDto.EvidenceItem> evidenceItems,
            List<AssessmentResponseDto.AdHocEvidenceItem> adHocItems,
            List<CriteriaWeightProjection> criteriaWeights,
            SeniorityLevel seniorityLevel) {
        return calculateWithBreakdown(evidenceItems, adHocItems, criteriaWeights, seniorityLevel).score();
    }

    // ─────────────────────────────────────────────────────────────────────────
    // Private helper
    // ─────────────────────────────────────────────────────────────────────────

    /**
     * Maps an evidence {@code status} string to a numeric point value.
     *
     * @param status    the status string ("matched", "weak", "missing", etc.)
     * @param weakCoeff the dynamically loaded coefficient for "weak" status
     * @return numeric point value (0.0 – 1.0)
     */
    private double statusToPoints(String status, double weakCoeff) {
        if (status == null) return POINTS_MISSING;
        return switch (status.toLowerCase().strip()) {
            case "matched" -> POINTS_MATCHED;
            case "weak"    -> weakCoeff;
            default        -> POINTS_MISSING; // "missing" or unknown
        };
    }
}
