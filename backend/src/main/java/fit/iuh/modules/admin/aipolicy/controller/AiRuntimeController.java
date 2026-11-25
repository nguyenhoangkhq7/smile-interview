package fit.iuh.modules.admin.aipolicy.controller;

import fit.iuh.modules.admin.aipolicy.dto.AiPolicyDtos.SealedRuntime;
import fit.iuh.modules.admin.aipolicy.service.AiPolicyConfigService;
import lombok.RequiredArgsConstructor;
import org.springframework.http.CacheControl;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

@RestController
@RequiredArgsConstructor
public class AiRuntimeController {
    private final AiPolicyConfigService configuration;

    @GetMapping("/api/internal/ai-runtime")
    public ResponseEntity<SealedRuntime> runtime(
            @RequestHeader(name = "X-Smile-Runtime-Token", required = false) String token) {
        return ResponseEntity.ok().cacheControl(CacheControl.noStore()).body(configuration.runtime(token));
    }
}
