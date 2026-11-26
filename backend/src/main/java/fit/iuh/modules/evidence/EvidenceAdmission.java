package fit.iuh.modules.evidence;

import fit.iuh.modules.admin.aipolicy.service.AiPolicyConfigService;
import lombok.RequiredArgsConstructor;
import org.springframework.http.HttpStatus;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;
import org.springframework.web.server.ResponseStatusException;

import java.sql.ResultSet;
import java.util.UUID;

@Service
@RequiredArgsConstructor
public class EvidenceAdmission {
    private final AiPolicyConfigService configuration;
    private final JdbcTemplate jdbc;

    public record Limits(int maxQuestions, int durationSeconds, int maxQuestionsPerObjective,
                         boolean voiceEnabled) {}

    public Limits limits() {
        var policy = configuration.policy();
        return new Limits(policy.maxQuestions(), policy.durationSeconds(), policy.maxQuestionsPerObjective(),
                policy.voiceEnabled());
    }

    void check(EvidenceDtos.Config requested) {
        var limits = limits();
        if (requested.maxQuestions() > limits.maxQuestions() || requested.durationSeconds() > limits.durationSeconds()
                || requested.maxPerObjective() > limits.maxQuestionsPerObjective()) {
            throw new ResponseStatusException(HttpStatus.UNPROCESSABLE_ENTITY, "Cấu hình vượt giới hạn phỏng vấn hiện tại.");
        }
        if ("VOICE".equals(requested.interactionMode()) && !limits.voiceEnabled()) {
            throw new ResponseStatusException(HttpStatus.UNPROCESSABLE_ENTITY, "Phỏng vấn giọng nói đang tắt.");
        }
    }

    void checkQuota(UUID user, boolean lock) {
        int quota = configuration.policy().dailyQuota();
        if (quota == 0) return;
        if (lock) {
            jdbc.query("SELECT pg_advisory_xact_lock(hashtextextended('interview-quota:' || CAST(? AS text), 0))",
                    (ResultSet ignored) -> {}, user);
        }
        Long starts = jdbc.queryForObject("""
                SELECT count(*) FROM interview_runs r JOIN sessions s ON s.id = r.session_id
                WHERE s.user_id = ? AND r.created_at >= date_trunc('day', now(), 'Asia/Ho_Chi_Minh')
                """, Long.class, user);
        if (starts != null && starts >= quota) {
            throw new ResponseStatusException(HttpStatus.TOO_MANY_REQUESTS, "Bạn đã hết hạn mức phỏng vấn hôm nay.");
        }
    }
}
