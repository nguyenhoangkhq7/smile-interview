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

    /** LLM API configuration. */
    private Llm llm = new Llm();

    /** Assessment module configuration. */
    private Assessment assessment = new Assessment();

    /** Question Bank generation configuration. */
    private QuestionBank questionBank = new QuestionBank();

    /** Chunking configuration. */
    private Chunking chunking = new Chunking();

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

        /** Global default LLM model identifier. */
        private String model;

        /** Global default timeout in seconds for LLM API calls. */
        private int timeoutSeconds = 60;

        /** Global default maximum tokens to generate in LLM response. */
        private int maxTokens = 4096;

        /** Global default temperature for LLM API calls. */
        private double temperature = 0.2;

        /** Global LLM concurrency limit permit count. */
        private int globalConcurrency = 10;

        /** Timeout in seconds waiting for global LLM concurrency permit. */
        private int concurrencyTimeoutSeconds = 60;

        /** Maximum retry attempts for LLM API errors. */
        private int maxRetries = 3;

        /** Sleep duration in milliseconds when encountering HTTP 429 Rate Limit. */
        private long rateLimitSleepMs = 35000;

        /** Task-specific LLM model overrides (legacy compatibility). */
        private TaskModels models = new TaskModels();

        /** Task-specific LLM full configurations (model, maxTokens, timeoutSeconds, temperature). */
        private TaskConfigs tasks = new TaskConfigs();

        public String resolveModel(String taskSpecificModel) {
            if (taskSpecificModel != null && !taskSpecificModel.isBlank()) {
                return taskSpecificModel;
            }
            return model;
        }

        public String resolveModel(TaskConfig taskConfig) {
            if (taskConfig != null && taskConfig.getModel() != null && !taskConfig.getModel().isBlank()) {
                return taskConfig.getModel();
            }
            return model;
        }

        public int resolveMaxTokens(Integer taskSpecificMaxTokens) {
            if (taskSpecificMaxTokens != null && taskSpecificMaxTokens > 0) {
                return taskSpecificMaxTokens;
            }
            return maxTokens > 0 ? maxTokens : 4096;
        }

        public int resolveMaxTokens(TaskConfig taskConfig) {
            if (taskConfig != null && taskConfig.getMaxTokens() != null && taskConfig.getMaxTokens() > 0) {
                return taskConfig.getMaxTokens();
            }
            return resolveMaxTokens((Integer) null);
        }

        public int resolveTimeoutSeconds(Integer taskSpecificTimeout) {
            if (taskSpecificTimeout != null && taskSpecificTimeout > 0) {
                return taskSpecificTimeout;
            }
            return timeoutSeconds > 0 ? timeoutSeconds : 60;
        }

        public int resolveTimeoutSeconds(TaskConfig taskConfig) {
            if (taskConfig != null && taskConfig.getTimeoutSeconds() != null && taskConfig.getTimeoutSeconds() > 0) {
                return taskConfig.getTimeoutSeconds();
            }
            return resolveTimeoutSeconds((Integer) null);
        }

        public double resolveTemperature(Double taskSpecificTemperature) {
            if (taskSpecificTemperature != null && taskSpecificTemperature >= 0.0) {
                return taskSpecificTemperature;
            }
            return temperature >= 0.0 ? temperature : 0.2;
        }

        public double resolveTemperature(TaskConfig taskConfig) {
            if (taskConfig != null && taskConfig.getTemperature() != null && taskConfig.getTemperature() >= 0.0) {
                return taskConfig.getTemperature();
            }
            return resolveTemperature((Double) null);
        }
    }

    @Data
    public static class TaskConfig {
        private String model;
        private Integer maxTokens;
        private Integer timeoutSeconds;
        private Double temperature;
    }

    @Data
    public static class TaskConfigs {
        private TaskConfig standardization = new TaskConfig();
        private TaskConfig metadataExtraction = new TaskConfig();
        private TaskConfig criteriaClassification = new TaskConfig();
        private TaskConfig gateExtraction = new TaskConfig();
        private TaskConfig assessment = new TaskConfig();
        private TaskConfig questionGeneration = new TaskConfig();
        private TaskConfig interviewEvaluation = new TaskConfig();
        private TaskConfig improvement = new TaskConfig();
    }

    @Data
    public static class TaskModels {
        private String standardization;
        private String metadataExtraction;
        private String criteriaClassification;
        private String gateExtraction;
        private String assessment;
        private String questionGeneration;
        private String interviewEvaluation;
    }

    @Data
    public static class Assessment {
        /** Maximum criteria per batch during JD criteria classification. */
        private int classifierBatchSize = 15;

        /** Truncation character limit for JD when performing metadata extraction. */
        private int metadataJdTruncateLength = 600;

        /** Jaccard similarity threshold for ad-hoc criteria deduplication against DB criteria. */
        private double jaccardDedupThreshold = 0.6;
    }

    @Data
    public static class QuestionBank {
        /** Maximum evidence items loaded for question bank generation. */
        private int maxEvidenceItems = 15;

        /** Maximum tokens to generate in LLM response for question generation. */
        private int maxTokens = 8192;

        /** Temperature for question generation (slightly creative). */
        private double temperature = 0.4;

        /** Maximum retry attempts when LLM returns invalid JSON. */
        private int maxRetries = 2;
    }

    @Data
    public static class Chunking {
        /** Jaccard similarity threshold for merging paraphrased CV experience bullets. */
        private double bulletMergeThreshold = 0.15;
    }

    @Data
    public static class Ollama {
        /** Ollama base URL. */
        private String baseUrl = "http://localhost:11434";

        /** Model used for embeddings. */
        private String embeddingModel = "bge-m3";

        /** Vector dimension of the embedding model. */
        private int vectorDimension = 1024;
    }
}
