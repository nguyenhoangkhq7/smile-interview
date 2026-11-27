package fit.iuh.modules.application;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.node.*;
import fit.iuh.modules.evidence.*;
import fit.iuh.modules.session.entity.Session;
import org.junit.jupiter.api.Test;
import java.time.LocalDateTime;
import java.util.*;
import static org.assertj.core.api.Assertions.*;
import static fit.iuh.modules.application.CompetencyProjection.*;

class CompetencyProjectionTest {
    private final EvidenceJson json = new EvidenceJson(new ObjectMapper());
    private final CompetencyProjection projection = new CompetencyProjection(json);
    private final ApplicationProfile profile = new ApplicationProfile();
    private record Attempt(Session session, InterviewRun run, ObjectNode snapshot) {}

    CompetencyProjectionTest() {
        profile.setSkillGapJson("[{\"jd_skill_id\":\"sql\",\"semantic_alignment\":\"MISSING\"},"
                + "{\"jd_skill_id\":\"java\",\"semantic_alignment\":\"MATCH\"}]");
        profile.setBlueprintJson(json.tree(Map.of("objectives", List.of(definition("sql"), definition("java")))).toString());
    }

    private JsonNodeFactory nodes() { return JsonNodeFactory.instance; }
    private ObjectNode definition(String skill) {
        return (ObjectNode) json.read("{\"objective_id\":\"" + skill + "-task\",\"skill_id\":\"" + skill
                + "\",\"claim\":\"Check " + skill + "\",\"target_depth\":3,\"rubric_fingerprint\":\"" + skill
                + "-rubric\",\"criteria\":[{\"criterion_id\":\"" + skill + "-c1\",\"description\":\"Explain the execution\","
                + "\"at_target\":\"Identify which operation uses the most time\",\"essential\":true}]}");
    }

    private Attempt attempt(int number, Map<String, String> assessments, String context) {
        ObjectNode snapshot = nodes().objectNode().put("is_finished", true);
        ObjectNode objectives = snapshot.putObject("objectives");
        ArrayNode turns = snapshot.putArray("turns");
        for (var entry : assessments.entrySet()) {
            String skill = entry.getKey(), assessment = entry.getValue();
            String turnId = "t" + number + "-" + skill;
            ObjectNode state = objectives.putObject(skill + "-task");
            state.set("objective", definition(skill));
            state.put("assessment", assessment).put("turns_spent", 1).put("lifecycle", "CLOSED");
            state.putArray("contradictions");
            boolean positive = AT.equals(assessment) || ABOVE.equals(assessment);
            ObjectNode evidence = nodes().objectNode().put("criterion_id", skill + "-c1").put("turn_id", turnId)
                    .put("independent", true).put("question_depth", 3).put("evidence_scope", context)
                    .put("response_excerpt", "EXPLAIN ANALYZE").put("rationale", "Grounded finding")
                    .put("observation", positive ? "SUPPORTS" : "CONTRADICTS")
                    .put("performance", positive ? "AT_TARGET" : "BELOW");
            if (INSUFFICIENT.equals(assessment)) evidence.put("observation", "NO_EVIDENCE").put("performance", "UNDETERMINED");
            state.putArray("evidence_history").add(evidence);
            state.putObject("criterion_results").set(skill + "-c1", evidence.deepCopy());
            ObjectNode turn = turns.addObject().put("turn_id", turnId).put("objective_id", skill + "-task")
                    .put("answer", "I use EXPLAIN ANALYZE to inspect the plan.");
            turn.putObject("question").put("text", "How would you diagnose this incident?");
        }
        Session session = Session.builder().id("s" + number).attemptNumber(number).applicationProfile(profile)
                .status("Completed").endedAt(LocalDateTime.of(2026, 11, 7, 10, number)).build();
        InterviewRun run = new InterviewRun(); run.setSessionId(session.getId());
        return new Attempt(session, run, snapshot);
    }

