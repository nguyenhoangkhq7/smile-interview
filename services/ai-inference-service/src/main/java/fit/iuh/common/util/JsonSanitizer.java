package fit.iuh.common.util;

import java.util.regex.Matcher;
import java.util.regex.Pattern;

/**
 * Utility for sanitizing and extracting JSON payloads from LLM outputs.
 * LLMs frequently wrap JSON in Markdown code fences (e.g. ```json ... ```)
 * or include conversational preambles/postambles.
 */
public final class JsonSanitizer {

    private static final Pattern CODE_BLOCK_PATTERN =
            Pattern.compile("```(?:json)?\\s*([\\s\\S]*?)\\s*```", Pattern.CASE_INSENSITIVE);

    private JsonSanitizer() {
        // Prevent instantiation
    }

    /**
     * Extracts and sanitizes clean JSON from raw LLM output text.
     *
     * @param rawText the raw output from the LLM
     * @return clean JSON string ready for Jackson parsing
     */
    public static String sanitize(String rawText) {
        if (rawText == null || rawText.isBlank()) {
            return "{}";
        }

        String content = rawText.trim();

        // 1. Check for markdown code fences: ```json ... ``` or ``` ... ```
        Matcher matcher = CODE_BLOCK_PATTERN.matcher(content);
        if (matcher.find()) {
            content = matcher.group(1).trim();
        }

        // 2. Locate boundaries of the outermost JSON Object or Array
        int firstBrace = content.indexOf('{');
        int lastBrace = content.lastIndexOf('}');

        if (firstBrace != -1 && lastBrace != -1 && lastBrace > firstBrace) {
            return content.substring(firstBrace, lastBrace + 1).trim();
        }

        int firstBracket = content.indexOf('[');
        int lastBracket = content.lastIndexOf(']');
        if (firstBracket != -1 && lastBracket != -1 && lastBracket > firstBracket) {
            return content.substring(firstBracket, lastBracket + 1).trim();
        }

        return content;
    }
}
