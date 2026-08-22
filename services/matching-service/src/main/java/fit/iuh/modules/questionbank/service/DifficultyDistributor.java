package fit.iuh.modules.questionbank.service;

import fit.iuh.modules.admin.entity.LevelDistributionRule;
import fit.iuh.modules.admin.entity.SystemSetting;
import fit.iuh.modules.admin.repository.LevelDistributionRuleRepository;
import fit.iuh.modules.admin.repository.SystemSettingRepository;
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
    private final SystemSettingRepository settingRepository;

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
                } else if ("missing".equalsIgnoreCase(item.status()) || "weak".equalsIgnoreCase(item.status()) || "partial".equalsIgnoreCase(item.status())) {
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

            double matchedRatio = 0.6;
            try {
                Optional<SystemSetting> setting = settingRepository.findBySettingKey("MATCHED_QUESTIONS_RATIO");
                if (setting.isPresent()) {
                    matchedRatio = Double.parseDouble(setting.get().getSettingValue());
                }
            } catch (Exception e) {
                log.warn("Invalid MATCHED_QUESTIONS_RATIO setting, falling back to 0.6");
            }
            
            int matchedCount = (int) Math.round(countForCategory * matchedRatio);
            int gapCount = countForCategory - matchedCount;

            for (int i = 0; i < matchedCount; i++) {
                EvidenceItemPair item = pickItemForQuestion(categoryItems, categoryMatched, categoryGap, i);
                String difficulty = determineDifficulty(item, level, overallMatchScore, false);
                String promptStrategy = determinePromptStrategy(category, true);
                result.add(new QuestionAssignment(category, difficulty, item, false, promptStrategy));
            }

            for (int i = 0; i < gapCount; i++) {
                EvidenceItemPair item = pickItemForQuestion(categoryItems, categoryGap, categoryMatched, i);
                String difficulty = determineDifficulty(item, level, overallMatchScore, true);
                String promptStrategy = determinePromptStrategy(category, false);
                result.add(new QuestionAssignment(category, difficulty, item, true, promptStrategy));
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

    private String determinePromptStrategy(String category, boolean isMatched) {
        if (category == null) return "";
        String type = category.toLowerCase();
        
        String settingKey = "";
        String defaultStrategy = "";
        
        switch (type) {
            case "technical":
                settingKey = isMatched ? "PROMPT_TECH_MATCHED" : "PROMPT_TECH_MISSING";
                defaultStrategy = isMatched 
                    ? "Đào sâu (Drill-down): Hỏi về cơ chế hoạt động ngầm, edge-cases, và best practices."
                    : "Đánh giá Khái niệm (Conceptual): Hỏi định nghĩa ở mức High-level và yêu cầu so sánh.";
                break;
            case "coding":
                settingKey = isMatched ? "PROMPT_CODE_MATCHED" : "PROMPT_CODE_MISSING";
                defaultStrategy = isMatched 
                    ? "Tối ưu hóa (Optimization): Đưa ra bài toán yêu cầu viết code tối ưu về Time/Space Complexity, chú trọng Clean Code và bắt lỗi (Exception Handling)."
                    : "Mã giả (Pseudo-code): Yêu cầu mô tả thuật toán bằng mã giả hoặc bằng ngôn ngữ thế mạnh để giải quyết bài toán tương tự.";
                break;
            case "system_design":
                settingKey = isMatched ? "PROMPT_SYS_MATCHED" : "PROMPT_SYS_MISSING";
                defaultStrategy = isMatched 
                    ? "Thiết kế & Đánh đổi (Trade-offs): Yêu cầu bóc tách kiến trúc phức tạp, cách xử lý phân tán, mTLS hoặc bảo mật Zero Trust."
                    : "Nhận diện Vấn đề (Bottleneck Identification): Đưa ra một luồng hệ thống có sẵn và yêu cầu chỉ ra điểm nghẽn (Single point of failure) dựa trên tư duy logic thông thường.";
                break;
            case "behavioural", "behavioral":
                settingKey = isMatched ? "PROMPT_BEHAV_MATCHED" : "PROMPT_BEHAV_MISSING";
                defaultStrategy = isMatched 
                    ? "Kiểm chứng Thực tế (STAR Method): Yêu cầu kể lại một dự án khó nhất đã làm, cách xử lý xung đột trong team, hoặc vai trò trong việc ra quyết định kỹ thuật."
                    : "Khả năng Tự học (Learnability): Đưa ra kịch bản giả định: 'Dự án tuần sau yêu cầu dùng công nghệ này ngay lập tức, bạn sẽ lên kế hoạch tiếp cận và triển khai nó như thế nào trong 3 ngày?'";
                break;
            default:
                return "";
        }
        
        Optional<SystemSetting> setting = settingRepository.findBySettingKey(settingKey);
        if (setting.isPresent() && setting.get().getSettingValue() != null && !setting.get().getSettingValue().isBlank()) {
            return setting.get().getSettingValue();
        }
        
        return defaultStrategy;
    }
}
