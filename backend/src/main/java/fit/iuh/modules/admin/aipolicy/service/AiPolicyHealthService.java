package fit.iuh.modules.admin.aipolicy.service;

import fit.iuh.modules.admin.aipolicy.dto.AiPolicyDtos.Check;
import fit.iuh.modules.skillgap.push.BrowserPush;
import lombok.RequiredArgsConstructor;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;
import software.amazon.awssdk.services.s3.S3Client;
import software.amazon.awssdk.services.s3.model.HeadBucketRequest;
import java.time.Duration;
import java.util.List;
import java.util.concurrent.Executors;
import java.util.concurrent.CompletableFuture;

@Service
@RequiredArgsConstructor
public class AiPolicyHealthService {
    private final AiPolicySources ai;
    private final JdbcTemplate jdbc;
    private final S3Client s3;
    private final BrowserPush push;
    @Value("${aws.s3.bucket:smile-interview}") private String bucket;

    public List<Check> check() {
        try (var pool = Executors.newVirtualThreadPerTaskExecutor()) {
            var db = CompletableFuture.supplyAsync(() -> measure("postgres", () -> jdbc.queryForObject("SELECT 1", Integer.class)), pool);
            var aws = CompletableFuture.supplyAsync(() -> measure("s3", () -> s3.headBucket(HeadBucketRequest.builder()
                    .bucket(bucket).overrideConfiguration(c -> c.apiCallTimeout(Duration.ofSeconds(3))).build())), pool);
            long start = System.nanoTime();
            var status = ai.status();
            var fastapi = status != null ? new Check("fastapi", "UP", elapsed(start), "Phản hồi từ AI service")
                    : new Check("fastapi", ai.reachable() ? "DEGRADED" : "DOWN", null, "Chưa nhận được trạng thái cấu hình");
            return List.of(db.join(), fastapi, aws.join(),
                    configured("push", !push.publicKey().isBlank(), "VAPID"),
                    status == null ? unknown("embedding") : new Check("embedding", status.embeddingLoaded() ? "UP" : "CONFIGURED",
                            null, status.settings().models().embeddingModel()),
                    status == null ? unknown("dspy") : configured("dspy", status.evidenceReady(), "OpenRouter / DSPy"),
                    status == null ? unknown("voice") : configured("voice", status.openRouterConfigured() && status.settings().policy().voiceEnabled(), "OpenRouter STT/TTS"),
                    status == null ? unknown("simli") : configured("simli", status.simliConfigured()
                            && status.settings().policy().voiceEnabled()
                            && status.settings().policy().simliAvatarEnabled()
                            && !status.settings().models().simliFaceId().isBlank(), "Simli"));
        }
    }

    private static Check measure(String id, Runnable operation) {
        long start = System.nanoTime();
        try { operation.run(); return new Check(id, "UP", elapsed(start), "Kết nối thành công"); }
        catch (RuntimeException ex) { return new Check(id, "DOWN", elapsed(start), "Không truy cập được"); }
    }

    private static Check configured(String id, boolean ready, String where) {
        return new Check(id, ready ? "CONFIGURED" : "DISABLED", null, where);
    }

    private static Check unknown(String id) { return new Check(id, "UNKNOWN", null, "Chưa nhận được trạng thái"); }
    private static long elapsed(long start) { return (System.nanoTime() - start) / 1_000_000; }
}
