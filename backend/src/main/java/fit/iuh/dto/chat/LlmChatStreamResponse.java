package fit.iuh.dto.chat;

import com.fasterxml.jackson.annotation.JsonIgnoreProperties;
import com.fasterxml.jackson.annotation.JsonProperty;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.util.List;

/**
 * DTO for a single Server-Sent Event chunk from an OpenAI-compatible streaming
 * chat completion endpoint ({@code "stream": true}).
 *
 * <p>Each SSE line from Groq/OpenAI looks like:
 * <pre>{@code
 * data: {"id":"...","choices":[{"delta":{"content":"Hello"},"finish_reason":null}]}
 * }</pre>
 *
 * <p>The stream ends with {@code data: [DONE]}, which is not JSON and should be
 * filtered out before deserialization.
 */
@Data
@NoArgsConstructor
@JsonIgnoreProperties(ignoreUnknown = true)
public class LlmChatStreamResponse {

    @JsonProperty("id")
    private String id;

    @JsonProperty("model")
    private String model;

    @JsonProperty("choices")
    private List<StreamChoice> choices;

    // -------------------------------------------------------------------------
    // Convenience accessor
    // -------------------------------------------------------------------------

    /**
     * Extracts the token fragment from the first choice's delta.
     *
     * @return the partial content string, or {@code null} if absent/empty
     */
    public String getDeltaContent() {
        if (choices == null || choices.isEmpty()) return null;
        StreamChoice first = choices.get(0);
        if (first.getDelta() == null) return null;
        return first.getDelta().getContent();
    }

    /**
     * Returns true if the stream has finished (finish_reason is not null).
     */
    public boolean isFinished() {
        if (choices == null || choices.isEmpty()) return false;
        return choices.get(0).getFinishReason() != null;
    }

    // -------------------------------------------------------------------------
    // Nested DTOs
    // -------------------------------------------------------------------------

    @Data
    @NoArgsConstructor
    @JsonIgnoreProperties(ignoreUnknown = true)
    public static class StreamChoice {

        @JsonProperty("index")
        private int index;

        @JsonProperty("delta")
        private Delta delta;

        @JsonProperty("finish_reason")
        private String finishReason;
    }

    @Data
    @NoArgsConstructor
    @JsonIgnoreProperties(ignoreUnknown = true)
    public static class Delta {

        @JsonProperty("role")
        private String role;

        /** The token fragment generated in this chunk. May be null on the last chunk. */
        @JsonProperty("content")
        private String content;
    }
}
