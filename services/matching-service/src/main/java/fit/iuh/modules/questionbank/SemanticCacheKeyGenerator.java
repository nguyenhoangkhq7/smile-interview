package fit.iuh.modules.questionbank;

import fit.iuh.modules.assessment.SeniorityLevel;
import org.springframework.stereotype.Component;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.util.*;
import java.util.stream.Collectors;

/**
 * Generates standardized cache keys for question generation inputs.
 *
 * <h3>Key Strategy (v2 — evidence-item based)</h3>
 * <p>Cache keys are now derived from structured assessment evidence items instead of raw
 * chunk text. This dramatically improves cross-candidate cache hit rates because:
 * <ul>
 *   <li>Standard items use a stable DB {@code criteria_id}, which is constant across all
 *       candidates evaluated against the same job category.</li>
 *   <li>The combination of {@code (criteria_id, status, seniority_level)} produces an
 *       identical key whenever two candidates share the same criteria outcome and level,
 *       regardless of how each candidate's CV is phrased.</li>
 *   <li>Ad-hoc items (no {@code criteria_id}) fall back to a normalized
 *       {@code criteria_name} hash — hit rate is lower but acceptable, since ad-hoc items
 *       are inherently JD-specific.</li>
 * </ul>
 *
 * <h3>Key Namespaces</h3>
 * <ul>
 *   <li>{@code siminterview:cache:item:*} — standard criteria items</li>
 *   <li>{@code siminterview:cache:adhoc:*} — ad-hoc items</li>
 * </ul>
 *
 * <h3>Backward Compatibility</h3>
 * The legacy {@link #generateKey(String, String)} method is kept but deprecated. Existing
 * Redis entries under the old {@code siminterview:cache:pair:*} namespace will expire
 * naturally based on the 7-day TTL already set when they were written.
 */
@Component
public class SemanticCacheKeyGenerator {

    private static final String PREFIX_ITEM  = "siminterview:cache:item:";
    private static final String PREFIX_ADHOC = "siminterview:cache:adhoc:";

    // -------------------------------------------------------------------------
    // v2 API — evidence-item based keys (preferred)
    // -------------------------------------------------------------------------

    /**
     * Generates a cache key for a <strong>standard</strong> evidence item that has a
     * known {@code criteria_id}.
     *
     * <p>Key composition: {@code sha256("crit:{criteriaId}|status:{status}|level:{level}")}
     *
     * @param criteriaId    DB primary key of the evaluation criterion (must not be null)
     * @param status        matching result: "matched" | "weak" | "missing" | "not_applicable"
     * @param seniorityLevel candidate seniority extracted from the assessment
     * @return Redis-safe cache key string
     */
    public String generateKey(Long criteriaId, String status, SeniorityLevel seniorityLevel) {
        if (criteriaId == null) {
            throw new IllegalArgumentException(
                    "criteriaId must not be null for standard item cache key. Use generateKeyForAdHoc() instead.");
        }
        String levelName = seniorityLevel != null ? seniorityLevel.name() : "MID";
        String normalizedStatus = status != null ? status.toLowerCase().strip() : "missing";
        String composite = "crit:" + criteriaId + "|status:" + normalizedStatus + "|level:" + levelName;
        return PREFIX_ITEM + sha256(composite);
    }

    /**
     * Generates a cache key for an <strong>ad-hoc</strong> evidence item that has no
     * {@code criteria_id} (sourced from {@code additional_evidence_items}).
     *
     * <p>Key composition: {@code sha256("name:{normalizedName}|status:{status}|level:{level}")}
     *
     * <p>Hit rate is inherently lower than for standard items because {@code criteria_name}
     * varies by JD phrasing, but still significantly better than hashing raw chunk text.
     *
     * @param criteriaName  human-readable criterion name (will be normalized before hashing)
     * @param status        matching result: "matched" | "weak" | "missing" | "not_applicable"
     * @param seniorityLevel candidate seniority extracted from the assessment
     * @return Redis-safe cache key string
     */
    public String generateKeyForAdHoc(String criteriaName, String status, SeniorityLevel seniorityLevel) {
        String levelName = seniorityLevel != null ? seniorityLevel.name() : "MID";
        String normalizedStatus = status != null ? status.toLowerCase().strip() : "missing";
        String normalizedName = normalizeName(criteriaName);
        String composite = "name:" + normalizedName + "|status:" + normalizedStatus + "|level:" + levelName;
        return PREFIX_ADHOC + sha256(composite);
    }

    // -------------------------------------------------------------------------
    // Legacy API — kept for backward compat with existing tests
    // -------------------------------------------------------------------------

    /**
     * @deprecated Since v2 (evidence-item key refactor). Use
     *             {@link #generateKey(Long, String, SeniorityLevel)} for standard items or
     *             {@link #generateKeyForAdHoc(String, String, SeniorityLevel)} for ad-hoc items.
     *             This method hashes raw chunk text, which produces poor cross-candidate hit rates.
     */
    @Deprecated(since = "v2", forRemoval = false)
    public String generateKey(String jdRequirement, String cvExperience) {
        String reqPart = extractAndNormalizeTokens(jdRequirement);
        String expPart = extractAndNormalizeTokens(cvExperience);
        String compositeKey = "req:" + reqPart + "|exp:" + expPart;
        return "siminterview:cache:pair:" + sha256(compositeKey);
    }

