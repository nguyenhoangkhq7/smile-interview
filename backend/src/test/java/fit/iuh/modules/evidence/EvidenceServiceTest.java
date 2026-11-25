package fit.iuh.modules.evidence;

import com.fasterxml.jackson.databind.ObjectMapper;
import fit.iuh.modules.auth.entity.User;
import fit.iuh.modules.session.entity.Session;
import fit.iuh.modules.session.repository.SessionRepository;
import fit.iuh.modules.session.repository.SessionTurnRepository;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.CsvSource;
import org.springframework.web.server.ResponseStatusException;
import java.util.Optional;
import java.util.UUID;
import static org.assertj.core.api.Assertions.*;
import static org.mockito.Mockito.*;

class EvidenceServiceTest {
    private final SessionRepository sessions = mock(SessionRepository.class);
    private final SessionTurnRepository turns = mock(SessionTurnRepository.class);
    private final InterviewRunRepository runs = mock(InterviewRunRepository.class);
    private final EvidenceStore store = mock(EvidenceStore.class);
    private final EvidenceAiClient ai = mock(EvidenceAiClient.class);
    private final EvidenceInputs inputs = mock(EvidenceInputs.class);
    private final EvidenceJson json = new EvidenceJson(new ObjectMapper());
    private final EvidenceService service = new EvidenceService(sessions, turns, runs, store, ai, inputs, json,
            mock(EvidenceAdmission.class));
    private final User owner = User.builder().id(UUID.randomUUID()).build();

    private void session() {
        when(sessions.findById("s")).thenReturn(Optional.of(Session.builder().id("s").userId(owner.getId()).build()));
    }

    @Test void voiceVocabularyUsesFrozenSkillNamesWithoutSendingCvOrExpectedAnswers() {
        session();
        InterviewRun run = new InterviewRun();
        run.setSnapshotJson("""
            {"skills":[{"jd_skill_id":"spring_boot"},{"jd_skill_id":"PostgreSQL"},{"jd_skill_id":"spring_boot"}],
             "secret_expected_answer":"must never be a transcription hint"}
            """);
        when(runs.findById("s")).thenReturn(Optional.of(run));
        assertThat(service.voiceTerms("s", owner)).containsExactly("spring boot", "PostgreSQL");
        assertThatThrownBy(() -> service.voiceTerms("s", User.builder().id(UUID.randomUUID()).build()))
                .isInstanceOf(ResponseStatusException.class);
        verifyNoInteractions(ai, inputs);
    }

    @Test void ownerIsCheckedBeforeReturningAReplay() {
        session();
        var answer = new EvidenceDtos.Answer(UUID.randomUUID(), "turn", 1, "answer");
        assertThatThrownBy(() -> service.respond("s", User.builder().id(UUID.randomUUID()).build(), answer))
                .isInstanceOfSatisfying(ResponseStatusException.class, ex -> assertThat(ex.getStatusCode().value()).isEqualTo(403));
        verifyNoInteractions(store, ai);
    }

    @Test void repeatedAnswerReturnsReceiptWithoutCallingAi() {
        session();
        var answer = new EvidenceDtos.Answer(UUID.randomUUID(), "turn", 1, "answer");
        var saved = json.read("{\"state_version\":2}");
        when(store.replay("s", answer.requestId(), json.hash(answer))).thenReturn(saved);
        assertThat(service.respond("s", owner, answer)).isEqualTo(saved);
        verifyNoInteractions(ai, runs);
    }

    @Test void staleAnswerIsRejectedBeforeModelCall() {
        session();
        InterviewRun run = new InterviewRun(); run.setStateVersion(2);
        when(runs.findById("s")).thenReturn(Optional.of(run));
        var answer = new EvidenceDtos.Answer(UUID.randomUUID(), "turn", 1, "answer");
        assertThatThrownBy(() -> service.respond("s", owner, answer)).isInstanceOf(ResponseStatusException.class);
        verifyNoInteractions(ai);
    }

