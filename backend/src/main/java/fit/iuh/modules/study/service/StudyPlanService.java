package fit.iuh.modules.study.service;

import fit.iuh.modules.application.ApplicationProfile;
import fit.iuh.modules.application.ApplicationProfileRepository;
import fit.iuh.modules.application.CompetencyProjection;
import fit.iuh.modules.auth.entity.User;
import fit.iuh.modules.evidence.EvidenceJson;
import fit.iuh.modules.evidence.EvidenceDtos.ChecklistRef;
import fit.iuh.modules.evidence.InterviewRun;
import com.fasterxml.jackson.databind.JsonNode;
import fit.iuh.modules.evidence.InterviewRunRepository;
import fit.iuh.modules.session.entity.Session;
import fit.iuh.modules.session.repository.SessionRepository;
import fit.iuh.modules.study.dto.StudyPlanDtos.*;
import fit.iuh.modules.study.entity.StudyPlan;
import fit.iuh.modules.study.entity.StudyTask;
import fit.iuh.modules.study.entity.StudyTaskChecklistItem;
import fit.iuh.modules.study.entity.StudyTaskResource;
import fit.iuh.modules.study.repository.StudyPlanRepository;
import lombok.RequiredArgsConstructor;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Isolation;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.multipart.MultipartFile;
import org.springframework.web.server.ResponseStatusException;

import java.io.IOException;
import java.math.BigDecimal;
import java.math.RoundingMode;
import java.net.URI;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.LinkedHashSet;
import java.util.Objects;
import java.util.UUID;
import java.util.stream.Collectors;

@Service
@RequiredArgsConstructor
@Transactional
public class StudyPlanService {
    private static final BigDecimal DEFAULT_TARGET = new BigDecimal("80.00");
    private static final BigDecimal HUNDRED = BigDecimal.valueOf(100);
    private static final long MAX_ATTACHMENT_BYTES = 10L * 1024 * 1024;

    private final StudyPlanRepository repository;
    private final ApplicationProfileRepository profiles;
    private final SessionRepository sessions;
    private final InterviewRunRepository runs;
    private final CompetencyProjection projection;
    private final EvidenceJson json;
    private final StudySuggestionProjection suggestions;

    @Transactional(readOnly = true, isolation = Isolation.REPEATABLE_READ)
    public PlanView get(UUID profileId, User user) {
        var profile = ownedProfile(profileId, user, false);
        return repository.findActive(profileId).map(this::view).orElseGet(() ->
                new PlanView(new StudyPlan(null, profileId, null, profile.getTitle(), null, DEFAULT_TARGET,
                        null, "ACTIVE", null, null), progress(0, 0, DEFAULT_TARGET), List.of()));
    }

    @Transactional(readOnly = true)
    public List<PlanProgress> listProgress(User user) {
        return repository.totalsForUser(user.getId()).stream().map(totals ->
                new PlanProgress(totals.applicationProfileId(),
                        progress(totals.done(), totals.total(), totals.targetCompletionPercent()))).toList();
    }

