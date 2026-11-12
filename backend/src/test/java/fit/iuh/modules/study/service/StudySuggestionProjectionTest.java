package fit.iuh.modules.study.service;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.node.ObjectNode;
import fit.iuh.modules.application.ApplicationProfile;
import fit.iuh.modules.application.CompetencyProjection;
import fit.iuh.modules.evidence.EvidenceJson;
import fit.iuh.modules.evidence.InterviewRun;
import fit.iuh.modules.session.entity.Session;
import org.junit.jupiter.api.Test;

import java.util.*;
import static org.assertj.core.api.Assertions.assertThat;

class StudySuggestionProjectionTest {
    private final EvidenceJson json = new EvidenceJson(new ObjectMapper());
    private final CompetencyProjection competency = new CompetencyProjection(json);
    private final StudySuggestionProjection suggestions = new StudySuggestionProjection(json);
    private final ApplicationProfile profile = new ApplicationProfile();
    private final ObjectNode definition = (ObjectNode) json.read("""
            {"objective_id":"a","skill_id":"sql","claim":"Diagnose SQL", "target_depth":3,
             "rubric_fingerprint":"v1","criteria":[]}
            """);
    private final ObjectNode snapshot = (ObjectNode) json.read("""
            {"is_finished":true,"turns":[],"objectives":{"a":{"assessment":"DEMONSTRATED_BELOW_TARGET",
              "lifecycle":"CLOSED","turns_spent":3,"criterion_progress":{},"evidence_history":[],"criterion_results":{}}}}
            """);
    private final Session session = Session.builder().id("s1").attemptNumber(1).status("Completed").build();

    StudySuggestionProjectionTest() {
        for (int i = 1; i <= 5; i++) definition.withArray("criteria").addObject()
                .put("criterion_id", "c" + i).put("description", "Criterion " + i).put("essential", true)
                .put("at_target", "Observable outcome " + i);
        profile.setSkillGapJson("[{\"jd_skill_id\":\"sql\"}]");
        profile.setBlueprintJson(json.tree(Map.of("objectives", List.of(definition))).toString());
        state().set("objective", definition.deepCopy());
    }

    private ObjectNode state() { return (ObjectNode) snapshot.path("objectives").path("a"); }
    private void answer(int turn, String criterion, String performance) {
        String turnId = "t" + turn;
        var item = snapshot.withArray("turns").addObject().put("turn_id", turnId).put("objective_id", "a")
                .put("answer", "Original answer " + turn);
        item.putObject("question").put("text", "Explain the example").put("assistance", "NONE")
                .putArray("criterion_ids").add(criterion);
        var evidence = state().withArray("evidence_history").addObject().put("criterion_id", criterion)
                .put("turn_id", turnId).put("independent", true).put("question_depth", 3)
                .put("evidence_scope", "context-" + turn).put("response_excerpt", "Original answer " + turn)
                .put("rationale", "Observed performance").put("performance", performance)
                .put("observation", "BELOW".equals(performance) ? "CONTRADICTS" : "SUPPORTS");
        state().withObject("criterion_results").set(criterion, evidence.deepCopy());
        state().withObject("criterion_progress").putObject(criterion).put("turns_spent", 1);
    }
    private List<fit.iuh.modules.study.dto.StudyPlanDtos.ObjectiveSuggestion> project() {
        var run = new InterviewRun();
        run.setSessionId(session.getId()); run.setSnapshotJson(snapshot.toString()); run.setPublicJson(snapshot.toString());
        var attempts = List.of(session); var runs = List.of(run);
        return suggestions.project(profile, competency.project(profile, attempts, runs), attempts, runs);
    }

    @Test void fiveCriteriaThreeQuestionsTwoFailuresSelectExactlyTwoCriteria() {
        answer(1, "c1", "AT_TARGET"); answer(2, "c2", "BELOW"); answer(3, "c3", "BELOW");
        var criteria = project().getFirst().criteria();
        assertThat(criteria).hasSize(5);
        assertThat(criteria.stream().filter(c -> c.selectedByDefault()).map(c -> c.criterionId()))
                .containsExactly("c2", "c3");
        assertThat(criteria.stream().map(c -> c.kind())).containsExactly("MET", "REVIEW", "REVIEW", "UNASSESSED", "UNASSESSED");
        assertThat(criteria.get(3).source()).isNull();
        assertThat(criteria.get(1).goal()).isEqualTo("Observable outcome 2");
    }

    @Test void repeatedQuestionsForOneCriterionProduceOneChecklistSuggestion() {
        answer(1, "c2", "BELOW"); answer(2, "c2", "BELOW"); answer(3, "c2", "BELOW");
        assertThat(project().getFirst().criteria().stream().filter(c -> c.selectedByDefault()).map(c -> c.criterionId()))
                .containsExactly("c2");
    }

    @Test void inconclusiveAnswerIsVerificationRatherThanConfirmedWeakness() {
        answer(1, "c1", "UNDETERMINED");
        state().put("assessment", "INSUFFICIENT_EVIDENCE");
        var item = project().getFirst().criteria().getFirst();
        assertThat(item.kind()).isEqualTo("VERIFY");
        assertThat(item.assessment()).isEqualTo("NOT_ASSESSED");
        assertThat(item.selectedByDefault()).isTrue();
    }

    @Test void contradictoryEvidenceRequiresVerification() {
        answer(1, "c1", "BELOW"); state().putArray("contradictions").add("c1");
        assertThat(project().getFirst().criteria().getFirst().kind()).isEqualTo("VERIFY");
    }

    @Test void runningAndIncompatibleInterviewsDoNotCreateSuggestions() {
        answer(1, "c1", "BELOW"); snapshot.put("is_finished", false);
        assertThat(project()).isEmpty();
        snapshot.put("is_finished", true);
        ((ObjectNode) state().path("objective")).put("rubric_fingerprint", "changed");
        assertThat(project()).isEmpty();
    }

    @Test void passingAfterAssistanceIsOptionalReinforcement() {
        answer(1, "c1", "AT_TARGET"); state().putArray("assisted_criteria").add("c1");
        var item = project().getFirst().criteria().getFirst();
        assertThat(item.kind()).isEqualTo("REINFORCE");
        assertThat(item.selectedByDefault()).isFalse();
    }
}
