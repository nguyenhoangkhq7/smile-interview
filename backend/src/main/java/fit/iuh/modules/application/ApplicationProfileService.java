package fit.iuh.modules.application;

import com.fasterxml.jackson.databind.JsonNode;
import fit.iuh.modules.auth.entity.User;
import fit.iuh.modules.evidence.*;
import fit.iuh.modules.session.entity.Session;
import fit.iuh.modules.session.repository.*;
import jakarta.validation.constraints.*;
import lombok.RequiredArgsConstructor;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.server.ResponseStatusException;
import java.time.LocalDateTime;
import java.util.*;

@Service @RequiredArgsConstructor
public class ApplicationProfileService {
    private final ApplicationProfileRepository profiles;
    private final SessionRepository sessions;
    private final InterviewRunRepository runs;
    private final SessionTurnRepository turns;
    private final EvidenceJson json;

    public record Create(@NotBlank String sourceSessionId, @NotBlank @Size(max = 200) String title,
                         @Size(max = 200) String company) {}
    public record Attempt(String id, int number, String status, LocalDateTime startedAt,
                          LocalDateTime endedAt, int answeredCount, String terminationReason) {}
    public record View(UUID id, String title, String company, String roleTitle, String cvFilename,
                       String jdTitle, LocalDateTime createdAt, JsonNode skills, JsonNode analysis,
                       List<Attempt> attempts) {}

    @Transactional
    public View create(User user, Create request) {
        Session source = sessions.lockById(request.sourceSessionId()).orElseThrow(() -> error(HttpStatus.NOT_FOUND, "Session not found"));
        requireOwner(source.getUserId(), user);
        if (source.getApplicationProfile() != null) return view(source.getApplicationProfile());
        if (runs.existsById(source.getId()) || source.getAiInterviewSessionId() != null
                || !turns.findBySessionIdOrderByIdAsc(source.getId()).isEmpty()) {
            throw error(HttpStatus.CONFLICT, "Create a profile from a prepared interview before starting it");
        }
        if (source.getResume() == null || source.getJobDescription() == null
                || source.getSkillGapJson() == null || source.getGapReportJson() == null
                || !EvidenceInputs.hasTaskContract(json.read(source.getSkillGapJson()))) {
            throw error(HttpStatus.UNPROCESSABLE_ENTITY, "Complete CV/JD analysis before creating an application profile");
        }
        requireOwner(source.getResume().getUserId(), user);
        requireOwner(source.getJobDescription().getUserId(), user);
        ApplicationProfile profile = new ApplicationProfile();
        profile.setId(UUID.randomUUID());
        profile.setUserId(user.getId());
        profile.setTitle(request.title().trim());
        profile.setCompany(request.company() == null ? null : request.company().trim());
        profile.setRoleTitle(source.getRoleTitle() == null ? source.getJobDescription().getTitle() : source.getRoleTitle());
        profile.setResume(source.getResume());
        profile.setJobDescription(source.getJobDescription());
        profile.setCvFilename(source.getResume().getFileName());
        profile.setJdTitle(source.getJobDescription().getTitle());
        profile.setCvText(Objects.requireNonNullElse(source.getResume().getRawText(), ""));
        profile.setJdText(Objects.requireNonNullElse(source.getJobDescription().getRawText(), ""));
        profile.setSkillGapJson(source.getSkillGapJson());
        profile.setGapReportJson(source.getGapReportJson());
        profile.setCreatedAt(LocalDateTime.now());
        profile = profiles.save(profile);
        source.setApplicationProfile(profile);
        source.setAttemptNumber(1);
        source.setStatus("Not started");
        source.setEndedAt(null);
        sessions.save(source);
        return view(profile);
    }

    @Transactional(readOnly = true)
    public List<View> list(User user) {
        return profiles.findByUserIdOrderByCreatedAtDesc(user.getId()).stream().map(this::view).toList();
    }

    @Transactional(readOnly = true)
    public View get(UUID id, User user) {
        ApplicationProfile profile = profiles.findById(id).orElseThrow(() -> error(HttpStatus.NOT_FOUND, "Application profile not found"));
        requireOwner(profile.getUserId(), user);
        return view(profile);
    }

    @Transactional
    public Attempt newAttempt(UUID id, User user) {
        // Serialize creation; repeated requests return the same unstarted attempt.
        ApplicationProfile profile = profiles.lockById(id).orElseThrow(() -> error(HttpStatus.NOT_FOUND, "Application profile not found"));
        requireOwner(profile.getUserId(), user);
        List<Session> previous = sessions.findByApplicationProfileIdOrderByAttemptNumberDesc(id);
        for (Session attempt : previous) {
            if ("Not started".equals(attempt.getStatus())) return attempt(attempt);
            if ("In progress".equals(attempt.getStatus())) {
                throw error(HttpStatus.CONFLICT, "Continue or finish the current interview before creating another attempt");
            }
        }
        int number = previous.stream().mapToInt(s -> s.getAttemptNumber()).max().orElse(0) + 1;
        Session session = Session.builder().id("session-" + UUID.randomUUID()).userId(user.getId())
                .applicationProfile(profile).attemptNumber(number).resume(profile.getResume())
                .jobDescription(profile.getJobDescription()).roleTitle(profile.getRoleTitle())
                .interviewType("Technical").status("Not started").startedAt(LocalDateTime.now())
                .skillGapJson(profile.getSkillGapJson()).gapReportJson(profile.getGapReportJson()).build();
        sessions.save(session);
        return attempt(session);
    }

    private View view(ApplicationProfile profile) {
        return new View(profile.getId(), profile.getTitle(), profile.getCompany(), profile.getRoleTitle(),
                profile.getCvFilename(), profile.getJdTitle(), profile.getCreatedAt(),
                json.read(profile.getSkillGapJson()), json.read(profile.getGapReportJson()),
                sessions.findByApplicationProfileIdOrderByAttemptNumberDesc(profile.getId()).stream().map(this::attempt).toList());
    }

    private Attempt attempt(Session session) {
        JsonNode visible = runs.findById(session.getId()).map(r -> json.read(r.getPublicJson())).orElse(null);
        return new Attempt(session.getId(), session.getAttemptNumber(), session.getStatus(), session.getStartedAt(),
                session.getEndedAt(), visible == null ? 0 : visible.path("turns").size(),
                visible == null ? null : visible.path("report").path("termination_reason").asText(null));
    }

    private void requireOwner(UUID owner, User user) {
        if (user == null || !Objects.equals(owner, user.getId())) throw error(HttpStatus.FORBIDDEN, "This resource belongs to another user");
    }

    private ResponseStatusException error(HttpStatus status, String message) {
        return new ResponseStatusException(status, message);
    }
}
