package fit.iuh.modules.assessment.util;

import java.util.Locale;

public final class TextSanitizationUtil {

    private TextSanitizationUtil() {
        throw new UnsupportedOperationException("Utility class");
    }

    public static String sanitizeCyrillicScript(String input) {
        if (input == null || input.isBlank()) {
            return input;
        }
        if (input.matches(".*[\\u0400-\\u04FF].*")) {
            return input.replaceAll("[\\u0400-\\u04FF]", "").trim();
        }
        return input;
    }

    public static String sanitizeLanguageText(String text) {
        if (text == null || text.isBlank()) {
            return text;
        }
        return sanitizeCyrillicScript(text);
    }

    public static String extractCleanJson(String rawResponse) {
        if (rawResponse == null || rawResponse.isBlank()) {
            return "";
        }
        return rawResponse
                .replaceAll("(?s)^```(?:json)?\\s*", "")
                .replaceAll("(?s)\\s*```$", "")
                .strip();
    }
}
