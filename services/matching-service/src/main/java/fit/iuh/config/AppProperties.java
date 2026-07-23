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



    /** Question Bank generation configuration. */
    private QuestionBank questionBank = new QuestionBank();

    /** Local Ollama configuration. */
    private Ollama ollama = new Ollama();

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
    public static class QuestionBank {
        /** Maximum tokens to generate in LLM response for question generation. */
        private int maxTokens = 8192;

        /** Temperature for question generation (slightly creative). */
        private double temperature = 0.4;

        /** Maximum retry attempts when LLM returns invalid JSON. */
        private int maxRetries = 2;
    }

    @Data
    public static class Ollama {
        /** Ollama base URL. */
        private String baseUrl = "http://localhost:11434";

        /** Model used for embeddings. */
        private String embeddingModel = "bge-m3";

        /** Small model used for contextual enrichment. */
        private String contextModel = "qwen2.5:3b-instruct";

        /** Vector dimension of the embedding model. */
        private int vectorDimension = 1024;
    }
}
