package fit.iuh.modules.evidence;

import fit.iuh.modules.auth.entity.User;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.web.bind.annotation.*;

@RestController
@RequestMapping(value = "/api/v2/sessions/{sessionId}/interview", produces = "application/json")
@RequiredArgsConstructor
public class EvidenceController {
    private final EvidenceService service;

    @GetMapping
    public String read(@PathVariable String sessionId, @AuthenticationPrincipal User user) {
        return service.read(sessionId, user).toString();
    }

    @PostMapping("/start")
    public String start(@PathVariable String sessionId, @AuthenticationPrincipal User user,
                          @Valid @RequestBody EvidenceDtos.Config config) {
        return service.start(sessionId, user, config).toString();
    }

    @PostMapping("/respond")
    public String respond(@PathVariable String sessionId, @AuthenticationPrincipal User user,
                            @Valid @RequestBody EvidenceDtos.Answer answer) {
        return service.respond(sessionId, user, answer).toString();
    }

    @PostMapping("/stop")
    public String stop(@PathVariable String sessionId, @AuthenticationPrincipal User user,
                         @Valid @RequestBody EvidenceDtos.Stop stop) {
        return service.stop(sessionId, user, stop).toString();
    }

    @PostMapping("/conversation")
    public String converse(@PathVariable String sessionId, @AuthenticationPrincipal User user,
                           @Valid @RequestBody EvidenceDtos.Conversation command) {
        return service.converse(sessionId, user, command).toString();
    }

    @GetMapping("/report")
    public String report(@PathVariable String sessionId, @AuthenticationPrincipal User user) {
        return service.read(sessionId, user).path("report").toString();
    }
}
