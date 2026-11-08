package fit.iuh.modules.evidence;

import fit.iuh.config.AppProperties;
import jakarta.servlet.http.HttpServletResponse;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Component;
import org.springframework.web.server.ResponseStatusException;

import java.io.IOException;
import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.nio.charset.StandardCharsets;
import java.time.Duration;

/** Streams audio without buffering it in Spring/Jackson. Provider keys stay in Python. */
@Component
public class VoiceAiClient {
    private final HttpClient client;
    private final String baseUrl;
    private final EvidenceJson json;

    public VoiceAiClient(AppProperties properties, EvidenceJson json) {
        this.baseUrl = properties.getAi().getFastapi().getBaseUrl().replaceAll("/+$", "") + "/api/v2/voice/";
        this.json = json;
        // Uvicorn serves HTTP/1.1. JDK's default h2c upgrade can leave it with an
        // unread POST body (422), followed by invalid HTTP/2 frames on keep-alive.
        this.client = HttpClient.newBuilder().version(HttpClient.Version.HTTP_1_1)
                .connectTimeout(Duration.ofSeconds(10)).build();
    }

    public String config() { return request("config", null); }
    public String transcribe(Object payload) { return request("transcribe", payload); }
    public String avatarSession(Object payload) { return request("avatar-session", payload); }

    private HttpRequest build(String operation, Object payload) {
        var builder = HttpRequest.newBuilder(URI.create(baseUrl + operation)).timeout(Duration.ofSeconds(65));
        return payload == null ? builder.GET().build() : builder.header("Content-Type", "application/json")
                .POST(HttpRequest.BodyPublishers.ofString(json.tree(payload).toString(), StandardCharsets.UTF_8)).build();
    }

    private String request(String operation, Object payload) {
        try {
            var response = client.send(build(operation, payload), HttpResponse.BodyHandlers.ofString(StandardCharsets.UTF_8));
            check(response.statusCode(), response.body());
            return response.body();
        } catch (InterruptedException ex) {
            Thread.currentThread().interrupt();
            throw unavailable();
        } catch (IOException ex) { throw unavailable(); }
    }

    public void speech(Object payload, HttpServletResponse output) {
        try {
            var response = client.send(build("speech", payload), HttpResponse.BodyHandlers.ofInputStream());
            try (var input = response.body()) {
                if (response.statusCode() >= 400) {
                    check(response.statusCode(), new String(input.readNBytes(8192), StandardCharsets.UTF_8));
                }
                String type = response.headers().firstValue("Content-Type").orElse("");
                if (!type.startsWith("audio/")) throw new ResponseStatusException(HttpStatus.BAD_GATEWAY, "Dịch vụ không trả về âm thanh.");
                output.setContentType(type);
                output.setHeader("Cache-Control", "no-store");
                output.setHeader("X-Accel-Buffering", "no");
                output.setHeader("Access-Control-Expose-Headers", "X-Audio-Sample-Rate, X-Audio-Format");
                output.setHeader("X-Audio-Sample-Rate", response.headers().firstValue("X-Audio-Sample-Rate").orElse("24000"));
                output.setHeader("X-Audio-Format", response.headers().firstValue("X-Audio-Format").orElse("pcm"));
                byte[] buffer = new byte[8192];
                int size;
                while ((size = input.read(buffer)) != -1) {
                    output.getOutputStream().write(buffer, 0, size);
                    output.flushBuffer();
                }
            } // A disconnected browser closes the upstream stream too.
        } catch (InterruptedException ex) {
            Thread.currentThread().interrupt();
            throw unavailable();
        } catch (IOException ex) {
            if (!output.isCommitted()) throw unavailable();
            // After streaming starts we must not write JSON into the PCM stream.
        }
    }

    private void check(int status, String body) {
        if (status < 400) return;
        String message = "Không thể xử lý giọng nói. Hãy thử lại.";
        try {
            var detail = json.read(body).path("detail");
            if (detail.isTextual()) message = detail.asText();
        } catch (RuntimeException ignored) { /* Keep a safe error for malformed upstream responses. */ }
        var mapped = switch (status) {
            case 422 -> HttpStatus.UNPROCESSABLE_ENTITY;
            case 429 -> HttpStatus.TOO_MANY_REQUESTS;
            case 503 -> HttpStatus.SERVICE_UNAVAILABLE;
            case 504 -> HttpStatus.GATEWAY_TIMEOUT;
            default -> HttpStatus.BAD_GATEWAY;
        };
        throw new ResponseStatusException(mapped, message);
    }

    private ResponseStatusException unavailable() {
        return new ResponseStatusException(HttpStatus.BAD_GATEWAY, "Không kết nối được dịch vụ giọng nói.");
    }
}
