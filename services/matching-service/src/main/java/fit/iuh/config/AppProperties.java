package fit.iuh.config;

import lombok.Data;
import org.springframework.boot.context.properties.ConfigurationProperties;
import org.springframework.context.annotation.Configuration;
import org.springframework.validation.annotation.Validated;

@Data
@Validated
@Configuration
@ConfigurationProperties(prefix = "app")
public class AppProperties {

    /** LLM API configuration (used for CV/JD standardization). */
    private Llm llm = new Llm();

    /** Local Ollama configuration for generating embeddings. */
    private Ollama ollama = new Ollama();

    /** LangChain4j text chunking configuration. */
    private Chunking chunking = new Chunking();

    /** Question Bank generation configuration. */
    private QuestionBank questionBank = new QuestionBank();

    // -------------------------------------------------------------------------
    // Nested config classes
    // -------------------------------------------------------------------------

    @Data
    public static class Llm {
        /** API key. */
        private String apiKey;

        /** API base URL. */
        private String apiUrl;

        /** Endpoint path for chat completions. */
        private String chatPath = "/openai/v1/chat/completions";

        /** LLM model identifier. */
        private String model;

        /** Timeout in seconds for LLM API calls. */
        private int timeoutSeconds;

        /** Maximum tokens to generate in LLM response. */
        private int maxTokens;
    }

    @Data
    public static class Ollama {
        /** Ollama base URL, e.g. http://host.docker.internal:11434 */
        private String embeddingUrl;

        /** Ollama embedding model name. */
        private String embeddingModel;

        /** Timeout in seconds for Ollama API calls. */
        private int timeoutSeconds;
    }

    @Data
    public static class Chunking {
        /** Maximum token count per text chunk. */
        private int maxTokens;

        /** Number of overlapping tokens between consecutive chunks. */
        private int overlapTokens;
    }

    @Data
    public static class QuestionBank {
        /** Maximum tokens to generate in LLM response for question generation. */
        private int maxTokens = 8192;

        /** Temperature for question generation (slightly creative). */
        private double temperature = 0.4;

        /** Maximum retry attempts when LLM returns invalid JSON. */
        private int maxRetries = 2;
    }
}
