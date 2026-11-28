package fit.iuh.modules.evidence;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.node.ObjectNode;
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
import java.time.Duration;
import java.time.Instant;
import java.util.HashMap;
import java.util.Map;
import java.util.UUID;

@Service @RequiredArgsConstructor
public class EvidenceStore {
    private final InterviewRunRepository runs;
    private final InterviewCommandRepository commands;
    private final SessionRepository sessions;
    private final SessionTurnRepository turns;
    private final EvidenceJson json;
    private final EvidenceAdmission admission;

    public record Commit(String sessionId, long expectedVersion, UUID requestId,
                         String requestHash, JsonNode config, JsonNode result) {}

    public JsonNode replay(String sessionId, UUID requestId, String hash) {
        return commands.findBySessionIdAndRequestId(sessionId, requestId).map(command -> {
            if (!command.getRequestHash().equals(hash)) throw conflict("Request ID reused with a different payload");
            return json.read(command.getResponseJson());
        }).orElse(null);
    }

    @Transactional
    public JsonNode acceptAnswer(String id, EvidenceDtos.Answer answer, Instant receivedAt) {
        sessions.lockById(id).orElseThrow(() -> conflict("Session removed"));
        var run = runs.findById(id).orElseThrow(() -> conflict("Interview not started"));
        String hash = json.hash(answer);
        var cached = replay(id, answer.requestId(), hash);
        if (cached != null) return cached.hasNonNull("submission") ? json.read(run.getPublicJson()) : cached;
        if (run.getStateVersion() != answer.expectedVersion() || run.getGradingDueAt() != null)
            throw conflict("Trạng thái phiên đã thay đổi. Hãy tải lại phiên.");
        ObjectNode visible = (ObjectNode) json.read(run.getPublicJson());
        ObjectNode snapshot = (ObjectNode) json.read(run.getSnapshotJson());
        JsonNode turn = snapshot.path("pending_turn");
        if (visible.path("is_finished").asBoolean() || !answer.turnId().equals(turn.path("turn_id").asText()))
            throw conflict("Câu hỏi này đã kết thúc.");
        JsonNode previous = visible.path("submission");
        if ("FAILED".equals(previous.path("status").asText())) {
            if (!answer.response().equals(previous.path("candidate_response").asText())
                    || !java.util.Objects.equals(answer.code(), previous.path("submitted_code").asText(null)))
                throw conflict("Chỉ có thể chấm lại bài đã nộp.");
            receivedAt = Instant.parse(previous.path("received_at").asText());
        }
        Instant deadline = Instant.parse(snapshot.path("deadline_at").asText());
        if (!receivedAt.isBefore(deadline)) throw conflict("Đã hết thời gian nộp bài.");
        validateAnswer(snapshot, turn, answer);
        long version = run.getStateVersion() + 1;
        ObjectNode submission = visible.putObject("submission");
        submission.put("turn_id", answer.turnId()).put("candidate_response", answer.response())
                .put("received_at", receivedAt.toString()).put("status", "QUEUED");
        if (answer.code() != null) submission.put("submitted_code", answer.code());
        visible.putNull("pending_turn").put("state_version", version);
        visible.put("paused_remaining_seconds", Duration.between(receivedAt, deadline).toNanos() / 1e9);
        snapshot.put("state_version", version).set("paused_remaining_seconds", visible.path("paused_remaining_seconds"));
        run.setStateVersion(version);
        run.setSnapshotJson(snapshot.toString());
        run.setPublicJson(visible.toString());
        run.setGradingDueAt(Instant.now());
        run.setGradingAttempt(0);
        runs.save(run);
        saveReceipt(new Commit(id, answer.expectedVersion(), answer.requestId(), hash, null, null), run.getPublicJson());
        return json.read(run.getPublicJson());
    }

    private void validateAnswer(JsonNode snapshot, JsonNode turn, EvidenceDtos.Answer answer) {
        var question = turn.path("question");
        boolean requiresCode = question.path("requires_code").asBoolean();
        boolean acceptsCode = requiresCode || question.hasNonNull("coding_spec") || "CODING".equals(turn.path("mode").asText());
        if (answer.code() != null && (!acceptsCode || answer.code().isBlank()))
            throw new ResponseStatusException(HttpStatus.UNPROCESSABLE_ENTITY, "Lượt này không nhận mã hoặc mã đang trống.");
        if (requiresCode && "VOICE".equals(snapshot.path("config").path("interaction_mode").asText())
                && answer.code() == null && !isInability(answer.response()))
            throw new ResponseStatusException(HttpStatus.UNPROCESSABLE_ENTITY, "Hãy nộp mã hoặc chọn Chưa làm được.");
    }

