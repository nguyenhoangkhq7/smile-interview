package fit.iuh.modules.application;

import fit.iuh.modules.auth.entity.User;
import fit.iuh.modules.evidence.EvidenceJson;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.web.bind.annotation.*;
import java.util.*;

@RestController @RequestMapping(value = "/api/v1/application-profiles", produces = "application/json") @RequiredArgsConstructor
public class ApplicationProfileController {
    private final ApplicationProfileService service;
    private final EvidenceJson json;
    private final ApplicationCompetencyService competency;
    @GetMapping
    public String list(@AuthenticationPrincipal User user) { return json.tree(service.list(user)).toString(); }
    @PostMapping
    public String create(@AuthenticationPrincipal User user,
            @Valid @RequestBody ApplicationProfileService.Create request) { return json.tree(service.create(user, request)).toString(); }
    @GetMapping("/{id}")
    public String get(@PathVariable UUID id, @AuthenticationPrincipal User user) { return json.tree(service.get(id, user)).toString(); }
    @GetMapping("/{id}/competency")
    public String competency(@PathVariable UUID id, @AuthenticationPrincipal User user) {
        return json.tree(competency.get(id, user)).toString();
    }
    @PostMapping("/{id}/attempts")
    public String newAttempt(@PathVariable UUID id, @AuthenticationPrincipal User user) {
        return json.tree(service.newAttempt(id, user)).toString();
    }
}
