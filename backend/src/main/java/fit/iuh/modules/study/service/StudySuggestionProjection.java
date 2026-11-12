package fit.iuh.modules.study.service;

import com.fasterxml.jackson.databind.JsonNode;
import fit.iuh.modules.application.ApplicationProfile;
import fit.iuh.modules.application.CompetencyProjection;
import fit.iuh.modules.evidence.EvidenceJson;
import fit.iuh.modules.evidence.InterviewRun;
import fit.iuh.modules.session.entity.Session;
import fit.iuh.modules.study.dto.StudyPlanDtos.*;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Component;

import java.util.*;
import java.util.stream.Collectors;

/** Study actions supplement the competency conclusion; they never change observed ability. */
@Component
@RequiredArgsConstructor
public class StudySuggestionProjection {
    private final EvidenceJson json;
    private record Activity(JsonNode state, CompetencyProjection.Source source) {}

    public List<ObjectiveSuggestion> project(ApplicationProfile profile, CompetencyProjection.View competency,
                                              List<Session> attempts, List<InterviewRun> runs) {
        var definitions = new HashMap<String, JsonNode>();
        for (var objective : json.read(profile.getBlueprintJson() == null ? "{}" : profile.getBlueprintJson()).path("objectives"))
            definitions.put(objective.path("objective_id").asText(), objective);
        var bySession = runs.stream().collect(Collectors.toMap(InterviewRun::getSessionId, run -> run));
        var activities = new HashMap<String, Activity>();
        for (var attempt : attempts.stream().sorted(Comparator.comparingInt(Session::getAttemptNumber).reversed()).toList()) {
            var run = bySession.get(attempt.getId());
            if (run == null) continue;
            var snapshot = json.read(run.getSnapshotJson());
            if (!snapshot.path("is_finished").asBoolean() || !json.read(run.getPublicJson()).path("is_finished").asBoolean()
                    || snapshot.path("turns").isEmpty()) continue;
            var source = new CompetencyProjection.Source(attempt.getId(), attempt.getAttemptNumber(),
                    attempt.getEndedAt() == null ? null : attempt.getEndedAt().toString());
            for (var definition : definitions.values()) {
                var state = snapshot.path("objectives").path(definition.path("objective_id").asText());
                if ("EXCLUDED".equals(state.path("lifecycle").asText())
                        || !CompetencyProjection.compatible(definition, state.path("objective"))) continue;
                for (var criterion : definition.path("criteria")) {
                    String id = criterion.path("criterion_id").asText();
                    boolean attempted = state.path("criterion_progress").path(id).path("turns_spent").asInt() > 0
                            || state.path("criterion_results").has(id);
                    for (var evidence : state.path("evidence_history"))
                        attempted |= id.equals(evidence.path("criterion_id").asText());
                    for (var turn : snapshot.path("turns"))
                        if (!turn.path("answer").asText("").isBlank()
                                && definition.path("objective_id").asText().equals(turn.path("objective_id").asText()))
                            attempted |= contains(turn.path("question").path("criterion_ids"), id);
                    if (attempted) activities.putIfAbsent(id, new Activity(state, source));
                }
            }
        }
        var suggestions = new ArrayList<ObjectiveSuggestion>();
        for (var skill : competency.skills()) for (var objective : skill.objectives()) {
            var definition = definitions.get(objective.id());
            if (definition == null || objective.lastChecked() == null) continue;
            var criteria = new ArrayList<CriterionSuggestion>();
            for (var criterion : objective.criteria()) {
                var activity = activities.get(criterion.id());
                boolean struggled = false;
                if (activity != null) {
                    var state = activity.state();
                    struggled = state.path("criterion_progress").path(criterion.id()).path("easier_spent").asBoolean()
                            || contains(state.path("assisted_criteria"), criterion.id());
                    for (var evidence : state.path("evidence_history"))
                        if (criterion.id().equals(evidence.path("criterion_id").asText()))
                            struggled |= "BELOW".equals(evidence.path("performance").asText())
                                    || evidence.path("explicit_inability").asBoolean();
                }
                String kind, reason;
                switch (criterion.assessment()) {
                    case "DEMONSTRATED_BELOW_TARGET", "NOT_DEMONSTRATED" -> {
                        kind = "REVIEW"; reason = "Có bằng chứng chưa đạt yêu cầu; ưu tiên ôn tiêu chí này.";
                    }
                    case "NEEDS_VERIFICATION" -> {
                        kind = "VERIFY"; reason = "Có bằng chứng mâu thuẫn; cần thực hành và kiểm chứng lại.";
                    }
                    case "DEMONSTRATED_AT_TARGET", "DEMONSTRATED_ABOVE_TARGET" -> {
                        kind = struggled ? "REINFORCE" : "MET";
                        reason = struggled ? "Đã đạt nhưng từng gặp khó khăn hoặc cần trợ giúp; có thể luyện để củng cố."
                                : "Đã có bằng chứng đạt yêu cầu.";
                    }
                    default -> {
                        kind = activity == null ? "UNASSESSED" : "VERIFY";
                        reason = activity == null ? "Chưa đánh giá; bạn có thể chủ động chọn ôn thêm."
                                : "Đã kiểm tra nhưng chưa đủ bằng chứng kết luận; cần luyện và kiểm chứng thêm.";
                    }
                }
                String goal = "";
                for (var item : definition.path("criteria"))
                    if (criterion.id().equals(item.path("criterion_id").asText())) goal = item.path("at_target").asText();
                var source = ("REVIEW".equals(kind) || "VERIFY".equals(kind)) && criterion.lastAssessment() != null
                        ? criterion.lastAssessment() : activity == null ? null : activity.source();
                criteria.add(new CriterionSuggestion(criterion.id(), criterion.description(), criterion.essential(),
                        criterion.assessment(), kind, Set.of("REVIEW", "VERIFY").contains(kind), reason, goal, source,
                        criterion.lastAssessment()));
            }
            suggestions.add(new ObjectiveSuggestion(skill.skillId(), objective.id(), objective.claim(),
                    objective.assessment(), objective.lastChecked(), criteria));
        }
        return suggestions;
    }

    private static boolean contains(JsonNode array, String value) {
        for (var item : array) if (value.equals(item.asText())) return true;
        return false;
    }
}
