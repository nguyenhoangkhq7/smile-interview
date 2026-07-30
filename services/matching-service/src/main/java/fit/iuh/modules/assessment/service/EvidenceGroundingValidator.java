package fit.iuh.modules.assessment.service;

import fit.iuh.modules.assessment.dto.AssessmentResponseDto;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Component;

import java.util.*;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

@Slf4j
@Component
public class EvidenceGroundingValidator {

    /**
     * Regex that captures contiguous sequences of ASCII letters, digits, dots, plus-signs,
     * and hash-signs with length ≥ 2 — i.e. English technical terms and technology names
     * that appear in both Vietnamese evidence sentences and English CV text.
     *
     * Examples matched: "PostgreSQL", "Docker", "JWT", "Spring Boot", "EC2", "RDS",
     *   "Next.js", "Redis", "C++", "C#", "AWS", "2026", "3.19"
     */
    private static final Pattern TECH_TOKEN_PATTERN =
            Pattern.compile("[A-Za-z0-9][A-Za-z0-9.+#]*[A-Za-z0-9]");

    /**
     * Validates cv_evidence against the full CV markdown using fuzzy similarity.
     * If similarity is below threshold, downgrade the status.
     */
    public AssessmentResponseDto.EvidenceItem validateAndApply(
            AssessmentResponseDto.EvidenceItem item,
            String cvMarkdown,
            double groundingThreshold) {

        if (item == null) return null;

        String cvEvidence = item.cvEvidence();
        String cvQuote = item.cvQuote();

        if ((cvEvidence == null || cvEvidence.isBlank()) && (cvQuote == null || cvQuote.isBlank())) {
            Double score = item.groundingScore() != null ? item.groundingScore() : 1.0;
            return new AssessmentResponseDto.EvidenceItem(
                    item.criteriaId(), item.criteriaName(), item.importance(), item.jdRequirement(),
                    item.cvEvidence(), item.cvQuote(), item.status(), item.reasoning(), item.weightUsed(),
                    item.scoreContribution(), score, item.confidenceVotes(), item.lowConfidence(), item.needsManualReview()
            );
        }

        double simEvidence = calculateFuzzySimilarity(cvEvidence, cvMarkdown);
        double simQuote = calculateFuzzySimilarity(cvQuote, cvMarkdown);
        double sim = Math.max(simEvidence, simQuote);

        boolean quoteHallucinated = cvQuote != null && !cvQuote.isBlank() && simQuote < 0.35;

        if (sim < groundingThreshold || quoteHallucinated) {
            String originalStatus = item.status();
            String downgradedStatus = downgradeStatus(originalStatus);
            log.warn("[GroundingCheck] criteria_id={} | status={} -> {} | score={} < threshold={} (quoteHallucinated={})",
                    item.criteriaId(), originalStatus, downgradedStatus, sim, groundingThreshold, quoteHallucinated);
            return new AssessmentResponseDto.EvidenceItem(
                    item.criteriaId(), item.criteriaName(), item.importance(), item.jdRequirement(),
                    item.cvEvidence(), item.cvQuote(), downgradedStatus,
                    item.reasoning() + " [Canh bao: Bang chung tu CV co do tin cay thap (" + String.format("%.2f", sim) + ").]",
                    item.weightUsed(), item.scoreContribution(), sim,
                    item.confidenceVotes(), item.lowConfidence(), true
            );
        }

        return new AssessmentResponseDto.EvidenceItem(
                item.criteriaId(), item.criteriaName(), item.importance(), item.jdRequirement(),
                item.cvEvidence(), item.cvQuote(), item.status(), item.reasoning(), item.weightUsed(),
                item.scoreContribution(), sim, item.confidenceVotes(), item.lowConfidence(), item.needsManualReview()
        );
    }

