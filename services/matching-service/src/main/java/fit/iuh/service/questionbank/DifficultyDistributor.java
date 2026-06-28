package fit.iuh.service.questionbank;

import org.springframework.stereotype.Component;
import java.util.*;

/**
 * Calculates difficulty distribution (easy/medium/hard count) based on candidate level
 * and overall match score using the largest remainder method for rounding.
 */
@Component
public class DifficultyDistributor {

    private static final Map<String, int[]> DISTRIBUTION_TABLE = Map.of(
        "junior_low",     new int[]{60, 35, 5},
        "junior_medium",  new int[]{50, 40, 10},
        "junior_high",    new int[]{40, 45, 15},
        "mid_low",        new int[]{35, 45, 20},
        "mid_medium",     new int[]{25, 50, 25},
        "mid_high",       new int[]{15, 45, 40},
        "senior_low",     new int[]{20, 45, 35},
        "senior_medium",  new int[]{10, 40, 50},
        "senior_high",    new int[]{5, 30, 65},
        "lead_high",      new int[]{5, 30, 65}
    );

    /**
     * Calculates the difficulty distribution for a given total number of questions.
     *
     * @param candidateLevel senior | mid | junior | lead
     * @param overallMatch low | medium | high
     * @param totalCount total number of questions required for a type
     * @return map mapping easy/medium/hard to their respective count
     */
    public Map<String, Integer> distribute(String candidateLevel, String overallMatch, int totalCount) {
        if (totalCount <= 0) {
            return Map.of("easy", 0, "medium", 0, "hard", 0);
        }
        if (totalCount == 1) {
            return Map.of("easy", 0, "medium", 1, "hard", 0);
        }

        String level = candidateLevel != null ? candidateLevel.toLowerCase().strip() : "mid";
        String match = overallMatch != null ? overallMatch.toLowerCase().strip() : "medium";
        
        // Lead falls back to senior-level ranges except for high match
        if ("lead".equals(level)) {
            if ("low".equals(match) || "medium".equals(match)) {
                level = "senior";
            }
        }

        String key = level + "_" + match;
        int[] pcts = DISTRIBUTION_TABLE.getOrDefault(key, DISTRIBUTION_TABLE.get("mid_medium"));

        // Special handling for count = 2
        if (totalCount == 2) {
            if ("junior".equals(level) && "low".equals(match)) {
                return Map.of("easy", 1, "medium", 1, "hard", 0);
            }
            if (("senior".equals(level) || "lead".equals(level)) && "high".equals(match)) {
                return Map.of("easy", 0, "medium", 1, "hard", 1);
            }
            return Map.of("easy", 0, "medium", 2, "hard", 0);
        }

        // Largest Remainder Method
        double easyRaw = totalCount * (pcts[0] / 100.0);
        double mediumRaw = totalCount * (pcts[1] / 100.0);
        double hardRaw = totalCount * (pcts[2] / 100.0);

        int easy = (int) Math.floor(easyRaw);
        int medium = (int) Math.floor(mediumRaw);
        int hard = (int) Math.floor(hardRaw);

        int sum = easy + medium + hard;
        int remainder = totalCount - sum;

        if (remainder > 0) {
            double easyFraction = easyRaw - easy;
            double mediumFraction = mediumRaw - medium;
            double hardFraction = hardRaw - hard;

            List<FractionBucket> buckets = new ArrayList<>(List.of(
                new FractionBucket("easy", easyFraction),
                new FractionBucket("medium", mediumFraction),
                new FractionBucket("hard", hardFraction)
            ));
            buckets.sort((a, b) -> Double.compare(b.fraction, a.fraction));

            for (int i = 0; i < remainder; i++) {
                String type = buckets.get(i).type;
                if ("easy".equals(type)) easy++;
                else if ("medium".equals(type)) medium++;
                else if ("hard".equals(type)) hard++;
            }
        }

        Map<String, Integer> result = new LinkedHashMap<>();
        result.put("easy", easy);
        result.put("medium", medium);
        result.put("hard", hard);
        return result;
    }

    private static class FractionBucket {
        String type;
        double fraction;
        FractionBucket(String type, double fraction) {
            this.type = type;
            this.fraction = fraction;
        }
    }
}
