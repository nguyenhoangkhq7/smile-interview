package fit.iuh.modules.evidence;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.sun.net.httpserver.HttpServer;
import fit.iuh.config.AppProperties;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.springframework.boot.test.system.CapturedOutput;
import org.springframework.boot.test.system.OutputCaptureExtension;
import java.net.InetSocketAddress;
import java.nio.charset.StandardCharsets;
import java.util.Map;
import java.util.concurrent.atomic.AtomicReference;
import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

@ExtendWith(OutputCaptureExtension.class)
class EvidenceAiClientTest {
    @Test void upstreamRateLimitIsRetriableWithoutLeakingProviderDetails(CapturedOutput output) throws Exception {
        HttpServer server = HttpServer.create(new InetSocketAddress("127.0.0.1", 0), 0);
        String message = "Dịch vụ AI đang giới hạn yêu cầu. Vui lòng thử lại.";
        server.createContext("/api/v2/interview/start", exchange -> {
            exchange.getRequestBody().readAllBytes();
            byte[] body = new ObjectMapper().writeValueAsBytes(Map.of("detail", message));
            exchange.getResponseHeaders().add("Content-Type", "application/json; charset=utf-8");
            exchange.sendResponseHeaders(429, body.length);
            exchange.getResponseBody().write(body); exchange.close();
        });
        server.start();
        try {
            AppProperties properties = new AppProperties();
            properties.getAi().getFastapi().setBaseUrl("http://127.0.0.1:" + server.getAddress().getPort());
            var client = new EvidenceAiClient(properties, new EvidenceJson(new ObjectMapper()));
            assertThatThrownBy(() -> client.compute("start", Map.of("session_id", "rate-limited-test")))
                    .isInstanceOfSatisfying(org.springframework.web.server.ResponseStatusException.class, ex -> {
                        assertThat(ex.getStatusCode().value()).isEqualTo(503);
                        assertThat(ex.getReason()).isEqualTo(message);
                    });
            assertThat(output).contains("session_id=rate-limited-test", "upstream_status=429");
        } finally { server.stop(0); }
    }

    @Test void slowStartReturnsAnActionableGatewayTimeout() throws Exception {
        HttpServer server = HttpServer.create(new InetSocketAddress("127.0.0.1", 0), 0);
        server.createContext("/api/v2/interview/start", exchange -> {
            exchange.getRequestBody().readAllBytes();
            try { Thread.sleep(1800); }
            catch (InterruptedException ex) { Thread.currentThread().interrupt(); }
            finally { exchange.close(); }
        });
        server.start();
        try {
            AppProperties properties = new AppProperties();
            properties.getAi().getFastapi().setBaseUrl("http://127.0.0.1:" + server.getAddress().getPort());
            properties.getAi().getFastapi().setReadTimeoutSeconds(1);
            var client = new EvidenceAiClient(properties, new EvidenceJson(new ObjectMapper()));
            assertThatThrownBy(() -> client.compute("start", Map.of("test", true)))
                    .isInstanceOfSatisfying(org.springframework.web.server.ResponseStatusException.class, ex -> {
                        assertThat(ex.getStatusCode().value()).isEqualTo(504);
                        assertThat(ex.getReason()).contains("Vui lòng thử lại", "vẫn được giữ nguyên");
                    });
        } finally { server.stop(0); }
    }

    @Test void invalidJudgeOutputIsPresentedAsRetriableServiceFailure() throws Exception {
        HttpServer server = HttpServer.create(new InetSocketAddress("127.0.0.1", 0), 0);
        String message = "AI chưa thể chấm câu trả lời một cách hợp lệ. Vui lòng thử gửi lại.";
        server.createContext("/api/v2/interview/respond", exchange -> {
            exchange.getRequestBody().readAllBytes();
            byte[] body = new ObjectMapper().writeValueAsBytes(Map.of("detail", message));
            exchange.getResponseHeaders().add("Content-Type", "application/json; charset=utf-8");
            exchange.sendResponseHeaders(503, body.length);
            exchange.getResponseBody().write(body); exchange.close();
        });
        server.start();
        try {
            AppProperties properties = new AppProperties();
            properties.getAi().getFastapi().setBaseUrl("http://127.0.0.1:" + server.getAddress().getPort());
            var client = new EvidenceAiClient(properties, new EvidenceJson(new ObjectMapper()));
            assertThatThrownBy(() -> client.compute("respond", Map.of("test", true)))
                    .isInstanceOfSatisfying(org.springframework.web.server.ResponseStatusException.class, ex -> {
                        assertThat(ex.getStatusCode().value()).isEqualTo(503);
                        assertThat(ex.getReason()).isEqualTo(message);
                    });
        } finally { server.stop(0); }
    }

    @Test void jsonTreeSurvivesTheRealHttpConverters(CapturedOutput output) throws Exception {
        var json = new EvidenceJson(new ObjectMapper());
        var received = new AtomicReference<String>();
        HttpServer server = HttpServer.create(new InetSocketAddress("127.0.0.1", 0), 0);
        server.createContext("/api/v2/interview/start", exchange -> {
            received.set(new String(exchange.getRequestBody().readAllBytes(), StandardCharsets.UTF_8));
            byte[] body = "{\"snapshot\":{\"state_version\":1},\"public\":{\"state_version\":1}}".getBytes(StandardCharsets.UTF_8);
            exchange.getResponseHeaders().add("Content-Type", "application/json");
            exchange.sendResponseHeaders(200, body.length);
            exchange.getResponseBody().write(body); exchange.close();
        });
        server.start();
        try {
            AppProperties properties = new AppProperties();
            properties.getAi().getFastapi().setBaseUrl("http://127.0.0.1:" + server.getAddress().getPort());
            var payload = json.tree(Map.of("session_id", "test", "config", EvidenceDtos.Config.defaults(),
                    "document", "PRIVATE_CV_SENTINEL"));
            var result = new EvidenceAiClient(properties, json).compute("start", payload);
            assertThat(json.read(received.get())).isEqualTo(payload);
            assertThat(result.path("public").path("state_version").asInt()).isEqualTo(1);
            assertThat(output).contains("Interview AI request started session_id=test", "Interview AI request completed session_id=test")
                    .doesNotContain("PRIVATE_CV_SENTINEL");
        } finally { server.stop(0); }
    }
}
