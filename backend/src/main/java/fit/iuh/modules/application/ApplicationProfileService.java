package fit.iuh.modules.application;

import com.fasterxml.jackson.databind.JsonNode;
import fit.iuh.modules.auth.entity.User;
import fit.iuh.modules.evidence.*;
import fit.iuh.modules.session.entity.Session;
import fit.iuh.modules.session.repository.*;
import jakarta.validation.constraints.*;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.transaction.support.TransactionSynchronization;
import org.springframework.transaction.support.TransactionSynchronizationManager;
import org.springframework.web.server.ResponseStatusException;
import java.net.URLDecoder;
import java.nio.charset.StandardCharsets;
import java.time.LocalDateTime;
import java.util.*;
import java.util.concurrent.CompletableFuture;

@Service @Slf4j
public class ApplicationProfileService {
    private static final int MAX_COMPANY_LENGTH = 200;
    private static final int MAX_ROLE_TITLE_LENGTH = 200;
    private static final int MAX_JD_SUMMARY_LENGTH = 1500;
    private static final String DEFAULT_ROLE_TITLE = "vị trí ứng tuyển";

    private final ApplicationProfileRepository profiles;
    private final SessionRepository sessions;
    private final InterviewRunRepository runs;
    private final SessionTurnRepository turns;
    private final EvidenceJson json;
    private final EvidenceAiClient ai;

    @Autowired
    public ApplicationProfileService(
            ApplicationProfileRepository profiles,
            SessionRepository sessions,
            InterviewRunRepository runs,
            SessionTurnRepository turns,
            EvidenceJson json,
            EvidenceAiClient ai) {
        this.profiles = profiles;
        this.sessions = sessions;
        this.runs = runs;
        this.turns = turns;
        this.json = json;
        this.ai = ai;
    }

    public ApplicationProfileService(
            ApplicationProfileRepository profiles,
            SessionRepository sessions,
            InterviewRunRepository runs,
            SessionTurnRepository turns,
            EvidenceJson json) {
        this(profiles, sessions, runs, turns, json, null);
    }

    public record Create(@NotBlank String sourceSessionId, @NotBlank @Size(max = 200) String title,
                         @Size(max = 200) String company) {}
    public record Attempt(String id, int number, String status, LocalDateTime startedAt,
                          LocalDateTime endedAt, int answeredCount, String terminationReason) {}
    public record View(UUID id, String title, String company, String roleTitle, String cvFilename,
                       String jdTitle, String jdFilename, LocalDateTime createdAt, JsonNode skills, JsonNode analysis,
                       List<Attempt> attempts) {}
    public record Documents(String cvFilename, String cvFileUrl, String cvText,
                            String jdTitle, String jdFilename, String jdFileUrl, String jdText) {}
    public record TrashView(View profile, LocalDateTime deletedAt, LocalDateTime expiresAt) {}

    @Transactional
    public View create(User user, Create request) {
        Session source = sessions.lockById(request.sourceSessionId()).orElseThrow(() -> error(HttpStatus.NOT_FOUND, "Session not found"));
        requireOwner(source.getUserId(), user);
        if (source.getApplicationProfile() != null) {
            requireActive(source.getApplicationProfile());
            return view(source.getApplicationProfile());
        }
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
        scheduleBlueprintPrewarm(profile);
        return view(profile);
    }

    private void scheduleBlueprintPrewarm(ApplicationProfile profile) {
        if (ai == null || profile.getId() == null || profile.getBlueprintJson() != null) {
            return;
        }
        UUID profileId = profile.getId();
        Map<String, Object> payload = buildBlueprintPayload(profile);
        Runnable task = () -> CompletableFuture.runAsync(() -> prewarmBlueprint(profileId, payload));
        if (TransactionSynchronizationManager.isSynchronizationActive()) {
            TransactionSynchronizationManager.registerSynchronization(new TransactionSynchronization() {
                @Override
                public void afterCommit() {
                    task.run();
                }
            });
        } else {
            task.run();
        }
    }

    void prewarmBlueprint(UUID profileId, Map<String, Object> payload) {
        if (ai == null || profileId == null) {
            return;
        }
        try {
            JsonNode blueprint = ai.blueprint(payload);
            if (blueprint != null && blueprint.path("objectives").isArray() && !blueprint.path("objectives").isEmpty()) {
                int updated = profiles.savePrewarmedBlueprintIfAbsent(profileId, blueprint.toString());
                log.info("Prewarmed blueprint for profile_id={} updated={}", profileId, updated > 0);
            }
        } catch (Exception ex) {
            log.debug("Background blueprint prewarm skipped for profile_id={} ({})", profileId, ex.getClass().getSimpleName());
        }
    }

