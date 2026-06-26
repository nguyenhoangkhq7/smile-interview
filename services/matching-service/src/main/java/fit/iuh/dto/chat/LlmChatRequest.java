package fit.iuh.dto.chat;

import com.fasterxml.jackson.annotation.JsonInclude;
import com.fasterxml.jackson.annotation.JsonProperty;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.util.List;
import java.util.Map;

@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
@JsonInclude(JsonInclude.Include.NON_NULL)
public class LlmChatRequest {

    /** The model identifier (provider-specific, e.g., {@code llama3-70b-8192} or {@code gpt-4o}). */
    @JsonProperty("model")
    private String model;

    /** The ordered list of conversation messages. */
    @JsonProperty("messages")
    private List<Message> messages;

    /**
     * Maximum tokens to generate in the response.
     * Default 4096 supports detailed structured Markdown output.
     */
    @JsonProperty("max_tokens")
    @Builder.Default
    private int maxTokens = 4096;

    /**
     * Response randomness: 0.0 = deterministic, 2.0 = very creative.
     * Default 0.3 for structured, consistent document outputs.
     */
    @JsonProperty("temperature")
    @Builder.Default
    private double temperature = 0.0;

    /**
     * Whether to stream the response token-by-token.
     * Must be explicitly set to {@code false} for standard blocking calls — some
     * providers (Groq, OpenAI) will return an empty {@code content} field if this
     * field is absent from the request body.
     */
    @JsonProperty("stream")
    @Builder.Default
    private boolean stream = false;

    /**
     * Optional JSON mode enforcement. Set to {@code Map.of("type", "json_object")}
     * to force the LLM to return a valid JSON object (Groq / OpenAI compatible).
     *
     * <p>When {@code null} (the default), this field is omitted from the request
     * body entirely ({@code @JsonInclude(NON_NULL)}) so existing calls are unaffected.
     */
    @JsonProperty("response_format")
    private Map<String, String> responseFormat;

    // -------------------------------------------------------------------------
    // Nested message class
    // -------------------------------------------------------------------------

    /**
     * A single chat turn. Roles follow the OpenAI convention:
     * {@code "system"}, {@code "user"}, or {@code "assistant"}.
     */
    @Data
    @Builder
    @NoArgsConstructor
    @AllArgsConstructor
    public static class Message {

        @JsonProperty("role")
        private String role;

        @JsonProperty("content")
        private String content;

        /** Factory: creates a system-role message (holds the ATS prompt). */
        public static Message system(String content) {
            return new Message("system", content);
        }

        /** Factory: creates a user-role message (holds the raw CV/JD text). */
        public static Message user(String content) {
            return new Message("user", content);
        }
    }
}
