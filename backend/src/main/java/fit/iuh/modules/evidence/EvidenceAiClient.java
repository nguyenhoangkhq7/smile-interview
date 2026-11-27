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
                JsonNode errorDetail = error == null ? null : error.path("detail");
                if (errorDetail != null && errorDetail.isTextual()) {
                    detail = errorDetail.asText();
                } else if (errorDetail != null && errorDetail.isArray() && ex.getStatusCode().value() == 422) {
                    log.warn("Interview AI validation failed session_id={} operation={} errors={}",
                            sessionId, operation, summarizeValidationErrors(errorDetail));
                }
            } catch (IllegalStateException ignored) {
                // Non-JSON upstream errors must not leak transport details to the UI.
            }
            throw new ResponseStatusException(status, detail);
        } catch (RestClientException ex) {
            log.warn("Interview AI transport failed session_id={} operation={} error_type={} elapsed_ms={}",
                    sessionId, operation, ex.getClass().getSimpleName(), TimeUnit.NANOSECONDS.toMillis(System.nanoTime() - started));
            for (Throwable cause = ex; cause != null; cause = cause.getCause()) {
                if (cause instanceof java.net.SocketTimeoutException
                        || cause instanceof java.net.http.HttpTimeoutException) {
                    throw new ResponseStatusException(HttpStatus.GATEWAY_TIMEOUT,
                            "Chuẩn bị phỏng vấn mất quá nhiều thời gian. Vui lòng thử lại; dữ liệu hồ sơ của bạn vẫn được giữ nguyên.", ex);
                }
            }
            throw new ResponseStatusException(HttpStatus.BAD_GATEWAY,
                    "Không thể kết nối dịch vụ phỏng vấn. Vui lòng thử lại.", ex);
        }
    }

    public JsonNode runCode(Object payload) {
        JsonNode request = json.tree(payload);
        String sessionId = request.path("snapshot").path("session_id").asText("-");
        long started = System.nanoTime();
        try {
            String body = client.post().uri("/api/v2/interview/run-code")
                    .contentType(MediaType.APPLICATION_JSON).body(request.toString())
                    .retrieve().body(String.class);
            JsonNode result = body == null ? null : json.read(body);
            if (result == null || !result.has("language")) {
                throw new ResponseStatusException(HttpStatus.BAD_GATEWAY, "Invalid AI code execution response");
            }
            log.info("Interview AI run-code completed session_id={} elapsed_ms={}",
                    sessionId, TimeUnit.NANOSECONDS.toMillis(System.nanoTime() - started));
            return result;
        } catch (RestClientResponseException ex) {
            HttpStatus status = ex.getStatusCode().value() == 422
                    ? HttpStatus.UNPROCESSABLE_ENTITY : HttpStatus.BAD_GATEWAY;
            String detail = "Không thể chạy thử mã nguồn. Vui lòng thử lại.";
            try {
                JsonNode error = json.read(ex.getResponseBodyAsString());
                if (error != null && error.path("detail").isTextual()) detail = error.path("detail").asText();
            } catch (IllegalStateException ignored) {}
            throw new ResponseStatusException(status, detail);
        } catch (RestClientException ex) {
            throw new ResponseStatusException(HttpStatus.BAD_GATEWAY,
                    "Không thể kết nối dịch vụ chạy thử mã nguồn.", ex);
        }
    }

    public JsonNode blueprint(Object payload) {
        JsonNode request = json.tree(payload);
        long started = System.nanoTime();
        log.info("Interview AI blueprint request started skills={}", request.path("skills").size());
        try {
            String body = client.post().uri("/api/v2/interview/blueprint")
                    .contentType(MediaType.APPLICATION_JSON).body(request.toString())
                    .retrieve().body(String.class);
            JsonNode result = body == null ? null : json.read(body);
            if (result == null || !result.path("objectives").isArray() || result.path("objectives").isEmpty()) {
                throw new ResponseStatusException(HttpStatus.BAD_GATEWAY, "Invalid AI blueprint");
            }
            log.info("Interview AI blueprint request completed objectives={} elapsed_ms={}",
                    result.path("objectives").size(), TimeUnit.NANOSECONDS.toMillis(System.nanoTime() - started));
            return result;
        } catch (RestClientException ex) {
            log.warn("Interview AI blueprint request failed error_type={} elapsed_ms={}",
                    ex.getClass().getSimpleName(), TimeUnit.NANOSECONDS.toMillis(System.nanoTime() - started));
            throw new ResponseStatusException(HttpStatus.BAD_GATEWAY,
                    "Không thể chuẩn bị sẵn blueprint phỏng vấn.", ex);
        }
    }

    private static String summarizeValidationErrors(JsonNode details) {
        var summary = new java.util.ArrayList<String>();
        for (JsonNode item : details) {
            if (summary.size() >= 5) break;
            var loc = new java.util.ArrayList<String>();
            for (JsonNode part : item.path("loc")) loc.add(part.asText());
            String path = loc.isEmpty() ? "<root>" : String.join(".", loc);
            summary.add(path + ":" + item.path("type").asText("invalid"));
        }
        return String.join(", ", summary);
    }
}