    private View view(Attempt... attempts) {
        for (Attempt attempt : attempts) {
            attempt.run().setSnapshotJson(attempt.snapshot().toString());
            attempt.run().setPublicJson(attempt.snapshot().toString());
        }
        return projection.project(profile, Arrays.stream(attempts).map(Attempt::session).toList(),
                Arrays.stream(attempts).map(Attempt::run).toList());
    }
    private Skill sql(View view) { return view.skills().getFirst(); }
    private ObjectNode state(Attempt attempt) { return (ObjectNode) attempt.snapshot().path("objectives").path("sql-task"); }

    @Test void cvDiagnosisNeverBecomesAbilityAndAbsentBlueprintIsSupported() {
        View result = view();
        assertThat(result.skills()).hasSize(2).allSatisfy(skill -> assertThat(skill.assessment()).isEqualTo(NONE));
        assertThat(result.skills().getFirst().objectives().getFirst().lastAssessment()).isNull();
        assertThat(result.skills().getFirst().objectives().getFirst().criteria().getFirst().atTarget()).isEmpty();
        profile.setBlueprintJson(null);
        assertThat(view().skills()).allSatisfy(skill -> assertThat(skill.assessment()).isEqualTo(NONE));
    }

    @Test void completedInterviewUpdatesAbilityWithTraceableEvidenceWithoutChangingBaseline() {
        String baseline = profile.getSkillGapJson();
        View result = view(attempt(1, Map.of("sql", AT), "query A"));
        assertThat(sql(result).assessment()).isEqualTo(AT);
        assertThat(result.skills().getLast().assessment()).isEqualTo(NONE);
        var criterion = sql(result).objectives().getFirst().criteria().getFirst();
        assertThat(criterion.atTarget()).isEqualTo("Identify which operation uses the most time");
        var evidence = criterion.evidence().getFirst();
        assertThat(evidence.source().sessionId()).isEqualTo("s1");
        assertThat(evidence.responseExcerpt()).isEqualTo("EXPLAIN ANALYZE");
        assertThat(profile.getSkillGapJson()).isEqualTo(baseline);
        assertThat(result.skills().stream().filter(s -> AT.equals(s.assessment())).count()).isEqualTo(1);
    }

    @Test void unaskedAndInconclusiveLaterChecksKeepPreviousAssessment() {
        var first = attempt(1, Map.of("sql", AT), "query A");
        var other = attempt(2, Map.of("java", AT), "java A");
        var unknown = attempt(3, Map.of("sql", INSUFFICIENT), "query B");
        View result = view(unknown, first, other); // Input order must not affect the result.
        assertThat(sql(result).assessment()).isEqualTo(AT);
        assertThat(sql(result).objectives().getFirst().lastAssessment().attemptNumber()).isEqualTo(1);
        assertThat(sql(result).objectives().getFirst().lastChecked().attemptNumber()).isEqualTo(3);
        assertThat(result.skills()).allSatisfy(s -> assertThat(s.assessment()).isEqualTo(AT));
    }

    @Test void runningAndZeroAnswerCancelledAttemptsDoNotUpdateAbility() {
        var first = attempt(1, Map.of("sql", AT), "A");
        var running = attempt(2, Map.of("sql", BELOW), "B"); running.snapshot().put("is_finished", false);
        var cancelled = attempt(3, Map.of("sql", BELOW), "C"); cancelled.snapshot().putArray("turns");
        var blank = attempt(4, Map.of("sql", BELOW), "D");
        ((ObjectNode) blank.snapshot().path("turns").get(0)).put("answer", " ");
        View result = view(first, running, cancelled, blank);
        assertThat(result.completedAttempts()).isEqualTo(1);
        assertThat(sql(result).assessment()).isEqualTo(AT);
        assertThat(sql(result).objectives().getFirst().lastAssessment().attemptNumber()).isEqualTo(1);
    }

