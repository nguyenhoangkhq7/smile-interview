package fit.iuh.modules.application;

import com.fasterxml.jackson.databind.ObjectMapper;
import fit.iuh.modules.auth.entity.User;
import fit.iuh.modules.evidence.*;
import fit.iuh.modules.session.entity.*;
import fit.iuh.modules.session.repository.*;
import fit.iuh.modules.skillgap.client.SkillGapClient;
import org.junit.jupiter.api.Test;
import org.springframework.web.server.ResponseStatusException;
import java.util.*;
import static org.assertj.core.api.Assertions.*;
import static org.mockito.Mockito.*;

class ApplicationProfileServiceTest {
    private final ApplicationProfileRepository profiles = mock(ApplicationProfileRepository.class);
    private final SessionRepository sessions = mock(SessionRepository.class);
    private final InterviewRunRepository runs = mock(InterviewRunRepository.class);
    private final SessionTurnRepository turns = mock(SessionTurnRepository.class);
    private final EvidenceJson json = new EvidenceJson(new ObjectMapper());
    private final ApplicationProfileService service = new ApplicationProfileService(profiles, sessions, runs, turns, json);
    private final User owner = User.builder().id(UUID.randomUUID()).build();

    private ApplicationProfile profile() {
        ApplicationProfile profile = new ApplicationProfile();
        profile.setId(UUID.randomUUID()); profile.setUserId(owner.getId());
        profile.setRoleTitle("Backend");
        profile.setResume(Resume.builder().id(UUID.randomUUID()).userId(owner.getId()).fileName("cv.pdf").rawText("CV").build());
        profile.setJobDescription(JobDescription.builder().id(UUID.randomUUID()).userId(owner.getId()).title("JD").rawText("JD text").build());
        profile.setSkillGapJson("[{\"jd_skill_id\":\"sql\",\"job_tasks\":[],\"jd_evidence_spans\":[],\"importance_weight\":1}]");
        profile.setGapReportJson("{}");
        return profile;
    }

    @Test void createsProfileFromOwnedAnalysisAndIsIdempotent() {
        when(profiles.save(any())).thenAnswer(invocation -> invocation.getArgument(0));
        var template = profile();
        var source = Session.builder().id("source").userId(owner.getId()).resume(template.getResume())
                .jobDescription(template.getJobDescription()).roleTitle("Backend").skillGapJson(template.getSkillGapJson())
                .gapReportJson("{}").build();
        when(sessions.lockById("source")).thenReturn(Optional.of(source));
        var request = new ApplicationProfileService.Create("source", "Company A", "A");
        var result = service.create(owner, request);
        assertThat(result.title()).isEqualTo("Company A");
        assertThat(source.getAttemptNumber()).isEqualTo(1);
        assertThat(source.getApplicationProfile().getCvText()).isEqualTo("CV");
        assertThat(service.create(owner, request).id()).isEqualTo(result.id());
        verify(profiles, times(1)).save(any());
    }

    @Test void newAttemptCopiesBaselineWithoutAnswersAndReusesPendingAttempt() {
        var profile = profile();
        when(profiles.lockById(profile.getId())).thenReturn(Optional.of(profile));
        var old = Session.builder().id("old").applicationProfile(profile).attemptNumber(1).status("Completed").build();
        when(sessions.findByApplicationProfileIdOrderByAttemptNumberDesc(profile.getId())).thenReturn(List.of(old));
        var created = service.newAttempt(profile.getId(), owner);
        var captor = org.mockito.ArgumentCaptor.forClass(Session.class);
        verify(sessions).save(captor.capture());
        var fresh = captor.getValue();
        assertThat(created.number()).isEqualTo(2);
        assertThat(fresh.getSkillGapJson()).isEqualTo(profile.getSkillGapJson());
        assertThat(fresh.getInterviewReportJson()).isNull();
        assertThat(fresh.getAiInterviewSessionId()).isNull();
        when(sessions.findByApplicationProfileIdOrderByAttemptNumberDesc(profile.getId())).thenReturn(List.of(fresh, old));
        assertThat(service.newAttempt(profile.getId(), owner).id()).isEqualTo(created.id());
        verify(sessions, times(1)).save(any());
    }

