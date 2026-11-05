package fit.iuh.config;

import io.netty.channel.ChannelOption;
import lombok.RequiredArgsConstructor;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.http.HttpHeaders;
import org.springframework.http.MediaType;
import org.springframework.http.client.reactive.ReactorClientHttpConnector;
import org.springframework.web.reactive.function.client.ExchangeStrategies;
import org.springframework.web.reactive.function.client.WebClient;
import reactor.netty.http.client.HttpClient;
import reactor.netty.resources.ConnectionProvider;

import java.time.Duration;

/**
 * Spring configuration class that provides pre-configured {@link WebClient} beans
 * for calling external AI APIs with optimized Connection Pooling & Keep-Alive.
 *
 * <p>A pre-configured {@link WebClient} bean is provided:
 * <ul>
 *   <li>{@link #llmWebClient()} — for LLM inference via OpenAI-compatible API</li>
 * </ul>
 *
 * <p>The client is configured with:
 * <ul>
 *   <li>Custom {@link ConnectionProvider} with keep-alive, maxConnections=50, maxIdleTime=60s</li>
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
     * WebClient configured for the LLM Chat Completions API with connection pooling.
     *
     * @return a {@link WebClient} bean named {@code llmWebClient}
     */
    @Bean("llmWebClient")
    public WebClient llmWebClient() {
        ConnectionProvider connectionProvider = ConnectionProvider.builder("llm-connection-pool")
                .maxConnections(50)
                .maxIdleTime(Duration.ofSeconds(60))
                .maxLifeTime(Duration.ofMinutes(5))
                .pendingAcquireTimeout(Duration.ofSeconds(45))
                .evictInBackground(Duration.ofSeconds(120))
                .build();

        HttpClient httpClient = HttpClient.create(connectionProvider)
                .option(ChannelOption.CONNECT_TIMEOUT_MILLIS, 10000)
                .responseTimeout(Duration.ofSeconds(120))
                .keepAlive(true);

        return WebClient.builder()
                .clientConnector(new ReactorClientHttpConnector(httpClient))
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
