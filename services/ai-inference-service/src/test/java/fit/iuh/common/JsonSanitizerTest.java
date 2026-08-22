package fit.iuh.common;

import fit.iuh.common.util.JsonSanitizer;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.assertEquals;

class JsonSanitizerTest {

    @Test
    @DisplayName("Sanitizes pure JSON string")
    void testPureJson() {
        String input = "{\"decision\": \"NEXT_TOPIC\", \"score\": 8}";
        assertEquals("{\"decision\": \"NEXT_TOPIC\", \"score\": 8}", JsonSanitizer.sanitize(input));
    }

    @Test
    @DisplayName("Sanitizes markdown json code block with backticks")
    void testMarkdownCodeBlock() {
        String input = """
                ```json
                {
                  "decision": "FOLLOW_UP",
                  "score": 7
                }
                ```
                """;
        String expected = """
                {
                  "decision": "FOLLOW_UP",
                  "score": 7
                }
                """.trim();
        assertEquals(expected, JsonSanitizer.sanitize(input));
    }

    @Test
    @DisplayName("Sanitizes markdown code block without json keyword")
    void testGenericCodeBlock() {
        String input = """
                ```
                {"decision": "NEXT_TOPIC"}
                ```
                """;
        assertEquals("{\"decision\": \"NEXT_TOPIC\"}", JsonSanitizer.sanitize(input));
    }

    @Test
    @DisplayName("Extracts JSON when LLM adds conversational text before and after")
    void testConversationalPreambleAndPostamble() {
        String input = "Here is the evaluation result you requested:\n{\"decision\": \"NEXT_TOPIC\", \"score\": 9}\nHope this helps!";
        assertEquals("{\"decision\": \"NEXT_TOPIC\", \"score\": 9}", JsonSanitizer.sanitize(input));
    }

    @Test
    @DisplayName("Handles null and blank inputs safely")
    void testNullAndBlank() {
        assertEquals("{}", JsonSanitizer.sanitize(null));
        assertEquals("{}", JsonSanitizer.sanitize("   "));
    }
}