    @Test void runningAttemptBlocksAnotherAndOtherUsersCannotAccess() {
        var profile = profile();
        when(profiles.lockById(profile.getId())).thenReturn(Optional.of(profile));
        when(profiles.findById(profile.getId())).thenReturn(Optional.of(profile));
        when(sessions.findByApplicationProfileIdOrderByAttemptNumberDesc(profile.getId())).thenReturn(List.of(
                Session.builder().id("running").status("In progress").attemptNumber(1).build()));
        assertThatThrownBy(() -> service.newAttempt(profile.getId(), owner)).isInstanceOfSatisfying(ResponseStatusException.class,
                ex -> assertThat(ex.getStatusCode().value()).isEqualTo(409));
        var stranger = User.builder().id(UUID.randomUUID()).build();
        assertThatThrownBy(() -> service.get(profile.getId(), stranger)).isInstanceOfSatisfying(ResponseStatusException.class,
                ex -> assertThat(ex.getStatusCode().value()).isEqualTo(403));
        assertThatThrownBy(() -> service.newAttempt(profile.getId(), stranger)).isInstanceOf(ResponseStatusException.class);
        verify(sessions, never()).save(any());
    }

    @Test void profileInputNeverCallsAnalysisPipelineAgain() {
        SkillGapClient gaps = mock(SkillGapClient.class);
        var profile = profile();
        var session = Session.builder().applicationProfile(profile).build();
        profile.setSkillGapJson("""
                [{"jd_skill_id":"sql","job_tasks":[],"jd_evidence_spans":["Tối ưu SQL"],
                  "importance_weight":1,"candidate_proficiency":3,"suggested_strategy":"PROBE_DEPTH"}]
                """);
        var skills = new EvidenceInputs(gaps, json).skills(session);
        assertThat(skills).isEqualTo(json.read("""
                [{"jd_skill_id":"sql","job_tasks":[],"jd_evidence_spans":["Tối ưu SQL"],"importance_weight":1}]
                """));
        verifyNoInteractions(gaps);
    }

    @Test void missingAnalysisAndForeignSourceAreRejected() {
        Session source = Session.builder().id("source").userId(owner.getId()).build();
        when(sessions.lockById("source")).thenReturn(Optional.of(source));
        var request = new ApplicationProfileService.Create("source", "Profile", null);
        assertThatThrownBy(() -> service.create(owner, request)).isInstanceOfSatisfying(ResponseStatusException.class,
                ex -> assertThat(ex.getStatusCode().value()).isEqualTo(422));
        assertThatThrownBy(() -> service.create(User.builder().id(UUID.randomUUID()).build(), request))
                .isInstanceOfSatisfying(ResponseStatusException.class, ex -> assertThat(ex.getStatusCode().value()).isEqualTo(403));
        verifyNoInteractions(profiles);
    }

    @Test void preservesRichModule2ContextAndPrewarmsBlueprintConditionally() {
        SkillGapClient gaps = mock(SkillGapClient.class);
        var profile = profile();
        profile.setCompany("Smile Tech");
        profile.setJdText("Thiết kế hệ thống phân tán Java Spring Boot");
        profile.setSkillGapJson("""
                [{"jd_skill_id":"spring_boot","jd_skill_name":"Spring Boot",
                  "matched_cv_skill_name":"Java Spring","semantic_alignment":"PARTIAL",
                  "context_job":"Xây dựng REST API tại công ty cũ","job_tasks":[],
                  "jd_evidence_spans":["Spring Boot"],"importance_weight":0.9}]
                """);
        var session = Session.builder().applicationProfile(profile).build();
        var evidenceInputs = new EvidenceInputs(gaps, json);
        var skills = evidenceInputs.enrichPersonalization(evidenceInputs.skills(session), session);
        var first = skills.get(0);
        assertThat(first.path("jd_skill_name").asText()).isEqualTo("Spring Boot");
        assertThat(first.path("matched_cv_skill_name").asText()).isEqualTo("Java Spring");
        assertThat(first.path("semantic_alignment").asText()).isEqualTo("PARTIAL");
        assertThat(first.path("context_job").asText()).isEqualTo("Xây dựng REST API tại công ty cũ");

        EvidenceAiClient ai = mock(EvidenceAiClient.class);
        var blueprint = json.read("{\"objectives\":[{\"objective_id\":\"obj-1\",\"skill_id\":\"spring_boot\"}]}");
        when(ai.blueprint(any())).thenReturn(blueprint);
        when(profiles.savePrewarmedBlueprintIfAbsent(eq(profile.getId()), any())).thenReturn(1);

        var prewarmService = new ApplicationProfileService(profiles, sessions, runs, turns, json, ai);
        var payload = prewarmService.buildBlueprintPayload(profile);
        prewarmService.prewarmBlueprint(profile.getId(), payload);

        verify(ai).blueprint(payload);
        verify(profiles).savePrewarmedBlueprintIfAbsent(profile.getId(), blueprint.toString());
    }
}
