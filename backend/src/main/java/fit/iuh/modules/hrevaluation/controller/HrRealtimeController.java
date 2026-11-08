package fit.iuh.modules.hrevaluation.controller;

import fit.iuh.modules.session.dto.UpdateSessionRequest;
import fit.iuh.modules.session.service.SessionService;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.servlet.mvc.method.annotation.SseEmitter;

import java.io.IOException;
import java.time.Instant;
import java.util.Map;
import java.util.Set;
import java.util.concurrent.CopyOnWriteArraySet;

/**
 * Real-time SSE controller for HR Dashboard notifications.
 * Migrated from Next.js BFF (/api/hr-realtime) so both Web and Mobile clients
 * can subscribe and publish session stage transitions directly to the backend.
 */
@Slf4j
@RestController
@RequestMapping("/api/v1/hr-realtime")
@RequiredArgsConstructor
public class HrRealtimeController {

    private final SessionService sessionService;
    private final Set<SseEmitter> emitters = new CopyOnWriteArraySet<>();

    @GetMapping(produces = MediaType.TEXT_EVENT_STREAM_VALUE)
    public SseEmitter subscribe() {
        SseEmitter emitter = new SseEmitter(0L);
        emitters.add(emitter);

        emitter.onCompletion(() -> emitters.remove(emitter));
        emitter.onTimeout(() -> emitters.remove(emitter));
        emitter.onError((ex) -> emitters.remove(emitter));

        try {
            emitter.send(SseEmitter.event()
                    .name("connected")
                    .data(Map.of(
                            "message", "Connected to HR Realtime Event Stream",
                            "timestamp", Instant.now().toString()
                    )));
        } catch (IOException e) {
            emitters.remove(emitter);
        }

        return emitter;
    }

    @PostMapping(consumes = MediaType.APPLICATION_JSON_VALUE, produces = MediaType.APPLICATION_JSON_VALUE)
    public ResponseEntity<Map<String, Object>> publishEvent(@RequestBody Map<String, Object> body) {
        String sessionId = (String) body.get("sessionId");
        String stage = (String) body.get("stage");
        Object payload = body.get("payload");

        if (stage == null || stage.isBlank()) {
            return ResponseEntity.badRequest().body(Map.of("error", "Missing stage parameter"));
        }

        if (sessionId != null && !sessionId.isBlank()) {
            try {
                sessionService.updateSession(
                        sessionId,
                        UpdateSessionRequest.builder().status(stage).build()
                );
            } catch (Exception e) {
                log.warn("[HR Realtime] Could not update session status for {}: {}", sessionId, e.getMessage());
            }
        }

        Map<String, Object> eventData = Map.of(
                "sessionId", sessionId != null ? sessionId : "",
                "stage", stage,
                "payload", payload != null ? payload : Map.of(),
                "timestamp", Instant.now().toString()
        );

        broadcast("SESSION_STAGE_UPDATED", eventData);

        return ResponseEntity.ok(Map.of(
                "success", true,
                "broadcastedTo", emitters.size(),
                "eventData", eventData
        ));
    }

    private void broadcast(String eventName, Object data) {
        for (SseEmitter emitter : emitters) {
            try {
                emitter.send(SseEmitter.event().name(eventName).data(data));
            } catch (Exception e) {
                emitters.remove(emitter);
            }
        }
    }
}
