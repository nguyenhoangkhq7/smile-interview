package fit.iuh.modules.evidence;

import com.fasterxml.jackson.databind.JsonNode;
import fit.iuh.modules.application.ApplicationProfile;
import fit.iuh.modules.application.CompetencyProjection;
import fit.iuh.modules.auth.entity.User;
import fit.iuh.modules.session.entity.Session;
import fit.iuh.modules.session.repository.SessionRepository;
import fit.iuh.modules.session.repository.SessionTurnRepository;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;
import org.springframework.web.server.ResponseStatusException;

import java.util.Comparator;
import java.util.LinkedHashMap;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Map;
import java.util.Objects;
import java.util.Set;
import java.util.UUID;

@Service @RequiredArgsConstructor @Slf4j
public class EvidenceService {
    private static final int MAX_COMPANY_LENGTH = 200;
    private static final int MAX_ROLE_TITLE_LENGTH = 200;
    private static final int MAX_CANDIDATE_NAME_LENGTH = 150;
    private static final int MAX_JD_SUMMARY_LENGTH = 1500;
    private static final int MAX_CV_SUMMARY_LENGTH = 1200;
    private static final int MAX_PRIOR_QUESTION_STEM_LENGTH = 200;
    private static final int MAX_PRIOR_QUESTION_STEMS = 20;
    private static final String DEFAULT_ROLE_TITLE = "vị trí ứng tuyển";
    private static final Set<String> MASTERED_ASSESSMENTS =
            Set.of("DEMONSTRATED_AT_TARGET", "DEMONSTRATED_ABOVE_TARGET");

    public record VoiceContext(JsonNode state, List<String> terms) {}

    private final SessionRepository sessions;
    private final SessionTurnRepository turns;
    private final InterviewRunRepository runs;
    private final EvidenceStore store;
    private final EvidenceAiClient ai;
    private final EvidenceInputs inputs;
    private final EvidenceJson json;
    private final EvidenceAdmission admission;
    private final fit.iuh.modules.study.service.StudyPlanService study;

    public JsonNode read(String sessionId, User user) {
        owned(sessionId, user);
        return json.read(run(sessionId).getPublicJson());
    }

    public VoiceContext voiceContext(String sessionId, User user) {
        owned(sessionId, user);
        InterviewRun current = run(sessionId);
        return new VoiceContext(
                json.read(current.getPublicJson()),
                extractVoiceTerms(json.read(current.getSnapshotJson()))
        );
    }

    public List<String> voiceTerms(String sessionId, User user) {
        owned(sessionId, user);
        return extractVoiceTerms(json.read(run(sessionId).getSnapshotJson()));
    }

