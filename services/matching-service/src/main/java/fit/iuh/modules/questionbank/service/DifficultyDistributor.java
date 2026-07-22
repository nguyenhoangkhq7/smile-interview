package fit.iuh.modules.questionbank.service;

import fit.iuh.modules.admin.entity.LevelDistributionRule;
import fit.iuh.modules.admin.repository.LevelDistributionRuleRepository;
import fit.iuh.modules.assessment.entity.SeniorityLevel;
import fit.iuh.modules.questionbank.dto.EvidenceItemPair;
import fit.iuh.modules.questionbank.dto.QuestionAssignment;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Component;

import java.util.*;

@Slf4j
@Component
@RequiredArgsConstructor
public class DifficultyDistributor {

    private final LevelDistributionRuleRepository levelRuleRepository;

    public List<QuestionAssignment> distribute(
            int totalCount,
            SeniorityLevel level,
            Integer overallMatchScore,
            List<EvidenceItemPair> evidenceItems) {

        if (totalCount <= 0) return Collections.emptyList();

        Map<String, Double> categoryRatios = getCategoryRatiosForLevel(level);
        Map<String, Integer> categoryCounts = allocateCounts(categoryRatios, totalCount);

        List<EvidenceItemPair> matchedItems = new ArrayList<>();
        List<EvidenceItemPair> gapItems = new ArrayList<>();

        if (evidenceItems != null) {
            for (EvidenceItemPair item : evidenceItems) {
                if ("matched".equalsIgnoreCase(item.status())) {
                    matchedItems.add(item);
                } else if ("missing".equalsIgnoreCase(item.status()) || "weak".equalsIgnoreCase(item.status())) {
                    gapItems.add(item);
                }
            }
        }

        List<QuestionAssignment> result = new ArrayList<>(totalCount);

        for (Map.Entry<String, Integer> entry : categoryCounts.entrySet()) {
            String category = entry.getKey();
            int countForCategory = entry.getValue();
            if (countForCategory <= 0) continue;

            List<EvidenceItemPair> categoryItems = filterItemsForCategory(category, evidenceItems);
            List<EvidenceItemPair> categoryMatched = filterItemsForCategory(category, matchedItems);
            List<EvidenceItemPair> categoryGap = filterItemsForCategory(category, gapItems);

            int mainCount = (int) Math.ceil(countForCategory * 0.7);
            int followUpCount = countForCategory - mainCount;

            for (int i = 0; i < mainCount; i++) {
                EvidenceItemPair item = pickItemForQuestion(categoryItems, categoryGap, categoryMatched, i);
                String difficulty = determineDifficulty(item, level, overallMatchScore, false);
                result.add(new QuestionAssignment(category, difficulty, item, false));
            }

            for (int i = 0; i < followUpCount; i++) {
                EvidenceItemPair item = pickItemForQuestion(categoryItems, categoryMatched, categoryGap, i);
                String difficulty = determineDifficulty(item, level, overallMatchScore, true);
                result.add(new QuestionAssignment(category, difficulty, item, true));
            }
        }

        return result;
    }

    private Map<String, Double> getCategoryRatiosForLevel(SeniorityLevel level) {
        String levelStr = level != null ? level.name() : "MID";
        Optional<LevelDistributionRule> ruleOpt = levelRuleRepository.findByLevel(levelStr);

        if (ruleOpt.isPresent()) {
            LevelDistributionRule rule = ruleOpt.get();
            Map<String, Double> map = new LinkedHashMap<>();
            map.put("behavioural", rule.getBehavioralPct());
            map.put("technical", rule.getTechnicalPct());
            map.put("coding", rule.getCodingPct());
            map.put("system_design", rule.getSystemDesignPct());
            return map;
        }

        return switch (levelStr) {
            case "INTERN" -> Map.of("behavioural", 30.0, "technical", 50.0, "coding", 20.0, "system_design", 0.0);
            case "FRESHER" -> Map.of("behavioural", 25.0, "technical", 50.0, "coding", 25.0, "system_design", 0.0);
            case "JUNIOR" -> Map.of("behavioural", 20.0, "technical", 45.0, "coding", 25.0, "system_design", 10.0);
            case "SENIOR" -> Map.of("behavioural", 15.0, "technical", 30.0, "coding", 20.0, "system_design", 35.0);
            case "LEAD" -> Map.of("behavioural", 25.0, "technical", 25.0, "coding", 10.0, "system_design", 40.0);
            default -> Map.of("behavioural", 15.0, "technical", 40.0, "coding", 25.0, "system_design", 20.0);
        };
    }

