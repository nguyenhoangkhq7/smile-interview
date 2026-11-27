package fit.iuh.modules.admin.interviews.service;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.node.MissingNode;
import fit.iuh.modules.admin.interviews.dto.AdminInterviewDtos.*;
import fit.iuh.modules.admin.interviews.model.InterviewStatus;
import fit.iuh.modules.admin.interviews.repository.AdminInterviewRepository;
import fit.iuh.modules.admin.interviews.repository.AdminInterviewRepository.Row;
import fit.iuh.modules.session.repository.SessionTurnRepository;
import lombok.RequiredArgsConstructor;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Isolation;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.server.ResponseStatusException;

import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Locale;

@Service
@RequiredArgsConstructor
public class AdminInterviewService {
    private final AdminInterviewRepository interviews;
    private final SessionTurnRepository legacyTurns;
    private final ObjectMapper json;

    @Transactional(readOnly = true, isolation = Isolation.REPEATABLE_READ)
    public QualityInput qualityInput(String id) {
        var source = interviews.quality(id).orElseThrow(() ->
                new ResponseStatusException(HttpStatus.NOT_FOUND, "Không tìm thấy phiên phỏng vấn."));
        var state = read(source.publicJson());
        var transcript = source.publicJson() != null
                ? v2Transcript(state, state.path("report").path("objectives"))
                : legacyTranscript(id);
        var questions = transcript.turns().stream()
                .map(turn -> new QualityQuestion(turn.question(), turn.skill())).toList();
        return new QualityInput(source.cv(), source.jd(), source.skillsJson(), source.reportJson(),
                interactionMode(read(source.configJson()), source.interviewType()), questions);
    }

    @Transactional(readOnly = true, isolation = Isolation.REPEATABLE_READ)
    public Page list(String search, InterviewStatus status, int page, int size) {
        String query = search.strip();
        if (query.startsWith("#")) query = query.substring(1).stripLeading();
        var counts = interviews.counts(query);
        long total = status == null ? counts.values().stream().mapToLong(Long::longValue).sum()
                : counts.getOrDefault(status, 0L);
        int current = (int) Math.min(page, Math.max(1, (total + size - 1) / size));
        var summaries = interviews.page(query, status, (current - 1L) * size, size).stream()
                .map(row -> summary(row, read(row.configJson()))).toList();
        return new Page(summaries, total, current, size, counts);
    }

    @Transactional(readOnly = true, isolation = Isolation.REPEATABLE_READ)
    public Detail detail(String id) {
        var source = interviews.detail(id).orElseThrow(() ->
                new ResponseStatusException(HttpStatus.NOT_FOUND, "Không tìm thấy phiên phỏng vấn."));
        var row = source.session();
        var config = read(row.configJson());
        var state = read(source.publicJson());
        boolean isV2 = source.publicJson() != null;
        boolean finalized = (row.status() == InterviewStatus.COMPLETED || row.status() == InterviewStatus.ANOMALY)
                && (!isV2 || state.path("is_finished").isBoolean() && state.path("is_finished").asBoolean());
        var gap = read(source.gapReport());
        var inputs = new Inputs(source.cvName(), source.jdTitle(), source.company());
        var matching = new Matching(matchingScore(gap), source.hasGap() || gap.isObject());
        var report = isV2 ? state.path("report") : read(source.legacyReport());
        var objectives = report.path("objectives");
        var blueprint = config.isObject() ? new Blueprint(integer(config, "max_questions"),
                integer(config, "duration_seconds"), integer(config, "max_questions_per_objective"),
                text(config, "focused_question_mode"), objectives.isArray() ? objectives.size() : null,
                policy(read(source.policyJson()))) : null;
        var session = summary(row, config);
        Transcript transcript = isV2 ? v2Transcript(state, objectives) : legacyTranscript(id);
        if (!finalized) return new Detail(session, inputs, matching, blueprint, false, transcript, null);

        var findings = new ArrayList<Objective>();
        if (objectives.isArray()) {
            for (var entry : objectives) {
                String skill = text(entry, "skill_id");
                if (skill != null) {
                    findings.add(new Objective(skill, text(entry, "claim"), text(entry, "assessment"),
                            strings(entry.path("strengths")), strings(entry.path("weaknesses"))));
                }
            }
        }
        String feedback = text(report.path("coaching"), "overall_summary");
        var result = new Report(termination(row, report), findings, source.overallScore(),
                feedback == null ? source.overallFeedback() : feedback);
        return new Detail(session, inputs, matching, blueprint, true, transcript, result);
    }

    public MatchingDetail matching(String id) {
        var source = interviews.matching(id).orElseThrow(() ->
                new ResponseStatusException(HttpStatus.NOT_FOUND, "Không tìm thấy phiên phỏng vấn."));
        var report = read(source.reportJson());
        var skills = new ArrayList<MatchingSkill>();
        var savedSkills = read(source.skillsJson());
        if (savedSkills.isArray()) {
            for (var entry : savedSkills) {
                if (text(entry, "jd_skill_id") != null) skills.add(matchingSkill(entry));
            }
        }
        return new MatchingDetail(matchingScore(report), report.path("degraded").asBoolean(false),
                savedSkills.isArray() || report.isObject(), skills);
    }

