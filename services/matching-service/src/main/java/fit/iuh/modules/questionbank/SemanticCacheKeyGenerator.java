package fit.iuh.modules.questionbank;

import org.springframework.stereotype.Component;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.util.*;
import java.util.stream.Collectors;

/**
 * Generates standardized semantic cache keys for experience-requirement pairs
 * to increase cache hit rate regardless of phrasing variations or tech versions.
 */
@Component
public class SemanticCacheKeyGenerator {

    private static final Map<String, String> TECH_SYNONYMS = new HashMap<>();

    static {
        // Languages & Core Runtimes
        TECH_SYNONYMS.put("java 21", "java");
        TECH_SYNONYMS.put("java 17", "java");
        TECH_SYNONYMS.put("java 11", "java");
        TECH_SYNONYMS.put("java 8", "java");
        TECH_SYNONYMS.put("core java", "java");
        TECH_SYNONYMS.put("java backend", "java");
        TECH_SYNONYMS.put("typescript", "ts");
        TECH_SYNONYMS.put("javascript", "js");
        TECH_SYNONYMS.put("python3", "python");
        TECH_SYNONYMS.put("python 3", "python");
        TECH_SYNONYMS.put("golang", "go");
        TECH_SYNONYMS.put("go language", "go");

        // Frameworks & Libraries
        TECH_SYNONYMS.put("spring boot", "springboot");
        TECH_SYNONYMS.put("springboot", "springboot");
        TECH_SYNONYMS.put("spring framework", "springboot");
        TECH_SYNONYMS.put("spring mvc", "springboot");
        TECH_SYNONYMS.put("react js", "react");
        TECH_SYNONYMS.put("reactjs", "react");
        TECH_SYNONYMS.put("next js", "nextjs");
        TECH_SYNONYMS.put("nextjs", "nextjs");
        TECH_SYNONYMS.put("angularjs", "angular");
        TECH_SYNONYMS.put("vuejs", "vue");

        // Databases & Cache
        TECH_SYNONYMS.put("postgresql", "postgres");
        TECH_SYNONYMS.put("postgres", "postgres");
        TECH_SYNONYMS.put("mongodb", "mongo");
        TECH_SYNONYMS.put("mongo db", "mongo");
        TECH_SYNONYMS.put("ms sql", "mssql");
        TECH_SYNONYMS.put("microsoft sql", "mssql");
        TECH_SYNONYMS.put("redis cache", "redis");

        // Architecture & Design Patterns
        TECH_SYNONYMS.put("microservices", "microservice");
        TECH_SYNONYMS.put("micro-service", "microservice");
        TECH_SYNONYMS.put("rest api", "restapi");
        TECH_SYNONYMS.put("restful", "restapi");
        TECH_SYNONYMS.put("rest apis", "restapi");
        
        // Clouds & DevOps
        TECH_SYNONYMS.put("kubernetes", "k8s");
        TECH_SYNONYMS.put("docker container", "docker");
        TECH_SYNONYMS.put("amazon web services", "aws");
    }

    private static final Set<String> STOPWORDS = new HashSet<>(Arrays.asList(
            "must", "have", "with", "experience", "in", "and", "or", "to", "the", "using", "of", "for", "a", "an", "at", "by", "from", "on", "as", "is", "are", "was", "were", "be", "been", "being", "that", "which", "who", "whom", "this", "these", "those"
    ));

    /**
     * Generates a unique, standardized SHA-256 hash key for a JD-CV matched pair.
     */
    public String generateKey(String jdRequirement, String cvExperience) {
        String reqPart = extractAndNormalizeTokens(jdRequirement);
        String expPart = extractAndNormalizeTokens(cvExperience);
        String compositeKey = "req:" + reqPart + "|exp:" + expPart;
        return "siminterview:cache:pair:" + sha256(compositeKey);
    }

    private String extractAndNormalizeTokens(String text) {
        if (text == null || text.isBlank()) return "";

        String cleaned = text.toLowerCase().replaceAll("[^a-z0-9\\s]", " ");
        String[] rawTokens = cleaned.split("\\s+");

        List<String> normalizedTokens = new ArrayList<>();

        // Try mapping multi-word synonyms first
        String lowercaseText = text.toLowerCase();
        for (Map.Entry<String, String> entry : TECH_SYNONYMS.entrySet()) {
            if (lowercaseText.contains(entry.getKey())) {
                normalizedTokens.add(entry.getValue());
            }
        }

        // Add regular words if they are not stopwords and not already matched by synonym keys
        for (String token : rawTokens) {
            if (token.length() > 2 && !STOPWORDS.contains(token) && !TECH_SYNONYMS.containsKey(token)) {
                normalizedTokens.add(token);
            }
        }

        // Remove duplicates, sort alphabetically and join
        return normalizedTokens.stream()
                .distinct()
                .sorted()
                .collect(Collectors.joining(","));
    }

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
