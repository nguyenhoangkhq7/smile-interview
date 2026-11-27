package fit.iuh.modules.application;

import com.fasterxml.jackson.databind.JsonNode;
import fit.iuh.modules.evidence.EvidenceJson;
import fit.iuh.modules.evidence.InterviewRun;
import fit.iuh.modules.session.entity.Session;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Component;
import java.util.*;

/** Deterministic read model. CV priors and unfinished runs never become observed ability. */
@Component @RequiredArgsConstructor
public class CompetencyProjection {
    static final String NONE = "NOT_ASSESSED", INSUFFICIENT = "INSUFFICIENT_EVIDENCE";
    static final String AT = "DEMONSTRATED_AT_TARGET", ABOVE = "DEMONSTRATED_ABOVE_TARGET";
    static final String BELOW = "DEMONSTRATED_BELOW_TARGET", NOT_DEMONSTRATED = "NOT_DEMONSTRATED";
    static final String VERIFY = "NEEDS_VERIFICATION", PARTIAL = "PARTIALLY_ASSESSED";
    private final EvidenceJson json;

    public record Source(String sessionId, int attemptNumber, String assessedAt) {}
    public record Evidence(Source source, String turnId, String question, String responseExcerpt,
                           String rationale, String performance) {}
    public record Criterion(String id, String description, boolean essential, String atTarget, String assessment,
                            Source lastAssessment, List<Evidence> evidence, String trend) {}
    public record Objective(String id, String claim, String assessment, Source lastChecked,
                            Source lastAssessment, String explanation, List<Criterion> criteria) {}
    public record Skill(String skillId, String baselineAlignment, String assessment, List<Objective> objectives) {}
    public record View(int completedAttempts, int incompatibleAssessments, List<Skill> skills) {}

    private record Signal(String assessment, Source source, Set<String> contexts) {}
    private record Resolution(String assessment, Source source) {}
    private static class CriterionState {
        final JsonNode definition;
        final List<Signal> signals = new ArrayList<>();
        final Map<String, Evidence> evidence = new LinkedHashMap<>();
        Source lastChecked;
        CriterionState(JsonNode definition) { this.definition = definition; }
        Criterion view(boolean checked) {
            Resolution current = resolve(signals);
            return new Criterion(definition.path("criterion_id").asText(), definition.path("description").asText(),
                    definition.path("essential").asBoolean(true), checked ? definition.path("at_target").asText("") : "",
                    current.assessment(), current.source(), List.copyOf(evidence.values()), trend(current));
        }
        private String trend(Resolution current) {
            if (!VERIFY.equals(current.assessment()) || signals.isEmpty()) return null;
            if (lastChecked != null && !lastChecked.equals(current.source())) return null;
            String latest = signals.getLast().assessment();
            if (VERIFY.equals(latest)) return null;
            for (int i = signals.size() - 2; i >= 0; i--) {
                String previous = signals.get(i).assessment();
                if (VERIFY.equals(previous)) return null;
                if (positive(previous) != positive(latest))
                    return positive(latest) ? "IMPROVING" : "DECLINING";
            }
            return null;
        }
    }
    private static class ObjectiveState {
        final JsonNode definition;
        final Map<String, CriterionState> criteria = new LinkedHashMap<>();
        final List<Signal> signals = new ArrayList<>();
        Source lastChecked;
        ObjectiveState(JsonNode definition) {
            this.definition = definition;
            for (JsonNode criterion : definition.path("criteria"))
                criteria.put(criterion.path("criterion_id").asText(), new CriterionState(criterion));
        }
        Objective view() {
            List<Criterion> items = criteria.values().stream().map(criterion -> criterion.view(lastChecked != null)).toList();
            Resolution current = resolve(signals);
            String status = current.assessment();
            Source basis = current.source();
            if (items.stream().anyMatch(c -> c.essential() && VERIFY.equals(c.assessment()))) status = VERIFY;
            if (Set.of(AT, ABOVE, BELOW, NOT_DEMONSTRATED).contains(status) && basis != null) {
                Source previousBasis = basis;
                boolean previousPositive = positive(status);
                if (items.stream().anyMatch(c -> c.essential() && c.lastAssessment() != null
                        && c.lastAssessment().attemptNumber() > previousBasis.attemptNumber()
                        && Set.of(AT, BELOW).contains(c.assessment()) && positive(c.assessment()) != previousPositive))
                    status = INSUFFICIENT;
            }
            if (NONE.equals(status) && lastChecked != null) status = INSUFFICIENT;
            if (basis == null || VERIFY.equals(status)) {
                for (Criterion criterion : items) basis = newer(basis, criterion.lastAssessment());
            }
            String explanation = VERIFY.equals(status)
                    ? "Có bằng chứng mâu thuẫn. Cần hai lượt xác nhận nhất quán về sau ở các bối cảnh độc lập để cập nhật kết luận."
                    : NONE.equals(status) ? "Nội dung này chưa được kiểm tra; không được xem là điểm yếu."
                    : INSUFFICIENT.equals(status) ? "Đã kiểm tra nhưng chưa đủ bằng chứng độc lập để kết luận theo yêu cầu JD."
                    : lastChecked != null && basis != null && lastChecked.attemptNumber() > basis.attemptNumber()
                        ? "Giữ kết luận đã có: lượt kiểm tra mới chưa bổ sung đủ bằng chứng để thay đổi."
                        : "Kết luận dựa trên bằng chứng phỏng vấn theo bộ tiêu chí của hồ sơ.";
            return new Objective(definition.path("objective_id").asText(), definition.path("claim").asText(),
                    status, lastChecked, basis, explanation, items);
        }
    }

