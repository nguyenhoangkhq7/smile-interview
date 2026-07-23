package fit.iuh.modules.assessment.service.impl;

import fit.iuh.modules.admin.repository.SystemSettingRepository;
import fit.iuh.modules.assessment.dto.AssessmentResponse;
import fit.iuh.modules.assessment.dto.AssessmentResponseDto;
import fit.iuh.modules.assessment.entity.SeniorityLevel;
import fit.iuh.modules.assessment.service.ScoringService;
import fit.iuh.modules.rulengine.repository.JobCriteriaRepository.CriteriaWeightProjection;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;

import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.stream.Collectors;

@Slf4j
@Service
@RequiredArgsConstructor
public class ScoringServiceImpl implements ScoringService {

    private static final double DEFAULT_WEAK_COEFF = 0.3;
    private static final double POINTS_MATCHED = 1.0;
    private static final double POINTS_MISSING = 0.0;

    private final SystemSettingRepository systemSettingRepository;

    @Override
    public ScoringResult calculateWithBreakdown(
            List<AssessmentResponseDto.EvidenceItem> evidenceItems,
            List<AssessmentResponseDto.AdHocEvidenceItem> adHocItems,
            List<CriteriaWeightProjection> criteriaWeights,
            SeniorityLevel seniorityLevel) {

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

        double mustHaveWeightedSum = 0.0;
        double mustHaveWeightSum = 0.0;
        int mustHaveCount = 0;

        double preferToHaveWeightedSum = 0.0;
        double preferToHaveWeightSum = 0.0;
        int preferToHaveCount = 0;

        List<AssessmentResponseDto.EvidenceItem> updatedItems = new ArrayList<>();

        if (evidenceItems != null && criteriaWeights != null && !criteriaWeights.isEmpty()) {
            Map<Long, Double> weightMap = criteriaWeights.stream()
                    .collect(Collectors.toMap(
                            CriteriaWeightProjection::getCriteriaId,
                            CriteriaWeightProjection::getWeightPercentage,
                            (existing, replacement) -> existing
                    ));

            for (AssessmentResponseDto.EvidenceItem item : evidenceItems) {
                Long id = item.criteriaId();
                if (id == null || !weightMap.containsKey(id)) {
                    log.warn("[Scoring] Evidence item references unknown criteria_id={}. Skipping.", id);
                    updatedItems.add(item);
                    continue;
                }

                boolean isNotApp = "not_applicable".equalsIgnoreCase(item.status()) || "NOT_APPLICABLE".equalsIgnoreCase(item.importance());

                double weight = isNotApp ? 0.0 : weightMap.get(id);
                double points = isNotApp ? 0.0 : statusToPoints(item.status(), pointsWeak);
                double scoreContribution = isNotApp ? 0.0 : weight * points;

                if (isNotApp) {
                    log.debug("[Scoring] JD-Driven logic: criteria='{}' is NOT_APPLICABLE. Weight and contribution set to 0.0.", item.criteriaName());
                } else if ("PREFERRED".equalsIgnoreCase(item.importance())) {
                    preferToHaveWeightedSum += scoreContribution;
                    preferToHaveWeightSum += weight;
                    preferToHaveCount++;
                    log.debug("[Scoring PREFERRED] criteria='{}' weight={} status='{}' points={} contribution={}",
                            item.criteriaName(), weight, item.status(), points, scoreContribution);
                } else {
                    mustHaveWeightedSum += scoreContribution;
                    mustHaveWeightSum += weight;
                    mustHaveCount++;
                    log.debug("[Scoring REQUIRED] criteria='{}' weight={} status='{}' points={} contribution={}",
                            item.criteriaName(), weight, item.status(), points, scoreContribution);
                }

                AssessmentResponseDto.EvidenceItem updated = new AssessmentResponseDto.EvidenceItem(
                        item.criteriaId(),
                        item.criteriaName(),
                        item.importance(),
                        item.jdRequirement(),
                        item.cvEvidence(),
                        item.status(),
                        item.reasoning(),
                        weight,
                        scoreContribution,
                        item.sourceSpan(),
                        item.groundingScore(),
                        item.confidenceVotes(),
                        item.lowConfidence(),
                        item.needsManualReview()
                );
                updatedItems.add(updated);
            }
        }

        if (adHocItems != null && !adHocItems.isEmpty()) {
            for (AssessmentResponseDto.AdHocEvidenceItem adHoc : adHocItems) {
                if ("not_applicable".equalsIgnoreCase(adHoc.status()) || "NOT_APPLICABLE".equalsIgnoreCase(adHoc.importance())) {
                    continue;
                }

                double points = statusToPoints(adHoc.status(), pointsWeak);

                if ("PREFERRED".equalsIgnoreCase(adHoc.importance())) {
                    double avgWeight = (preferToHaveWeightSum > 0 && preferToHaveCount > 0)
                            ? (preferToHaveWeightSum / preferToHaveCount) : 10.0;
                    double contribution = avgWeight * points;
                    preferToHaveWeightedSum += contribution;
                    preferToHaveWeightSum += avgWeight;
                    preferToHaveCount++;
                    log.debug("[Scoring AdHoc PREFERRED] criteria='{}' weight={} status='{}' points={}",
                            adHoc.criteriaName(), avgWeight, adHoc.status(), points);
                } else {
                    double avgWeight = (mustHaveWeightSum > 0 && mustHaveCount > 0)
                            ? (mustHaveWeightSum / mustHaveCount) : 10.0;
                    double contribution = avgWeight * points;
                    mustHaveWeightedSum += contribution;
                    mustHaveWeightSum += avgWeight;
                    mustHaveCount++;
                    log.debug("[Scoring AdHoc REQUIRED] criteria='{}' weight={} status='{}' points={}",
                            adHoc.criteriaName(), avgWeight, adHoc.status(), points);
                }
            }
        }

        double mustHaveWeightRatio = systemSettingRepository.getDouble("MUST_HAVE_WEIGHT_RATIO", 0.8);
        double preferToHaveWeightRatio = systemSettingRepository.getDouble("PREFER_TO_HAVE_WEIGHT_RATIO", 0.2);

        double rawMustHaveScore = mustHaveWeightSum > 0.0 ? (mustHaveWeightedSum / mustHaveWeightSum) * 100.0 : 0.0;
        double rawPreferToHaveScore = preferToHaveWeightSum > 0.0 ? (preferToHaveWeightedSum / preferToHaveWeightSum) * 100.0 : rawMustHaveScore;

        double finalScoreDouble = (rawMustHaveScore * mustHaveWeightRatio) + (rawPreferToHaveScore * preferToHaveWeightRatio);
        int finalScore = (int) Math.round(finalScoreDouble);

        log.info("[Scoring] Calculation complete: rawMustHave={}/100 (weight={}), rawPreferToHave={}/100 (weight={}) -> overall_match_score={}",
                Math.round(rawMustHaveScore), mustHaveWeightRatio, Math.round(rawPreferToHaveScore), preferToHaveWeightRatio, finalScore);

        AssessmentResponse.ScoreBreakdown breakdown = new AssessmentResponse.ScoreBreakdown(
                (int) Math.round(rawMustHaveScore),
                mustHaveWeightRatio,
                (int) Math.round(rawPreferToHaveScore),
                preferToHaveWeightRatio,
                finalScore
        );

        return new ScoringResult(finalScore, breakdown, updatedItems);
    }

    private double statusToPoints(String status, double pointsWeak) {
        if (status == null) return POINTS_MISSING;
        return switch (status.toLowerCase()) {
            case "matched" -> POINTS_MATCHED;
            case "weak" -> pointsWeak;
            case "missing" -> POINTS_MISSING;
            case "not_applicable" -> 0.0;
            default -> {
                log.warn("[Scoring] Unknown status '{}' — treating as missing.", status);
                yield POINTS_MISSING;
            }
        };
    }
}