    @Test void answerCommitsBeforeQuestionGenerationAndRetryReplaysOnlyItsOwnCommand() {
        session();
        var run = new InterviewRun();
        run.setStateVersion(1);
        run.setConfigJson("{}");
        run.setSnapshotJson("{\"pending_turn\":{\"turn_id\":\"turn-1\"}}");
        when(runs.findById("s")).thenReturn(Optional.of(run));
        var answer = new EvidenceDtos.Answer(UUID.randomUUID(), "turn-1", 1, "answer");
        var graded = json.read("""
            {"snapshot":{"next_question_action":"INITIAL","turns":[{"answer":"answer"}]},
             "public":{"state_version":2,"awaiting_question":true,"turns":[{"answer":"answer"}]}}
            """);
        when(ai.compute(eq("respond"), any())).thenReturn(graded);
        when(store.commit(any())).thenAnswer(call -> {
            var commit = call.<EvidenceStore.Commit>getArgument(0);
            var next = commit.result();
            run.setStateVersion(next.path("public").path("state_version").asLong());
            run.setSnapshotJson(next.path("snapshot").toString());
            run.setPublicJson(next.path("public").toString());
            return next.path("public");
        });
        assertThat(service.respond("s", owner, answer)).isEqualTo(graded.path("public"));
        var gradePayload = org.mockito.ArgumentCaptor.forClass(com.fasterxml.jackson.databind.JsonNode.class);
        verify(ai).compute(eq("respond"), gradePayload.capture());
        assertThat(gradePayload.getValue().path("defer_question").asBoolean()).isTrue();

        var command = new EvidenceDtos.NextQuestion(UUID.randomUUID(), 2);
        var ready = json.read("""
            {"snapshot":{},"public":{"state_version":3,"pending_turn":{"turn_id":"turn-2"}}}
            """);
        when(ai.compute(eq("next-question"), any()))
                .thenThrow(new ResponseStatusException(org.springframework.http.HttpStatus.SERVICE_UNAVAILABLE))
                .thenReturn(ready);
        assertThatThrownBy(() -> service.nextQuestion("s", owner, command)).isInstanceOf(ResponseStatusException.class);
        assertThat(service.read("s", owner)).isEqualTo(graded.path("public"));
        assertThat(service.nextQuestion("s", owner, command)).isEqualTo(ready.path("public"));
        var hash = json.hash(java.util.Map.of("next-question", command));
        when(store.replay("s", command.requestId(), hash)).thenReturn(ready.path("public"));
        assertThat(service.nextQuestion("s", owner, command)).isEqualTo(ready.path("public"));
        verify(ai, times(2)).compute(eq("next-question"), any());
        verifyNoMoreInteractions(ai);
    }

    @Test void repeatedStartReusesFrozenConfigurationAndPlan() {
        session();
        InterviewRun run = new InterviewRun();
        when(runs.findById("s")).thenReturn(Optional.of(run));
        var config = EvidenceDtos.Config.defaults();
        service.start("s", owner, config);
        verify(store).sameStart(run, json.tree(config));
        verifyNoInteractions(ai, inputs);
    }

