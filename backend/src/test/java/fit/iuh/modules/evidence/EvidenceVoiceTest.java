package fit.iuh.modules.evidence;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.sun.net.httpserver.HttpServer;
import fit.iuh.config.AppProperties;
import fit.iuh.modules.auth.entity.User;
import org.junit.jupiter.api.Test;
import org.springframework.mock.web.MockHttpServletResponse;
import org.springframework.web.server.ResponseStatusException;

import java.net.InetSocketAddress;
import java.nio.charset.StandardCharsets;
import java.util.concurrent.CopyOnWriteArrayList;
import java.util.UUID;
import java.time.Instant;
import org.mockito.ArgumentCaptor;
import java.util.Map;

import static org.assertj.core.api.Assertions.*;
import static org.mockito.Mockito.*;

class EvidenceVoiceTest {
    private final EvidenceService interviews = mock(EvidenceService.class);
    private final VoiceAiClient voice = mock(VoiceAiClient.class);
    private final EvidenceVoiceController controller = new EvidenceVoiceController(interviews, voice);
    private final User user = User.builder().id(UUID.randomUUID()).build();
    private final EvidenceJson json = new EvidenceJson(new ObjectMapper());

    private void state() {
        when(interviews.read("s", user)).thenReturn(json.read("""
            {"state_version":2,"config":{"interaction_mode":"VOICE"},"is_finished":false,"deadline_at":"2099-01-01T00:00:00Z",
             "pending_turn":{"turn_id":"t","question":"Câu hỏi đã lưu"}}
            """));
    }

    @Test void authorizationHappensBeforeVoiceCalls() {
        when(interviews.read("s", user)).thenThrow(new ResponseStatusException(org.springframework.http.HttpStatus.FORBIDDEN));
        assertThatThrownBy(() -> controller.config("s", user)).isInstanceOf(ResponseStatusException.class);
        verifyNoInteractions(voice);
    }

    @Test void staleTranscriptionCannotUsePaidProvider() {
        state();
        assertThatThrownBy(() -> controller.transcribe("s", user,
                new EvidenceVoiceController.Recording("old-turn", 2, "audio")))
                .isInstanceOfSatisfying(ResponseStatusException.class, ex -> assertThat(ex.getStatusCode().value()).isEqualTo(409));
        verifyNoInteractions(voice);
    }

    @Test void textInterviewsCannotCallVoiceProviders() {
        when(interviews.read("s", user)).thenReturn(json.read("{\"config\":{\"interaction_mode\":\"TEXT\"}}"));
        assertThatThrownBy(() -> controller.config("s", user)).isInstanceOf(ResponseStatusException.class);
        assertThatThrownBy(() -> controller.transcribe("s", user,
                new EvidenceVoiceController.Recording("t", 2, "audio"))).isInstanceOf(ResponseStatusException.class);
        assertThatThrownBy(() -> controller.speech("s", user,
                new EvidenceVoiceController.Turn("t", 2), new MockHttpServletResponse())).isInstanceOf(ResponseStatusException.class);
        verifyNoInteractions(voice);
    }

    @Test void speechUsesPersistedQuestionAndNeverClientText() {
        state();
        var output = new MockHttpServletResponse();
        controller.speech("s", user, new EvidenceVoiceController.Turn("t", 2), output);
        verify(voice).speech(java.util.Map.of("text", "Câu hỏi đã lưu"), output);
    }

    @Test void realHttpClientPreservesPcmBytesAndHeaders() throws Exception {
        HttpServer server = HttpServer.create(new InetSocketAddress("127.0.0.1", 0), 0);
        byte[] pcm = {0, 1, -1, 127, 0, -128};
        var upgrades = new CopyOnWriteArrayList<String>();
        var http2Settings = new CopyOnWriteArrayList<String>();
        var bodies = new CopyOnWriteArrayList<String>();
        server.createContext("/api/v2/voice/config", exchange -> {
            upgrades.add(String.valueOf(exchange.getRequestHeaders().getFirst("Upgrade")));
            http2Settings.add(String.valueOf(exchange.getRequestHeaders().getFirst("HTTP2-Settings")));
            exchange.getResponseHeaders().add("Content-Type", "application/json");
            exchange.sendResponseHeaders(200, 0);
            exchange.getResponseBody().write("{}".getBytes(StandardCharsets.UTF_8)); exchange.close();
        });
        server.createContext("/api/v2/voice/transcribe", exchange -> {
            upgrades.add(String.valueOf(exchange.getRequestHeaders().getFirst("Upgrade")));
            http2Settings.add(String.valueOf(exchange.getRequestHeaders().getFirst("HTTP2-Settings")));
            bodies.add(new String(exchange.getRequestBody().readAllBytes(), StandardCharsets.UTF_8));
            exchange.getResponseHeaders().add("Content-Type", "application/json");
            exchange.sendResponseHeaders(200, 0);
            exchange.getResponseBody().write("{\"text\":\"Xin chào\"}".getBytes(StandardCharsets.UTF_8)); exchange.close();
        });
        server.createContext("/api/v2/voice/speech", exchange -> {
            upgrades.add(String.valueOf(exchange.getRequestHeaders().getFirst("Upgrade")));
            http2Settings.add(String.valueOf(exchange.getRequestHeaders().getFirst("HTTP2-Settings")));
            var request = json.read(new String(exchange.getRequestBody().readAllBytes(), StandardCharsets.UTF_8));
            assertThat(request.path("text").asText()).isEqualTo("Câu hỏi");
            exchange.getResponseHeaders().add("Content-Type", "audio/pcm");
            exchange.getResponseHeaders().add("X-Audio-Sample-Rate", "44100");
            exchange.getResponseHeaders().add("X-Audio-Format", "pcm");
            exchange.sendResponseHeaders(200, 0);
            exchange.getResponseBody().write(pcm); exchange.close();
        });
        server.start();
        try {
            var properties = new AppProperties();
            properties.getAi().getFastapi().setBaseUrl("http://127.0.0.1:" + server.getAddress().getPort());
            var output = new MockHttpServletResponse();
            var client = new VoiceAiClient(properties, json);
            assertThat(client.config()).isEqualTo("{}");
            assertThat(json.read(client.transcribe(java.util.Map.of("audio", "base64-recording"))).path("text").asText())
                    .isEqualTo("Xin chào");
            client.speech(java.util.Map.of("text", "Câu hỏi"), output);
            assertThat(upgrades).containsExactly("null", "null", "null");
            assertThat(http2Settings).containsExactly("null", "null", "null");
            assertThat(json.read(bodies.getFirst()).path("audio").asText()).isEqualTo("base64-recording");
            assertThat(output.getContentAsByteArray()).isEqualTo(pcm);
            assertThat(output.getHeader("X-Audio-Sample-Rate")).isEqualTo("44100");
            assertThat(output.getContentType()).isEqualTo("audio/pcm");
        } finally { server.stop(0); }
    }

