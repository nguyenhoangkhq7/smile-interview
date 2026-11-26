package fit.iuh.config;

import org.springframework.context.annotation.Configuration;
import org.springframework.http.client.ClientHttpRequestFactory;
import org.springframework.http.client.JdkClientHttpRequestFactory;
import org.springframework.web.client.RestClient;

import java.net.http.HttpClient;
import java.time.Duration;

/**
 * Shared configuration for HTTP clients connecting to the external AI Service (FastAPI).
 * Uses a pooled JDK HttpClient pinned to HTTP/1.1 with generous connect and read timeouts (default 180s).
 */
@Configuration
public class AiClientConfig {

    public static ClientHttpRequestFactory createRequestFactory(AppProperties appProperties) {
        int connectTimeout = appProperties != null && appProperties.getAi() != null && appProperties.getAi().getFastapi() != null
                ? appProperties.getAi().getFastapi().getConnectTimeoutSeconds()
                : 15;
        int readTimeout = appProperties != null && appProperties.getAi() != null && appProperties.getAi().getFastapi() != null
                ? appProperties.getAi().getFastapi().getReadTimeoutSeconds()
                : 180;

        HttpClient httpClient = HttpClient.newBuilder()
                .version(HttpClient.Version.HTTP_1_1)
                .connectTimeout(Duration.ofSeconds(connectTimeout))
                .build();
        JdkClientHttpRequestFactory requestFactory = new JdkClientHttpRequestFactory(httpClient);
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