    private static boolean isInability(String response) {
        String normalized = java.text.Normalizer.normalize(response, java.text.Normalizer.Form.NFC)
                .strip().toLowerCase(java.util.Locale.ROOT).replaceAll("\\s+", " ");
        return normalized.matches("(?:dạ[, ]+)?(?:(?:tôi|em|mình) )?(?:(?:không|chưa) (?:biết|làm được|trả lời được|nhớ)"
                + "(?: câu trả lời| trả lời| cách làm| câu này)?|bỏ qua(?: câu này| câu hỏi này)?|skip(?: this question)?)(?: ạ)?[.!…]*");
    }

    public record GradingJob(String sessionId, long version, int attempt, JsonNode payload, JsonNode config) {}

    @Transactional
    public GradingJob claimAnswer(Duration lease) {
        return runs.lockNextSubmission().map(run -> {
            JsonNode submission = json.read(run.getPublicJson()).path("submission");
            ObjectNode payload = (ObjectNode) submission.deepCopy();
            payload.remove("status");
            payload.set("snapshot", json.read(run.getSnapshotJson()));
            payload.put("expected_state_version", run.getStateVersion()).put("defer_question", true);
            run.setGradingAttempt(run.getGradingAttempt() + 1);
            run.setGradingDueAt(Instant.now().plus(lease));
            return new GradingJob(run.getSessionId(), run.getStateVersion(), run.getGradingAttempt(),
                    payload, json.read(run.getConfigJson()));
        }).orElse(null);
    }

    @Transactional
    public void gradingFailed(GradingJob job) {
        if (sessions.lockById(job.sessionId()).isEmpty()) return;
        var run = runs.lockRun(job.sessionId()).orElse(null);
        if (run == null || run.getStateVersion() != job.version() || run.getGradingAttempt() != job.attempt()) return;
        if (job.attempt() < 3) {
            run.setGradingDueAt(Instant.now().plusSeconds(job.attempt() * 5L));
            return;
        }
        ObjectNode visible = (ObjectNode) json.read(run.getPublicJson());
        ((ObjectNode) visible.path("submission")).put("status", "FAILED");
        run.setPublicJson(visible.toString());
        run.setGradingDueAt(null);
    }

