package fit.iuh.modules.assessment.service;

import fit.iuh.modules.admin.repository.SystemSettingRepository;
import fit.iuh.modules.assessment.dto.AssessmentResponse;
import fit.iuh.modules.assessment.dto.AssessmentResponseDto;
import fit.iuh.modules.assessment.entity.SeniorityLevel;
import fit.iuh.modules.rulengine.repository.JobCriteriaRepository.CriteriaWeightProjection;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;

import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.stream.Collectors;

/**
 * High-cohesion service responsible for score calculation, weight breakdowns,
 * and seniority-level adjustments.
 */
@Slf4j
@Service
public class AssessmentScoringEngine {

    private static final double DEFAULT_PARTIAL_COEFF = 0.65;
    private static final double DEFAULT_WEAK_COEFF = 0.30;
    private static final double POINTS_MATCHED = 1.0;
    private static final double POINTS_MISSING = 0.0;

    private final SystemSettingRepository systemSettingRepository;

    public record ScoringResult(
            int overallScore,
            AssessmentResponse.ScoreBreakdown breakdown,
            List<AssessmentResponseDto.EvidenceItem> updatedItems
    ) {}

    @Autowired
    public AssessmentScoringEngine(SystemSettingRepository systemSettingRepository) {
        this.systemSettingRepository = systemSettingRepository;
    }