    Map<String, Object> buildBlueprintPayload(ApplicationProfile profile) {
        JsonNode rawSkills = json.read(profile.getSkillGapJson());
        var evidenceInputs = new EvidenceInputs(null, json);
        JsonNode interviewSkills = evidenceInputs.enrichPersonalization(evidenceInputs.interviewSkills(rawSkills), rawSkills);
        var opening = new HashMap<String, Object>();
        opening.put("company", clip(profile.getCompany(), MAX_COMPANY_LENGTH));
        opening.put("role_title", clip(firstNonBlank(profile.getRoleTitle(), profile.getJdTitle(), DEFAULT_ROLE_TITLE), MAX_ROLE_TITLE_LENGTH));
        opening.put("jd_summary", clip(profile.getJdText(), MAX_JD_SUMMARY_LENGTH));
        return Map.of("skills", interviewSkills, "opening", opening);
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

    @Transactional(readOnly = true)
    public List<View> list(User user) {
        return profiles.findByUserIdAndDeletedAtIsNullOrderByCreatedAtDesc(user.getId()).stream().map(this::view).toList();
    }

    @Transactional(readOnly = true)
    public List<TrashView> trash(User user) {
        LocalDateTime now = LocalDateTime.now();
        return profiles.findByUserIdAndDeletedAtIsNotNullOrderByDeletedAtDesc(user.getId()).stream()
                .filter(profile -> profile.getDeletedAt().plusDays(30).isAfter(now))
                .map(profile -> new TrashView(view(profile), profile.getDeletedAt(), profile.getDeletedAt().plusDays(30)))
                .toList();
    }

    @Transactional(readOnly = true)
    public View get(UUID id, User user) {
        ApplicationProfile profile = profiles.findById(id).orElseThrow(() -> error(HttpStatus.NOT_FOUND, "Application profile not found"));
        requireOwner(profile.getUserId(), user);
        requireActive(profile);
        return view(profile);
    }

    @Transactional
    public void moveToTrash(UUID id, User user) {
        ApplicationProfile profile = profiles.lockById(id).orElseThrow(() -> error(HttpStatus.NOT_FOUND, "Application profile not found"));
        requireOwner(profile.getUserId(), user);
        if (profile.getDeletedAt() == null) {
            profile.setDeletedAt(LocalDateTime.now());
            profiles.save(profile);
        }
    }

    @Transactional
    public void restore(UUID id, User user) {
        ApplicationProfile profile = profiles.lockById(id).orElseThrow(() -> error(HttpStatus.NOT_FOUND, "Application profile not found"));
        requireOwner(profile.getUserId(), user);
        if (profile.getDeletedAt() == null) return;
        if (!profile.getDeletedAt().plusDays(30).isAfter(LocalDateTime.now())) {
            throw error(HttpStatus.GONE, "The retention period has expired");
        }
        profile.setDeletedAt(null);
        profiles.save(profile);
    }

    @Transactional(readOnly = true)
    public Documents documents(UUID id, User user) {
        ApplicationProfile profile = profiles.findById(id).orElseThrow(() -> error(HttpStatus.NOT_FOUND, "Application profile not found"));
        requireOwner(profile.getUserId(), user);
        requireActive(profile);
        var resume = profile.getResume();
        var jd = profile.getJobDescription();
        return new Documents(profile.getCvFilename(), resume.getFileUrl(), Objects.requireNonNullElse(profile.getCvText(), ""),
                profile.getJdTitle(), uploadedFilename(jd.getFileUrl(), profile.getJdTitle()), jd.getFileUrl(),
                Objects.requireNonNullElse(profile.getJdText(), ""));
    }

    @Transactional
    public Attempt newAttempt(UUID id, User user) {
        // Serialize creation; repeated requests return the same unstarted attempt.
        ApplicationProfile profile = profiles.lockById(id).orElseThrow(() -> error(HttpStatus.NOT_FOUND, "Application profile not found"));
        requireOwner(profile.getUserId(), user);
        requireActive(profile);
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
                profile.getCvFilename(), profile.getJdTitle(), uploadedFilename(profile.getJobDescription().getFileUrl(), profile.getJdTitle()), profile.getCreatedAt(),
                json.read(profile.getSkillGapJson()), json.read(profile.getGapReportJson()),
                sessions.findByApplicationProfileIdOrderByAttemptNumberDesc(profile.getId()).stream().map(this::attempt).toList());
    }

    private String uploadedFilename(String fileUrl, String fallback) {
        if (fileUrl == null || fileUrl.isBlank()) return fallback;
        String segment = fileUrl.substring(fileUrl.lastIndexOf('/') + 1);
        try {
            segment = URLDecoder.decode(segment, StandardCharsets.UTF_8);
        } catch (IllegalArgumentException ignored) {
            // Keep the stored path segment if its percent encoding is malformed.
        }
        return segment.replaceFirst("^\\d+_", "");
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

    private void requireActive(ApplicationProfile profile) {
        if (profile.getDeletedAt() != null) throw error(HttpStatus.GONE, "Application profile is in the trash");
    }

    private ResponseStatusException error(HttpStatus status, String message) {
        return new ResponseStatusException(status, message);
    }
}
