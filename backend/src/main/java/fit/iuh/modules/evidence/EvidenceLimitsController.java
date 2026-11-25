package fit.iuh.modules.evidence;

import lombok.RequiredArgsConstructor;
import org.springframework.http.CacheControl;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequiredArgsConstructor
public class EvidenceLimitsController {
    private final EvidenceAdmission admission;

    @GetMapping("/api/v2/interview/limits")
    public ResponseEntity<EvidenceAdmission.Limits> limits() {
        return ResponseEntity.ok().cacheControl(CacheControl.noStore()).body(admission.limits());
    }
}
