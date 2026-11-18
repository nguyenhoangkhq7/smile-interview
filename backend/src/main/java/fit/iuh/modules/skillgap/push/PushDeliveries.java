package fit.iuh.modules.skillgap.push;

import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Component;

import java.util.UUID;

@Component
@RequiredArgsConstructor
@Slf4j
public class PushDeliveries {
    private final JdbcTemplate db;
    private final BrowserPush push;

    record Delivery(UUID job, UUID subscription, int attempt, String session, String endpoint, String key, String auth) {}

    @Scheduled(fixedDelayString = "${app.push.poll-ms:1500}")
    public void deliver() {
        if (push.publicKey().isBlank()) return;
        var due = db.query("""
            WITH candidate AS (
                SELECT job_id,subscription_id FROM analysis_push_deliveries WHERE available_at<=now()
                ORDER BY available_at LIMIT 1 FOR UPDATE SKIP LOCKED
            ), claimed AS (
                UPDATE analysis_push_deliveries d SET attempts=attempts+1, available_at=now()+interval '1 minute'
                FROM candidate c WHERE d.job_id=c.job_id AND d.subscription_id=c.subscription_id
                RETURNING d.*
            )
            SELECT c.job_id,s.id,c.attempts,j.session_id,s.endpoint,s.p256dh,s.auth_key
            FROM claimed c JOIN skill_gap_jobs j ON j.id=c.job_id
            JOIN analysis_push_subscriptions s ON s.id=c.subscription_id AND s.owner_id=j.owner_id
            """, (rs,n) -> new Delivery(rs.getObject(1,UUID.class), rs.getObject(2,UUID.class), rs.getInt(3),
                rs.getString(4), rs.getString(5), rs.getString(6), rs.getString(7)));
        if (due.isEmpty()) return;
        var d = due.getFirst();
        int status = 0;
        try {
            status = push.send(d);
        } catch (InterruptedException ex) {
            Thread.currentThread().interrupt();
            return;
        } catch (Exception ex) {
            log.warn("Push delivery failed job={} attempt={} error={}", d.job(), d.attempt(), ex.getClass().getSimpleName());
        }
        if (status == 404 || status == 410) {
            db.update("DELETE FROM analysis_push_subscriptions WHERE id=?", d.subscription());
            return;
        }
        boolean retry = status == 0 || status == 408 || status == 429 || status >= 500;
        db.update("""
            UPDATE analysis_push_deliveries SET available_at=CASE WHEN ? AND attempts<6
                THEN now()+make_interval(secs => attempts*30) END
            WHERE job_id=? AND subscription_id=? AND attempts=?
            """, retry, d.job(), d.subscription(), d.attempt());
    }
}
