package fit.iuh.config;

import org.springframework.context.annotation.Configuration;
import org.springframework.http.client.SimpleClientHttpRequestFactory;
import org.springframework.web.client.RestClient;

import java.time.Duration;

/**
 * Shared configuration for HTTP clients connecting to the external AI Service (FastAPI).
 * Configures generous connect and read timeouts (default 180s) to accommodate long LLM/LangGraph inference cycles.
 */
@Configuration
public class AiClientConfig {

    public static SimpleClientHttpRequestFactory createRequestFactory(AppProperties appProperties) {
        int connectTimeout = appProperties != null && appProperties.getAi() != null && appProperties.getAi().getFastapi() != null
                ? appProperties.getAi().getFastapi().getConnectTimeoutSeconds()
                : 15;
        int readTimeout = appProperties != null && appProperties.getAi() != null && appProperties.getAi().getFastapi() != null
                ? appProperties.getAi().getFastapi().getReadTimeoutSeconds()
                : 180;

        SimpleClientHttpRequestFactory requestFactory = new SimpleClientHttpRequestFactory();
        requestFactory.setConnectTimeout(Duration.ofSeconds(connectTimeout));
        requestFactory.setReadTimeout(Duration.ofSeconds(readTimeout));
        return requestFactory;
    }

    public static RestClient createAiRestClient(AppProperties appProperties) {
        String baseUrl = appProperties != null && appProperties.getAi() != null && appProperties.getAi().getFastapi() != null
                ? appProperties.getAi().getFastapi().getBaseUrl()
                : "http://localhost:8000";

        return RestClient.builder()
                .baseUrl(baseUrl)
                .requestFactory(createRequestFactory(appProperties))
                .build();
    }
}