    public PlanView updatePlan(UUID profileId, User user, PlanInput input) {
        var profile = ownedProfile(profileId, user, true);
        if (input.sourceSessionId() != null && competency(profile, input.sourceSessionId()).completedAttempts() == 0) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "Source session has no completed interview with answers");
        }
        return view(repository.updatePlan(ensurePlan(profile).id(), input));
    }

    @Transactional(readOnly = true, isolation = Isolation.REPEATABLE_READ)
    public KnowledgeGaps gaps(UUID profileId, User user) {
        var profile = ownedProfile(profileId, user, false);
        var attempts = interviewAttempts(profile, repository.findActive(profileId).map(StudyPlan::sourceSessionId).orElse(null));
        var savedRuns = runs.findAllById(attempts.stream().map(Session::getId).toList());
        var result = projection.project(profile, attempts, savedRuns);
        return new KnowledgeGaps(result.completedAttempts(),
                result.skills().stream().filter(skill -> "DEMONSTRATED_BELOW_TARGET".equals(skill.assessment())).toList(),
                result.skills().stream().filter(skill -> switch (skill.assessment()) {
                    case "NEEDS_VERIFICATION", "INSUFFICIENT_EVIDENCE", "PARTIALLY_ASSESSED" -> true;
                    default -> false;
                }).toList(),
                result.skills().stream().filter(skill -> "NOT_ASSESSED".equals(skill.assessment()))
                        .map(CompetencyProjection.Skill::skillId).toList(),
                suggestions.project(profile, result, attempts, savedRuns));
    }

    public record RecheckTurn(String question, String answer, String code, String transcript) {}
    public record CriterionAttempt(String sessionId, String assessment, List<RecheckTurn> turns) {}
    public record RecheckResult(long checklistItemId, CriterionAttempt before, CriterionAttempt after) {}
    public record RecheckPreview(String description, CriterionAttempt before) {}

    @Transactional(readOnly = true, isolation = Isolation.REPEATABLE_READ)
    public RecheckPreview recheckPreview(UUID profileId, User user, ChecklistRef ref) {
        var target = recheckTarget(profileId, user, ref);
        String source = target.path("source_session_id").asText(null);
        var before = source == null ? null : runs.findById(source)
                .map(run -> criterionAttempt(run, target.path("objective_id").asText(), target.path("criterion_id").asText()))
                .orElse(null);
        return new RecheckPreview(target.path("description").asText(), before);
    }

    @Transactional(readOnly = true)
    public JsonNode recheckTarget(UUID profileId, User user, ChecklistRef ref) {
        var profile = ownedProfile(profileId, user, false);
        var plan = requirePlan(profileId);
        var task = repository.tasks(plan.id()).stream().filter(t -> t.id() == ref.taskId()).findFirst()
                .orElseThrow(() -> notFound("Không tìm thấy đầu việc"));
        var item = repository.checklist(plan.id()).stream()
                .filter(i -> i.taskId() == task.id() && i.id() == ref.checklistItemId()).findFirst()
                .orElseThrow(() -> notFound("Không tìm thấy mục checklist"));
        if (item.sourceCriterionId() == null || task.gapSourceObjectiveId() == null)
            throw new ResponseStatusException(HttpStatus.UNPROCESSABLE_ENTITY, "Mục này chưa liên kết với tiêu chí");
        var definition = objectiveDefinition(profile, task.gapSourceObjectiveId());
        var criterion = java.util.stream.StreamSupport.stream(definition.path("criteria").spliterator(), false)
                .filter(c -> item.sourceCriterionId().equals(c.path("criterion_id").asText())).findFirst()
                .orElseThrow(() -> new ResponseStatusException(HttpStatus.CONFLICT, "Tiêu chí nguồn đã thay đổi"));
        String sourceId = item.sourceSessionId() == null ? task.gapSourceSessionId() : item.sourceSessionId();
        var questions = new ArrayList<String>();
        var scopes = new LinkedHashSet<String>();
        if (sourceId != null) {
            interviewAttempts(profile, sourceId);
            var source = runs.findById(sourceId).orElseThrow(() -> notFound("Không tìm thấy phiên nguồn"));
            var snapshot = json.read(source.getSnapshotJson());
            var original = snapshot.path("objectives").path(task.gapSourceObjectiveId()).path("objective");
            if (!snapshot.path("is_finished").asBoolean() || !CompetencyProjection.compatible(definition, original))
                throw new ResponseStatusException(HttpStatus.CONFLICT, "Chuẩn đánh giá đã thay đổi so với phiên nguồn");
            for (var turn : snapshot.path("turns")) {
                if (!matchesCriterion(turn, task.gapSourceObjectiveId(), item.sourceCriterionId())) continue;
                questions.add(turn.path("question").path("text").asText());
                scopes.add(turn.path("question").path("evidence_scope").asText());
            }
        }
        var target = new LinkedHashMap<String, Object>();
        target.put("source_session_id", sourceId);
        target.put("criterion_id", item.sourceCriterionId());
        target.put("description", criterion.path("description").asText());
        target.put("objective_id", task.gapSourceObjectiveId());
        target.put("rubric_fingerprint", definition.path("rubric_fingerprint").asText(json.hash(definition)));
        target.put("source_questions", questions);
        target.put("source_scopes", scopes);
        return json.tree(target);
    }

    private static boolean matchesCriterion(JsonNode turn, String objective, String criterion) {
        if (!objective.equals(turn.path("objective_id").asText())) return false;
        for (var id : turn.path("question").path("criterion_ids")) if (criterion.equals(id.asText())) return true;
        return false;
    }

    @Transactional(readOnly = true, isolation = Isolation.REPEATABLE_READ)
    public List<RecheckResult> rechecks(UUID profileId, User user, long taskId) {
        var profile = ownedProfile(profileId, user, false);
        if (!repository.hasTask(requirePlan(profileId).id(), taskId)) throw notFound("Không tìm thấy đầu việc");
        var attempts = interviewAttempts(profile, null);
        var byId = runs.findAllById(attempts.stream().map(Session::getId).toList()).stream()
                .collect(Collectors.toMap(r -> r.getSessionId(), r -> r));
        var results = new ArrayList<RecheckResult>();
        for (var attempt : attempts) {
            var run = byId.get(attempt.getId());
            if (run == null) continue;
            var config = json.read(run.getConfigJson()).path("recheck");
            if (config.path("taskId").asLong() != taskId) continue;
            var snapshot = json.read(run.getSnapshotJson());
            if (!snapshot.path("is_finished").asBoolean()) continue;
            var target = snapshot.path("recheck_target");
            String obj = target.path("objective_id").asText(), criterion = target.path("criterion_id").asText();
            var source = byId.get(target.path("source_session_id").asText(""));
            var before = source == null ? null : criterionAttempt(source, obj, criterion);
            results.add(new RecheckResult(config.path("checklistItemId").asLong(), before, criterionAttempt(run, obj, criterion)));
        }
        return results;
    }

    private CriterionAttempt criterionAttempt(InterviewRun run, String objective, String criterion) {
        var visible = json.read(run.getPublicJson());
        var answers = new ArrayList<RecheckTurn>();
        for (var t : json.read(run.getSnapshotJson()).path("turns")) {
            if (matchesCriterion(t, objective, criterion) && t.hasNonNull("answer"))
                answers.add(new RecheckTurn(t.path("question").path("text").asText(), t.path("answer").asText(),
                        t.path("submitted_code").asText(null), t.path("transcript").asText(null)));
        }
        String status = answers.isEmpty() ? "NOT_ASSESSED" : "INSUFFICIENT_EVIDENCE";
        for (var obj : visible.path("report").path("objectives")) {
            if (!objective.equals(obj.path("objective_id").asText())) continue;
            for (var c : obj.path("criteria")) if (criterion.equals(c.path("criterion_id").asText()))
                status = c.path("assessment").asText(status);
        }
        var selected = visible.path("report").path("recheck_criterion");
        if (criterion.equals(selected.path("criterion_id").asText())) status = selected.path("assessment").asText(status);
        return new CriterionAttempt(run.getSessionId(), status, answers);
    }

    public StudyTask createTask(UUID profileId, User user, CreateTaskInput input) {
        var profile = ownedProfile(profileId, user, true);
        validateSkill(profile, input.skillId());
        var gapOrigin = input.gapOrigin();
        if (gapOrigin != null) {
            validateSkill(profile, gapOrigin.skillId());
            if (gapOrigin.objectiveId() != null) {
                var definition = objectiveDefinition(profile, gapOrigin.objectiveId());
                if (!gapOrigin.skillId().equals(definition.path("skill_id").asText())
                        || !gapOrigin.skillId().equals(input.skillId()))
                    throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "Objective does not belong to the selected skill");
            }
            if (gapOrigin.sessionId() != null && interviewAttempts(profile, null).stream().noneMatch(attempt ->
                    gapOrigin.sessionId().equals(attempt.getId())
                            && (gapOrigin.attemptNumber() == null || gapOrigin.attemptNumber().equals(attempt.getAttemptNumber())))) {
                throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "Gap source session is outside this profile");
            }
        }
        if (input.checklist() != null) for (var item : input.checklist())
            validateChecklistOrigin(profile, gapOrigin == null ? null : gapOrigin.objectiveId(), item);
        if (input.resource() != null) validateUrl(input.resource().url());
        var plan = input.parentTaskId() == null ? ensurePlan(profile) : requirePlan(profileId);
        if (input.parentTaskId() != null && !repository.hasTask(plan.id(), input.parentTaskId())) {
            throw notFound("Parent study task not found");
        }
        var task = repository.createTask(plan.id(), input.task(), input.parentTaskId(), gapOrigin);
        if (input.checklist() != null) {
            for (var item : input.checklist()) repository.createChecklistItem(task.id(), item);
        }
        if (input.resource() != null) saveLink(task.id(), input.resource());
        return task;
    }

    public StudyTask updateTask(UUID profileId, long taskId, User user, TaskInput input) {
        var profile = ownedProfile(profileId, user, true);
        validateSkill(profile, input.skillId());
        long planId = requirePlan(profileId).id();
        if ("DONE".equals(input.status())) requireChildrenComplete(repository.tasks(planId), taskId);
        return repository.updateTask(planId, taskId, input)
                .orElseThrow(() -> notFound("Study task not found"));
    }

    public void updateTaskParent(UUID profileId, long taskId, User user, Long parentTaskId, String status) {
        ownedProfile(profileId, user, true);
        long planId = requirePlan(profileId).id();
        var tasks = repository.tasks(planId);
        if (tasks.stream().noneMatch(task -> task.id() == taskId)) throw notFound("Study task not found");
        if ("DONE".equals(status)) requireChildrenComplete(tasks, taskId);
        if (parentTaskId != null) {
            var byId = tasks.stream().collect(Collectors.toMap(StudyTask::id, task -> task));
            if (!byId.containsKey(parentTaskId)) throw notFound("Parent study task not found");
            long ancestor = parentTaskId;
            while (true) {
                if (ancestor == taskId) throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "A task cannot be nested inside itself or its descendants");
                var parent = byId.get(ancestor);
                if (parent == null || parent.parentTaskId() == null) break;
                ancestor = parent.parentTaskId();
            }
        }
        repository.updateTaskParent(planId, taskId, parentTaskId, status);
    }

    public void moveTask(UUID profileId, long taskId, User user, TaskPositionInput input) {
        ownedProfile(profileId, user, true);
        long planId = requirePlan(profileId).id();
        var tasks = repository.tasks(planId);
        var moved = tasks.stream().filter(task -> task.id() == taskId).findFirst()
                .orElseThrow(() -> notFound("Study task not found"));
        if ("DONE".equals(input.status())) requireChildrenComplete(tasks, taskId);
        var destination = new java.util.ArrayList<>(tasks.stream()
                .filter(task -> task.id() != taskId && task.status().equals(input.status())).toList());
        int index = destination.size();
        if (input.beforeTaskId() != null) {
            for (int i = 0; i < destination.size(); i++) {
                if (destination.get(i).id() == input.beforeTaskId()) {
                    index = i;
                    break;
                }
            }
            if (index == destination.size()) throw notFound("Destination task not found");
        }
        destination.add(index, moved);
        for (int i = 0; i < destination.size(); i++) {
            var task = destination.get(i);
            if (task.sortOrder() != i || !task.status().equals(input.status())) {
                repository.moveTask(planId, task.id(), input.status(), i);
            }
        }
    }

    private void requireChildrenComplete(List<StudyTask> tasks, long taskId) {
        var descendants = new LinkedHashSet<Long>();
        descendants.add(taskId);
        boolean expanded;
        do {
            expanded = false;
            for (var task : tasks) {
                if (task.parentTaskId() != null && descendants.contains(task.parentTaskId())) {
                    expanded |= descendants.add(task.id());
                }
            }
        } while (expanded);

        boolean hasIncompleteChild = tasks.stream().anyMatch(task -> task.id() != taskId
                && descendants.contains(task.id()) && !"DONE".equals(task.status()));
        if (hasIncompleteChild) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "Hoàn thành các đầu việc con trước khi đánh dấu đầu việc cha là đã xong.");
        }
    }

    public void deleteTask(UUID profileId, long taskId, User user) {
        ownedProfile(profileId, user, true);
        if (!repository.deleteTask(requirePlan(profileId).id(), taskId)) throw notFound("Study task not found");
    }

    public StudyTaskChecklistItem createChecklistItem(UUID profileId, long taskId, User user, ChecklistInput input) {
        requireTask(profileId, taskId, user);
        var profile = ownedProfile(profileId, user, false);
        var task = repository.tasks(requirePlan(profileId).id()).stream().filter(t -> t.id() == taskId).findFirst().orElseThrow();
        validateChecklistOrigin(profile, task.gapSourceObjectiveId(), input);
        return repository.createChecklistItem(taskId, input);
    }

    public StudyTaskChecklistItem updateChecklistItem(UUID profileId, long taskId, long itemId, User user, ChecklistInput input) {
        requireTask(profileId, taskId, user);
        return repository.updateChecklistItem(taskId, itemId, input)
                .orElseThrow(() -> notFound("Checklist item not found"));
    }

    public void deleteChecklistItem(UUID profileId, long taskId, long itemId, User user) {
        requireTask(profileId, taskId, user);
        if (!repository.deleteChecklistItem(taskId, itemId)) throw notFound("Checklist item not found");
    }

    public StudyTaskResource createLink(UUID profileId, long taskId, User user, ResourceInput input) {
        requireTask(profileId, taskId, user);
        validateUrl(input.url());
        return saveLink(taskId, input);
    }

    private StudyTaskResource saveLink(long taskId, ResourceInput input) {
        return repository.createResource(taskId, input.title().strip(), input.url().strip(), null, null);
    }

    public StudyTaskResource updateLink(UUID profileId, long taskId, long resourceId, User user, ResourceInput input) {
        requireTask(profileId, taskId, user);
        validateUrl(input.url());
        return repository.updateLink(taskId, resourceId, input).orElseThrow(() -> notFound("Resource link not found"));
    }

    public StudyTaskResource upload(UUID profileId, long taskId, User user, String title, MultipartFile file) {
        requireTask(profileId, taskId, user);
        if (file.isEmpty()) throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "Attachment is empty");
        if (file.getSize() > MAX_ATTACHMENT_BYTES) {
            throw new ResponseStatusException(HttpStatus.PAYLOAD_TOO_LARGE, "Attachment exceeds 10 MiB");
        }
        String fileName = Objects.requireNonNullElse(file.getOriginalFilename(), "attachment").replace('\\', '/');
        fileName = fileName.substring(fileName.lastIndexOf('/') + 1).strip();
        if (fileName.isBlank() || fileName.length() > 255 || fileName.chars().anyMatch(Character::isISOControl)) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "Invalid attachment filename");
        }
        String label = title == null || title.isBlank() ? fileName : title.strip();
        if (label.length() > 255) throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "Attachment title is too long");
        try {
            return repository.createResource(taskId, label, null, fileName, file.getBytes());
        } catch (IOException ex) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "Could not read the attachment", ex);
        }
    }

    @Transactional(readOnly = true, isolation = Isolation.REPEATABLE_READ)
    public Attachment download(UUID profileId, long taskId, long resourceId, User user) {
        ownedProfile(profileId, user, false);
        return repository.attachment(requirePlan(profileId).id(), taskId, resourceId)
                .orElseThrow(() -> notFound("Attachment not found"));
    }

    public void deleteResource(UUID profileId, long taskId, long resourceId, User user) {
        requireTask(profileId, taskId, user);
        if (!repository.deleteResource(taskId, resourceId)) throw notFound("Study resource not found");
    }

    private ApplicationProfile ownedProfile(UUID id, User user, boolean write) {
        var profile = (write ? profiles.lockById(id) : profiles.findById(id))
                .orElseThrow(() -> notFound("Application profile not found"));
        if (user == null || !profile.getUserId().equals(user.getId())) {
            throw new ResponseStatusException(HttpStatus.FORBIDDEN, "This application profile belongs to another user");
        }
        return profile;
    }

    private StudyPlan ensurePlan(ApplicationProfile profile) {
        return repository.findActive(profile.getId())
                .orElseGet(() -> repository.createPlan(profile.getId(), profile.getTitle()));
    }

    private StudyPlan requirePlan(UUID profileId) {
        return repository.findActive(profileId).orElseThrow(() -> notFound("Study plan not found"));
    }

    private void requireTask(UUID profileId, long taskId, User user) {
        ownedProfile(profileId, user, true);
        if (!repository.hasTask(requirePlan(profileId).id(), taskId)) throw notFound("Study task not found");
    }

    private CompetencyProjection.View competency(ApplicationProfile profile, String sourceSessionId) {
        var attempts = interviewAttempts(profile, sourceSessionId);
        return projection.project(profile, attempts, runs.findAllById(attempts.stream().map(Session::getId).toList()));
    }

    private List<Session> interviewAttempts(ApplicationProfile profile, String sourceSessionId) {
        var attempts = sessions.findByApplicationProfileIdOrderByAttemptNumberDesc(profile.getId());
        if (sourceSessionId != null) {
            attempts = attempts.stream().filter(attempt -> sourceSessionId.equals(attempt.getId())).toList();
            if (attempts.isEmpty()) throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "Source session is outside this profile");
        }
        return attempts;
    }

    private void validateSkill(ApplicationProfile profile, String skillId) {
        if (skillId == null) return;
        for (var skill : json.read(profile.getSkillGapJson())) {
            if (skillId.equals(skill.path("jd_skill_id").asText())) return;
        }
        throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "Skill is outside this profile");
    }

    private com.fasterxml.jackson.databind.JsonNode objectiveDefinition(ApplicationProfile profile, String id) {
        for (var definition : json.read(profile.getBlueprintJson() == null ? "{}" : profile.getBlueprintJson()).path("objectives"))
            if (id.equals(definition.path("objective_id").asText())) return definition;
        throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "Objective is outside this profile");
    }

    private void validateChecklistOrigin(ApplicationProfile profile, String objectiveId, ChecklistInput item) {
        if (item.sourceCriterionId() == null) {
            if (item.sourceSessionId() != null || item.sourceAttemptNumber() != null)
                throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "Checklist source requires a criterion");
            return;
        }
        if (objectiveId == null) throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "Criterion source requires an objective");
        boolean found = false;
        for (var criterion : objectiveDefinition(profile, objectiveId).path("criteria"))
            found |= item.sourceCriterionId().equals(criterion.path("criterion_id").asText());
        if (!found) throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "Criterion is outside this objective");
        if (item.sourceSessionId() == null && item.sourceAttemptNumber() != null)
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "Source attempt requires a session");
        if (item.sourceSessionId() != null && interviewAttempts(profile, null).stream().noneMatch(attempt ->
                item.sourceSessionId().equals(attempt.getId())
                        && (item.sourceAttemptNumber() == null || item.sourceAttemptNumber().equals(attempt.getAttemptNumber()))))
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "Criterion source session is outside this profile");
    }

    private static void validateUrl(String url) {
        URI parsed = URI.create(url.strip());
        if (parsed.getHost() == null || parsed.getUserInfo() != null
                || !("http".equalsIgnoreCase(parsed.getScheme()) || "https".equalsIgnoreCase(parsed.getScheme()))) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "Resource URL must be an HTTP or HTTPS link");
        }
    }

    private PlanView view(StudyPlan plan) {
        var tasks = repository.tasks(plan.id());
        var checklist = repository.checklist(plan.id()).stream().collect(Collectors.groupingBy(StudyTaskChecklistItem::taskId));
        var resources = repository.resources(plan.id()).stream().collect(Collectors.groupingBy(StudyTaskResource::taskId));
        long done = tasks.stream().filter(task -> "DONE".equals(task.status())).count();
        return new PlanView(plan, progress(done, tasks.size(), plan.targetCompletionPercent()), tasks.stream()
                .map(task -> new TaskView(task, checklist.getOrDefault(task.id(), List.of()),
                        resources.getOrDefault(task.id(), List.of()))).toList());
    }

    private static Progress progress(long done, int total, BigDecimal target) {
        if (total == 0) return new Progress(0, 0, null, null);
        BigDecimal scaledDone = BigDecimal.valueOf(done).multiply(HUNDRED);
        BigDecimal totalDecimal = BigDecimal.valueOf(total);
        return new Progress(done, total, scaledDone.divide(totalDecimal, 2, RoundingMode.HALF_UP),
                scaledDone.compareTo(target.multiply(totalDecimal)) >= 0);
    }

    private static ResponseStatusException notFound(String message) {
        return new ResponseStatusException(HttpStatus.NOT_FOUND, message);
    }
}
