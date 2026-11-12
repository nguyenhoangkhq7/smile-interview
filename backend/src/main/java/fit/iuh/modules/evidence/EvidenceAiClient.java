package fit.iuh.modules.evidence;

import com.fasterxml.jackson.databind.JsonNode;
import fit.iuh.config.AiClientConfig;
import fit.iuh.config.AppProperties;
import org.springframework.http.HttpStatus;
import org.springframework.http.MediaType;
import org.springframework.stereotype.Component;
import org.springframework.web.client.RestClient;
import org.springframework.web.client.RestClientResponseException;
import org.springframework.web.client.RestClientException;
import org.springframework.web.server.ResponseStatusException;
import lombok.extern.slf4j.Slf4j;
import java.util.concurrent.TimeUnit;

@Component @Slf4j
public class EvidenceAiClient {
    private final RestClient client;
    private final EvidenceJson json;

    public EvidenceAiClient(AppProperties properties, EvidenceJson json) {
        this.client = AiClientConfig.createAiRestClient(properties);
        this.json = json;
    }

    public JsonNode compute(String operation, Object payload) {
        JsonNode request = json.tree(payload);
        String sessionId = request.path("session_id").asText(request.path("snapshot").path("session_id").asText("-"));
        long started = System.nanoTime();
        log.info("Interview AI request started session_id={} operation={}", sessionId, operation);
        try {
            String body = client.post().uri("/api/v2/interview/" + operation)
                    .contentType(MediaType.APPLICATION_JSON).body(request.toString())
                    .retrieve().body(String.class);
            JsonNode result = body == null ? null : json.read(body);
            if (result == null || !result.has("snapshot") || !result.has("public")) {
                throw new ResponseStatusException(HttpStatus.BAD_GATEWAY, "Invalid AI transition");
            }
            log.info("Interview AI request completed session_id={} operation={} elapsed_ms={}",
                    sessionId, operation, TimeUnit.NANOSECONDS.toMillis(System.nanoTime() - started));
            return result;
        } catch (RestClientResponseException ex) {
            log.warn("Interview AI request failed session_id={} operation={} upstream_status={} elapsed_ms={}",
                    sessionId, operation, ex.getStatusCode().value(), TimeUnit.NANOSECONDS.toMillis(System.nanoTime() - started));
            HttpStatus status = switch (ex.getStatusCode().value()) {
                case 422 -> HttpStatus.UNPROCESSABLE_ENTITY;
                case 429 -> HttpStatus.SERVICE_UNAVAILABLE;
                case 503 -> HttpStatus.SERVICE_UNAVAILABLE;
                case 504 -> HttpStatus.GATEWAY_TIMEOUT;
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
        } catch (RestClientException ex) {
            log.warn("Interview AI transport failed session_id={} operation={} error_type={} elapsed_ms={}",
                    sessionId, operation, ex.getClass().getSimpleName(), TimeUnit.NANOSECONDS.toMillis(System.nanoTime() - started));
            for (Throwable cause = ex; cause != null; cause = cause.getCause()) {
                if (cause instanceof java.net.SocketTimeoutException) {
                    throw new ResponseStatusException(HttpStatus.GATEWAY_TIMEOUT,
                            "Chuẩn bị phỏng vấn mất quá nhiều thời gian. Vui lòng thử lại; dữ liệu hồ sơ của bạn vẫn được giữ nguyên.", ex);
                }
            }
            throw new ResponseStatusException(HttpStatus.BAD_GATEWAY,
                    "Không thể kết nối dịch vụ phỏng vấn. Vui lòng thử lại.", ex);
        }
    }
}
