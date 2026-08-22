package fit.iuh.modules.session.service;

import fit.iuh.modules.session.dto.CreateSessionRequest;
import fit.iuh.modules.session.dto.SessionResponse;
import fit.iuh.modules.session.dto.UpdateSessionRequest;

import java.util.List;
import java.util.UUID;

public interface SessionService {

    SessionResponse createSession(UUID userId, CreateSessionRequest request);

    SessionResponse getSession(String sessionId);

    List<SessionResponse> getSessionsByUser(UUID userId);

    List<SessionResponse> getAllSessions();

    SessionResponse updateSession(String sessionId, UpdateSessionRequest request);

    void deleteSession(String sessionId);
}
