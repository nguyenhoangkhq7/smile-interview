package fit.iuh.modules.admin.aipolicy.controller;

import fit.iuh.modules.admin.aipolicy.dto.AiPolicyDtos.*;
import fit.iuh.modules.admin.aipolicy.service.AiPolicyConfigService;
import fit.iuh.modules.admin.aipolicy.service.AiPolicyHealthService;
import fit.iuh.modules.auth.entity.User;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import org.springframework.http.*;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.web.bind.annotation.*;
import java.util.List;

@RestController
@RequestMapping("/api/v1/admin/ai-policy")
@RequiredArgsConstructor
public class AiPolicyController {
    private final AiPolicyConfigService configuration;
    private final AiPolicyHealthService health;

    @GetMapping
    public ResponseEntity<View> configuration() {
        return ResponseEntity.ok().cacheControl(CacheControl.noStore()).body(configuration.view());
    }

    @PutMapping
    @ResponseStatus(HttpStatus.NO_CONTENT)
    public void save(@Valid @RequestBody Save request, @AuthenticationPrincipal User actor) {
        configuration.save(request, actor.getId());
    }

    @PostMapping("/reset")
    @ResponseStatus(HttpStatus.NO_CONTENT)
    public void reset(@Valid @RequestBody Reset request, @AuthenticationPrincipal User actor) {
        configuration.reset(request, actor.getId());
    }

    @GetMapping("/health")
    public ResponseEntity<List<Check>> health() {
        return ResponseEntity.ok().cacheControl(CacheControl.noStore()).body(health.check());
    }

    @PostMapping("/health")
    public ResponseEntity<List<Check>> measureHealth() {
        return ResponseEntity.ok().cacheControl(CacheControl.noStore()).body(health.measure());
    }
}
