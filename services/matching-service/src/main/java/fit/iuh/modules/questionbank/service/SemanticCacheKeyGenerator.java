package fit.iuh.modules.questionbank.service;

import fit.iuh.modules.assessment.entity.SeniorityLevel;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Component;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.util.Locale;

@Slf4j
@Component
public class SemanticCacheKeyGenerator {

    private static final String KEY_PREFIX = "siminterview:cache:";

    public String generateKey(Long criteriaId, String status, SeniorityLevel level) {
        String safeStatus = status != null ? status.toLowerCase(Locale.ROOT).strip() : "unknown";
        String safeLevel = level != null ? level.name() : "MID";
        return KEY_PREFIX + "item:" + criteriaId + ":" + safeStatus + ":" + safeLevel;
    }

    public String generateKeyForAdHoc(String criteriaName, String status, SeniorityLevel level) {
        String normalizedName = criteriaName != null ? criteriaName.toLowerCase(Locale.ROOT).strip() : "adhoc";
        String safeStatus = status != null ? status.toLowerCase(Locale.ROOT).strip() : "unknown";
        String safeLevel = level != null ? level.name() : "MID";

        String nameHash = sha256Hex(normalizedName).substring(0, 16);
        return KEY_PREFIX + "adhoc:" + nameHash + ":" + safeStatus + ":" + safeLevel;
    }

    public String generateCacheKey(String type, Long criteriaId, String status, SeniorityLevel level, String difficulty) {
        String safeType = type != null ? type.toLowerCase(Locale.ROOT).strip() : "general";
        String safeStatus = status != null ? status.toLowerCase(Locale.ROOT).strip() : "unknown";
        String safeLevel = level != null ? level.name() : "MID";
        String safeDiff = difficulty != null ? difficulty.toLowerCase(Locale.ROOT).strip() : "medium";
        String cid = criteriaId != null ? String.valueOf(criteriaId) : "adhoc";

        return KEY_PREFIX + safeType + ":" + cid + ":" + safeStatus + ":" + safeLevel + ":" + safeDiff;
    }

    private String sha256Hex(String input) {
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
            log.error("SHA-256 algorithm not found", e);
            return String.valueOf(input.hashCode());
        }
    }
}
