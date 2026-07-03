package fit.iuh.config;

import lombok.RequiredArgsConstructor;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.http.HttpHeaders;
import org.springframework.http.MediaType;
import org.springframework.web.reactive.function.client.ExchangeStrategies;
import org.springframework.web.reactive.function.client.WebClient;

import java.time.Duration;

/**
 * Spring configuration class that provides pre-configured {@link WebClient} beans
 * for calling external AI APIs.
 *
 * <p>Two separate beans are provided:
 * <ul>
 *   <li>{@link #groqWebClient()} — for CV/JD Markdown standardization via Groq LLM API</li>
 *   <li>{@link #openAiWebClient()} — for embedding generation via OpenAI Embeddings API</li>
 * </ul>
 *
 * <p>Both clients are configured with:
 * <ul>
 *   <li>Base URL from {@link AppProperties}</li>
 *   <li>Authorization Bearer token from API key</li>
 *   <li>Content-Type / Accept headers set to {@code application/json}</li>
 *   <li>Increased memory buffer size (16 MB) to handle large LLM responses</li>
 * </ul>
 */
@Configuration
@RequiredArgsConstructor
public class WebClientConfig {

    private final AppProperties appProperties;

    /**
     * WebClient configured for the LLM Chat Completions API.
     * Endpoint path: {@code /openai/v1/chat/completions}.
     *
     * @return a {@link WebClient} bean named {@code llmWebClient}
     */
    @Bean("llmWebClient")
    public WebClient llmWebClient() {
        return WebClient.builder()
                .baseUrl(appProperties.getLlm().getApiUrl())
                .defaultHeader(HttpHeaders.CONTENT_TYPE, MediaType.APPLICATION_JSON_VALUE)
                .defaultHeader(HttpHeaders.ACCEPT, MediaType.APPLICATION_JSON_VALUE)
                .defaultHeader(
                        HttpHeaders.AUTHORIZATION,
                        "Bearer " + appProperties.getLlm().getApiKey()
                )
                .defaultHeader("HTTP-Referer", "https://github.com/nguyenhoangkhq7/smile-interview")
                .defaultHeader("X-Title", "Smile Interview App")
                .exchangeStrategies(largeBufferStrategy())
                .build();
    }

    /**
     * WebClient configured for the Ollama Local Embeddings API.
     *
     * @return a {@link WebClient} bean named {@code embeddingWebClient}
     */
    @Bean("embeddingWebClient")
    public WebClient embeddingWebClient() {
        return WebClient.builder()
                .baseUrl(appProperties.getOllama().getEmbeddingUrl())
                .defaultHeader(HttpHeaders.CONTENT_TYPE, MediaType.APPLICATION_JSON_VALUE)
                .defaultHeader(HttpHeaders.ACCEPT, MediaType.APPLICATION_JSON_VALUE)
                .exchangeStrategies(largeBufferStrategy())
                .build();
    }

    /**
     * Configures a 16 MB in-memory buffer for {@link WebClient} codec.
     * The default (256 KB) is insufficient for large LLM responses.
     *
     * @return {@link ExchangeStrategies} with 16 MB memory limit
     */
    private ExchangeStrategies largeBufferStrategy() {
        return ExchangeStrategies.builder()
                .codecs(configurer ->
                        configurer.defaultCodecs().maxInMemorySize(16 * 1024 * 1024) // 16 MB
                )
                .build();
    }
}
