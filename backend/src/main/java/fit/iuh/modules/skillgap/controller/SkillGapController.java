package fit.iuh.modules.skillgap.controller;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import fit.iuh.modules.auth.entity.User;
import fit.iuh.modules.skillgap.SkillGapJobs;
import lombok.RequiredArgsConstructor;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.web.bind.annotation.*;

import java.util.UUID;

@RestController
@RequestMapping(value = "/api/v1/sessions/{sessionId}/analyze-gap", produces = MediaType.APPLICATION_JSON_VALUE)
@RequiredArgsConstructor
public class SkillGapController {
    private final SkillGapJobs jobs;
    private final ObjectMapper json;

    @PostMapping
    public ResponseEntity<String> submit(@PathVariable String sessionId, @AuthenticationPrincipal User user,
            @RequestParam(defaultValue = "false") boolean forceRefresh) throws JsonProcessingException {
        var submission = jobs.submit(sessionId, user.getId(), forceRefresh);
        if (submission.cached() != null) return ResponseEntity.ok(submission.cached().toString());
        return ResponseEntity.accepted().body(json.writeValueAsString(submission.job()));
    }

    @GetMapping("/{jobId}")
    public String status(@PathVariable String sessionId, @PathVariable UUID jobId,
                         @AuthenticationPrincipal User user) throws JsonProcessingException {
        return json.writeValueAsString(jobs.status(sessionId, user.getId(), jobId));
    }
}
