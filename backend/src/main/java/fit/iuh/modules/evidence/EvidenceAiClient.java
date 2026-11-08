package fit.iuh.modules.evidence;

import com.fasterxml.jackson.databind.JsonNode;
import fit.iuh.config.AiClientConfig;
import fit.iuh.config.AppProperties;
import org.springframework.http.HttpStatus;
import org.springframework.http.MediaType;
import org.springframework.stereotype.Component;
import org.springframework.web.client.RestClient;
import org.springframework.web.client.RestClientResponseException;
import org.springframework.web.server.ResponseStatusException;

@Component
public class EvidenceAiClient {
    private final RestClient client;
    private final EvidenceJson json;

    public EvidenceAiClient(AppProperties properties, EvidenceJson json) {
        this.client = AiClientConfig.createAiRestClient(properties);
        this.json = json;
    }

    public JsonNode compute(String operation, Object payload) {
        try {
            String body = client.post().uri("/api/v2/interview/" + operation)
                    .contentType(MediaType.APPLICATION_JSON).body(json.tree(payload).toString())
                    .retrieve().body(String.class);
            JsonNode result = body == null ? null : json.read(body);
            if (result == null || !result.has("snapshot") || !result.has("public")) {
                throw new ResponseStatusException(HttpStatus.BAD_GATEWAY, "Invalid AI transition");
            }
            return result;
        } catch (RestClientResponseException ex) {
            HttpStatus status = switch (ex.getStatusCode().value()) {
                case 422 -> HttpStatus.UNPROCESSABLE_ENTITY;
                case 503 -> HttpStatus.SERVICE_UNAVAILABLE;
                default -> HttpStatus.BAD_GATEWAY;
            };
            String detail = "Không thể xử lý yêu cầu phỏng vấn. Vui lòng thử lại.";
            try {
                JsonNode error = json.read(ex.getResponseBodyAsString());
                if (error != null && error.path("detail").isTextual()) detail = error.path("detail").asText();
            } catch (IllegalStateException ignored) {
                // Non-JSON upstream errors must not leak transport details to the UI.
            }
            throw new ResponseStatusException(status, detail);
        }
    }
}
