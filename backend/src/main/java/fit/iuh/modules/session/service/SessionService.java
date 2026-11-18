package fit.iuh.modules.session.service;

import fit.iuh.modules.session.dto.CreateSessionRequest;
import fit.iuh.modules.session.dto.SessionResponse;
import fit.iuh.modules.session.dto.UpdateSessionRequest;
import fit.iuh.modules.session.entity.SessionTurn;

import java.util.List;
import java.util.Map;
import java.util.UUID;

public interface SessionService {

    SessionResponse createSession(UUID userId, CreateSessionRequest request);

    SessionResponse getSession(String sessionId);

    List<SessionResponse> getSessionsByUser(UUID userId);

    SessionResponse updateSession(String sessionId, UpdateSessionRequest request);

    void deleteSession(String sessionId);

    SessionTurn addTurn(String sessionId, SessionTurn turn);

    List<SessionTurn> getSessionTurns(String sessionId);

    String cloneSession(String sessionId);

    Map<String, Object> getRawTexts(UUID resumeId, UUID jdId);
}