    public double calculateFuzzySimilarity(String needle, String haystack) {
        if (needle == null || haystack == null || needle.isBlank() || haystack.isBlank()) return 0.0;

        // --- Pass 1: Tech-keyword matching (language-agnostic) ---
        // LLM writes cv_evidence in Vietnamese, but the CV source is in English.
        // Extract English/ASCII technical tokens from the evidence and check whether
        // they actually appear in the full CV markdown. This sidesteps Jaccard failing
        // because Vietnamese words share no tokens with English words.
        double techKeywordScore = calculateTechKeywordMatchScore(needle, haystack);
        if (techKeywordScore >= 0.5) {
            log.debug("[GroundingCheck] Tech-keyword match score={} (≥0.5) — grounding accepted", String.format("%.2f", techKeywordScore));
            return techKeywordScore;
        }

        // --- Pass 2: Classic fuzzy comparison on normalised text ---
        String normNeedle = normalizeText(needle);
        String normHaystack = normalizeText(haystack);
        if (normHaystack.contains(normNeedle)) return 1.0;
        double tokenJaccard = calculateTokenJaccardOverlap(normNeedle, normHaystack);
        double slidingLev = calculateSlidingLevenshtein(normNeedle, normHaystack);
        double classicScore = Math.max(tokenJaccard, slidingLev);

        // Return the best of both approaches so we never penalise valid evidence
        return Math.max(techKeywordScore, classicScore);
    }

    /**
     * Extracts ASCII technical tokens (tech names, version numbers, acronyms, etc.) from
     * {@code evidence} — which may be written in Vietnamese — and counts how many of them
     * appear (case-insensitive) inside the English {@code cvMarkdown}.
     *
     * <p>Returns a ratio in [0, 1]:
     * <ul>
     *   <li>1.0 → all tokens found (perfect grounding)</li>
     *   <li>0.0 → no tokens found <em>or</em> evidence contains no tech tokens at all</li>
     * </ul>
     *
     * <p>Single-character tokens and stop-words are skipped to avoid false positives.
     */
    private double calculateTechKeywordMatchScore(String evidence, String cvMarkdown) {
        Set<String> techTokens = extractTechTokens(evidence);
        if (techTokens.isEmpty()) {
            return 0.0;
        }
        String cvLower = cvMarkdown.toLowerCase(Locale.ROOT);
        long matched = techTokens.stream()
                .filter(token -> cvLower.contains(token.toLowerCase(Locale.ROOT)))
                .count();
        double score = (double) matched / techTokens.size();
        log.debug("[GroundingCheck] Tech-keyword match: {}/{} tokens found → score={}",
                matched, techTokens.size(), String.format("%.2f", score));
        return score;
    }

    private static final Set<String> SHORT_TECH_TERMS = Set.of(
            "AWS", "EC2", "RDS", "JPA", "JVM", "JWT", "SQL", "API", "CSS", "DOM",
            "ORM", "OOP", "GIT", "TDD", "CI", "CD", "DDD", "SPA", "SSR", "SSG",
            "UI", "UX", "DB", "ML", "AI", "IOT", "SDK", "VPC", "IAM",
            "SLO", "SLA", "APM", "ECS", "EKS", "S3", "SNS", "SQS", "RPC"
    );

    /**
     * Extracts distinct ASCII technical tokens from {@code text} using {@link #TECH_TOKEN_PATTERN}.
     * Tokens that are pure common English stop-words (≤ 3 chars, not known tech acronyms) are
     * excluded to reduce noise.
     */
    private Set<String> extractTechTokens(String text) {
        if (text == null || text.isBlank()) return Set.of();
        Set<String> tokens = new LinkedHashSet<>();
        Matcher m = TECH_TOKEN_PATTERN.matcher(text);
        while (m.find()) {
            String token = m.group();
            // Skip very short tokens unless they are known tech acronyms
            if (token.length() <= 2 && !SHORT_TECH_TERMS.contains(token.toUpperCase(Locale.ROOT))) {
                continue;
            }
            // Skip pure numeric tokens (page numbers, scores) unless they look like version strings
            if (token.matches("\\d+") && token.length() <= 2) {
                continue;
            }
            tokens.add(token);
        }
        return tokens;
    }

    private String normalizeText(String text) {
        return text.toLowerCase(Locale.ROOT)
                .replaceAll("[^a-z0-9\\s]", " ")
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
            if (haystackTokens.contains(token)) intersection++;
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
            if (sim > maxSim) maxSim = sim;
            if (maxSim >= 0.95) break;
        }
        return maxSim;
    }

    private int computeLevenshteinDistance(String s1, String s2) {
        int[] dp = new int[s2.length() + 1];
        for (int j = 0; j <= s2.length(); j++) dp[j] = j;
        for (int i = 1; i <= s1.length(); i++) {
            int prev = dp[0];
            dp[0] = i;
            for (int j = 1; j <= s2.length(); j++) {
                int temp = dp[j];
                dp[j] = s1.charAt(i - 1) == s2.charAt(j - 1) ? prev
                        : 1 + Math.min(prev, Math.min(dp[j], dp[j - 1]));
                prev = temp;
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