    @Test void conflictingResultsNeedTwoLaterIndependentConsistentAttempts() {
        var first = attempt(1, Map.of("sql", BELOW), "A");
        var second = attempt(2, Map.of("sql", AT), "B");
        assertThat(sql(view(first, second)).assessment()).isEqualTo(VERIFY);
        assertThat(sql(view(first, second)).objectives().getFirst().criteria().getFirst().trend()).isEqualTo("IMPROVING");
        var unknown = attempt(3, Map.of("sql", INSUFFICIENT), "query C");
        var unconfirmed = sql(view(first, second, unknown)).objectives().getFirst().criteria().getFirst();
        assertThat(unconfirmed.assessment()).isEqualTo(VERIFY);
        assertThat(unconfirmed.trend()).isNull();
        var repeated = attempt(3, Map.of("sql", AT), " B  ");
        assertThat(sql(view(first, second, repeated)).assessment()).isEqualTo(VERIFY);
        var confirmation = attempt(4, Map.of("sql", AT), "C");
        assertThat(sql(view(first, second, repeated, confirmation)).assessment()).isEqualTo(AT);
    }

    @Test void oppositeDirectionAlsoRequiresConfirmationAndDoesNotAverageScores() {
        var first = attempt(1, Map.of("sql", AT), "A");
        var second = attempt(2, Map.of("sql", BELOW), "B");
        var third = attempt(3, Map.of("sql", BELOW), "C");
        assertThat(sql(view(first, second)).assessment()).isEqualTo(VERIFY);
        assertThat(sql(view(first, second)).objectives().getFirst().criteria().getFirst().trend()).isEqualTo("DECLINING");
        assertThat(sql(view(first, second, third)).assessment()).isEqualTo(BELOW);
        assertThat(sql(view(first, second, third)).objectives().getFirst().criteria().getFirst().trend()).isNull();
    }

    @Test void easierUnmeasuredAndUngroundedEvidenceCannotReplaceVerifiedAbility() {
        for (String invalid : List.of("easier", "unknown-depth", "invented-excerpt", "not-independent")) {
            var first = attempt(1, Map.of("sql", AT), "A");
            var second = attempt(2, Map.of("sql", BELOW), "B");
            var evidence = (ObjectNode) state(second).path("evidence_history").get(0);
            switch (invalid) {
                case "easier" -> evidence.put("question_depth", 2);
                case "unknown-depth" -> evidence.remove("question_depth");
                case "invented-excerpt" -> evidence.put("response_excerpt", "invented quote");
                case "not-independent" -> evidence.put("independent", false);
            }
            View result = view(first, second);
            assertThat(sql(result).assessment()).as(invalid).isEqualTo(AT);
            assertThat(sql(result).objectives().getFirst().criteria().getFirst().evidence()).hasSize(1);
        }
    }

    @Test void changedRubricCannotOverwriteSameObjectiveId() {
        var first = attempt(1, Map.of("sql", AT), "A");
        var changed = attempt(2, Map.of("sql", BELOW), "B");
        ((ObjectNode) state(changed).path("objective")).put("rubric_fingerprint", "other-rubric");
        View result = view(first, changed);
        assertThat(result.incompatibleAssessments()).isEqualTo(1);
        assertThat(sql(result).assessment()).isEqualTo(AT);
    }

    @Test void compatibleObjectivesMatchWithoutRubricVersion() {
        var blueprint = (ObjectNode) json.read(profile.getBlueprintJson());
        for (var objective : blueprint.path("objectives")) {
            ((ObjectNode) objective).remove("rubric_fingerprint");
        }
        profile.setBlueprintJson(blueprint.toString());
        var currentRun = attempt(1, Map.of("sql", AT), "A");
        ((ObjectNode) state(currentRun).path("objective")).remove("rubric_fingerprint");
        assertThat(sql(view(currentRun)).assessment()).isEqualTo(AT);
    }

    @Test void incompleteCheckDoesNotClaimFailureOrExceedingTheTarget() {
        assertThat(sql(view(attempt(1, Map.of("sql", INSUFFICIENT), "A"))).assessment()).isEqualTo(INSUFFICIENT);
        assertThat(sql(view(attempt(1, Map.of("sql", ABOVE), "A"))).assessment()).isEqualTo(AT);
    }

    @Test void unresolvedWithinAttemptContradictionRequiresVerification() {
        var attempt = attempt(1, Map.of("sql", AT), "A");
        state(attempt).putArray("contradictions").add("sql-c1");
        assertThat(sql(view(attempt)).assessment()).isEqualTo(VERIFY);
    }