    @Test void startReusingProfileBlueprintDoesNotSendPolicy() {
        var profile = new fit.iuh.modules.application.ApplicationProfile();
        profile.setCompany("Acme");
        profile.setBlueprintJson("{\"objectives\":[]}");
        profile.setPolicyJson("{\"fallback_depth\":1}");
        profile.setCvText("CV. Đã xử lý lỗi tạo đơn\r\nhàng trùng. Kết thúc.");
        profile.setJdText("JD. Xử lý yêu cầu\t gửi lại sau timeout. Kết thúc.");
        var session = Session.builder().id("s").userId(owner.getId()).roleTitle("Backend")
                .applicationProfile(profile).build();
        when(sessions.findById("s")).thenReturn(Optional.of(session));
        when(runs.findById("s")).thenReturn(Optional.empty());
        when(turns.findBySessionIdOrderByIdAsc("s")).thenReturn(java.util.List.of());
        when(inputs.skills(session)).thenReturn(json.read("""
                [{"jd_skill_id":"sql",
                  "cv_evidence_spans":["Đã xử lý lỗi tạo đơn hàng trùng.","Cụm do mô hình thêm"],
                  "job_tasks":[{"evidence_spans":["Xử lý yêu cầu gửi lại sau timeout.","Xử lý sau khi thanh toán"]}]}]
                """));
        var aiResult = json.read("{\"snapshot\":{\"state_version\":1},\"public\":{\"state_version\":1}}");
        when(ai.compute(eq("start"), any())).thenReturn(aiResult);
        when(store.commit(any())).thenReturn(aiResult.path("public"));

        service.start("s", owner, EvidenceDtos.Config.defaults());

        var payloadCaptor = org.mockito.ArgumentCaptor.forClass(com.fasterxml.jackson.databind.JsonNode.class);
        verify(ai).compute(eq("start"), payloadCaptor.capture());
        assertThat(payloadCaptor.getValue().has("blueprint")).isTrue();
        assertThat(payloadCaptor.getValue().has("policy")).isFalse();
        assertThat(payloadCaptor.getValue().path("verification_sources")).isEqualTo(json.read("""
                {"cv":{"Đã xử lý lỗi tạo đơn hàng trùng.":"Đã xử lý lỗi tạo đơn\\r\\nhàng trùng."},
                 "jd":{"Xử lý yêu cầu gửi lại sau timeout.":"Xử lý yêu cầu\\t gửi lại sau timeout."}}
                """));
    }

    @Test void startStripsRetiredFieldsFromLegacyProfileBlueprint() {
        var profile = new fit.iuh.modules.application.ApplicationProfile();
        profile.setBlueprintJson("""
                {"objectives":[{
                  "objective_id":"obj-1","requirement_id":"sql:inferred","skill_id":"sql",
                  "claim":"Optimize SQL","required_proficiency":3.0,"target_depth":2,
                  "extension_criterion_ids":[],"inferred":true,"rubric_version":"evidence-2.0",
                  "rubric_fingerprint":"legacy-fp",
                  "criteria":[{"criterion_id":"obj-1:c1","description":"Explain EXPLAIN","expected_evidence":"Plan",
                    "below_target":"Wrong","at_target":"Correct","above_target":"Deep","essential":true}],
                  "suitable_modes":[{"mode":"CODING","rationale":"Legacy rationale","criterion_indices":[0]}],
                  "estimated_seconds":120,"jd_evidence_spans":["SQL"]
                }]}
                """);
        var session = Session.builder().id("s").userId(owner.getId()).applicationProfile(profile).build();
        when(sessions.findById("s")).thenReturn(Optional.of(session));
        when(runs.findById("s")).thenReturn(Optional.empty());
        when(turns.findBySessionIdOrderByIdAsc("s")).thenReturn(java.util.List.of());
        when(inputs.skills(session)).thenReturn(json.read("[{\"jd_skill_id\":\"sql\"}]"));
        var aiResult = json.read("{\"snapshot\":{\"state_version\":1},\"public\":{\"state_version\":1}}");
        when(ai.compute(eq("start"), any())).thenReturn(aiResult);
        when(store.commit(any())).thenReturn(aiResult.path("public"));

        service.start("s", owner, EvidenceDtos.Config.defaults());

        var payloadCaptor = org.mockito.ArgumentCaptor.forClass(com.fasterxml.jackson.databind.JsonNode.class);
        verify(ai).compute(eq("start"), payloadCaptor.capture());
        var objective = payloadCaptor.getValue().path("blueprint").path("objectives").get(0);
        assertThat(objective.path("objective_id").asText()).isEqualTo("obj-1");
        assertThat(objective.has("required_proficiency")).isFalse();
        assertThat(objective.has("extension_criterion_ids")).isFalse();
        assertThat(objective.has("inferred")).isFalse();
        assertThat(objective.has("rubric_version")).isFalse();
        assertThat(objective.has("rubric_fingerprint")).isFalse();
        assertThat(objective.path("suitable_modes").get(0).has("rationale")).isFalse();
        assertThat(objective.path("suitable_modes").get(0).path("mode").asText()).isEqualTo("CODING");
    }

