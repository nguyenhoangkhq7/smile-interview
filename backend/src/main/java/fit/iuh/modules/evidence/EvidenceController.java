package fit.iuh.modules.evidence;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.node.ObjectNode;
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
        return candidateView(service.read(sessionId, user)).toString();
    }

    @PostMapping("/start")
    public String start(@PathVariable String sessionId, @AuthenticationPrincipal User user,
                          @Valid @RequestBody EvidenceDtos.Config config) {
        return candidateView(service.start(sessionId, user, config)).toString();
    }

    @PostMapping("/respond")
    public String respond(@PathVariable String sessionId, @AuthenticationPrincipal User user,
                            @Valid @RequestBody EvidenceDtos.Answer answer) {
        return candidateView(service.respond(sessionId, user, answer)).toString();
    }

    @PostMapping("/next-question")
    public String nextQuestion(@PathVariable String sessionId, @AuthenticationPrincipal User user,
                               @Valid @RequestBody EvidenceDtos.NextQuestion command) {
        return candidateView(service.nextQuestion(sessionId, user, command)).toString();
    }

    @PostMapping("/stop")
    public String stop(@PathVariable String sessionId, @AuthenticationPrincipal User user,
                         @Valid @RequestBody EvidenceDtos.Stop stop) {
        return candidateView(service.stop(sessionId, user, stop)).toString();
    }

    @PostMapping("/conversation")
    public String converse(@PathVariable String sessionId, @AuthenticationPrincipal User user,
                           @Valid @RequestBody EvidenceDtos.Conversation command) {
        return candidateView(service.converse(sessionId, user, command)).toString();
    }

    @PostMapping("/run-code")
    public String runCode(@PathVariable String sessionId, @AuthenticationPrincipal User user,
                          @Valid @RequestBody EvidenceDtos.RunCode command) {
        return service.runCode(sessionId, user, command).toString();
    }

    @PostMapping("/clarify")
    public String clarify(@PathVariable String sessionId, @AuthenticationPrincipal User user,
                          @Valid @RequestBody EvidenceDtos.Clarify command) {
        return candidateView(service.clarify(sessionId, user, command)).toString();
    }

    @GetMapping("/report")
    public String report(@PathVariable String sessionId, @AuthenticationPrincipal User user) {
        return candidateView(service.read(sessionId, user)).path("report").toString();
    }

    // Older V2 snapshots and command receipts can contain post-interview coaching during a live turn.
    private JsonNode candidateView(JsonNode session) {
        if (session.path("is_finished").asBoolean() || !session.path("report").isObject()) return session;
        JsonNode visible = session.deepCopy();
        ObjectNode report = (ObjectNode) visible.path("report");
        report.putArray("turn_reviews");
        report.putNull("coaching");
        for (JsonNode entry : report.path("objectives")) {
            if (!(entry instanceof ObjectNode objective)) continue;
            objective.putArray("strengths");
            objective.putArray("weaknesses");
            objective.putArray("study_recommendations");
            for (JsonNode evidence : objective.path("evidence")) {
                if (evidence instanceof ObjectNode item) item.put("rationale", "");
            }
        }
        return visible;
    }
}
