package fit.iuh.modules.session.controller;

import fit.iuh.modules.auth.entity.User;
import fit.iuh.modules.session.dto.CreateSessionRequest;
import fit.iuh.modules.session.dto.SessionResponse;
import fit.iuh.modules.session.dto.UpdateSessionRequest;
import fit.iuh.modules.session.service.SessionService;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.web.bind.annotation.*;

import java.util.List;
import java.util.Map;
import java.util.UUID;

@Slf4j
@RestController
@RequestMapping("/api/v1/sessions")
@RequiredArgsConstructor
public class SessionController {

    private final SessionService sessionService;

    @PostMapping
    public ResponseEntity<SessionResponse> createSession(
            @AuthenticationPrincipal User currentUser,
            @RequestBody CreateSessionRequest request) {
        UUID userId = (currentUser != null) ? currentUser.getId() : null;
        log.info("Received request to create session: userId={}, request={}", userId, request);
        SessionResponse response = sessionService.createSession(userId, request);
        return ResponseEntity.status(HttpStatus.CREATED).body(response);
    }

    @GetMapping("/{sessionId}")
    public ResponseEntity<SessionResponse> getSession(@PathVariable String sessionId) {
        return ResponseEntity.ok(sessionService.getSession(sessionId));
    }

    @GetMapping("/user")
    public ResponseEntity<List<SessionResponse>> getUserSessions(@AuthenticationPrincipal User currentUser) {
        UUID userId = (currentUser != null) ? currentUser.getId() : null;
        return ResponseEntity.ok(sessionService.getSessionsByUser(userId));
    }

    @GetMapping
    public ResponseEntity<List<SessionResponse>> getAllSessions() {
        return ResponseEntity.ok(sessionService.getAllSessions());
    }

    @PutMapping("/{sessionId}")
    public ResponseEntity<SessionResponse> updateSession(
            @PathVariable String sessionId,
            @RequestBody UpdateSessionRequest request) {
        return ResponseEntity.ok(sessionService.updateSession(sessionId, request));
    }

    @DeleteMapping("/{sessionId}")
    public ResponseEntity<Map<String, String>> deleteSession(@PathVariable String sessionId) {
        sessionService.deleteSession(sessionId);
        return ResponseEntity.ok(Map.of(
                "sessionId", sessionId,
                "message", "Session deleted successfully."
        ));
    }
}