    @Transactional
    public void completeGrading(GradingJob job, JsonNode result) {
        if (sessions.lockById(job.sessionId()).isEmpty()) return;
        var run = runs.lockRun(job.sessionId()).orElse(null);
        if (run == null || run.getStateVersion() != job.version() || run.getGradingAttempt() != job.attempt()
                || run.getGradingDueAt() == null) return;
        commit(new Commit(job.sessionId(), job.version(), null, null, job.config(), result));
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
        if (run == null) admission.checkQuota(session.getUserId(), true);
        run = updateRun(run, input);
        runs.save(run);
        var profile = session.getApplicationProfile();
        if (profile != null && profile.getBlueprintJson() == null) {
            var objectives = json.read("[]").deepCopy();
            input.result().path("snapshot").path("objectives").elements().forEachRemaining(state -> {
                var objective = state.path("objective");
                if (!"behavioral_competency".equals(objective.path("skill_id").asText())) {
                    ((com.fasterxml.jackson.databind.node.ArrayNode) objectives).add(objective);
                }
            });
            if (objectives.isEmpty()) throw conflict("Interview blueprint is missing");
            profile.setBlueprintJson(json.tree(java.util.Map.of("objectives", objectives)).toString());
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
        if (!(config instanceof ObjectNode object)) return config;
        var normalized = object.deepCopy();
        if (!normalized.hasNonNull("interaction_mode")) normalized.put("interaction_mode", "TEXT");
        if (!normalized.has("focused_question_mode")) normalized.putNull("focused_question_mode");
        if (!normalized.has("mode")) {
            normalized.put("mode", EvidenceDtos.Config.modeFor(normalized.path("focused_question_mode").asText(null)));
        }
        if (!normalized.hasNonNull("max_questions_per_objective")) {
            normalized.put("max_questions_per_objective", EvidenceDtos.Config.DEFAULT_MAX_PER_OBJECTIVE);
        }
        if (!normalized.hasNonNull("session_purpose")) normalized.put("session_purpose", "ASSESSMENT");
        if (!normalized.hasNonNull("include_mastered_skills")) normalized.put("include_mastered_skills", false);
        if (!normalized.hasNonNull("include_behavioral_in_mixed")) normalized.put("include_behavioral_in_mixed", false);
        JsonNode focusSkills = normalized.get("focus_skill_ids");
        if (focusSkills == null || focusSkills.isNull() || (focusSkills.isArray() && focusSkills.isEmpty())) {
            normalized.remove("focus_skill_ids");
        }
        if (normalized.get("recheck") instanceof ObjectNode ref) {
            for (String key : java.util.List.of("taskId", "checklistItemId")) {
                if (ref.path(key).isIntegralNumber() && ref.path(key).canConvertToLong()) ref.put(key, ref.path(key).longValue());
            }
        } else if (!normalized.hasNonNull("recheck")) {
            normalized.remove("recheck");
        }
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
        JsonNode target = normalizedConfig(input.config()).path("recheck");
        if (!target.equals(normalizedConfig(snapshot.path("config")).path("recheck"))
                || !target.equals(normalizedConfig(visible.path("config")).path("recheck"))
                || target.isObject() != snapshot.hasNonNull("recheck_target")) {
            throw new ResponseStatusException(HttpStatus.BAD_GATEWAY, "AI changed the checklist reference");
        }
        boolean awaiting = visible.path("awaiting_question").asBoolean();
        if (snapshot.hasNonNull("next_question_action") != awaiting || (awaiting
                && (visible.hasNonNull("pending_turn") || snapshot.hasNonNull("pending_turn")
                || visible.path("is_finished").asBoolean() || snapshot.path("is_finished").asBoolean()))) {
            throw new ResponseStatusException(HttpStatus.BAD_GATEWAY, "Invalid pending question transition");
        }
    }

    private InterviewRun updateRun(InterviewRun run, Commit input) {
        if (run == null) run = new InterviewRun();
        if (run.getPublicJson() != null && input.result().path("public").path("is_finished").asBoolean()) {
            var submission = json.read(run.getPublicJson()).path("submission");
            if ("FAILED".equals(submission.path("status").asText()) || "UNASSESSED".equals(submission.path("status").asText())) {
                ObjectNode ungraded = submission.deepCopy();
                ungraded.put("status", "UNASSESSED");
                ((ObjectNode) input.result().path("public")).set("submission", ungraded);
            }
        }
        run.setSessionId(input.sessionId());
        run.setStateVersion(input.expectedVersion() + 1);
        run.setConfigJson(input.config().toString());
        run.setSnapshotJson(input.result().path("snapshot").toString());
        run.setPublicJson(input.result().path("public").toString());
        run.setGradingDueAt(null);
        run.setGradingAttempt(0);
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
                ? (visible.path("turns").isEmpty() && !visible.hasNonNull("submission") ? "Cancelled" : "Stopped early") : "Completed");
        session.setEndedAt(finished ? LocalDateTime.now() : null);
        Map<String, String> skillByObjective = new HashMap<>();
        for (JsonNode objective : visible.path("report").path("objectives")) {
            String objectiveId = objective.path("objective_id").asText("");
            String skillId = objective.path("skill_id").asText("");
            if (!objectiveId.isEmpty() && !skillId.isEmpty()) skillByObjective.put(objectiveId, skillId);
        }
        Map<String, SessionTurn> existingTurns = new HashMap<>();
        var loadedTurns = turns.findBySessionIdOrderByIdAsc(session.getId());
        if (loadedTurns != null) {
            for (SessionTurn existing : loadedTurns) {
                if (existing.getExternalTurnId() != null) {
                    existingTurns.put(existing.getExternalTurnId(), existing);
                }
            }
        }
        for (JsonNode turn : visible.path("turns")) {
            projectTurn(session.getId(), turn, skillByObjective, existingTurns);
        }
        if (visible.path("pending_turn").isObject()) {
            projectTurn(session.getId(), visible.path("pending_turn"), skillByObjective, existingTurns);
        }
        sessions.save(session);
    }

    private void projectTurn(String sessionId, JsonNode value, Map<String, String> skillByObjective,
                             Map<String, SessionTurn> existingTurns) {
        String turnId = value.path("turn_id").asText();
        if (turnId.isEmpty()) return;
        SessionTurn turn = existingTurns.get(turnId);
        boolean isNew = turn == null;
        if (isNew) {
            turn = new SessionTurn();
        }
        String question = value.path("question").asText();
        String answer = value.path("answer").asText("");
        String topicTag = skillByObjective.getOrDefault(value.path("objective_id").asText(""), "");
        boolean changed = isNew
                || !java.util.Objects.equals(turn.getQuestion(), question)
                || !java.util.Objects.equals(turn.getAnswer(), answer)
                || !java.util.Objects.equals(turn.getTopicTag(), topicTag)
                || !Boolean.FALSE.equals(turn.getIsDeepDive());
        if (!changed) return;
        turn.setSessionId(sessionId);
        turn.setExternalTurnId(turnId);
        turn.setQuestion(question);
        turn.setAnswer(answer);
        turn.setTopicTag(topicTag);
        turn.setIsDeepDive(false);
        turns.save(turn);
        existingTurns.put(turnId, turn);
    }

    static ResponseStatusException conflict(String message) {
        return new ResponseStatusException(HttpStatus.CONFLICT, message);
    }
}
