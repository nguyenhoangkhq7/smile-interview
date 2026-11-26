package fit.iuh.modules.admin.aipolicy.service;

import fit.iuh.config.AppProperties;
import fit.iuh.modules.admin.aipolicy.dto.AiPolicyDtos.Defaults;
import org.springframework.stereotype.Component;
import org.springframework.web.client.RestClient;
import org.springframework.web.client.RestClientException;
import org.springframework.http.client.JdkClientHttpRequestFactory;
import java.net.http.HttpClient;
import java.time.Duration;

@Component
public class AiPolicySources {
    private final RestClient ai;
    private final AiRuntimeKey key;

    public AiPolicySources(AppProperties properties, AiRuntimeKey key) {
        this.key = key;
        var http = HttpClient.newBuilder().version(HttpClient.Version.HTTP_1_1)
                .connectTimeout(Duration.ofSeconds(3)).build();
        var requests = new JdkClientHttpRequestFactory(http);
        requests.setReadTimeout(Duration.ofSeconds(5));
        ai = RestClient.builder().baseUrl(properties.getAi().getFastapi().getBaseUrl()).requestFactory(requests).build();
    }

    public Defaults defaults() { return get("/internal/runtime/defaults"); }
    public Defaults status() { return get("/internal/runtime/status"); }

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
