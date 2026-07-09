package fit.iuh.modules.questionbank;

import fit.iuh.modules.admin.LevelDistributionRule;
import fit.iuh.modules.admin.LevelDistributionRuleRepository;
import fit.iuh.modules.admin.SystemSettingRepository;
import fit.iuh.modules.assessment.SeniorityLevel;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Component;

import java.util.*;

/**
 * Calculates difficulty distribution (easy/medium/hard count) based on candidate level
 * and overall match score using the largest remainder method for rounding.
 *
 * <h2>Dynamic Configuration</h2>
 * This component previously contained hardcoded constants:
 * <ul>
 *   <li>{@code 50.0} — pivot score (now read from {@code system_settings.MATCH_SCORE_PIVOT})</li>
 *   <li>Switch-case level distributions — now read from {@code level_distribution_rules}</li>
 * </ul>
 * If either source returns {@code null} or is empty, sensible fallbacks are used to
 * ensure the service never crashes due to a missing configuration row.
 */
@Slf4j
@Component
@RequiredArgsConstructor
public class DifficultyDistributor {

    // ─── Fallback constants (used when DB is not yet seeded) ────────────────
    private static final double DEFAULT_PIVOT = 50.0;

    private final SystemSettingRepository          systemSettingRepository;
    private final LevelDistributionRuleRepository  levelDistributionRuleRepository;

    /**
     * Calculates the difficulty and category distribution for a given total number of questions,
     * assigning specific evidence items to each generated question.
     *
     * @param totalQuestions     total number of questions to generate
     * @param level              candidate seniority level
     * @param overallMatchScore  overall match score (0-100)
     * @param items              list of evidence items
     * @return list of question assignments
     */
    public List<QuestionAssignment> distribute(int totalQuestions, SeniorityLevel level, Integer overallMatchScore, List<EvidenceItemPair> items) {
        if (totalQuestions <= 0) {
            return Collections.emptyList();
        }

        // 1. Calculate category distribution
        Map<String, Integer> categoryCounts = calculateCategoryDistribution(totalQuestions, level, overallMatchScore);

        // 2. Select items and assign difficulty
        return assignQuestions(categoryCounts, items);
    }

    // ─────────────────────────────────────────────────────────────────────────
    // Category distribution calculation — reads from DB with fallbacks
    // ─────────────────────────────────────────────────────────────────────────

    private Map<String, Integer> calculateCategoryDistribution(int totalQuestions, SeniorityLevel level, Integer overallMatchScore) {
        // Read pivot from system_settings (fallback: 50.0)
        double pivot = systemSettingRepository.getDouble("MATCH_SCORE_PIVOT", DEFAULT_PIVOT);

        double f = (overallMatchScore != null ? overallMatchScore : pivot) - pivot;
        f = f / pivot;
        f = Math.max(-1.0, Math.min(1.0, f));

        if (level == null) level = SeniorityLevel.MID;

        // Read base distributions from level_distribution_rules (fallback: hardcoded defaults)
        LevelDistributionRule rule = levelDistributionRuleRepository
                .findByLevel(level.name())
                .orElse(null);

        double baseBeh, baseTech, baseCod, baseSys;
        double shiftCod, shiftSys;
        double shiftBeh = -10.0 * f;

        if (rule != null) {
            baseBeh = rule.getBehavioralPct();
            baseTech = rule.getTechnicalPct();
            baseCod  = rule.getCodingPct();
            baseSys  = rule.getSystemDesignPct();

            // Adaptive shifts: if system design is non-zero apply split shift, otherwise all to coding
            if (baseSys > 0) {
                shiftCod = 5.0 * f;
                shiftSys = 5.0 * f;
            } else {
                shiftCod = 10.0 * f;
                shiftSys = 0;
            }

            log.debug("[DifficultyDistributor] Loaded rule from DB for level={}: beh={}, tech={}, cod={}, sys={}",
                    level, baseBeh, baseTech, baseCod, baseSys);
        } else {
            // Fallback: embedded defaults matching original hardcoded behaviour
            log.warn("[DifficultyDistributor] No DB rule found for level={}, using hardcoded fallback.", level);
            switch (level) {
                case INTERN:
                case FRESHER:
                    baseBeh = 40; baseTech = 50; baseCod = 10; baseSys = 0;
                    shiftCod = 10.0 * f; shiftSys = 0;
                    break;
                case JUNIOR:
                    baseBeh = 30; baseTech = 50; baseCod = 20; baseSys = 0;
                    shiftCod = 10.0 * f; shiftSys = 0;
                    break;
                case SENIOR:
                    baseBeh = 20; baseTech = 30; baseCod = 10; baseSys = 40;
                    shiftCod = 5.0 * f; shiftSys = 5.0 * f;
                    break;
                case LEAD:
                    baseBeh = 20; baseTech = 20; baseCod = 10; baseSys = 50;
                    shiftCod = 5.0 * f; shiftSys = 5.0 * f;
                    break;
                default: // MID
                    baseBeh = 20; baseTech = 40; baseCod = 20; baseSys = 20;
                    shiftCod = 5.0 * f; shiftSys = 5.0 * f;
                    break;
            }
        }

        double behPct  = baseBeh + shiftBeh;
        double techPct = baseTech;
        double codPct  = baseCod + shiftCod;
        double sysPct  = baseSys + shiftSys;

        return applyLargestRemainderMethod(totalQuestions, behPct, techPct, codPct, sysPct);
    }

