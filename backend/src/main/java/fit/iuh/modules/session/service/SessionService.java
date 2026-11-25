package fit.iuh.modules.session.service;

import fit.iuh.modules.auth.entity.User;
import fit.iuh.modules.session.dto.CreateSessionRequest;
import fit.iuh.modules.session.dto.SessionResponse;
import fit.iuh.modules.session.dto.UpdateSessionRequest;
import fit.iuh.modules.session.entity.SessionTurn;

import java.util.List;
import java.util.Map;
import java.util.UUID;

public interface SessionService {

    SessionResponse createSession(User currentUser, CreateSessionRequest request);

    SessionResponse getSession(User currentUser, String sessionId);

    List<SessionResponse> getSessionsByUser(UUID userId);

    SessionResponse updateSession(User currentUser, String sessionId, UpdateSessionRequest request);

    void deleteSession(User currentUser, String sessionId);

    SessionTurn addTurn(User currentUser, String sessionId, SessionTurn turn);

    List<SessionTurn> getSessionTurns(User currentUser, String sessionId);

    String cloneSession(User currentUser, String sessionId);

    Map<String, Object> getRawTexts(User currentUser, UUID resumeId, UUID jdId);
}
