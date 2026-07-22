package fit.iuh.modules.assessment;

import fit.iuh.modules.assessment.AssessmentResponseDto.EvidenceItem;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Component;

import java.util.*;
import java.util.regex.Pattern;

/**
 * Pure Java utility that validates whether an evidence item's {@code source_span}
 * is grounded in the original CV Markdown document using fuzzy string matching.
 *
 * <p>No LLM calls are made in this component.
 */
@Slf4j
@Component
public class EvidenceGroundingValidator {

    private static final Pattern NON_ALPHANUMERIC = Pattern.compile("[^\\p{L}\\p{N}]+");

    /**
     * Validates and applies grounding check to a single {@link EvidenceItem}.
     *
     * <p>If the calculated {@code groundingScore} is below {@code threshold}:
     * <ul>
     *   <li>{@code "matched"} is downgraded to {@code "weak"}</li>
     *   <li>{@code "weak"} is downgraded to {@code "missing"}</li>
     * </ul>
     *
     * @param item           the evidence item to validate
     * @param fullCvMarkdown full CV Markdown text
     * @param threshold      minimum grounding threshold (0.0 to 1.0)
     * @return updated {@link EvidenceItem} with populated {@code groundingScore} and possibly downgraded status
     */
    public EvidenceItem validateAndApply(EvidenceItem item, String fullCvMarkdown, double threshold) {
        if (item == null) {
            return null;
        }

        String currentStatus = item.status();
        double groundingScore = calculateGroundingScore(item.sourceSpan(), fullCvMarkdown, currentStatus);

        String newStatus = currentStatus;
        if (groundingScore < threshold) {
            if ("matched".equalsIgnoreCase(currentStatus)) {
                newStatus = "weak";
            } else if ("weak".equalsIgnoreCase(currentStatus)) {
                newStatus = "missing";
            }

            if (!Objects.equals(currentStatus, newStatus)) {
                log.warn("[GroundingCheck] criteria_id={} | status={} -> {} | score={} < threshold={}",
                        item.criteriaId(), currentStatus, newStatus,
                        String.format("%.2f", groundingScore), String.format("%.2f", threshold));
            }
        } else {
            log.debug("[GroundingCheck] criteria_id={} | status={} | score={} >= threshold={}",
                    item.criteriaId(), currentStatus,
                    String.format("%.2f", groundingScore), String.format("%.2f", threshold));
        }

        return new EvidenceItem(
                item.criteriaId(),
                item.criteriaName(),
                item.jdRequirement(),
                item.cvEvidence(),
                newStatus,
                item.reasoning(),
                item.weightUsed(),
                item.scoreContribution(),
                item.sourceSpan(),
                groundingScore,
                item.confidenceVotes(),
                item.lowConfidence(),
                item.needsManualReview()
        );
    }

    /**
     * Calculates the grounding score (0.0 to 1.0) of a {@code sourceSpan} within {@code fullCvMarkdown}.
     */
    public double calculateGroundingScore(String sourceSpan, String fullCvMarkdown, String status) {
        if ("missing".equalsIgnoreCase(status)) {
            // Missing items don't require a source span
            return 1.0;
        }

        if (sourceSpan == null || sourceSpan.isBlank()) {
            // Non-missing status but no source span provided -> 0.0 score
            return 0.0;
        }

        if (fullCvMarkdown == null || fullCvMarkdown.isBlank()) {
            return 0.0;
        }

        String spanNorm = normalize(sourceSpan);
        String cvNorm = normalize(fullCvMarkdown);

        if (spanNorm.isBlank()) {
            return 0.0;
        }

        // 1. Direct substring containment match
        if (cvNorm.contains(spanNorm)) {
            return 1.0;
        }

        // 2. Token overlap ratio
        String[] spanTokens = spanNorm.split("\\s+");
        if (spanTokens.length == 0) {
            return 0.0;
        }

        Set<String> cvTokenSet = new HashSet<>(Arrays.asList(cvNorm.split("\\s+")));
        int matchedTokens = 0;
        for (String token : spanTokens) {
            if (cvTokenSet.contains(token)) {
                matchedTokens++;
            }
        }

        double tokenOverlapRatio = (double) matchedTokens / spanTokens.length;

        // 3. Sliding window Levenshtein ratio for sequential similarity
        double bestLevenshteinRatio = findBestWindowLevenshteinRatio(spanTokens, cvNorm.split("\\s+"));

        // Final grounding score is the max of token overlap and window Levenshtein similarity
        return Math.max(tokenOverlapRatio, bestLevenshteinRatio);
    }

    private String normalize(String text) {
        if (text == null) return "";
        String clean = NON_ALPHANUMERIC.matcher(text.toLowerCase(Locale.ROOT)).replaceAll(" ");
        return clean.trim().replaceAll("\\s+", " ");
    }

    private double findBestWindowLevenshteinRatio(String[] spanTokens, String[] cvTokens) {
        if (spanTokens.length == 0 || cvTokens.length == 0) {
            return 0.0;
        }

        int windowSize = spanTokens.length;
        String spanJoined = String.join(" ", spanTokens);
        double maxRatio = 0.0;

        // Slide window across CV tokens
        int step = Math.max(1, windowSize / 3);
        for (int i = 0; i <= cvTokens.length - windowSize; i += step) {
            String windowJoined = String.join(" ", Arrays.copyOfRange(cvTokens, i, i + windowSize));
            double ratio = levenshteinRatio(spanJoined, windowJoined);
            if (ratio > maxRatio) {
                maxRatio = ratio;
                if (maxRatio >= 0.95) break; // early exit on high match
            }
        }
        return maxRatio;
    }

    /**
     * Pure Java Levenshtein similarity ratio between two strings (0.0 to 1.0).
     */
    public double levenshteinRatio(String s1, String s2) {
        if (s1.equals(s2)) return 1.0;
        int len1 = s1.length();
        int len2 = s2.length();
        if (len1 == 0 || len2 == 0) return 0.0;

        int maxLen = Math.max(len1, len2);
        int distance = computeLevenshteinDistance(s1, s2);
        return 1.0 - ((double) distance / maxLen);
    }

    private int computeLevenshteinDistance(String s1, String s2) {
        int[] costs = new int[s2.length() + 1];
        for (int i = 0; i <= s1.length(); i++) {
            int lastValue = i;
            for (int j = 0; j <= s2.length(); j++) {
                if (i == 0) {
                    costs[j] = j;
                } else if (j > 0) {
                    int newValue = costs[j - 1];
                    if (s1.charAt(i - 1) != s2.charAt(j - 1)) {
                        newValue = Math.min(Math.min(newValue, lastValue), costs[j]) + 1;
                    }
                    costs[j - 1] = lastValue;
                    lastValue = newValue;
                }
            }
            if (i > 0) {
                costs[s2.length()] = lastValue;
            }
        }
        return costs[s2.length()];
    }
}
