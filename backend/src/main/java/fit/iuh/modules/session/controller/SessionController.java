package fit.iuh.modules.session.controller;

import fit.iuh.modules.auth.entity.User;
import fit.iuh.modules.session.dto.CreateSessionRequest;
import fit.iuh.modules.session.dto.SessionResponse;
import fit.iuh.modules.session.dto.UpdateSessionRequest;
import fit.iuh.modules.session.entity.SessionTurn;
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
            @jakarta.validation.Valid @RequestBody CreateSessionRequest request) {
        log.info("Received request to create session: userId={}, request={}",
                currentUser != null ? currentUser.getId() : null, request);
        SessionResponse response = sessionService.createSession(currentUser, request);
        return ResponseEntity.status(HttpStatus.CREATED).body(response);
    }

    @GetMapping("/{sessionId}")
    public ResponseEntity<SessionResponse> getSession(
            @PathVariable String sessionId,
            @AuthenticationPrincipal User currentUser) {
        return ResponseEntity.ok(sessionService.getSession(currentUser, sessionId));
    }

    @GetMapping("/user")
    public ResponseEntity<List<SessionResponse>> getUserSessions(@AuthenticationPrincipal User currentUser) {
        UUID userId = (currentUser != null) ? currentUser.getId() : null;
        return ResponseEntity.ok(sessionService.getSessionsByUser(userId));
    }

    @PutMapping("/{sessionId}")
    public ResponseEntity<SessionResponse> updateSession(
            @PathVariable String sessionId,
            @AuthenticationPrincipal User currentUser,
            @jakarta.validation.Valid @RequestBody UpdateSessionRequest request) {
        return ResponseEntity.ok(sessionService.updateSession(currentUser, sessionId, request));
    }

    @DeleteMapping("/{sessionId}")
    public ResponseEntity<Map<String, String>> deleteSession(
            @PathVariable String sessionId,
            @AuthenticationPrincipal User currentUser) {
        sessionService.deleteSession(currentUser, sessionId);
        return ResponseEntity.ok(Map.of(
                "sessionId", sessionId,
                "message", "Session deleted successfully."
        ));
    }

    @PostMapping("/{sessionId}/turns")
    public ResponseEntity<SessionTurn> addTurn(
            @PathVariable String sessionId,
            @AuthenticationPrincipal User currentUser,
            @RequestBody SessionTurn turn) {
        return ResponseEntity.status(HttpStatus.CREATED).body(sessionService.addTurn(currentUser, sessionId, turn));
    }

    @GetMapping("/{sessionId}/turns")
    public ResponseEntity<List<SessionTurn>> getSessionTurns(
            @PathVariable String sessionId,
            @AuthenticationPrincipal User currentUser) {
        return ResponseEntity.ok(sessionService.getSessionTurns(currentUser, sessionId));
    }

    @PostMapping("/{sessionId}/clone")
    public ResponseEntity<Map<String, Object>> cloneSession(
            @PathVariable String sessionId,
            @AuthenticationPrincipal User currentUser) {
        String newSessionId = sessionService.cloneSession(currentUser, sessionId);
        return ResponseEntity.ok(Map.of(
                "success", true,
                "newSessionId", newSessionId
        ));
    }

    @GetMapping("/raw-texts")
    public ResponseEntity<Map<String, Object>> getRawTexts(
            @AuthenticationPrincipal User currentUser,
            @RequestParam(value = "resumeId", required = false) UUID resumeId,
            @RequestParam(value = "jdId", required = false) UUID jdId) {
        return ResponseEntity.ok(sessionService.getRawTexts(currentUser, resumeId, jdId));
    }
}
