package fit.iuh.modules.assessment.service;

import fit.iuh.modules.admin.repository.SystemSettingRepository;
import fit.iuh.modules.assessment.dto.AssessmentResponse;
import fit.iuh.modules.assessment.dto.AssessmentResponseDto;
import fit.iuh.modules.assessment.entity.SeniorityLevel;
import fit.iuh.modules.ontology.dto.GraphMatchResult;
import fit.iuh.modules.ontology.service.SkillKnowledgeGraphService;
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
 * seniority-level adjustments, and Ontology graph matching score boosts.
 */
@Slf4j
@Service
public class AssessmentScoringEngine {

    private static final double DEFAULT_WEAK_COEFF = 0.3;
    private static final double POINTS_MATCHED = 1.0;
    private static final double POINTS_MISSING = 0.0;

    private final SystemSettingRepository systemSettingRepository;
    private final SkillKnowledgeGraphService skillKnowledgeGraphService;

    public record ScoringResult(
            int overallScore,
            AssessmentResponse.ScoreBreakdown breakdown,
            List<AssessmentResponseDto.EvidenceItem> updatedItems
    ) {}

    @Autowired
    public AssessmentScoringEngine(
            SystemSettingRepository systemSettingRepository,
            @Autowired(required = false) SkillKnowledgeGraphService skillKnowledgeGraphService) {
        this.systemSettingRepository = systemSettingRepository;
        this.skillKnowledgeGraphService = skillKnowledgeGraphService;
    }

    public ScoringResult calculateWithBreakdown(
            List<AssessmentResponseDto.EvidenceItem> evidenceItems,
            List<AssessmentResponseDto.AdHocEvidenceItem> adHocItems,
            List<CriteriaWeightProjection> criteriaWeights,
            SeniorityLevel seniorityLevel) {

        double pointsWeak;
        if (seniorityLevel == SeniorityLevel.INTERN || seniorityLevel == SeniorityLevel.FRESHER) {
            pointsWeak = getSettingDouble("WEAK_COEFF_INTERN_FRESHER", 0.5);
            log.info("[AssessmentScoringEngine] Intern/Fresher seniority level. pointsWeak={}", pointsWeak);
        } else if (seniorityLevel == SeniorityLevel.SENIOR || seniorityLevel == SeniorityLevel.LEAD) {
            pointsWeak = getSettingDouble("WEAK_COEFF_SENIOR_LEAD", 0.1);
            log.info("[AssessmentScoringEngine] Senior/Lead seniority level. pointsWeak={}", pointsWeak);
        } else {
            pointsWeak = getSettingDouble("STATUS_WEAK_COEFF", DEFAULT_WEAK_COEFF);
            log.info("[AssessmentScoringEngine] Standard seniority level. pointsWeak={}", pointsWeak);
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

            double avgDbWeight = weightMap.values().stream()
                    .mapToDouble(Double::doubleValue)
                    .average()
                    .orElse(10.0);

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

                double points = isNotApp ? 0.0 : statusToPoints(item.status(), pointsWeak);

                // Ontology Graph Matching Enhancement
                GraphMatchResult graphResult = null;
                if (!isNotApp && skillKnowledgeGraphService != null) {
                    graphResult = skillKnowledgeGraphService.matchSkills(item.criteriaName(), item.cvEvidence());
                    if (graphResult != null && graphResult.similarityScore() > points) {
                        log.info("[OntologyBoost] criteria='{}' score boosted from {} to {} via graph: {}",
                                item.criteriaName(), String.format("%.2f", points),
                                String.format("%.2f", graphResult.similarityScore()), graphResult.relationPath());
                        points = graphResult.similarityScore();
                    }
                }

                double scoreContribution = isNotApp ? 0.0 : weight * points;
                String finalReasoning = item.reasoning();
                if (graphResult != null && graphResult.similarityScore() > 0.0 && graphResult.relationPath() != null) {
                    finalReasoning = (finalReasoning != null ? finalReasoning + " | " : "") + "[Ontology: " + graphResult.relationPath() + "]";
                }

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
                        item.status(),
                        finalReasoning,
                        weight,
                        scoreContribution,
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
                } else {
                    double avgWeight = (mustHaveWeightSum > 0 && mustHaveCount > 0)
                            ? (mustHaveWeightSum / mustHaveCount) : 10.0;
                    double contribution = avgWeight * points;
                    mustHaveWeightedSum += contribution;
                    mustHaveWeightSum += avgWeight;
                    mustHaveCount++;
                }
            }
        }

        double mustHaveWeightRatio = getSettingDouble("MUST_HAVE_WEIGHT_RATIO", 0.8);
        double preferToHaveWeightRatio = getSettingDouble("PREFER_TO_HAVE_WEIGHT_RATIO", 0.2);

        double rawMustHaveScore = mustHaveWeightSum > 0.0 ? (mustHaveWeightedSum / mustHaveWeightSum) * 100.0 : 0.0;
        double rawPreferToHaveScore = preferToHaveWeightSum > 0.0 ? (preferToHaveWeightedSum / preferToHaveWeightSum) * 100.0 : rawMustHaveScore;

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

    private double statusToPoints(String status, double pointsWeak) {
        if (status == null) return POINTS_MISSING;
        return switch (status.toLowerCase()) {
            case "matched" -> POINTS_MATCHED;
            case "weak" -> pointsWeak;
            case "missing" -> POINTS_MISSING;
            case "not_applicable" -> 0.0;
            default -> POINTS_MISSING;
        };
    }

    private double getSettingDouble(String key, double defaultValue) {
        return systemSettingRepository != null ? systemSettingRepository.getDouble(key, defaultValue) : defaultValue;
    }
}