    // -------------------------------------------------------------------------
    // Private helpers
    // -------------------------------------------------------------------------

    /**
     * Normalizes a criteria name for use in an ad-hoc cache key: lowercase, strip
     * punctuation, collapse whitespace, remove common stopwords.
     */
    private String normalizeName(String name) {
        if (name == null || name.isBlank()) return "unknown";
        return Arrays.stream(
                        name.toLowerCase()
                            .replaceAll("[^a-z0-9\\s]", " ")
                            .trim()
                            .split("\\s+"))
                .filter(t -> t.length() > 2 && !STOPWORDS.contains(t))
                .sorted()
                .collect(Collectors.joining(","));
    }

    private static final Set<String> STOPWORDS = Set.of(
            "and", "or", "the", "in", "of", "for", "a", "an", "at", "by",
            "from", "on", "as", "is", "are", "to", "with"
    );

    // Legacy stopwords — kept in full to preserve the deprecated method's hash output.
    private static final Set<String> LEGACY_STOPWORDS = new HashSet<>(Arrays.asList(
            "must", "have", "with", "experience", "in", "and", "or", "to", "the",
            "using", "of", "for", "a", "an", "at", "by", "from", "on", "as", "is",
            "are", "was", "were", "be", "been", "being", "that", "which", "who",
            "whom", "this", "these", "those"
    ));

    // ── Legacy token extraction (used only by the deprecated overload) ────────

    private static final Map<String, String> TECH_SYNONYMS = new HashMap<>();

    static {
        TECH_SYNONYMS.put("java 21", "java"); TECH_SYNONYMS.put("java 17", "java");
        TECH_SYNONYMS.put("java 11", "java"); TECH_SYNONYMS.put("java 8", "java");
        TECH_SYNONYMS.put("core java", "java"); TECH_SYNONYMS.put("java backend", "java");
        TECH_SYNONYMS.put("typescript", "ts"); TECH_SYNONYMS.put("javascript", "js");
        TECH_SYNONYMS.put("python3", "python"); TECH_SYNONYMS.put("python 3", "python");
        TECH_SYNONYMS.put("golang", "go"); TECH_SYNONYMS.put("go language", "go");
        TECH_SYNONYMS.put("spring boot", "springboot"); TECH_SYNONYMS.put("springboot", "springboot");
        TECH_SYNONYMS.put("spring framework", "springboot"); TECH_SYNONYMS.put("spring mvc", "springboot");
        TECH_SYNONYMS.put("react js", "react"); TECH_SYNONYMS.put("reactjs", "react");
        TECH_SYNONYMS.put("next js", "nextjs"); TECH_SYNONYMS.put("nextjs", "nextjs");
        TECH_SYNONYMS.put("angularjs", "angular"); TECH_SYNONYMS.put("vuejs", "vue");
        TECH_SYNONYMS.put("postgresql", "postgres"); TECH_SYNONYMS.put("postgres", "postgres");
        TECH_SYNONYMS.put("mongodb", "mongo"); TECH_SYNONYMS.put("mongo db", "mongo");
        TECH_SYNONYMS.put("ms sql", "mssql"); TECH_SYNONYMS.put("microsoft sql", "mssql");
        TECH_SYNONYMS.put("redis cache", "redis");
        TECH_SYNONYMS.put("microservices", "microservice"); TECH_SYNONYMS.put("micro-service", "microservice");
        TECH_SYNONYMS.put("rest api", "restapi"); TECH_SYNONYMS.put("restful", "restapi");
        TECH_SYNONYMS.put("rest apis", "restapi");
        TECH_SYNONYMS.put("kubernetes", "k8s"); TECH_SYNONYMS.put("docker container", "docker");
        TECH_SYNONYMS.put("amazon web services", "aws");
    }

    private String extractAndNormalizeTokens(String text) {
        if (text == null || text.isBlank()) return "";
        String cleaned = text.toLowerCase().replaceAll("[^a-z0-9\\s]", " ");
        String[] rawTokens = cleaned.split("\\s+");
        List<String> normalizedTokens = new ArrayList<>();
        String lowercaseText = text.toLowerCase();
        for (Map.Entry<String, String> entry : TECH_SYNONYMS.entrySet()) {
            if (lowercaseText.contains(entry.getKey())) normalizedTokens.add(entry.getValue());
        }
        for (String token : rawTokens) {
            // Use LEGACY_STOPWORDS to preserve the deprecated method's hash behaviour
            if (token.length() > 2 && !LEGACY_STOPWORDS.contains(token) && !TECH_SYNONYMS.containsKey(token)) {
                normalizedTokens.add(token);
            }
        }
        return normalizedTokens.stream().distinct().sorted().collect(Collectors.joining(","));
    }

    // ── SHA-256 ───────────────────────────────────────────────────────────────

    private String sha256(String input) {
        try {
            MessageDigest digest = MessageDigest.getInstance("SHA-256");
            byte[] hash = digest.digest(input.getBytes(StandardCharsets.UTF_8));
            StringBuilder hexString = new StringBuilder();
            for (byte b : hash) {
                String hex = Integer.toHexString(0xff & b);
                if (hex.length() == 1) hexString.append('0');
                hexString.append(hex);
            }
            return hexString.toString();
        } catch (NoSuchAlgorithmException e) {
            throw new RuntimeException("SHA-256 algorithm not found", e);
        }
    }
}