    @Test void startIncludesUserAndJdContextInOpeningAndClipsLongText() {
        var namedOwner = User.builder().id(owner.getId()).username("Nguyễn Minh Tuấn").email("tuan@example.com").build();
        var profile = new fit.iuh.modules.application.ApplicationProfile();
        profile.setCompany("Smile Tech");
        profile.setRoleTitle("Senior Java Engineer");
        profile.setJdText("Xây dựng hệ thống microservice Java   " + "A".repeat(2000));
        profile.setCvText("5 năm kinh nghiệm Spring Boot   " + "B".repeat(2000));
        var session = Session.builder().id("s").userId(namedOwner.getId()).attemptNumber(2)
                .applicationProfile(profile).build();
        when(sessions.findById("s")).thenReturn(Optional.of(session));
        when(runs.findById("s")).thenReturn(Optional.empty());
        when(turns.findBySessionIdOrderByIdAsc("s")).thenReturn(java.util.List.of());
        when(inputs.skills(session)).thenReturn(json.read("[{\"jd_skill_id\":\"java\"}]"));
        var aiResult = json.read("{\"snapshot\":{\"state_version\":1},\"public\":{\"state_version\":1}}");
        when(ai.compute(eq("start"), any())).thenReturn(aiResult);
        when(store.commit(any())).thenReturn(aiResult.path("public"));

        service.start("s", namedOwner, EvidenceDtos.Config.defaults());

        var payloadCaptor = org.mockito.ArgumentCaptor.forClass(com.fasterxml.jackson.databind.JsonNode.class);
        verify(ai).compute(eq("start"), payloadCaptor.capture());
        var opening = payloadCaptor.getValue().path("opening");
        assertThat(opening.path("company").asText()).isEqualTo("Smile Tech");
        assertThat(opening.path("role_title").asText()).isEqualTo("Senior Java Engineer");
        assertThat(opening.path("candidate_name").asText()).isEqualTo("Nguyễn Minh Tuấn");
        assertThat(opening.path("attempt_number").asInt()).isEqualTo(2);
        assertThat(opening.path("jd_summary").asText()).startsWith("Xây dựng hệ thống microservice Java ");
        assertThat(opening.path("jd_summary").asText().length()).isEqualTo(1500);
        assertThat(opening.path("cv_summary").asText()).startsWith("5 năm kinh nghiệm Spring Boot ");
        assertThat(opening.path("cv_summary").asText().length()).isEqualTo(1200);
    }

    @Test void conversationChecksOwnerAndReplaysReceiptsBeforeAiCalls() {
        session();
        var command = new EvidenceDtos.Conversation(UUID.randomUUID(), "intro", 1, "NEXT", "");
        assertThatThrownBy(() -> service.converse("s", User.builder().id(UUID.randomUUID()).build(), command))
                .isInstanceOf(ResponseStatusException.class);
        verifyNoInteractions(store, ai);
        var saved = json.read("{\"state_version\":2}");
        when(store.replay("s", command.requestId(), json.hash(command))).thenReturn(saved);
        assertThat(service.converse("s", owner, command)).isEqualTo(saved);
        verifyNoInteractions(ai, runs);
    }

    @Test void staleConversationCannotCallAi() {
        session();
        InterviewRun run = new InterviewRun(); run.setStateVersion(3);
        when(runs.findById("s")).thenReturn(Optional.of(run));
        assertThatThrownBy(() -> service.converse("s", owner,
                new EvidenceDtos.Conversation(UUID.randomUUID(), "intro", 2, "NEXT", "")))
                .isInstanceOf(ResponseStatusException.class);
        verifyNoInteractions(ai);
    }