    public View project(ApplicationProfile profile, List<Session> attempts, List<InterviewRun> savedRuns) {
        Map<String, JsonNode> baseline = new LinkedHashMap<>();
        for (JsonNode skill : json.read(profile.getSkillGapJson())) baseline.put(skill.path("jd_skill_id").asText(), skill);
        Map<String, ObjectiveState> objectives = new LinkedHashMap<>();
        if (profile.getBlueprintJson() != null) {
            for (JsonNode definition : json.read(profile.getBlueprintJson()).path("objectives")) {
                if (baseline.containsKey(definition.path("skill_id").asText()))
                    objectives.put(definition.path("objective_id").asText(), new ObjectiveState(definition));
            }
        }
        Map<String, InterviewRun> runs = new HashMap<>();
        savedRuns.forEach(run -> runs.put(run.getSessionId(), run));
        int completed = 0, incompatible = 0;
        for (Session attempt : attempts.stream().sorted(Comparator.comparingInt(s -> s.getAttemptNumber())).toList()) {
            InterviewRun run = runs.get(attempt.getId());
            if (run == null) continue;
            JsonNode snapshot = json.read(run.getSnapshotJson()), visible = json.read(run.getPublicJson());
            if (!snapshot.path("is_finished").asBoolean() || !visible.path("is_finished").asBoolean()) continue;
            Map<String, JsonNode> turns = new HashMap<>();
            for (JsonNode turn : snapshot.path("turns")) turns.put(turn.path("turn_id").asText(), turn);
            if (turns.values().stream().noneMatch(turn -> !turn.path("answer").asText("").isBlank())) continue;
            completed++;
            Source source = new Source(attempt.getId(), attempt.getAttemptNumber(),
                    attempt.getEndedAt() == null ? null : attempt.getEndedAt().toString());
            JsonNode target = snapshot.path("recheck_target");
            for (var entry : objectives.entrySet()) {
                if (target.isObject() && !entry.getKey().equals(target.path("objective_id").asText())) continue;
                ObjectiveState objective = entry.getValue();
                JsonNode state = snapshot.path("objectives").path(entry.getKey());
                if (state.isMissingNode()) continue;
                if (!compatible(objective.definition, state.path("objective"))) { incompatible++; continue; }
                boolean visited = turns.values().stream().anyMatch(turn -> entry.getKey().equals(turn.path("objective_id").asText())
                        && !turn.path("answer").asText("").isBlank());
                if (!visited || "EXCLUDED".equals(state.path("lifecycle").asText())) continue;
                objective.lastChecked = source;
                Set<String> contexts = new LinkedHashSet<>();
                boolean hasEvidence = false;
                for (var criterionEntry : objective.criteria.entrySet()) {
                    String criterionId = criterionEntry.getKey();
                    if (target.isObject() && !criterionId.equals(target.path("criterion_id").asText())) continue;
                    CriterionState criterion = criterionEntry.getValue();
                    List<JsonNode> accepted = new ArrayList<>();
                    for (JsonNode evidence : state.path("evidence_history")) {
                        JsonNode turn = turns.get(evidence.path("turn_id").asText());
                        if (turn != null && criterionId.equals(evidence.path("criterion_id").asText())
                                && entry.getKey().equals(turn.path("objective_id").asText())) criterion.lastChecked = source;
                        if (!validEvidence(evidence, turn, objective.definition, criterionId)) continue;
                        accepted.add(evidence);
                        String context = normalize(evidence.path("evidence_scope").asText());
                        if (!context.isBlank()) contexts.add(context);
                        String key = attempt.getId() + ":" + evidence.path("turn_id").asText() + ":" + criterionId;
                        criterion.evidence.put(key, new Evidence(source, evidence.path("turn_id").asText(),
                                turn.path("question").path("text").asText(), evidence.path("response_excerpt").asText(),
                                evidence.path("rationale").asText(), evidence.path("performance").asText()));
                    }
                    if (accepted.isEmpty()) continue;
                    if (target.isObject() && !contains(state.path("contradictions"), criterionId)
                            && !conclusiveCriterion(visible, entry.getKey(), criterionId)) continue;
                    hasEvidence = true;
                    JsonNode finalEvidence = state.path("criterion_results").path(criterionId);
                    JsonNode last = accepted.getLast();
                    for (JsonNode evidence : accepted) {
                        if (evidence.equals(finalEvidence)) last = evidence;
                    }
                    boolean contradictory = contains(state.path("contradictions"), criterionId);
                    String status = contradictory ? VERIFY : "BELOW".equals(last.path("performance").asText()) ? BELOW : AT;
                    Set<String> criterionContexts = new LinkedHashSet<>();
                    String context = normalize(last.path("evidence_scope").asText());
                    if (!context.isBlank()) criterionContexts.add(context);
                    criterion.signals.add(new Signal(status, source, criterionContexts));
                }
                String assessment = state.path("assessment").asText();
                if (ABOVE.equals(assessment) && !hasExtensionEvidence(state, turns, objective.definition)) assessment = AT;
                if (hasEvidence && Set.of(AT, ABOVE, BELOW, NOT_DEMONSTRATED).contains(assessment)) {
                    boolean allRequiredSupported = objective.criteria.values().stream()
                            .filter(c -> c.definition.path("essential").asBoolean(true))
                            .allMatch(c -> !c.signals.isEmpty() && c.signals.getLast().source().equals(source)
                                    && AT.equals(c.signals.getLast().assessment()));
                    boolean hasRequiredFailure = objective.criteria.values().stream()
                            .filter(c -> c.definition.path("essential").asBoolean(true))
                            .anyMatch(c -> !c.signals.isEmpty() && c.signals.getLast().source().equals(source)
                                    && BELOW.equals(c.signals.getLast().assessment()));
                    if (positive(assessment) ? allRequiredSupported : hasRequiredFailure)
                        objective.signals.add(new Signal(assessment, source, contexts));
                }
            }
        }
        List<Skill> skills = new ArrayList<>();
        for (var entry : baseline.entrySet()) {
            List<Objective> items = objectives.values().stream()
                    .filter(o -> entry.getKey().equals(o.definition.path("skill_id").asText())).map(ObjectiveState::view).toList();
            String status = skillAssessment(items);
            skills.add(new Skill(entry.getKey(), entry.getValue().path("semantic_alignment").asText(), status, items));
        }
        return new View(completed, incompatible, skills);
    }

