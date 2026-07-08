package fit.iuh.modules.questionbank;

import fit.iuh.modules.assessment.SeniorityLevel;
import org.springframework.stereotype.Component;
import java.util.*;

/**
 * Calculates difficulty distribution (easy/medium/hard count) based on candidate level
 * and overall match score using the largest remainder method for rounding.
 */
@Component
public class DifficultyDistributor {

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

    private Map<String, Integer> calculateCategoryDistribution(int totalQuestions, SeniorityLevel level, Integer overallMatchScore) {
        double f = (overallMatchScore != null ? overallMatchScore : 50) - 50.0;
        f = f / 50.0;
        f = Math.max(-1.0, Math.min(1.0, f));

        double baseBeh, baseTech, baseCod, baseSys;
        double shiftBeh = -10.0 * f;
        double shiftCod, shiftSys;

        if (level == null) level = SeniorityLevel.MID;

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
            case MID:
                baseBeh = 20; baseTech = 40; baseCod = 20; baseSys = 20;
                shiftCod = 5.0 * f; shiftSys = 5.0 * f;
                break;
            case SENIOR:
                baseBeh = 20; baseTech = 30; baseCod = 10; baseSys = 40;
                shiftCod = 5.0 * f; shiftSys = 5.0 * f;
                break;
            case LEAD:
                baseBeh = 20; baseTech = 20; baseCod = 10; baseSys = 50;
                shiftCod = 5.0 * f; shiftSys = 5.0 * f;
                break;
            default:
                baseBeh = 20; baseTech = 40; baseCod = 20; baseSys = 20;
                shiftCod = 5.0 * f; shiftSys = 5.0 * f;
                break;
        }

        double behPct = baseBeh + shiftBeh;
        double techPct = baseTech;
        double codPct = baseCod + shiftCod;
        double sysPct = baseSys + shiftSys;

        return applyLargestRemainderMethod(totalQuestions, behPct, techPct, codPct, sysPct);
    }

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

    /**
     * Determines item-level difficulty.
     * INVARIANT: overallMatchScore MUST NOT be used here to preserve cache consistency.
     */
    private String mapDifficulty(String status) {
        if (status == null) return "medium"; // baseline
        return switch (status.toLowerCase().strip()) {
            case "missing" -> "easy";
            case "weak" -> "medium";
            case "matched" -> "hard";
            default -> "medium";
        };
    }

    private List<QuestionAssignment> assignQuestions(Map<String, Integer> categoryCounts, List<EvidenceItemPair> items) {
        List<QuestionAssignment> assignments = new ArrayList<>();
        
        // Ensure non-null items list
        List<EvidenceItemPair> safeItems = items != null ? new ArrayList<>(items) : new ArrayList<>();
        
        // Remove not_applicable or missing items we don't want to ask about? No, user says "missing -> foundational/easy".
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