    @Test void speechReadsPersistedFeedbackAndBridgeBeforeTheNextQuestionInOneRequest() {
        when(interviews.read("s", user)).thenReturn(json.read("""
            {"state_version":2,"config":{"interaction_mode":"VOICE"},"is_finished":false,"deadline_at":"2099-01-01T00:00:00Z",
             "pending_turn":{"turn_id":"t","question":"Bạn kiểm tra dữ liệu ra sao?",
              "introduction":"Bạn đã nêu cách đọc dữ liệu.\\n\\nMình muốn làm rõ thêm một ý nhé."}}
            """));
        var output = new MockHttpServletResponse();
        controller.speech("s", user, new EvidenceVoiceController.Turn("t", 2), output);
        verify(voice, times(1)).speech(java.util.Map.of("text",
                "Bạn đã nêu cách đọc dữ liệu.\n\nMình muốn làm rõ thêm một ý nhé.\n\nBạn kiểm tra dữ liệu ra sao?"), output);
    }

    @Test void staleSpeechCannotReadFeedbackFromAnotherTurn() {
        state();
        assertThatThrownBy(() -> controller.speech("s", user,
                new EvidenceVoiceController.Turn("old-turn", 2), new MockHttpServletResponse()))
                .isInstanceOfSatisfying(ResponseStatusException.class, ex -> assertThat(ex.getStatusCode().value()).isEqualTo(409));
        verifyNoInteractions(voice);
    }

    @Test void simliSessionChecksOwnerModeAndTurnBeforeToken() {
        state();
        assertThatThrownBy(() -> controller.avatarSession("s", user,
                new EvidenceVoiceController.Turn("old", 2), new MockHttpServletResponse()))
                .isInstanceOf(ResponseStatusException.class);
        verifyNoInteractions(voice);
        when(interviews.read("s", user)).thenReturn(json.read("{\"config\":{\"interaction_mode\":\"TEXT\"}}"));
        assertThatThrownBy(() -> controller.avatarSession("s", user,
                new EvidenceVoiceController.Turn("t", 2), new MockHttpServletResponse()))
                .isInstanceOf(ResponseStatusException.class);
        verifyNoInteractions(voice);
        when(interviews.read("s", user)).thenThrow(new ResponseStatusException(org.springframework.http.HttpStatus.FORBIDDEN));
        assertThatThrownBy(() -> controller.avatarSession("s", user,
                new EvidenceVoiceController.Turn("t", 2), new MockHttpServletResponse()))
                .isInstanceOf(ResponseStatusException.class);
        verifyNoInteractions(voice);
    }

    @Test void simliDurationIsDerivedFromInterviewDeadline() {
        var state = json.read("""
            {"state_version":2,"config":{"interaction_mode":"VOICE"},"is_finished":false,
             "pending_turn":{"turn_id":"t"}}
            """);
        ((com.fasterxml.jackson.databind.node.ObjectNode) state).put("deadline_at", Instant.now().plusSeconds(120).toString());
        when(interviews.read("s", user)).thenReturn(state);
        when(voice.avatarSession(any())).thenReturn("{\"session_token\":\"temporary\"}");
        var response = new MockHttpServletResponse();
        assertThat(controller.avatarSession("s", user, new EvidenceVoiceController.Turn("t", 2), response)).contains("temporary");
        var payload = ArgumentCaptor.forClass(Object.class);
        verify(voice).avatarSession(payload.capture());
        var length = ((Number) ((Map<?, ?>) payload.getValue()).get("max_session_length")).longValue();
        assertThat(length).isBetween(115L, 120L);
        assertThat(response.getHeader("Cache-Control")).isEqualTo("no-store");
    }
}
