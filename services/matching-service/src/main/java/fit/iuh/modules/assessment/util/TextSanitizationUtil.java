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
        String cleaned = rawResponse
                .replaceAll("(?s)^```(?:json)?\\s*", "")
                .replaceAll("(?s)\\s*```$", "")
                .strip();

        int firstBrace = cleaned.indexOf('{');
        int firstBracket = cleaned.indexOf('[');
        int start = -1;
        if (firstBrace != -1 && firstBracket != -1) {
            start = Math.min(firstBrace, firstBracket);
        } else if (firstBrace != -1) {
            start = firstBrace;
        } else if (firstBracket != -1) {
            start = firstBracket;
        }

        int lastBrace = cleaned.lastIndexOf('}');
        int lastBracket = cleaned.lastIndexOf(']');
        int end = Math.max(lastBrace, lastBracket);

        if (start != -1 && end != -1 && end > start) {
            return cleaned.substring(start, end + 1).strip();
        }
        return cleaned;
    }
}