    private List<String> extractVoiceTerms(JsonNode snapshot) {
        var terms = new LinkedHashSet<String>();
        for (var skill : snapshot.path("skills")) {
            var jdName = skill.path("jd_skill_name").asText("").strip();
            var rawName = skill.path("jd_skill_id").asText("").replace('_', ' ').strip();
            var primary = !jdName.isEmpty() ? jdName : rawName;
            if (!primary.isEmpty() && primary.length() <= 100) {
                terms.add(primary);
            }
            var cvName = skill.path("matched_cv_skill_name").asText("").strip();
            if (!cvName.isEmpty() && cvName.length() <= 100) {
                terms.add(cvName);
            }
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
        admission.check(config);
        admission.checkQuota(user.getId(), false);
        var start = new java.util.HashMap<String, Object>();
        start.put("session_id", sessionId);
        start.put("config", config);
        JsonNode baseSkills = inputs.skills(session);
        JsonNode enrichedSkills = new EvidenceInputs(null, json).enrichPersonalization(baseSkills, session);
        start.put("skills", enrichedSkills);
        start.put("verification_sources", EvidenceInputs.verificationSources(session, enrichedSkills));
        var profile = session.getApplicationProfile();
        if (config.recheck() == null) {
            start.put("opening", openingContext(session, user));
        } else {
            if (profile == null || config.focusedMode() != null || config.maxQuestions() > 3 || config.durationSeconds() > 300)
                throw new ResponseStatusException(HttpStatus.UNPROCESSABLE_ENTITY, "Cấu hình kiểm chứng không hợp lệ");
            start.put("recheck_target", study.recheckTarget(profile.getId(), user, config.recheck()));
        }
        if (profile != null && profile.getBlueprintJson() != null) {
            start.put("blueprint", EvidenceInputs.leanBlueprint(json.read(profile.getBlueprintJson())));
        }
        var priorAttempts = priorAttemptContext(session, profile);
        if (priorAttempts != null) {
            start.put("prior_attempts", priorAttempts);
        }
        JsonNode payload = json.tree(start);
        log.info("Interview preparation started session_id={} skills={} reuse_blueprint={} has_prior_attempts={}",
                sessionId, payload.path("skills").size(), start.containsKey("blueprint"), start.containsKey("prior_attempts"));
        JsonNode result = ai.compute("start", payload);
        JsonNode committed = store.commit(new EvidenceStore.Commit(sessionId, 0, null, null, configNode, result));
        log.info("Interview preparation committed session_id={} state_version={} phase={} has_question={}",
                sessionId, committed.path("state_version").asLong(),
                committed.path("conversation").path("phase").asText("INTERVIEW"), committed.hasNonNull("pending_turn"));
        return committed;
    }

    public JsonNode respond(String sessionId, User user, EvidenceDtos.Answer answer) {
        var receivedAt = java.time.Instant.now();
        owned(sessionId, user);
        return store.acceptAnswer(sessionId, answer, receivedAt);
    }

    public JsonNode nextQuestion(String sessionId, User user, EvidenceDtos.NextQuestion command) {
        owned(sessionId, user);
        String hash = json.hash(Map.of("next-question", command));
        JsonNode cached = store.replay(sessionId, command.requestId(), hash);
        if (cached != null) return cached;
        InterviewRun run = current(sessionId, command.expectedVersion());
        if (!json.read(run.getPublicJson()).path("awaiting_question").asBoolean()) {
            throw EvidenceStore.conflict("Interview is not waiting for a question");
        }
        var payload = Map.of("snapshot", json.read(run.getSnapshotJson()),
                "expected_state_version", command.expectedVersion());
        JsonNode result = ai.compute("next-question", payload);
        return store.commit(new EvidenceStore.Commit(sessionId, run.getStateVersion(), command.requestId(),
                hash, json.read(run.getConfigJson()), result));
    }

    public JsonNode clarify(String sessionId, User user, EvidenceDtos.Clarify command) {
        owned(sessionId, user);
        String hash = json.hash(command);
        JsonNode cached = store.replay(sessionId, command.requestId(), hash);
        if (cached != null) return cached;
        InterviewRun run = current(sessionId, command.expectedVersion());
        var payload = Map.of(
                "snapshot", json.read(run.getSnapshotJson()),
                "turn_id", command.turnId(),
                "expected_state_version", command.expectedVersion(),
                "kind", command.kind(),
                "candidate_question", command.candidateQuestion()
        );
        JsonNode result = ai.compute("clarify", payload);
        return store.commit(new EvidenceStore.Commit(
                sessionId, run.getStateVersion(), command.requestId(), hash, json.read(run.getConfigJson()), result));
    }

    public JsonNode runCode(String sessionId, User user, EvidenceDtos.RunCode request) {
        owned(sessionId, user);
        InterviewRun run = run(sessionId);
        JsonNode visible = json.read(run.getPublicJson());
        if (visible.path("is_finished").asBoolean() || !visible.path("pending_turn").isObject()) {
            throw EvidenceStore.conflict("Phiên phỏng vấn không có câu hỏi đang chờ");
        }
        String pendingTurnId = visible.path("pending_turn").path("turn_id").asText("");
        if (!pendingTurnId.equals(request.turnId())) {
            throw EvidenceStore.conflict("Mã lượt không khớp với câu hỏi hiện tại");
        }
        var payload = new java.util.HashMap<String, Object>();
        payload.put("snapshot", json.read(run.getSnapshotJson()));
        payload.put("turn_id", request.turnId());
        payload.put("code", request.code());
        if (request.language() != null && !request.language().isBlank()) {
            payload.put("language", request.language());
        }
        return ai.runCode(payload);
    }

    public JsonNode stop(String sessionId, User user, EvidenceDtos.Stop stop) {
        owned(sessionId, user);
        String hash = json.hash(stop);
        JsonNode cached = store.replay(sessionId, stop.requestId(), hash);
        if (cached != null) return cached;
        InterviewRun run = current(sessionId, stop.expectedVersion(), true);
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
                "introduction", Objects.requireNonNullElse(command.introduction(), ""), "defer_question", true);
        JsonNode result = ai.compute("conversation", payload);
        return store.commit(new EvidenceStore.Commit(sessionId, run.getStateVersion(), command.requestId(),
                hash, json.read(run.getConfigJson()), result));
    }

