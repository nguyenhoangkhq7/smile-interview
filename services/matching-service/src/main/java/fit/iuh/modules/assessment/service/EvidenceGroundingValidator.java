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
     * hash-signs, and slashes — i.e. English technical terms and technology names
     * that appear in both Vietnamese evidence sentences and English CV text.
     *
     * Examples matched: "PostgreSQL", "Docker", "JWT", "Spring Boot", "EC2", "RDS",
     *   "Next.js", "Redis", "C++", "C#", "CI/CD", "AWS", "2026", "3.19"
     */
    private static final Pattern TECH_TOKEN_PATTERN =
            Pattern.compile("[A-Za-z0-9][A-Za-z0-9.+#/]*");

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

        // Handle case where evidence/quote is empty
        if ((cvEvidence == null || cvEvidence.isBlank()) && (cvQuote == null || cvQuote.isBlank())) {
            String currentStatus = item.status() != null ? item.status().toLowerCase(Locale.ROOT) : "missing";
            if ("matched".equals(currentStatus) || "partial".equals(currentStatus) || "weak".equals(currentStatus)) {
                // LLM claimed match/partial without providing any evidence -> downgrade to missing
                log.warn("[GroundingCheck] criteria_id={} | status={} -> missing | Reason: No cv_evidence or cv_quote provided.",
                        item.criteriaId(), item.status());
                return new AssessmentResponseDto.EvidenceItem(
                        item.criteriaId(), item.criteriaName(), item.importance(), item.jdRequirement(),
                        null, null, "missing",
                        item.reasoning() + " [Warning: Missing evidence context from CV.]",
                        item.weightUsed(), item.scoreContribution(), 0.0,
                        item.confidenceVotes(), item.lowConfidence(), true, item.matchMetadata()
                );
            }
            Double score = item.groundingScore() != null ? item.groundingScore() : 1.0;
            return new AssessmentResponseDto.EvidenceItem(
                    item.criteriaId(), item.criteriaName(), item.importance(), item.jdRequirement(),
                    item.cvEvidence(), item.cvQuote(), item.status(), item.reasoning(), item.weightUsed(),
                    item.scoreContribution(), score, item.confidenceVotes(), item.lowConfidence(), item.needsManualReview(), item.matchMetadata()
            );
        }

        double simEvidence = calculateFuzzySimilarity(cvEvidence, cvMarkdown);
        double simQuote = calculateFuzzySimilarity(cvQuote, cvMarkdown);
        double sim = Math.max(simEvidence, simQuote);

        boolean hasTechTokens = !extractTechTokens(cvEvidence).isEmpty() || !extractTechTokens(cvQuote).isEmpty();
        
        // Soft skills / non-technical criteria check vs Technical criteria check
        double effectiveThreshold;
        if (hasTechTokens) {
            effectiveThreshold = Math.min(groundingThreshold, 0.50);
        } else if (cvQuote != null && !cvQuote.isBlank()) {
            effectiveThreshold = Math.min(groundingThreshold, 0.40);
        } else {
            effectiveThreshold = Math.min(groundingThreshold, 0.25);
        }

        boolean quoteHallucinated = cvQuote != null && !cvQuote.isBlank() && simQuote < 0.20;

        if (sim < effectiveThreshold || quoteHallucinated) {
            String originalStatus = item.status();
            String downgradedStatus = downgradeStatus(originalStatus);
            log.warn("[GroundingCheck] criteria_id={} | status={} -> {} | score={} < effectiveThreshold={} (quoteHallucinated={})",
                    item.criteriaId(), originalStatus, downgradedStatus, sim, effectiveThreshold, quoteHallucinated);
            return new AssessmentResponseDto.EvidenceItem(
                    item.criteriaId(), item.criteriaName(), item.importance(), item.jdRequirement(),
                    item.cvEvidence(), item.cvQuote(), downgradedStatus,
                    item.reasoning() + " [Warning: Low evidence grounding confidence (" + String.format("%.2f", sim) + ").]",
                    item.weightUsed(), item.scoreContribution(), sim,
                    item.confidenceVotes(), item.lowConfidence(), true, item.matchMetadata()
            );
        }

        return new AssessmentResponseDto.EvidenceItem(
                item.criteriaId(), item.criteriaName(), item.importance(), item.jdRequirement(),
                item.cvEvidence(), item.cvQuote(), item.status(), item.reasoning(), item.weightUsed(),
                item.scoreContribution(), sim, item.confidenceVotes(), item.lowConfidence(), item.needsManualReview(), item.matchMetadata()
        );
    }

    public double calculateFuzzySimilarity(String needle, String haystack) {
        if (needle == null || haystack == null || needle.isBlank() || haystack.isBlank()) return 0.0;

        // --- Pass 1: Tech-keyword matching (language-agnostic) ---
        // LLM writes cv_evidence in Vietnamese, but the CV source is in English.
        // Extract English/ASCII technical tokens from the evidence and check whether
        // they actually appear in the full CV markdown. This sidesteps Jaccard failing
        // because Vietnamese words share no tokens with English words.
        Set<String> techTokens = extractTechTokens(needle);
        double techKeywordScore = calculateTechKeywordMatchScore(needle, haystack);
        if (!techTokens.isEmpty() && techKeywordScore >= 0.5) {
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
        long matched = techTokens.stream()
                .filter(token -> fit.iuh.modules.assessment.util.TechLexiconDictionary.containsTechOrSynonym(cvMarkdown, token))
                .count();
        double score = (double) matched / techTokens.size();
        log.debug("[GroundingCheck] Tech-keyword match: {}/{} tokens found → score={}",
                matched, techTokens.size(), String.format("%.2f", score));
        return score;
    }

    private static final Set<String> SHORT_TECH_TERMS = Set.of(
            "AWS", "EC2", "RDS", "JPA", "JVM", "JWT", "SQL", "API", "CSS", "DOM",
            "ORM", "OOP", "GIT", "TDD", "CI", "CD", "DDD", "SPA", "SSR", "SSG",
            "UI", "UX", "DB", "ML", "AI", "DL", "CV", "QA", "QC", "IOT", "SDK", "VPC", "IAM",
            "SLO", "SLA", "APM", "ECS", "EKS", "GKE", "AKS", "S3", "SNS", "SQS", "RPC",
            "GO", "C", "R", "PHP", "CPP", "K8S", "K3S", "K9S", "JS", "TS", "OS", "IP",
            "TCP", "UDP", "SSH", "SSL", "TLS", "FTP", "DNS", "CDN", "WAF", "VPN",
            "BQ", "VM", "ES", "TF", "MQ", "EF", "SH", "DRF", "RTK", "SSO", "MFA",
            "2FA", "ETL", "ELT", "EVM", "DAO", "NFT", "LLM", "RAG", "NLP", "SRE", "SVN", "KMP", "LTS"
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
            String upper = token.toUpperCase(Locale.ROOT);
            // Skip very short tokens unless they are known tech acronyms or registered in TechLexiconDictionary
            if (token.length() <= 2 && !SHORT_TECH_TERMS.contains(upper) && !fit.iuh.modules.assessment.util.TechLexiconDictionary.isKnownShortTerm(token)) {
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

    private static final Set<String> STOPWORDS = Set.of(
            "the", "a", "an", "in", "on", "at", "to", "for", "of", "with", "is", "are", "was", "were",
            "and", "or", "as", "by", "from", "that", "this", "it", "has", "have", "had", "can", "will",
            "be", "been", "being", "candidate", "experience", "skills", "skill", "projects", "project",
            "working", "work", "responsible", "using", "used", "knowledge", "strong", "proficient",
            "có", "và", "trong", "với", "cho", "được", "các", "những", "của", "tại", "là", "đã",
            "đang", "khi", "về", "như", "ứng", "viên", "kinh", "nghiệm", "dự", "án", "kỹ", "năng"
    );

    private double calculateTokenJaccardOverlap(String needle, String haystack) {
        Set<String> allNeedleTokens = new HashSet<>(Arrays.asList(needle.split(" ")));
        allNeedleTokens.removeIf(String::isBlank);
        if (allNeedleTokens.isEmpty()) return 0.0;

        Set<String> contentNeedleTokens = new HashSet<>(allNeedleTokens);
        contentNeedleTokens.removeIf(token -> STOPWORDS.contains(token) || token.length() <= 1);
        Set<String> targetNeedleTokens = contentNeedleTokens.isEmpty() ? allNeedleTokens : contentNeedleTokens;

        Set<String> haystackTokens = new HashSet<>(Arrays.asList(haystack.split(" ")));
        haystackTokens.removeIf(String::isBlank);

        int intersection = 0;
        for (String token : targetNeedleTokens) {
            if (haystackTokens.contains(token)) intersection++;
        }
        return (double) intersection / targetNeedleTokens.size();
    }

    /**
     * Optimized segment-based Levenshtein distance calculation.
     * Evaluates paragraphs / sentences that share content tokens with the needle rather
     * than brute-force sliding over the entire 30,000-character document.
     */
    private double calculateSlidingLevenshtein(String needle, String haystack) {
        int nLen = needle.length();
        if (nLen == 0 || haystack == null || haystack.isBlank()) return 0.0;

        Set<String> needleWords = new HashSet<>(Arrays.asList(needle.split(" ")));
        needleWords.removeIf(w -> STOPWORDS.contains(w) || w.length() <= 2);

        String[] rawLines = haystack.split("\\r?\\n");
        List<String> segments = new ArrayList<>();
        StringBuilder currentSeg = new StringBuilder();

        for (String line : rawLines) {
            String trimmed = line.trim();
            if (trimmed.isEmpty()) {
                if (currentSeg.length() > 0) {
                    segments.add(currentSeg.toString());
                    currentSeg.setLength(0);
                }
            } else {
                if (currentSeg.length() > 0) currentSeg.append(" ");
                currentSeg.append(trimmed);
                if (currentSeg.length() >= nLen * 2) {
                    segments.add(currentSeg.toString());
                    currentSeg.setLength(0);
                }
            }
        }
        if (currentSeg.length() > 0) segments.add(currentSeg.toString());

        double maxSim = 0.0;

        for (String segment : segments) {
            if (segment.isBlank()) continue;
            String normSeg = normalizeText(segment);
            if (normSeg.contains(needle)) return 1.0;

            // Pre-filter: only compute DP Levenshtein if segment shares at least 1 keyword
            boolean hasTokenOverlap = needleWords.isEmpty();
            if (!hasTokenOverlap) {
                for (String nw : needleWords) {
                    if (normSeg.contains(nw)) {
                        hasTokenOverlap = true;
                        break;
                    }
                }
            }

            if (hasTokenOverlap) {
                int sLen = normSeg.length();
                if (sLen <= nLen * 2.5) {
                    int dist = computeLevenshteinDistance(needle, normSeg);
                    int maxLen = Math.max(nLen, sLen);
                    double sim = 1.0 - ((double) dist / maxLen);
                    if (sim > maxSim) maxSim = sim;
                    if (maxSim >= 0.90) return maxSim;
                } else {
                    // Small local sliding window inside the candidate segment
                    int windowSize = Math.min(sLen, Math.max(nLen + 10, (int) (nLen * 1.3)));
                    int step = Math.max(1, nLen / 3);
                    for (int i = 0; i <= sLen - Math.min(windowSize, nLen); i += step) {
                        int end = Math.min(sLen, i + windowSize);
                        String window = normSeg.substring(i, end);
                        int dist = computeLevenshteinDistance(needle, window);
                        int maxLen = Math.max(nLen, window.length());
                        double sim = 1.0 - ((double) dist / maxLen);
                        if (sim > maxSim) maxSim = sim;
                        if (maxSim >= 0.90) return maxSim;
                    }
                }
            }
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
        fit.iuh.modules.assessment.entity.EvaluationStatus eval = fit.iuh.modules.assessment.entity.EvaluationStatus.fromCode(status);
        return switch (eval) {
            case MATCHED -> fit.iuh.modules.assessment.entity.EvaluationStatus.PARTIAL.getCode();
            case PARTIAL -> fit.iuh.modules.assessment.entity.EvaluationStatus.WEAK.getCode();
            case WEAK -> fit.iuh.modules.assessment.entity.EvaluationStatus.MISSING.getCode();
            default -> fit.iuh.modules.assessment.entity.EvaluationStatus.MISSING.getCode();
        };
    }
}
