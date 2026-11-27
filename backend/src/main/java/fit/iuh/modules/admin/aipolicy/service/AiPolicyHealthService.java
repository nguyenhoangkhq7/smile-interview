package fit.iuh.modules.admin.aipolicy.service;

import fit.iuh.modules.admin.aipolicy.dto.AiPolicyDtos.Check;
import fit.iuh.modules.skillgap.push.BrowserPush;
import lombok.RequiredArgsConstructor;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.jdbc.core.StatementCallback;
import org.springframework.stereotype.Service;
import software.amazon.awssdk.services.s3.S3Client;
import software.amazon.awssdk.services.s3.model.HeadBucketRequest;
import java.time.Duration;
import java.util.ArrayList;
import java.util.List;
import java.util.concurrent.Executor;
import java.util.concurrent.Executors;
import java.util.concurrent.CompletableFuture;
import java.util.concurrent.TimeUnit;

@Service
@RequiredArgsConstructor
public class AiPolicyHealthService {
    private static final int DATABASE_TIMEOUT_SECONDS = 3;
    private static final long DATABASE_DEADLINE_MS = 5_000;
    private final AiPolicySources ai;
    private final JdbcTemplate jdbc;
    private final S3Client s3;
    private final BrowserPush push;
    @Value("${aws.s3.bucket:smile-interview}") private String bucket;

    public List<Check> check() {
        return collect(false);
    }

    public List<Check> measure() {
        return collect(true);
    }

    private List<Check> collect(boolean active) {
        var pool = Executors.newVirtualThreadPerTaskExecutor();
        try {
            return checks(active, pool);
        } finally {
            pool.shutdown();
        }
    }

    private List<Check> checks(boolean active, Executor pool) {
        var db = CompletableFuture.supplyAsync(this::database, pool)
                .completeOnTimeout(new Check("postgres", "DOWN", DATABASE_DEADLINE_MS, "Truy vấn SELECT 1 · Quá thời gian"),
                        DATABASE_DEADLINE_MS, TimeUnit.MILLISECONDS);
        var aws = CompletableFuture.supplyAsync(this::storage, pool);
        var fastapi = CompletableFuture.supplyAsync(this::fastapi, pool);
        var webPush = active && !push.publicKey().isBlank()
                ? timed("push", "Ký VAPID và mã hóa cục bộ", push::prepareTestNotification)
                : configured("push", !push.publicKey().isBlank(), "VAPID");
        var runtime = active ? measuredRuntime() : configuredRuntime();
        var checks = new ArrayList<>(List.of(db.join(), fastapi.join(), aws.join(), webPush));
        checks.addAll(runtime);
        return checks;
    }

    private Check database() {
        return timed("postgres", "Truy vấn SELECT 1", () -> jdbc.execute((StatementCallback<Void>) statement -> {
            statement.setQueryTimeout(DATABASE_TIMEOUT_SECONDS);
            statement.execute("SELECT 1");
            return null;
        }));
    }

    private Check storage() {
        return timed("s3", "Kiểm tra truy cập bucket", () -> s3.headBucket(HeadBucketRequest.builder()
                .bucket(bucket).overrideConfiguration(c -> c.apiCallTimeout(Duration.ofSeconds(3))).build()));
    }

    private Check fastapi() {
        long start = System.nanoTime();
        boolean reachable = ai.reachable();
        return new Check("fastapi", reachable ? "UP" : "DOWN", elapsed(start),
                reachable ? "Phản hồi /health" : "Không truy cập được /health");
    }

    private List<Check> measuredRuntime() {
        var results = ai.measure();
        return results == null ? unavailableRuntime() : results;
    }

    private List<Check> configuredRuntime() {
        var status = ai.status();
        if (status == null) return unavailableRuntime();
        var settings = status.settings();
        var voiceEnabled = status.openRouterConfigured() && settings.policy().voiceEnabled();
        return List.of(
                new Check("embedding", status.embeddingLoaded() ? "UP" : "CONFIGURED",
                        null, settings.models().embeddingModel()),
                configured("dspy", status.evidenceReady(), "OpenRouter / DSPy"),
                configured("voice", voiceEnabled, "OpenRouter STT/TTS"),
                configured("simli", voiceEnabled && status.simliConfigured() && settings.policy().simliAvatarEnabled()
                        && !settings.models().simliFaceId().isBlank() && "pcm".equals(settings.models().ttsFormat()), "Simli"));
    }

    private static List<Check> unavailableRuntime() {
        return List.of("embedding", "dspy", "voice", "simli").stream()
                .map(id -> new Check(id, "UNKNOWN", null, "Chưa nhận được kết quả từ AI service")).toList();
    }

    private static Check timed(String id, String detail, Runnable operation) {
        long start = System.nanoTime();
        try {
            operation.run();
            return new Check(id, "UP", elapsed(start), detail);
        } catch (RuntimeException ex) {
            return new Check(id, "DOWN", elapsed(start), detail + " · Phép thử thất bại");
        }
    }

    private static Check configured(String id, boolean ready, String where) {
        return new Check(id, ready ? "CONFIGURED" : "DISABLED", null, where);
    }

    private static long elapsed(long start) { return (System.nanoTime() - start) / 1_000_000; }
}