    @Test void respondChainsNextQuestionInSameRoundtripAndFallsBackToAwaitingWhenGenerationFails() {
        session();
        var run = new InterviewRun();
        run.setStateVersion(1);
        run.setConfigJson("{}");
        run.setSnapshotJson("{\"pending_turn\":{\"turn_id\":\"turn-1\"}}");
        when(runs.findById("s")).thenReturn(Optional.of(run));

        var graded = json.read("""
            {"snapshot":{"next_question_action":"INITIAL","turns":[{"answer":"answer"}]},
             "public":{"state_version":2,"is_finished":false,"deadline_at":"2099-01-01T00:00:00Z",
                       "awaiting_question":true,"turns":[{"answer":"answer"}]}}
            """);
        var ready = json.read("""
            {"snapshot":{"pending_turn":{"turn_id":"turn-2"}},
             "public":{"state_version":3,"is_finished":false,"deadline_at":"2099-01-01T00:00:00Z",
                       "awaiting_question":false,"pending_turn":{"turn_id":"turn-2","question":"Q2"}}}
            """);
        when(ai.compute(eq("respond"), any())).thenReturn(graded);
        when(ai.compute(eq("next-question"), any())).thenReturn(ready);
        when(store.commit(any())).thenAnswer(call -> {
            var commit = call.<EvidenceStore.Commit>getArgument(0);
            var next = commit.result();
            run.setStateVersion(next.path("public").path("state_version").asLong());
            run.setSnapshotJson(next.path("snapshot").toString());
            run.setPublicJson(next.path("public").toString());
            return next.path("public");
        });

        var answer = new EvidenceDtos.Answer(UUID.randomUUID(), "turn-1", 1, "answer");
        var response = service.respond("s", owner, answer);
        assertThat(response.path("state_version").asLong()).isEqualTo(3L);
        assertThat(response.path("pending_turn").path("turn_id").asText()).isEqualTo("turn-2");

        // Now verify graceful fallback to awaiting_question=true if Tx 2 throws 503
        run.setStateVersion(3);
        var graded2 = json.read("""
            {"snapshot":{"next_question_action":"FOLLOW_UP","turns":[{"answer":"answer2"}]},
             "public":{"state_version":4,"is_finished":false,"deadline_at":"2099-01-01T00:00:00Z",
                       "awaiting_question":true,"turns":[{"answer":"answer2"}]}}
            """);
        when(ai.compute(eq("respond"), any())).thenReturn(graded2);
        when(ai.compute(eq("next-question"), any()))
                .thenThrow(new ResponseStatusException(org.springframework.http.HttpStatus.SERVICE_UNAVAILABLE, "Outage"));

        var answer2 = new EvidenceDtos.Answer(UUID.randomUUID(), "turn-2", 3, "answer2");
        var fallback = service.respond("s", owner, answer2);
        assertThat(fallback.path("state_version").asLong()).isEqualTo(4L);
        assertThat(fallback.path("awaiting_question").asBoolean()).isTrue();
    }