    private static MatchingSkill matchingSkill(JsonNode entry) {
        var tasks = new ArrayList<MatchingTask>();
        for (var task : entry.path("job_tasks")) {
            String description = text(task, "description");
            if (description != null) tasks.add(new MatchingTask(description, text(task, "requirement_kind"),
                    decimal(task, "required_level"), strings(task.path("evidence_spans"))));
        }
        String cvSkill = text(entry, "matched_cv_skill_name");
        return new MatchingSkill(text(entry, "jd_skill_id"), text(entry, "jd_skill_name"),
                text(entry, "semantic_alignment"), cvSkill == null ? text(entry, "matched_cv_skill_id") : cvSkill,
                decimal(entry, "required_proficiency"), decimal(entry, "priority"), decimal(entry, "importance_weight"),
                text(entry, "context_job"), strings(entry.path("cv_evidence_spans")),
                strings(entry.path("jd_evidence_spans")), tasks);
    }

    private static Double matchingScore(JsonNode report) {
        Double score = decimal(report, "matching_score");
        return score != null && score >= 0 && score <= 1 ? score : null;
    }

    private static Transcript v2Transcript(JsonNode state, JsonNode objectives) {
        var skills = new HashMap<String, String>();
        var evidence = new HashMap<String, List<Evidence>>();
        if (objectives.isArray()) {
            for (var objective : objectives) {
                skills.put(text(objective, "objective_id"), text(objective, "skill_id"));
                for (var entry : objective.path("evidence")) {
                    String turn = text(entry, "turn_id");
                    if (turn != null) {
                        evidence.computeIfAbsent(turn, ignored -> new ArrayList<>())
                                .add(new Evidence(text(entry, "criterion_id"), text(entry, "response_excerpt"),
                                        text(entry, "rationale"), text(entry, "performance")));
                    }
                }
            }
        }
        var turns = new ArrayList<Turn>();
        for (var entry : state.path("turns")) {
            String id = text(entry, "turn_id");
            if (id != null) {
                turns.add(new Turn(id, skills.get(text(entry, "objective_id")), text(entry, "mode"),
                        text(entry, "question"), text(entry, "answer"), text(entry, "feedback"), null,
                        null, null, null, evidence.getOrDefault(id, List.of())));
            }
        }
        var pending = state.path("pending_turn");
        String pendingId = text(pending, "turn_id");
        if (pendingId != null && turns.stream().noneMatch(turn -> pendingId.equals(turn.id()))) {
            turns.add(new Turn(pendingId, skills.get(text(pending, "objective_id")), text(pending, "mode"),
                    text(pending, "question"), text(pending, "answer"), text(pending, "feedback"), null,
                    null, null, null, evidence.getOrDefault(pendingId, List.of())));
        }
        var conversation = state.path("conversation");
        String phase = text(conversation, "phase");
        String closing = "FINISHED".equals(phase) || "CLOSING".equals(phase)
                ? text(conversation.path("message"), "text") : null;
        return new Transcript(text(conversation, "opening_text"), text(conversation, "introduction"), closing, turns);
    }

    private Transcript legacyTranscript(String session) {
        var turns = legacyTurns.findBySessionIdOrderByIdAsc(session).stream()
                .filter(turn -> turn.getQuestion() != null || turn.getAnswer() != null)
                .map(turn -> new Turn(Long.toString(turn.getId()), turn.getTopicTag(), null, turn.getQuestion(),
                        turn.getAnswer(), null, turn.getScore(), turn.getStrengths(), turn.getImprovements(),
                        turn.getSuggestedAnswer(), List.of())).toList();
        return new Transcript(null, null, null, turns);
    }

    private static Summary summary(Row row, JsonNode config) {
        String mode = interactionMode(config, row.interviewType());
        var started = row.runStartedAt();
        if (started == null && (row.status() == InterviewStatus.IN_PROGRESS || row.status() == InterviewStatus.COMPLETED)) {
            started = row.createdAt();
        }
        return new Summary(row.id(), row.candidateName(), row.roleTitle(), row.status(), mode, row.createdAt(),
                started, row.endedAt(), row.userRating());
    }

    private static String interactionMode(JsonNode config, String fallback) {
        String mode = config.isObject() ? config.path("interaction_mode").asText("TEXT") : fallback;
        String normalized = mode == null ? "" : mode.toUpperCase(Locale.ROOT);
        return "VOICE".equals(normalized) || "TEXT".equals(normalized) ? normalized : null;
    }

    private static Policy policy(JsonNode node) {
        if (!node.isObject()) return null;
        var extension = node.path("allow_extension_probes");
        return new Policy(decimal(node, "core_importance"), decimal(node, "reserve_followup_fraction"),
                integer(node, "fallback_depth"), integer(node, "min_failure_contexts"),
                extension.isBoolean() ? extension.booleanValue() : null);
    }

    private static Double decimal(JsonNode node, String field) {
        var value = node.path(field);
        return value.isNumber() ? value.doubleValue() : null;
    }

    private static String termination(Row row, JsonNode report) {
        String reason = text(report, "termination_reason");
        return reason == null && row.status() == InterviewStatus.ANOMALY ? row.rawStatus() : reason;
    }

    private JsonNode read(String value) {
        if (value != null && !value.isBlank()) {
            try {
                var node = json.readTree(value);
                if (node != null) return node;
            } catch (JsonProcessingException ex) {
                // Older sessions may contain incomplete optional metadata.
            }
        }
        return MissingNode.getInstance();
    }

    private static String text(JsonNode node, String field) {
        var value = node.path(field);
        return value.isTextual() && !value.asText().isBlank() ? value.asText() : null;
    }

    private static Integer integer(JsonNode node, String field) {
        var value = node.path(field);
        return value.isIntegralNumber() && value.canConvertToInt() ? value.intValue() : null;
    }

    private static List<String> strings(JsonNode array) {
        var result = new ArrayList<String>();
        if (array.isArray()) {
            for (var entry : array) {
                if (entry.isTextual() && !entry.asText().isBlank()) result.add(entry.asText());
            }
        }
        return result;
    }
}
