package fit.iuh.modules.admin.aipolicy.service;

import fit.iuh.config.AppProperties;
import fit.iuh.modules.admin.aipolicy.dto.AiPolicyDtos.Check;
import fit.iuh.modules.admin.aipolicy.dto.AiPolicyDtos.Defaults;
import fit.iuh.modules.admin.interviews.dto.AdminInterviewDtos.QualityInput;
import fit.iuh.modules.admin.interviews.dto.AdminInterviewDtos.QualityReview;
import org.springframework.core.ParameterizedTypeReference;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Component;
import org.springframework.web.client.HttpClientErrorException;
import org.springframework.web.client.RestClient;
import org.springframework.web.client.RestClientException;
import org.springframework.http.client.JdkClientHttpRequestFactory;
import org.springframework.web.server.ResponseStatusException;
import java.net.http.HttpClient;
import java.time.Duration;
import java.util.List;

@Component
public class AiPolicySources {
    private final RestClient ai;
    private final RestClient probes;
    private final AiRuntimeKey key;

    public AiPolicySources(AppProperties properties, AiRuntimeKey key) {
        this.key = key;
        var http = HttpClient.newBuilder().version(HttpClient.Version.HTTP_1_1)
                .connectTimeout(Duration.ofSeconds(3)).build();
        String baseUrl = properties.getAi().getFastapi().getBaseUrl();
        ai = client(http, baseUrl, Duration.ofSeconds(5));
        probes = client(http, baseUrl, Duration.ofSeconds(22));
    }

    private static RestClient client(HttpClient http, String baseUrl, Duration timeout) {
        var requests = new JdkClientHttpRequestFactory(http);
        requests.setReadTimeout(timeout);
        return RestClient.builder().baseUrl(baseUrl).requestFactory(requests).build();
    }

    public Defaults defaults() { return get("/internal/runtime/defaults"); }
    public Defaults status() { return get("/internal/runtime/status"); }

    public QualityReview quality(QualityInput input) {
        key.provision();
        try {
            var review = ai.post().uri("/internal/runtime/quality")
                    .header("X-Smile-Runtime-Token", key.token()).body(input).retrieve().body(QualityReview.class);
            if (review != null) return review;
        } catch (RestClientException ex) {
            throw new ResponseStatusException(HttpStatus.BAD_GATEWAY, "Không thể chạy kiểm tra chất lượng AI.", ex);
        }
        throw new ResponseStatusException(HttpStatus.BAD_GATEWAY, "Không nhận được kết quả kiểm tra chất lượng AI.");
    }

    public List<Check> measure() {
        key.provision();
        try {
            return probes.post().uri("/internal/runtime/probe")
                    .header("X-Smile-Runtime-Token", key.token()).retrieve()
                    .body(new ParameterizedTypeReference<List<Check>>() {});
        } catch (HttpClientErrorException.TooManyRequests ex) {
            throw new ResponseStatusException(HttpStatus.TOO_MANY_REQUESTS, "Latency check already running", ex);
        } catch (RestClientException ex) {
            return null;
        }
    }

    private Defaults get(String path) {
        key.provision();
        try {
            return ai.get().uri(path).header("X-Smile-Runtime-Token", key.token()).retrieve().body(Defaults.class);
        } catch (RestClientException ex) {
            return null;
        }
    }

    public boolean reachable() {
        try {
            return ai.get().uri("/health").retrieve().toBodilessEntity().getStatusCode().is2xxSuccessful();
        } catch (RestClientException ex) {
            return false;
        }
    }
}