    private Map<String, Object> priorAttemptContext(Session currentSession, ApplicationProfile profile) {
        if (profile == null || profile.getId() == null
                || currentSession.getAttemptNumber() == null || currentSession.getAttemptNumber() < 2) {
            return null;
        }
        List<Session> allAttempts = sessions.findByApplicationProfileIdOrderByAttemptNumberDesc(profile.getId());
        if (allAttempts == null || allAttempts.isEmpty()) {
            return null;
        }
        List<Session> priorAttempts = allAttempts.stream()
                .filter(s -> !Objects.equals(s.getId(), currentSession.getId()))
                .toList();
        if (priorAttempts.isEmpty()) {
            return null;
        }
        List<InterviewRun> savedRuns = runs.findAllById(priorAttempts.stream().map(Session::getId).toList());
        if (savedRuns == null || savedRuns.isEmpty()) {
            return null;
        }
        Map<String, String> objectiveAssessments = new LinkedHashMap<>();
        var masteredSkillIds = new LinkedHashSet<String>();
        try {
            var projection = new CompetencyProjection(json).project(profile, priorAttempts, savedRuns);
            for (var skill : projection.skills()) {
                if (MASTERED_ASSESSMENTS.contains(skill.assessment())) masteredSkillIds.add(skill.skillId());
                for (var objective : skill.objectives()) {
                    if (objective.id() != null && !objective.id().isBlank()
                            && objective.assessment() != null && !"NOT_ASSESSED".equals(objective.assessment())) {
                        objectiveAssessments.put(objective.id(), objective.assessment());
                    }
                }
            }
        } catch (Exception ex) {
            log.warn("Failed to project prior competency for profile_id={} ({})", profile.getId(), ex.getClass().getSimpleName());
        }

        var runBySession = new java.util.HashMap<String, InterviewRun>();
        for (InterviewRun r : savedRuns) {
            runBySession.put(r.getSessionId(), r);
        }
        var priorQuestionStems = new LinkedHashSet<String>();
        for (Session attempt : priorAttempts.stream()
                .sorted(Comparator.comparingInt((Session s) -> s.getAttemptNumber() == null ? 0 : s.getAttemptNumber()).reversed())
                .toList()) {
            InterviewRun r = runBySession.get(attempt.getId());
            if (r == null || r.getSnapshotJson() == null) continue;
            JsonNode snapshot = json.read(r.getSnapshotJson());
            boolean isPractice = "PRACTICE".equals(snapshot.path("config").path("session_purpose").asText("ASSESSMENT"));
            if (!isPractice) {
                snapshot.path("objectives").fields().forEachRemaining(entry -> {
                    String objId = entry.getKey();
                    String status = entry.getValue().path("assessment").asText("");
                    if (!objId.isBlank() && !status.isBlank() && !"NOT_ASSESSED".equals(status)) {
                        objectiveAssessments.putIfAbsent(objId, status);
                    }
                });
            }
            for (JsonNode turn : snapshot.path("turns")) {
                if (priorQuestionStems.size() >= MAX_PRIOR_QUESTION_STEMS) break;
                String stem = clip(turn.path("question").path("text").asText(""), MAX_PRIOR_QUESTION_STEM_LENGTH);
                if (!stem.isBlank()) {
                    priorQuestionStems.add(stem);
                }
            }
        }
        if (objectiveAssessments.isEmpty() && priorQuestionStems.isEmpty() && masteredSkillIds.isEmpty()) {
            return null;
        }
        return Map.of(
                "objective_assessments", objectiveAssessments,
                "mastered_skill_ids", List.copyOf(masteredSkillIds),
                "prior_question_stems", List.copyOf(priorQuestionStems)
        );
    }

    private Map<String, Object> openingContext(Session session, User user) {
        var profile = session.getApplicationProfile();
        var jd = session.getJobDescription();
        var resume = session.getResume();
        var opening = new java.util.HashMap<String, Object>();
        opening.put("company", clip(profile == null ? "" : profile.getCompany(), MAX_COMPANY_LENGTH));
        opening.put("role_title", clip(firstNonBlank(session.getRoleTitle(),
                profile == null ? null : profile.getRoleTitle(),
                jd == null ? null : jd.getTitle(),
                DEFAULT_ROLE_TITLE), MAX_ROLE_TITLE_LENGTH));
        opening.put("candidate_name", clip(user == null ? "" : user.getDisplayUsername(), MAX_CANDIDATE_NAME_LENGTH));
        opening.put("jd_summary", clip(firstNonBlank(profile == null ? null : profile.getJdText(),
                jd == null ? null : jd.getRawText()), MAX_JD_SUMMARY_LENGTH));
        opening.put("cv_summary", clip(firstNonBlank(profile == null ? null : profile.getCvText(),
                resume == null ? null : resume.getRawText()), MAX_CV_SUMMARY_LENGTH));
        if (session.getAttemptNumber() != null && session.getAttemptNumber() >= 1) {
            opening.put("attempt_number", session.getAttemptNumber());
        }
        return opening;
    }

    private static String firstNonBlank(String... values) {
        for (String value : values) {
            if (value != null && !value.isBlank()) return value;
        }
        return "";
    }

    private static String clip(String value, int maxLength) {
        if (value == null) return "";
        String normalized = value.trim().replaceAll("\\s+", " ");
        return normalized.length() <= maxLength ? normalized : normalized.substring(0, maxLength);
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
        return current(id, version, false);
    }

    private InterviewRun current(String id, long version, boolean allowFailedSubmission) {
        InterviewRun run = run(id);
        if (run.getStateVersion() != version) throw EvidenceStore.conflict("State changed; refresh the interview");
        if (run.getGradingDueAt() != null || (!allowFailedSubmission && run.getGradingAttempt() > 0))
            throw EvidenceStore.conflict("Bài đã nộp đang chờ kết quả chấm.");
        return run;
    }
}
