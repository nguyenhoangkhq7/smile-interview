package fit.iuh.modules.assessment.service;

import fit.iuh.modules.assessment.dto.AssessmentResponseDto;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Component;

import java.util.*;

@Slf4j
@Component
public class EvidenceGroundingValidator {

    public AssessmentResponseDto.EvidenceItem validateAndApply(
            AssessmentResponseDto.EvidenceItem item,
            String cvMarkdown,
            double groundingThreshold) {

        if (item == null) return null;

        String sourceSpan = item.sourceSpan();
        if (sourceSpan == null || sourceSpan.isBlank() || cvMarkdown == null || cvMarkdown.isBlank()) {
            Double score = item.groundingScore() != null ? item.groundingScore() : 1.0;
            return new AssessmentResponseDto.EvidenceItem(
                    item.criteriaId(),
                    item.criteriaName(),
                    item.importance(),
                    item.jdRequirement(),
                    item.cvEvidence(),
                    item.status(),
                    item.reasoning(),
                    item.weightUsed(),
                    item.scoreContribution(),
                    item.sourceSpan(),
                    score,
                    item.confidenceVotes(),
                    item.lowConfidence(),
                    item.needsManualReview()
            );
        }

        double sim = calculateFuzzySimilarity(sourceSpan, cvMarkdown);

        if (sim < groundingThreshold) {
            String originalStatus = item.status();
            String downgradedStatus = downgradeStatus(originalStatus);

            log.warn("[GroundingCheck] criteria_id={} | status={} -> {} | score={} < threshold={}",
                    item.criteriaId(), originalStatus, downgradedStatus, sim, groundingThreshold);

            return new AssessmentResponseDto.EvidenceItem(
                    item.criteriaId(),
                    item.criteriaName(),
                    item.importance(),
                    item.jdRequirement(),
                    item.cvEvidence(),
                    downgradedStatus,
                    item.reasoning() + " [Cảnh báo: Trích dẫn chứng cứ từ CV có độ tin cậy thấp (" + String.format("%.2f", sim) + ").]",
                    item.weightUsed(),
                    item.scoreContribution(),
                    item.sourceSpan(),
                    sim,
                    item.confidenceVotes(),
                    item.lowConfidence(),
                    true
            );
        }

        return new AssessmentResponseDto.EvidenceItem(
                item.criteriaId(),
                item.criteriaName(),
                item.importance(),
                item.jdRequirement(),
                item.cvEvidence(),
                item.status(),
                item.reasoning(),
                item.weightUsed(),
                item.scoreContribution(),
                item.sourceSpan(),
                sim,
                item.confidenceVotes(),
                item.lowConfidence(),
                item.needsManualReview()
        );
    }

    public double calculateFuzzySimilarity(String needle, String haystack) {
        if (needle == null || haystack == null || needle.isBlank() || haystack.isBlank()) {
            return 0.0;
        }

        String normNeedle = normalizeText(needle);
        String normHaystack = normalizeText(haystack);

        if (normHaystack.contains(normNeedle)) {
            return 1.0;
        }

        double tokenJaccard = calculateTokenJaccardOverlap(normNeedle, normHaystack);
        double slidingLev = calculateSlidingLevenshtein(normNeedle, normHaystack);

        return Math.max(tokenJaccard, slidingLev);
    }

    private String normalizeText(String text) {
        return text.toLowerCase(Locale.ROOT)
                .replaceAll("[^a-z0-9àáảãạâầấẩẫậăằắẳẵặèéẻẽẹêềếểễệìíỉĩịòóỏõọôồốổỗộơờớởỡợùúủũụưừứửữựỳýỷỹỵđ\\s]", " ")
                .replaceAll("\\s+", " ")
                .trim();
    }

    private double calculateTokenJaccardOverlap(String needle, String haystack) {
        Set<String> needleTokens = new HashSet<>(Arrays.asList(needle.split(" ")));
        Set<String> haystackTokens = new HashSet<>(Arrays.asList(haystack.split(" ")));

        needleTokens.removeIf(String::isBlank);
        haystackTokens.removeIf(String::isBlank);

        if (needleTokens.isEmpty()) return 0.0;

        int intersection = 0;
        for (String token : needleTokens) {
            if (haystackTokens.contains(token)) {
                intersection++;
            }
        }
        return (double) intersection / needleTokens.size();
    }

    private double calculateSlidingLevenshtein(String needle, String haystack) {
        int nLen = needle.length();
        int hLen = haystack.length();
        if (nLen == 0 || hLen == 0) return 0.0;

        int windowSize = Math.min(hLen, Math.max(nLen + 10, (int) (nLen * 1.3)));
        int step = Math.max(1, nLen / 4);

        double maxSim = 0.0;
        for (int i = 0; i <= hLen - Math.min(windowSize, nLen); i += step) {
            int end = Math.min(hLen, i + windowSize);
            String window = haystack.substring(i, end);

            int dist = computeLevenshteinDistance(needle, window);
            int maxLen = Math.max(needle.length(), window.length());
            double sim = 1.0 - ((double) dist / maxLen);

            if (sim > maxSim) {
                maxSim = sim;
            }
            if (maxSim >= 0.95) break;
        }
        return maxSim;
    }

    private int computeLevenshteinDistance(String s1, String s2) {
        int[] dp = new int[s2.length() + 1];
        for (int j = 0; j <= s2.length(); j++) {
            dp[j] = j;
        }

        for (int i = 1; i <= s1.length(); i++) {
            int previousDiagonal = dp[0];
            dp[0] = i;
            for (int j = 1; j <= s2.length(); j++) {
                int temp = dp[j];
                if (s1.charAt(i - 1) == s2.charAt(j - 1)) {
                    dp[j] = previousDiagonal;
                } else {
                    dp[j] = 1 + Math.min(previousDiagonal, Math.min(dp[j], dp[j - 1]));
                }
                previousDiagonal = temp;
            }
        }
        return dp[s2.length()];
    }

    private String downgradeStatus(String status) {
        if (status == null) return "missing";
        return switch (status.toLowerCase(Locale.ROOT)) {
            case "matched" -> "weak";
            case "weak" -> "missing";
            default -> "missing";
        };
    }
}