    private Map<String, Integer> allocateCounts(Map<String, Double> ratios, int totalCount) {
        double sumRatios = ratios.values().stream().mapToDouble(Double::doubleValue).sum();
        if (sumRatios <= 0) sumRatios = 1.0;

        Map<String, Integer> counts = new LinkedHashMap<>();
        Map<String, Double> remainders = new LinkedHashMap<>();
        int allocated = 0;

        for (Map.Entry<String, Double> entry : ratios.entrySet()) {
            double normalizedWeight = entry.getValue() / sumRatios;
            double exactCount = normalizedWeight * totalCount;
            int floorCount = (int) Math.floor(exactCount);

            counts.put(entry.getKey(), floorCount);
            remainders.put(entry.getKey(), exactCount - floorCount);
            allocated += floorCount;
        }

        int unallocated = totalCount - allocated;
        if (unallocated > 0) {
            List<Map.Entry<String, Double>> sortedRemainders = new ArrayList<>(remainders.entrySet());
            sortedRemainders.sort(Map.Entry.<String, Double>comparingByValue().reversed());

            for (int i = 0; i < unallocated; i++) {
                String cat = sortedRemainders.get(i % sortedRemainders.size()).getKey();
                counts.put(cat, counts.get(cat) + 1);
            }
        }

        return counts;
    }

    private List<EvidenceItemPair> filterItemsForCategory(String category, List<EvidenceItemPair> items) {
        if (items == null || items.isEmpty()) return Collections.emptyList();
        List<EvidenceItemPair> filtered = new ArrayList<>();
        for (EvidenceItemPair item : items) {
            if (categoryMatches(category, item.questionType())) {
                filtered.add(item);
            }
        }
        return filtered;
    }

    private boolean categoryMatches(String category, String questionType) {
        if (questionType == null) return "technical".equalsIgnoreCase(category);
        return switch (category.toLowerCase()) {
            case "behavioural", "behavioral" -> "behavioural".equalsIgnoreCase(questionType) || "behavioral".equalsIgnoreCase(questionType);
            case "technical" -> "technical".equalsIgnoreCase(questionType);
            case "coding" -> "coding".equalsIgnoreCase(questionType);
            case "system_design" -> "system_design".equalsIgnoreCase(questionType);
            default -> false;
        };
    }

    private EvidenceItemPair pickItemForQuestion(
            List<EvidenceItemPair> allCategoryItems,
            List<EvidenceItemPair> primaryList,
            List<EvidenceItemPair> fallbackList,
            int index) {

        if (primaryList != null && !primaryList.isEmpty()) {
            return primaryList.get(index % primaryList.size());
        }
        if (fallbackList != null && !fallbackList.isEmpty()) {
            return fallbackList.get(index % fallbackList.size());
        }
        if (allCategoryItems != null && !allCategoryItems.isEmpty()) {
            return allCategoryItems.get(index % allCategoryItems.size());
        }
        return null;
    }

    private String determineDifficulty(
            EvidenceItemPair item,
            SeniorityLevel level,
            Integer overallMatchScore,
            boolean isFollowUp) {

        int baseScore = levelScore(level);

        if (item != null && item.status() != null) {
            switch (item.status().toLowerCase()) {
                case "matched" -> baseScore += 1;
                case "missing" -> baseScore -= 1;
                case "weak" -> { }
            }
        }

        if (overallMatchScore != null) {
            if (overallMatchScore >= 80) baseScore += 1;
            else if (overallMatchScore < 50) baseScore -= 1;
        }

        if (isFollowUp) {
            baseScore += 1;
        }

        if (baseScore <= 1) return "easy";
        if (baseScore == 2) return "medium";
        return "hard";
    }

    private int levelScore(SeniorityLevel level) {
        if (level == null) return 2;
        return switch (level) {
            case INTERN, FRESHER -> 1;
            case JUNIOR, MID -> 2;
            case SENIOR, LEAD -> 3;
        };
    }
}
