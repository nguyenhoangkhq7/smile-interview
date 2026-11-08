package fit.iuh.modules.evidence;

import com.fasterxml.jackson.databind.JsonNode;
import fit.iuh.modules.auth.entity.User;
import jakarta.servlet.http.HttpServletResponse;
import jakarta.validation.Valid;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Size;
import lombok.RequiredArgsConstructor;
import org.springframework.http.HttpStatus;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.server.ResponseStatusException;

import java.time.Instant;
import java.time.Duration;
import java.util.Map;

@RestController
@RequestMapping("/api/v2/sessions/{sessionId}/interview/voice")
@RequiredArgsConstructor
public class EvidenceVoiceController {
    private final EvidenceService interviews;
    private final VoiceAiClient voice;

    public record Turn(@NotBlank String turn_id, long expected_state_version) {}
    public record Recording(@NotBlank String turn_id, long expected_state_version,
                            @NotBlank @Size(max = 2_000_000) String audio) {}

    @GetMapping(value = "/config", produces = "application/json")
    public String config(@PathVariable String sessionId, @AuthenticationPrincipal User user) {
        voiceSession(sessionId, user); // Checks ownership and selected channel before upstream requests.
        return voice.config();
    }

    @PostMapping(value = "/transcribe", produces = "application/json")
    public String transcribe(@PathVariable String sessionId, @AuthenticationPrincipal User user,
                             @Valid @RequestBody Recording recording) {
        active(sessionId, user, recording.turn_id(), recording.expected_state_version());
        return voice.transcribe(Map.of("audio", recording.audio()));
    }

    @PostMapping(value = "/avatar-session", produces = "application/json")
    public String avatarSession(@PathVariable String sessionId, @AuthenticationPrincipal User user,
                                @Valid @RequestBody Turn turn, HttpServletResponse response) {
        var state = active(sessionId, user, turn.turn_id(), turn.expected_state_version());
        long remaining = Duration.between(Instant.now(), Instant.parse(state.path("deadline_at").asText())).getSeconds();
        response.setHeader("Cache-Control", "no-store");
        return voice.avatarSession(Map.of("max_session_length", Math.max(1, Math.min(7200, remaining))));
    }

    @PostMapping("/speech")
    public void speech(@PathVariable String sessionId, @AuthenticationPrincipal User user,
                       @Valid @RequestBody Turn turn, HttpServletResponse response) {
        var state = active(sessionId, user, turn.turn_id(), turn.expected_state_version());
        // Speak the saved acknowledgment, bridge and question in one continuous request.
        voice.speech(Map.of("text", spokenTurn(state.path("pending_turn"))), response);
    }

    private String spokenTurn(JsonNode pending) {
        var introduction = pending.path("introduction").asText("").strip();
        var question = pending.path("question").asText();
        return introduction.isEmpty() ? question : introduction + "\n\n" + question;
    }

    private JsonNode active(String sessionId, User user, String turnId, long version) {
        var state = voiceSession(sessionId, user);
        if (state.path("is_finished").asBoolean() || state.path("pending_turn").isNull()
                || !Instant.parse(state.path("deadline_at").asText()).isAfter(Instant.now())) {
            throw new ResponseStatusException(HttpStatus.CONFLICT, "Phiên phỏng vấn đã kết thúc.");
        }
        if (state.path("state_version").asLong() != version
                || !state.path("pending_turn").path("turn_id").asText().equals(turnId)) {
            throw new ResponseStatusException(HttpStatus.CONFLICT, "Câu hỏi đã thay đổi. Hãy tải lại phiên.");
        }
        return state;
    }

    private JsonNode voiceSession(String sessionId, User user) {
        var state = interviews.read(sessionId, user);
        if (!"VOICE".equals(state.path("config").path("interaction_mode").asText("TEXT"))) {
            throw new ResponseStatusException(HttpStatus.CONFLICT, "Phiên này sử dụng phỏng vấn bằng văn bản.");
        }
        return state;
    }
}
