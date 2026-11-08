package fit.iuh.modules.evidence;

import com.fasterxml.jackson.databind.JsonNode;
import fit.iuh.modules.session.entity.Session;
import fit.iuh.modules.session.entity.SessionTurn;
import fit.iuh.modules.session.repository.SessionRepository;
import fit.iuh.modules.session.repository.SessionTurnRepository;
import lombok.RequiredArgsConstructor;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.server.ResponseStatusException;
import java.time.LocalDateTime;
import java.util.UUID;

@Service @RequiredArgsConstructor
public class EvidenceStore {
    private final InterviewRunRepository runs;
    private final InterviewCommandRepository commands;
    private final SessionRepository sessions;
    private final SessionTurnRepository turns;
    private final EvidenceJson json;

    public record Commit(String sessionId, long expectedVersion, UUID requestId,
                         String requestHash, JsonNode config, JsonNode result) {}

    public JsonNode replay(String sessionId, UUID requestId, String hash) {
        return commands.findBySessionIdAndRequestId(sessionId, requestId).map(command -> {
            if (!command.getRequestHash().equals(hash)) throw conflict("Request ID reused with a different payload");
            return json.read(command.getResponseJson());
        }).orElse(null);
    }

    @Transactional
    public JsonNode commit(Commit input) {
        Session session = sessions.lockById(input.sessionId()).orElseThrow(() -> conflict("Session removed"));
        if (input.requestId() != null) {
            JsonNode cached = replay(input.sessionId(), input.requestId(), input.requestHash());
            if (cached != null) return cached;
        }
        InterviewRun run = runs.findById(input.sessionId()).orElse(null);
        if (input.expectedVersion() == 0 && run != null) return sameStart(run, input.config());
        if (run == null && (session.getAiInterviewSessionId() != null
                || !turns.findBySessionIdOrderByIdAsc(session.getId()).isEmpty())) {
            throw conflict("Session was started by another engine; clone to start V2");
        }
        if ((run == null ? 0 : run.getStateVersion()) != input.expectedVersion()) throw conflict("State changed; refresh the interview");
        validateTransition(input);
        run = updateRun(run, input);
        runs.save(run);
        var profile = session.getApplicationProfile();
        if (profile != null && profile.getBlueprintJson() == null) {
            var objectives = json.read("[]").deepCopy();
            input.result().path("snapshot").path("objectives").elements().forEachRemaining(state ->
                    ((com.fasterxml.jackson.databind.node.ArrayNode) objectives).add(state.path("objective")));
            if (objectives.isEmpty()) throw conflict("Interview blueprint is missing");
            profile.setBlueprintJson(json.tree(java.util.Map.of("objectives", objectives)).toString());
            profile.setPolicyJson(input.result().path("snapshot").path("policy").toString());
        }
        projectSession(session, input.result().path("public"));
        if (input.requestId() != null) saveReceipt(input, run.getPublicJson());
        return json.read(run.getPublicJson());
    }

    public JsonNode sameStart(InterviewRun run, JsonNode config) {
        if (!normalizedConfig(json.read(run.getConfigJson())).equals(normalizedConfig(config)))
            throw conflict("Configuration is locked after start");
        return json.read(run.getPublicJson());
    }

    private JsonNode normalizedConfig(JsonNode config) {
        var normalized = config.deepCopy();
        if (normalized.isObject() && !normalized.hasNonNull("interaction_mode"))
            ((com.fasterxml.jackson.databind.node.ObjectNode) normalized).put("interaction_mode", "TEXT");
        return normalized;
    }

    private void validateTransition(Commit input) {
        JsonNode snapshot = input.result().path("snapshot");
        JsonNode visible = input.result().path("public");
        long next = input.expectedVersion() + 1;
        if (!snapshot.path("session_id").asText().equals(input.sessionId())
                || snapshot.path("schema_version").asInt() != 2
                || visible.path("schema_version").asInt() != 2
                || snapshot.path("state_version").asLong() != next
                || visible.path("state_version").asLong() != next
                || !visible.path("session_id").asText().equals(input.sessionId())) {
            throw new ResponseStatusException(HttpStatus.BAD_GATEWAY, "AI transition identity/version mismatch");
        }
        String channel = input.config().path("interaction_mode").asText("TEXT");
        if (!channel.equals(snapshot.path("config").path("interaction_mode").asText("TEXT"))
                || !channel.equals(visible.path("config").path("interaction_mode").asText("TEXT"))) {
            throw new ResponseStatusException(HttpStatus.BAD_GATEWAY, "AI changed the interview interaction mode");
        }
    }

    private InterviewRun updateRun(InterviewRun run, Commit input) {
        if (run == null) run = new InterviewRun();
        run.setSessionId(input.sessionId());
        run.setStateVersion(input.expectedVersion() + 1);
        run.setConfigJson(input.config().toString());
        run.setSnapshotJson(input.result().path("snapshot").toString());
        run.setPublicJson(input.result().path("public").toString());
        return run;
    }

    private void saveReceipt(Commit input, String response) {
        InterviewCommand command = new InterviewCommand();
        command.setId(UUID.randomUUID());
        command.setSessionId(input.sessionId());
        command.setRequestId(input.requestId());
        command.setRequestHash(input.requestHash());
        command.setResponseJson(response);
        commands.save(command);
    }

    private void projectSession(Session session, JsonNode visible) {
        boolean finished = visible.path("is_finished").asBoolean();
        String reason = visible.path("report").path("termination_reason").asText();
        session.setStatus(!finished ? "In progress" : "USER_STOP".equals(reason)
                ? (visible.path("turns").isEmpty() ? "Cancelled" : "Stopped early") : "Completed");
        session.setEndedAt(finished ? LocalDateTime.now() : null);
        for (JsonNode turn : visible.path("turns")) projectTurn(session.getId(), turn);
        if (visible.path("pending_turn").isObject()) projectTurn(session.getId(), visible.path("pending_turn"));
        sessions.save(session);
    }

    private void projectTurn(String sessionId, JsonNode value) {
        String turnId = value.path("turn_id").asText();
        SessionTurn turn = turns.findBySessionIdAndExternalTurnId(sessionId, turnId).orElseGet(SessionTurn::new);
        turn.setSessionId(sessionId);
        turn.setExternalTurnId(turnId);
        turn.setQuestion(value.path("question").asText());
        turn.setAnswer(value.path("answer").asText(""));
        turn.setTopicTag(value.path("skill_id").asText());
        turn.setIsDeepDive(false);
        turns.save(turn);
    }

    static ResponseStatusException conflict(String message) {
        return new ResponseStatusException(HttpStatus.CONFLICT, message);
    }
}
