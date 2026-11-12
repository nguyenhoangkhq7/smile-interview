package fit.iuh.modules.evidence;

import com.fasterxml.jackson.databind.JsonNode;
import fit.iuh.modules.auth.entity.User;
import fit.iuh.modules.session.entity.Session;
import fit.iuh.modules.session.repository.SessionRepository;
import fit.iuh.modules.session.repository.SessionTurnRepository;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;
import org.springframework.web.server.ResponseStatusException;
import java.util.Map;
import java.util.Objects;

@Service @RequiredArgsConstructor @Slf4j
public class EvidenceService {
    private final SessionRepository sessions;
    private final SessionTurnRepository turns;
    private final InterviewRunRepository runs;
    private final EvidenceStore store;
    private final EvidenceAiClient ai;
    private final EvidenceInputs inputs;
    private final EvidenceJson json;

    public JsonNode read(String sessionId, User user) {
        owned(sessionId, user);
        return json.read(run(sessionId).getPublicJson());
    }

    public java.util.List<String> voiceTerms(String sessionId, User user) {
        owned(sessionId, user);
        var snapshot = json.read(run(sessionId).getSnapshotJson());
        var terms = new java.util.LinkedHashSet<String>();
        for (var skill : snapshot.path("skills")) {
            var name = skill.path("jd_skill_id").asText("").replace('_', ' ').strip();
            if (!name.isEmpty() && name.length() <= 100) terms.add(name);
        }
        return terms.stream().limit(60).toList();
    }

    public JsonNode start(String sessionId, User user, EvidenceDtos.Config config) {
        Session session = owned(sessionId, user);
        log.info("Interview start requested session_id={} interaction_mode={}", sessionId, config.interactionMode());
        JsonNode configNode = json.tree(config);
        var existing = runs.findById(sessionId);
        if (existing.isPresent()) {
            log.info("Interview start reused session_id={} state_version={}", sessionId, existing.get().getStateVersion());
            return store.sameStart(existing.get(), configNode);
        }
        if (session.getAiInterviewSessionId() != null || !turns.findBySessionIdOrderByIdAsc(sessionId).isEmpty()) {
            throw EvidenceStore.conflict("Legacy session must continue with its original engine; clone to use V2");
        }
        var start = new java.util.HashMap<String, Object>();
        start.put("session_id", sessionId);
        start.put("config", config);
        start.put("skills", inputs.skills(session));
        var profile = session.getApplicationProfile();
        start.put("opening", Map.of("company", profile == null ? "" : Objects.requireNonNullElse(profile.getCompany(), ""),
                "role_title", Objects.requireNonNullElse(session.getRoleTitle(), "vị trí ứng tuyển")));
        if (profile != null && profile.getBlueprintJson() != null) {
            start.put("blueprint", json.read(profile.getBlueprintJson()));
            start.put("policy", json.read(profile.getPolicyJson()));
        }
        JsonNode payload = json.tree(start);
        log.info("Interview preparation started session_id={} skills={} reuse_blueprint={}",
                sessionId, payload.path("skills").size(), start.containsKey("blueprint"));
        JsonNode result = ai.compute("start", payload);
        JsonNode committed = store.commit(new EvidenceStore.Commit(sessionId, 0, null, null, configNode, result));
        log.info("Interview preparation committed session_id={} state_version={} phase={} has_question={}",
                sessionId, committed.path("state_version").asLong(),
                committed.path("conversation").path("phase").asText("INTERVIEW"), committed.hasNonNull("pending_turn"));
        return committed;
    }

    public JsonNode respond(String sessionId, User user, EvidenceDtos.Answer answer) {
        owned(sessionId, user);
        String hash = json.hash(answer);
        JsonNode cached = store.replay(sessionId, answer.requestId(), hash);
        if (cached != null) return cached;
        InterviewRun run = current(sessionId, answer.expectedVersion());
        JsonNode payload = json.tree(Map.of("snapshot", json.read(run.getSnapshotJson()),
                "turn_id", answer.turnId(), "expected_state_version", answer.expectedVersion(),
                "candidate_response", answer.response()));
        JsonNode result = ai.compute("respond", payload);
        return store.commit(new EvidenceStore.Commit(sessionId, run.getStateVersion(), answer.requestId(),
                hash, json.read(run.getConfigJson()), result));
    }

    public JsonNode stop(String sessionId, User user, EvidenceDtos.Stop stop) {
        owned(sessionId, user);
        String hash = json.hash(stop);
        JsonNode cached = store.replay(sessionId, stop.requestId(), hash);
        if (cached != null) return cached;
        InterviewRun run = current(sessionId, stop.expectedVersion());
        JsonNode visible = json.read(run.getPublicJson());
        if (visible.path("is_finished").asBoolean()) return visible;
        JsonNode result = ai.compute("stop", json.read(run.getSnapshotJson()));
        return store.commit(new EvidenceStore.Commit(sessionId, run.getStateVersion(), stop.requestId(),
                hash, json.read(run.getConfigJson()), result));
    }

    public JsonNode converse(String sessionId, User user, EvidenceDtos.Conversation command) {
        owned(sessionId, user);
        String hash = json.hash(command);
        JsonNode cached = store.replay(sessionId, command.requestId(), hash);
        if (cached != null) return cached;
        InterviewRun run = current(sessionId, command.expectedVersion());
        var payload = Map.of("snapshot", json.read(run.getSnapshotJson()), "message_id", command.messageId(),
                "expected_state_version", command.expectedVersion(), "action", command.action(),
                "introduction", Objects.requireNonNullElse(command.introduction(), ""));
        JsonNode result = ai.compute("conversation", payload);
        return store.commit(new EvidenceStore.Commit(sessionId, run.getStateVersion(), command.requestId(),
                hash, json.read(run.getConfigJson()), result));
    }

    private Session owned(String id, User user) {
        Session session = sessions.findById(id).orElseThrow(() -> new ResponseStatusException(HttpStatus.NOT_FOUND));
        if (user == null || !Objects.equals(user.getId(), session.getUserId())) {
            throw new ResponseStatusException(HttpStatus.FORBIDDEN, "This interview belongs to another user");
        }
        return session;
    }

    private InterviewRun run(String id) {
        return runs.findById(id).orElseThrow(() -> new ResponseStatusException(HttpStatus.NOT_FOUND, "V2 interview not started"));
    }

    private InterviewRun current(String id, long version) {
        InterviewRun run = run(id);
        if (run.getStateVersion() != version) throw EvidenceStore.conflict("State changed; refresh the interview");
        return run;
    }
}