    private static boolean conclusiveCriterion(JsonNode visible, String objectiveId, String criterionId) {
        for (JsonNode objective : visible.path("report").path("objectives")) {
            if (!objectiveId.equals(objective.path("objective_id").asText())) continue;
            for (JsonNode criterion : objective.path("criteria"))
                if (criterionId.equals(criterion.path("criterion_id").asText()))
                    return Set.of(AT, ABOVE, BELOW, NOT_DEMONSTRATED).contains(criterion.path("assessment").asText());
        }
        return false;
    }

    public static boolean compatible(JsonNode expected, JsonNode actual) {
        if (!expected.path("objective_id").equals(actual.path("objective_id"))
                || !expected.path("skill_id").equals(actual.path("skill_id"))
                || !expected.path("criteria").equals(actual.path("criteria"))
                || !expected.path("target_depth").equals(actual.path("target_depth"))) return false;
        String expectedFingerprint = expected.path("rubric_fingerprint").asText();
        String actualFingerprint = actual.path("rubric_fingerprint").asText();
        if (!expectedFingerprint.isBlank() && !actualFingerprint.isBlank()) {
            return expectedFingerprint.equals(actualFingerprint);
        }
        return !expected.path("criteria").isEmpty() && expected.path("target_depth").isInt();
    }