    @ParameterizedTest
    @CsvSource({
            "DEMONSTRATED_BELOW_TARGET, CONTRADICTS, BELOW, 3, DEMONSTRATED_BELOW_TARGET, false",
            "DEMONSTRATED_AT_TARGET, SUPPORTS, AT_TARGET, 3, DEMONSTRATED_AT_TARGET, true",
            "DEMONSTRATED_AT_TARGET, SUPPORTS, AT_TARGET, 2, INSUFFICIENT_EVIDENCE, false",
    })
    void startUsesOnlyVerifiedMasteryFromPriorAttempts(
            String assessment, String observation, String performance, int depth,
            String expectedAssessment, boolean mastered
    ) {
        var profile = new fit.iuh.modules.application.ApplicationProfile();
        profile.setId(UUID.randomUUID());
        profile.setSkillGapJson("[{\"jd_skill_id\":\"sql\",\"semantic_alignment\":\"MATCH\"}]");
        profile.setBlueprintJson("""
            {"objectives":[{"objective_id":"obj-sql","skill_id":"sql","claim":"Tune queries","target_depth":3,
              "criteria":[{"criterion_id":"c1","description":"Explain plan","essential":true}]}]}
            """);
        var attempt1 = Session.builder().id("s-1").userId(owner.getId()).attemptNumber(1)
                .status("Completed").applicationProfile(profile).build();
        var attempt2 = Session.builder().id("s-2").userId(owner.getId()).attemptNumber(2)
                .status("Not started").applicationProfile(profile).build();
        var priorRun = new InterviewRun();
        priorRun.setSessionId("s-1");
        priorRun.setPublicJson("{\"is_finished\":true}");
        priorRun.setSnapshotJson("""
            {"is_finished":true,
             "turns":[{"turn_id":"t1","objective_id":"obj-sql","answer":"Use EXPLAIN ANALYZE",
                       "question":{"text":"How do you inspect a slow SQL query in PostgreSQL?"}}],
             "objectives":{"obj-sql":{
               "objective":{"objective_id":"obj-sql","skill_id":"sql","claim":"Tune queries","target_depth":3,
                 "criteria":[{"criterion_id":"c1","description":"Explain plan","essential":true}]},
               "assessment":"%s","lifecycle":"CLOSED","turns_spent":1,
               "evidence_history":[{"turn_id":"t1","criterion_id":"c1","independent":true,"question_depth":%d,
                 "evidence_scope":"s1","observation":"%s","performance":"%s",
                 "response_excerpt":"Use EXPLAIN ANALYZE","rationale":"Chưa nêu cách đọc nút thực thi."}]
             }}}
            """.formatted(assessment, depth, observation, performance));

        when(sessions.findById("s-2")).thenReturn(Optional.of(attempt2));
        when(runs.findById("s-2")).thenReturn(Optional.empty());
        when(turns.findBySessionIdOrderByIdAsc("s-2")).thenReturn(java.util.List.of());
        when(inputs.skills(attempt2)).thenReturn(json.read("[{\"jd_skill_id\":\"sql\"}]"));
        when(sessions.findByApplicationProfileIdOrderByAttemptNumberDesc(profile.getId()))
                .thenReturn(java.util.List.of(attempt2, attempt1));
        when(runs.findAllById(java.util.List.of("s-1"))).thenReturn(java.util.List.of(priorRun));
        var aiResult = json.read("{\"snapshot\":{\"state_version\":1},\"public\":{\"state_version\":1}}");
        when(ai.compute(eq("start"), any())).thenReturn(aiResult);
        when(store.commit(any())).thenReturn(aiResult.path("public"));

        service.start("s-2", owner, EvidenceDtos.Config.defaults());

        var payloadCaptor = org.mockito.ArgumentCaptor.forClass(com.fasterxml.jackson.databind.JsonNode.class);
        verify(ai).compute(eq("start"), payloadCaptor.capture());
        var priorAttempts = payloadCaptor.getValue().path("prior_attempts");
        assertThat(priorAttempts.path("objective_assessments").path("obj-sql").asText())
                .isEqualTo(expectedAssessment);
        assertThat(priorAttempts.path("mastered_skill_ids"))
                .isEqualTo(json.read(mastered ? "[\"sql\"]" : "[]"));
        assertThat(priorAttempts.path("prior_question_stems").get(0).asText())
                .isEqualTo("How do you inspect a slow SQL query in PostgreSQL?");
    }

    @Test void voiceContextLoadsPublicStateAndRichSkillTermsInOneRead() {
        session();
        InterviewRun run = new InterviewRun();
        run.setPublicJson("{\"state_version\":2,\"config\":{\"interaction_mode\":\"VOICE\"}}");
        run.setSnapshotJson("""
            {"skills":[
               {"jd_skill_id":"sql_optimization","jd_skill_name":"SQL Optimization","matched_cv_skill_name":"PostgreSQL Indexing"},
               {"jd_skill_id":"spring_boot"}
             ]}
            """);
        when(runs.findById("s")).thenReturn(Optional.of(run));

        var ctx = service.voiceContext("s", owner);
        assertThat(ctx.state().path("state_version").asInt()).isEqualTo(2);
        assertThat(ctx.terms()).containsExactly("SQL Optimization", "PostgreSQL Indexing", "spring boot");
        verify(runs, times(1)).findById("s");
    }
}
