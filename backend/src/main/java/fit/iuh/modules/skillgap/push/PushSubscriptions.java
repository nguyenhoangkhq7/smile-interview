package fit.iuh.modules.skillgap.push;

import jakarta.validation.Valid;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.Size;
import fit.iuh.modules.auth.entity.User;
import fit.iuh.exception.ResourceNotFoundException;
import lombok.RequiredArgsConstructor;
import nl.martijndwars.webpush.Utils;
import org.springframework.http.HttpStatus;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.server.ResponseStatusException;

import java.net.URI;
import java.util.Base64;
import java.util.Map;
import java.util.UUID;

@RestController
@RequestMapping("/api/v1/analysis-push")
@RequiredArgsConstructor
public class PushSubscriptions {
    private final JdbcTemplate db;
    private final BrowserPush push;

    public record Endpoint(@NotBlank @Size(max=2048) String endpoint) {}
    public record Keys(@NotBlank @Size(max=100) String p256dh, @NotBlank @Size(max=32) String auth) {}
    public record Subscription(@NotBlank @Size(max=2048) String endpoint, @NotNull @Valid Keys keys, UUID jobId) {}

    @GetMapping("/config")
    public Map<String,String> config() { return Map.of("publicKey", push.publicKey()); }

    @PostMapping("/status")
    public boolean status(@AuthenticationPrincipal User user, @Valid @RequestBody Endpoint body) {
        return Boolean.TRUE.equals(db.queryForObject("""
            SELECT EXISTS(SELECT 1 FROM analysis_push_subscriptions WHERE owner_id=? AND endpoint=?)
            """, Boolean.class, user.getId(), body.endpoint()));
    }

    @PutMapping
    @Transactional
    @ResponseStatus(HttpStatus.NO_CONTENT)
    public void enable(@AuthenticationPrincipal User user, @Valid @RequestBody Subscription body) {
        if (push.publicKey().isBlank()) throw new ResponseStatusException(HttpStatus.SERVICE_UNAVAILABLE);
        try {
            if (!BrowserPush.supportedEndpoint(URI.create(body.endpoint())) ||
                    Base64.getUrlDecoder().decode(body.keys().auth()).length != 16)
                throw new IllegalArgumentException();
            Utils.loadPublicKey(body.keys().p256dh());
        } catch (Exception ex) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "Invalid browser subscription");
        }
        boolean finished = false;
        if (body.jobId() != null) {
            finished = db.query("SELECT status FROM skill_gap_jobs WHERE id=? AND owner_id=? FOR UPDATE",
                    (rs,n) -> rs.getString(1).equals("SUCCEEDED"), body.jobId(), user.getId())
                    .stream().findFirst().orElseThrow(() -> new ResourceNotFoundException("Job not found"));
        }
        var ids = db.query("""
            INSERT INTO analysis_push_subscriptions(id,owner_id,endpoint,p256dh,auth_key) VALUES (?,?,?,?,?)
            ON CONFLICT(endpoint) DO UPDATE SET p256dh=excluded.p256dh,auth_key=excluded.auth_key
            WHERE analysis_push_subscriptions.owner_id=excluded.owner_id RETURNING id
            """, (rs,n) -> rs.getObject(1,UUID.class), UUID.randomUUID(), user.getId(), body.endpoint(),
                body.keys().p256dh(), body.keys().auth());
        if (ids.isEmpty()) throw new ResponseStatusException(HttpStatus.CONFLICT, "Renew this browser subscription");
        if (finished) db.update("INSERT INTO analysis_push_deliveries(job_id,subscription_id) VALUES (?,?) ON CONFLICT DO NOTHING",
                body.jobId(), ids.getFirst());
    }

    @DeleteMapping
    @ResponseStatus(HttpStatus.NO_CONTENT)
    public void disable(@AuthenticationPrincipal User user, @Valid @RequestBody Endpoint body) {
        db.update("DELETE FROM analysis_push_subscriptions WHERE owner_id=? AND endpoint=?", user.getId(), body.endpoint());
    }
}