    // ─────────────────────────────────────────────────────────────────────────
    // Largest Remainder Method — unchanged from original implementation
    // ─────────────────────────────────────────────────────────────────────────

    private Map<String, Integer> applyLargestRemainderMethod(int totalCount, double... pcts) {
        String[] types = {"behavioural", "technical", "coding", "system_design"};
        int[] counts = new int[4];
        double[] fractions = new double[4];
        int sum = 0;

        for (int i = 0; i < 4; i++) {
            double raw = totalCount * (pcts[i] / 100.0);
            counts[i] = (int) Math.floor(raw);
            fractions[i] = raw - counts[i];
            sum += counts[i];
        }

        int remainder = totalCount - sum;
        if (remainder > 0) {
            List<FractionBucket> buckets = new ArrayList<>();
            for (int i = 0; i < 4; i++) {
                buckets.add(new FractionBucket(i, fractions[i]));
            }
            buckets.sort((a, b) -> Double.compare(b.fraction, a.fraction));

            for (int i = 0; i < remainder; i++) {
                counts[buckets.get(i).index]++;
            }
        }

        Map<String, Integer> result = new LinkedHashMap<>();
        for (int i = 0; i < 4; i++) {
            if (counts[i] > 0) {
                result.put(types[i], counts[i]);
            }
        }
        return result;
    }

    private static class FractionBucket {
        int index;
        double fraction;
        FractionBucket(int index, double fraction) {
            this.index = index;
            this.fraction = fraction;
        }
    }

    // ─────────────────────────────────────────────────────────────────────────
    // Item-level difficulty mapping — unchanged from original
    // ─────────────────────────────────────────────────────────────────────────

    /**
     * Determines item-level difficulty.
     * INVARIANT: overallMatchScore MUST NOT be used here to preserve cache consistency.
     */
    private String mapDifficulty(String status) {
        if (status == null) return "medium"; // baseline
        return switch (status.toLowerCase().strip()) {
            case "missing" -> "easy";
            case "weak"    -> "medium";
            case "matched" -> "hard";
            default        -> "medium";
        };
    }

    private List<QuestionAssignment> assignQuestions(Map<String, Integer> categoryCounts, List<EvidenceItemPair> items) {
        List<QuestionAssignment> assignments = new ArrayList<>();

        // Ensure non-null items list
        List<EvidenceItemPair> safeItems = items != null ? new ArrayList<>(items) : new ArrayList<>();

        // Sort items: weightUsed DESC, then missing status
        safeItems.sort((a, b) -> {
            double wA = a.weightUsed() != null ? a.weightUsed() : 0.0;
            double wB = b.weightUsed() != null ? b.weightUsed() : 0.0;
            if (Double.compare(wB, wA) != 0) return Double.compare(wB, wA);

            boolean aMissing = "missing".equalsIgnoreCase(a.status());
            boolean bMissing = "missing".equalsIgnoreCase(b.status());
            if (aMissing && !bMissing) return -1;
            if (!aMissing && bMissing) return 1;
            return 0;
        });

        // Ensure at least 1 matched item is at the top if it exists
        EvidenceItemPair topMatched = null;
        for (int i = 0; i < safeItems.size(); i++) {
            if ("matched".equalsIgnoreCase(safeItems.get(i).status())) {
                topMatched = safeItems.remove(i);
                break;
            }
        }
        if (topMatched != null) {
            safeItems.add(0, topMatched);
        }

        int itemIndex = 0;
        int pass = 0;

        for (Map.Entry<String, Integer> entry : categoryCounts.entrySet()) {
            String category = entry.getKey();
            int count = entry.getValue();

            for (int i = 0; i < count; i++) {
                EvidenceItemPair assignedItem = null;
                boolean isFollowUp = pass > 0;

                if (!safeItems.isEmpty()) {
                    assignedItem = safeItems.get(itemIndex);
                    itemIndex++;
                    if (itemIndex >= safeItems.size()) {
                        itemIndex = 0;
                        pass++;
                    }
                }

                String difficulty = assignedItem != null ? mapDifficulty(assignedItem.status()) : "medium";
                assignments.add(new QuestionAssignment(assignedItem, category, difficulty, isFollowUp));
            }
        }

        return assignments;
    }
}
