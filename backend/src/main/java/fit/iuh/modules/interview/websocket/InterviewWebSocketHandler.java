package fit.iuh.modules.interview.websocket;

import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Component;
import org.springframework.web.socket.BinaryMessage;
import org.springframework.web.socket.CloseStatus;
import org.springframework.web.socket.TextMessage;
import org.springframework.web.socket.WebSocketSession;
import org.springframework.web.socket.handler.AbstractWebSocketHandler;

import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;

/**
 * Handles real-time interview WebSocket connections (audio chunks, session events).
 * Replaces the Node.js streaming-service signaling gateway directly inside the Spring Boot Monolith.
 */
@Slf4j
@Component
public class InterviewWebSocketHandler extends AbstractWebSocketHandler {

    private final Map<String, WebSocketSession> activeSessions = new ConcurrentHashMap<>();

    @Override
    public void afterConnectionEstablished(WebSocketSession session) {
        activeSessions.put(session.getId(), session);
        log.info("[WebSocket] Interview client connected: sessionId={}", session.getId());
    }

    @Override
    protected void handleTextMessage(WebSocketSession session, TextMessage message) throws Exception {
        log.debug("[WebSocket] Received text message from {}: {}", session.getId(), message.getPayload());
        // Acknowledge receipt back to client
        session.sendMessage(new TextMessage("{\"status\":\"RECEIVED\",\"timestamp\":" + System.currentTimeMillis() + "}"));
    }

    @Override
    protected void handleBinaryMessage(WebSocketSession session, BinaryMessage message) {
        log.debug("[WebSocket] Received binary audio chunk: {} bytes from {}", message.getPayloadLength(), session.getId());
        // Process audio stream buffer from client
    }

    @Override
    public void handleTransportError(WebSocketSession session, Throwable exception) {
        log.error("[WebSocket] Transport error for sessionId={}: {}", session.getId(), exception.getMessage());
    }

    @Override
    public void afterConnectionClosed(WebSocketSession session, CloseStatus status) {
        activeSessions.remove(session.getId());
        log.info("[WebSocket] Interview client disconnected: sessionId={}, status={}", session.getId(), status);
    }
}