    public ScoringResult calculateWithBreakdown(
            List<AssessmentResponseDto.EvidenceItem> evidenceItems,
            List<AssessmentResponseDto.AdHocEvidenceItem> adHocItems,
            List<CriteriaWeightProjection> criteriaWeights,
            SeniorityLevel seniorityLevel) {

        double pointsMatched = getSettingDouble("STATUS_MATCHED_COEFF", POINTS_MATCHED);
        double pointsPartial;
        double pointsWeak;
        double pointsMissing = getSettingDouble("STATUS_MISSING_COEFF", POINTS_MISSING);

        if (seniorityLevel == SeniorityLevel.INTERN || seniorityLevel == SeniorityLevel.FRESHER) {
            pointsPartial = getSettingDouble("PARTIAL_COEFF_INTERN_FRESHER", 0.75);
            pointsWeak = getSettingDouble("WEAK_COEFF_INTERN_FRESHER", 0.50);
            log.info("[AssessmentScoringEngine] Intern/Fresher seniority level. pointsPartial={}, pointsWeak={}", pointsPartial, pointsWeak);
        } else if (seniorityLevel == SeniorityLevel.SENIOR || seniorityLevel == SeniorityLevel.LEAD) {
            pointsPartial = getSettingDouble("PARTIAL_COEFF_SENIOR_LEAD", 0.50);
            pointsWeak = getSettingDouble("WEAK_COEFF_SENIOR_LEAD", 0.10);
            log.info("[AssessmentScoringEngine] Senior/Lead seniority level. pointsPartial={}, pointsWeak={}", pointsPartial, pointsWeak);
        } else {
            pointsPartial = getSettingDouble("STATUS_PARTIAL_COEFF", DEFAULT_PARTIAL_COEFF);
            pointsWeak = getSettingDouble("STATUS_WEAK_COEFF", DEFAULT_WEAK_COEFF);
            log.info("[AssessmentScoringEngine] Standard seniority level. pointsPartial={}, pointsWeak={}", pointsPartial, pointsWeak);
        }

        double mustHaveWeightedSum = 0.0;
        double mustHaveWeightSum = 0.0;
        int mustHaveCount = 0;

        double preferToHaveWeightedSum = 0.0;
        double preferToHaveWeightSum = 0.0;
        int preferToHaveCount = 0;

        List<AssessmentResponseDto.EvidenceItem> updatedItems = new ArrayList<>();

        if (evidenceItems != null) {
            Map<Long, Double> weightMap = (criteriaWeights != null && !criteriaWeights.isEmpty())
                    ? criteriaWeights.stream().collect(Collectors.toMap(
                            CriteriaWeightProjection::getCriteriaId,
                            CriteriaWeightProjection::getWeightPercentage,
                            (existing, replacement) -> existing
                    ))
                    : Map.of();

            double avgDbWeight = (!weightMap.isEmpty())
                    ? weightMap.values().stream().mapToDouble(Double::doubleValue).average().orElse(10.0)
                    : 10.0;

            for (AssessmentResponseDto.EvidenceItem item : evidenceItems) {
                Long id = item.criteriaId();
                boolean isNotApp = "not_applicable".equalsIgnoreCase(item.status()) || "NOT_APPLICABLE".equalsIgnoreCase(item.importance());

                double weight;
                if (isNotApp) {
                    weight = 0.0;
                } else if (id != null && weightMap.containsKey(id)) {
                    weight = weightMap.get(id);
                } else {
                    weight = avgDbWeight;
                }

                double points = isNotApp ? 0.0 : statusToPoints(item.status(), pointsMatched, pointsPartial, pointsWeak, pointsMissing);
                double scoreContribution = isNotApp ? 0.0 : weight * points;

                if (isNotApp) {
                    log.debug("[ScoringEngine] NOT_APPLICABLE criteria='{}'", item.criteriaName());
                } else if ("PREFERRED".equalsIgnoreCase(item.importance())) {
                    preferToHaveWeightedSum += scoreContribution;
                    preferToHaveWeightSum += weight;
                    preferToHaveCount++;
                } else {
                    mustHaveWeightedSum += scoreContribution;
                    mustHaveWeightSum += weight;
                    mustHaveCount++;
                }

                AssessmentResponseDto.EvidenceItem updated = new AssessmentResponseDto.EvidenceItem(
                        item.criteriaId(),
                        item.criteriaName(),
                        item.importance(),
                        item.jdRequirement(),
                        item.cvEvidence(),
                        item.cvQuote(),
                        item.status(),
                        item.reasoning(),
                        weight,
                        scoreContribution,
                        item.groundingScore(),
                        item.confidenceVotes(),
                        item.lowConfidence(),
                        item.needsManualReview(),
                        item.matchMetadata()
                );
                updatedItems.add(updated);
            }
        }

        if (adHocItems != null && !adHocItems.isEmpty()) {
            double fixedAvgPreferWeight = (preferToHaveWeightSum > 0 && preferToHaveCount > 0)
                    ? (preferToHaveWeightSum / preferToHaveCount) : 10.0;
            double fixedAvgMustHaveWeight = (mustHaveWeightSum > 0 && mustHaveCount > 0)
                    ? (mustHaveWeightSum / mustHaveCount) : 10.0;

            for (AssessmentResponseDto.AdHocEvidenceItem adHoc : adHocItems) {
                if ("not_applicable".equalsIgnoreCase(adHoc.status()) || "NOT_APPLICABLE".equalsIgnoreCase(adHoc.importance())) {
                    continue;
                }

                double points = statusToPoints(adHoc.status(), pointsMatched, pointsPartial, pointsWeak, pointsMissing);

                if ("PREFERRED".equalsIgnoreCase(adHoc.importance())) {
                    double contribution = fixedAvgPreferWeight * points;
                    preferToHaveWeightedSum += contribution;
                    preferToHaveWeightSum += fixedAvgPreferWeight;
                    preferToHaveCount++;
                } else {
                    double contribution = fixedAvgMustHaveWeight * points;
                    mustHaveWeightedSum += contribution;
                    mustHaveWeightSum += fixedAvgMustHaveWeight;
                    mustHaveCount++;
                }
            }
        }

        double mustHaveWeightRatio = getSettingDouble("MUST_HAVE_WEIGHT_RATIO", 0.8);
        double preferToHaveWeightRatio = getSettingDouble("PREFER_TO_HAVE_WEIGHT_RATIO", 0.2);

        double rawPreferToHaveScore = preferToHaveWeightSum > 0.0 ? (preferToHaveWeightedSum / preferToHaveWeightSum) * 100.0 : 0.0;
        double rawMustHaveScore = mustHaveWeightSum > 0.0 
                ? (mustHaveWeightedSum / mustHaveWeightSum) * 100.0 
                : (preferToHaveWeightSum > 0.0 ? rawPreferToHaveScore : 0.0);
        if (preferToHaveWeightSum == 0.0) {
            rawPreferToHaveScore = rawMustHaveScore;
        }

        double finalScoreDouble = (rawMustHaveScore * mustHaveWeightRatio) + (rawPreferToHaveScore * preferToHaveWeightRatio);
        int finalScore = (int) Math.round(finalScoreDouble);

        log.info("[ScoringEngine] Overall match score: {} (MustHave={}, PreferToHave={})",
                finalScore, Math.round(rawMustHaveScore), Math.round(rawPreferToHaveScore));

        AssessmentResponse.ScoreBreakdown breakdown = new AssessmentResponse.ScoreBreakdown(
                (int) Math.round(rawMustHaveScore),
                mustHaveWeightRatio,
                (int) Math.round(rawPreferToHaveScore),
                preferToHaveWeightRatio,
                finalScore
        );

        return new ScoringResult(finalScore, breakdown, updatedItems);
    }

    private double statusToPoints(String status, double pointsMatched, double pointsPartial, double pointsWeak, double pointsMissing) {
        fit.iuh.modules.assessment.entity.EvaluationStatus evalStatus = fit.iuh.modules.assessment.entity.EvaluationStatus.fromCode(status);
        return switch (evalStatus) {
            case MATCHED -> pointsMatched;
            case PARTIAL -> pointsPartial;
            case WEAK -> pointsWeak;
            case MISSING -> pointsMissing;
            case NOT_APPLICABLE -> 0.0;
        };
    }

    private double getSettingDouble(String key, double defaultValue) {
        return systemSettingRepository != null ? systemSettingRepository.getDouble(key, defaultValue) : defaultValue;
    }
}
