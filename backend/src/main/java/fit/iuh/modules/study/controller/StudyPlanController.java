package fit.iuh.modules.study.controller;

import fit.iuh.modules.auth.entity.User;
import fit.iuh.modules.study.dto.StudyPlanDtos.*;
import fit.iuh.modules.study.entity.StudyTask;
import fit.iuh.modules.study.entity.StudyTaskChecklistItem;
import fit.iuh.modules.study.entity.StudyTaskResource;
import fit.iuh.modules.study.service.StudyPlanService;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import org.springframework.http.CacheControl;
import org.springframework.http.ContentDisposition;
import org.springframework.http.HttpHeaders;
import org.springframework.http.HttpStatus;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.http.converter.HttpMessageNotReadableException;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.method.annotation.MethodArgumentTypeMismatchException;
import org.springframework.web.multipart.MultipartFile;
import org.springframework.web.multipart.support.MissingServletRequestPartException;

import java.nio.charset.StandardCharsets;
import java.util.List;
import java.util.Map;
import java.util.UUID;

@RestController
@RequestMapping("/api/v1/application-profiles")
@RequiredArgsConstructor
public class StudyPlanController {
    private static final String PLAN = "/{profileId}/study-plan";
    private final StudyPlanService service;

    @GetMapping("/study-plan-progress")
    public List<PlanProgress> listProgress(@AuthenticationPrincipal User user) {
        return service.listProgress(user);
    }

    @GetMapping(PLAN)
    public PlanView get(@PathVariable UUID profileId, @AuthenticationPrincipal User user) {
        return service.get(profileId, user);
    }

    @PutMapping(PLAN)
    public PlanView update(@PathVariable UUID profileId, @AuthenticationPrincipal User user,
                           @Valid @RequestBody PlanInput input) {
        return service.updatePlan(profileId, user, input);
    }

    @GetMapping(PLAN + "/knowledge-gaps")
    public KnowledgeGaps gaps(@PathVariable UUID profileId, @AuthenticationPrincipal User user) {
        return service.gaps(profileId, user);
    }

    @PostMapping(PLAN + "/tasks")
    @ResponseStatus(HttpStatus.CREATED)
    public StudyTask createTask(@PathVariable UUID profileId, @AuthenticationPrincipal User user,
                                @Valid @RequestBody CreateTaskInput input) {
        return service.createTask(profileId, user, input);
    }

    @PutMapping(PLAN + "/tasks/{taskId}")
    public StudyTask updateTask(@PathVariable UUID profileId, @PathVariable long taskId,
                                @AuthenticationPrincipal User user, @Valid @RequestBody TaskInput input) {
        return service.updateTask(profileId, taskId, user, input);
    }

    @PutMapping(PLAN + "/tasks/{taskId}/position")
    @ResponseStatus(HttpStatus.NO_CONTENT)
    public void moveTask(@PathVariable UUID profileId, @PathVariable long taskId,
                         @AuthenticationPrincipal User user, @Valid @RequestBody TaskPositionInput input) {
        service.moveTask(profileId, taskId, user, input);
    }

    @DeleteMapping(PLAN + "/tasks/{taskId}")
    @ResponseStatus(HttpStatus.NO_CONTENT)
    public void deleteTask(@PathVariable UUID profileId, @PathVariable long taskId, @AuthenticationPrincipal User user) {
        service.deleteTask(profileId, taskId, user);
    }

    @PostMapping(PLAN + "/tasks/{taskId}/checklist")
    @ResponseStatus(HttpStatus.CREATED)
    public StudyTaskChecklistItem createChecklistItem(@PathVariable UUID profileId, @PathVariable long taskId,
                                                      @AuthenticationPrincipal User user, @Valid @RequestBody ChecklistInput input) {
        return service.createChecklistItem(profileId, taskId, user, input);
    }

    @PutMapping(PLAN + "/tasks/{taskId}/checklist/{itemId}")
    public StudyTaskChecklistItem updateChecklistItem(@PathVariable UUID profileId, @PathVariable long taskId,
                                                      @PathVariable long itemId, @AuthenticationPrincipal User user,
                                                      @Valid @RequestBody ChecklistInput input) {
        return service.updateChecklistItem(profileId, taskId, itemId, user, input);
    }

    @DeleteMapping(PLAN + "/tasks/{taskId}/checklist/{itemId}")
    @ResponseStatus(HttpStatus.NO_CONTENT)
    public void deleteChecklistItem(@PathVariable UUID profileId, @PathVariable long taskId,
                                    @PathVariable long itemId, @AuthenticationPrincipal User user) {
        service.deleteChecklistItem(profileId, taskId, itemId, user);
    }

    @PostMapping(PLAN + "/tasks/{taskId}/resources")
    @ResponseStatus(HttpStatus.CREATED)
    public StudyTaskResource createLink(@PathVariable UUID profileId, @PathVariable long taskId,
                                        @AuthenticationPrincipal User user, @Valid @RequestBody ResourceInput input) {
        return service.createLink(profileId, taskId, user, input);
    }

    @PutMapping(PLAN + "/tasks/{taskId}/resources/{resourceId}")
    public StudyTaskResource updateLink(@PathVariable UUID profileId, @PathVariable long taskId, @PathVariable long resourceId,
                                        @AuthenticationPrincipal User user, @Valid @RequestBody ResourceInput input) {
        return service.updateLink(profileId, taskId, resourceId, user, input);
    }

    @PostMapping(path = PLAN + "/tasks/{taskId}/resources/upload", consumes = MediaType.MULTIPART_FORM_DATA_VALUE)
    @ResponseStatus(HttpStatus.CREATED)
    public StudyTaskResource upload(@PathVariable UUID profileId, @PathVariable long taskId, @AuthenticationPrincipal User user,
                                    @RequestParam(required = false) String title, @RequestPart("file") MultipartFile file) {
        return service.upload(profileId, taskId, user, title, file);
    }

    @GetMapping(PLAN + "/tasks/{taskId}/resources/{resourceId}/file")
    public ResponseEntity<byte[]> download(@PathVariable UUID profileId, @PathVariable long taskId,
                                           @PathVariable long resourceId, @AuthenticationPrincipal User user) {
        var file = service.download(profileId, taskId, resourceId, user);
        return ResponseEntity.ok().contentType(MediaType.APPLICATION_OCTET_STREAM).cacheControl(CacheControl.noStore())
                .header(HttpHeaders.CONTENT_DISPOSITION, ContentDisposition.attachment()
                        .filename(file.fileName(), StandardCharsets.UTF_8).build().toString())
                .body(file.fileData());
    }

    @DeleteMapping(PLAN + "/tasks/{taskId}/resources/{resourceId}")
    @ResponseStatus(HttpStatus.NO_CONTENT)
    public void deleteResource(@PathVariable UUID profileId, @PathVariable long taskId, @PathVariable long resourceId,
                               @AuthenticationPrincipal User user) {
        service.deleteResource(profileId, taskId, resourceId, user);
    }

    @ExceptionHandler({HttpMessageNotReadableException.class, MethodArgumentTypeMismatchException.class,
            MissingServletRequestPartException.class})
    @ResponseStatus(HttpStatus.BAD_REQUEST)
    public Map<String, String> invalidRequest() {
        return Map.of("message", "Invalid study plan request");
    }
}