    @Test void newUnconfirmedWeaknessMustNotKeepAnObsoletePositiveConclusion() {
        var first = attempt(1, Map.of("sql", AT), "A");
        var second = attempt(2, Map.of("sql", BELOW), "B"); state(second).put("assessment", INSUFFICIENT);
        var third = attempt(3, Map.of("sql", BELOW), "C"); state(third).put("assessment", INSUFFICIENT);
        assertThat(sql(view(first, second)).assessment()).isEqualTo(VERIFY);
        assertThat(sql(view(first, second, third)).assessment()).isEqualTo(INSUFFICIENT);
    }

    @Test void oneVerifiedRequirementCannotClaimTheWholeSkillMeetsTheJd() {
        var blueprint = (ObjectNode) json.read(profile.getBlueprintJson());
        ObjectNode secondSqlTask = definition("sql");
        secondSqlTask.put("objective_id", "sql-second-task");
        ((ArrayNode) blueprint.path("objectives")).add(secondSqlTask);
        profile.setBlueprintJson(blueprint.toString());
        View result = view(attempt(1, Map.of("sql", AT), "A"));
        assertThat(sql(result).assessment()).isEqualTo(PARTIAL);
    }

    @Test void aboveTargetRequiresIndependentExtensionEvidence() {
        var blueprint = (ObjectNode) json.read(profile.getBlueprintJson());
        ((ObjectNode) blueprint.path("objectives").get(0)).put("extension_depth", 4);
        profile.setBlueprintJson(blueprint.toString());
        var attempt = attempt(1, Map.of("sql", ABOVE), "A");
        state(attempt).set("objective", blueprint.path("objectives").get(0).deepCopy());
        ObjectNode extension = ((ObjectNode) state(attempt).path("evidence_history").get(0)).deepCopy()
                .put("turn_id", "extension-turn").put("question_depth", 4).put("performance", "ABOVE");
        ((ArrayNode) state(attempt).path("evidence_history")).add(extension);
        ObjectNode turn = ((ObjectNode) attempt.snapshot().path("turns").get(0)).deepCopy().put("turn_id", "extension-turn");
        ((ArrayNode) attempt.snapshot().path("turns")).add(turn);
        assertThat(sql(view(attempt)).assessment()).isEqualTo(ABOVE);
        extension.put("independent", false);
        assertThat(sql(view(attempt)).assessment()).isEqualTo(AT);
    }

    @Test void optionalFailureCannotDiagnoseAnUnobservedEssentialCriterion() {
        var blueprint = (ObjectNode) json.read(profile.getBlueprintJson());
        ObjectNode definition = (ObjectNode) blueprint.path("objectives").get(0);
        ((ObjectNode) definition.path("criteria").get(0)).put("essential", false);
        ((ArrayNode) definition.path("criteria")).addObject().put("criterion_id", "sql-core")
                .put("description", "Essential requirement").put("essential", true);
        profile.setBlueprintJson(blueprint.toString());
        var attempt = attempt(1, Map.of("sql", BELOW), "A");
        state(attempt).set("objective", definition.deepCopy());
        assertThat(sql(view(attempt)).assessment()).isEqualTo(INSUFFICIENT);
    }

    @Test void newestEvidenceSourceIsSeparateFromTheBasisForTheFullAssessment() {
        var first = attempt(1, Map.of("sql", AT), "A");
        var second = attempt(2, Map.of("sql", AT), "B"); state(second).put("assessment", INSUFFICIENT);
        var result = view(first, second);
        assertThat(sql(result).objectives().getFirst().criteria().getFirst().lastAssessment().attemptNumber()).isEqualTo(2);
        assertThat(sql(result).objectives().getFirst().lastAssessment().attemptNumber()).isEqualTo(1);
        assertThat(sql(result).assessment()).isEqualTo(AT);
    }

    @Test void legacyBlueprintFingerprintRemainsCompatibleWithLeanAttemptSnapshot() {
        var currentRun = attempt(1, Map.of("sql", AT), "A");
        ((ObjectNode) state(currentRun).path("objective")).remove("rubric_fingerprint");
        View result = view(currentRun);
        assertThat(result.incompatibleAssessments()).isZero();
        assertThat(sql(result).assessment()).isEqualTo(AT);
    }
}