    private static boolean validEvidence(JsonNode evidence, JsonNode turn, JsonNode objective, String criterionId) {
        return validEvidenceAtDepth(evidence, turn, objective, criterionId, objective.path("target_depth").asInt(-1));
    }

    private static boolean validEvidenceAtDepth(JsonNode evidence, JsonNode turn, JsonNode objective, String criterionId, int depth) {
        if (turn == null || !criterionId.equals(evidence.path("criterion_id").asText())
                || !objective.path("objective_id").asText().equals(turn.path("objective_id").asText())
                || !evidence.path("independent").asBoolean(false)
                || !objective.path("target_depth").isInt() || !evidence.path("question_depth").isInt()
                || evidence.path("question_depth").asInt() != depth) return false;
        String performance = evidence.path("performance").asText(), observation = evidence.path("observation").asText();
        if (!Set.of("AT_TARGET", "ABOVE", "BELOW").contains(performance)
                || !Set.of("SUPPORTS", "CONTRADICTS").contains(observation)
                || ("CONTRADICTS".equals(observation) && !"BELOW".equals(performance))) return false;
        String excerpt = evidence.path("response_excerpt").asText();
        return !excerpt.isBlank() && turn.path("answer").asText("").contains(excerpt);
    }

    private static boolean hasExtensionEvidence(JsonNode state, Map<String, JsonNode> turns, JsonNode objective) {
        int depth = objective.path("extension_depth").asInt(-1);
        if (depth <= objective.path("target_depth").asInt()) return false;
        for (JsonNode criterion : objective.path("criteria")) {
            if (!criterion.path("essential").asBoolean(true)) continue;
            boolean found = false;
            for (JsonNode evidence : state.path("evidence_history")) {
                if ("ABOVE".equals(evidence.path("performance").asText())
                        && "SUPPORTS".equals(evidence.path("observation").asText())
                        && validEvidenceAtDepth(evidence, turns.get(evidence.path("turn_id").asText()), objective,
                            criterion.path("criterion_id").asText(), depth)) found = true;
            }
            if (!found) return false;
        }
        return true;
    }

    /** Opposite observations need two later attempts with distinct known contexts to settle. */
    private static Resolution resolve(List<Signal> signals) {
        Signal current = null;
        boolean conflict = false;
        Set<String> contexts = new HashSet<>();
        Set<String> attempts = new HashSet<>();
        for (Signal signal : signals) {
            if (VERIFY.equals(signal.assessment())) {
                current = signal; conflict = true; contexts.clear(); attempts.clear(); continue;
            }
            if (current != null && (VERIFY.equals(current.assessment()) || positive(current.assessment()) != positive(signal.assessment()))) {
                conflict = true; contexts.clear(); attempts.clear();
            }
            if (!signal.contexts().isEmpty() && Collections.disjoint(contexts, signal.contexts())) {
                contexts.addAll(signal.contexts()); attempts.add(signal.source().sessionId());
            }
            current = signal;
            if (conflict && attempts.size() >= 2) conflict = false;
        }
        return current == null ? new Resolution(NONE, null) : new Resolution(conflict ? VERIFY : current.assessment(), current.source());
    }

    private static boolean positive(String value) { return AT.equals(value) || ABOVE.equals(value); }
    private static Source newer(Source a, Source b) {
        return a == null ? b : b == null || a.attemptNumber() >= b.attemptNumber() ? a : b;
    }
    private static boolean contains(JsonNode values, String value) {
        for (JsonNode item : values) if (value.equals(item.asText())) return true;
        return false;
    }
    private static String normalize(String value) { return value.strip().toLowerCase(Locale.ROOT).replaceAll("\\s+", " "); }
    private static String skillAssessment(List<Objective> objectives) {
        if (objectives.isEmpty() || objectives.stream().allMatch(o -> NONE.equals(o.assessment()))) return NONE;
        if (objectives.stream().anyMatch(o -> VERIFY.equals(o.assessment()))) return VERIFY;
        if (objectives.stream().anyMatch(o -> BELOW.equals(o.assessment()) || NOT_DEMONSTRATED.equals(o.assessment()))) return BELOW;
        if (objectives.stream().allMatch(o -> positive(o.assessment())))
            return objectives.stream().allMatch(o -> ABOVE.equals(o.assessment())) ? ABOVE : AT;
        if (objectives.stream().anyMatch(o -> positive(o.assessment()))) return PARTIAL;
        return INSUFFICIENT;
    }
}
