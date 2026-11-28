package fit.iuh.modules.evidence;

import fit.iuh.config.AppProperties;
import jakarta.annotation.PreDestroy;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Component;
import java.time.Duration;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.Semaphore;

@Component @RequiredArgsConstructor @Slf4j
@org.springframework.boot.autoconfigure.condition.ConditionalOnProperty(name = "app.interview.grading-enabled", matchIfMissing = true)
public class InterviewGradingWorker {
    private final EvidenceStore store;
    private final EvidenceAiClient ai;
    private final AppProperties properties;
    private final Semaphore slots = new Semaphore(4);
    private final ExecutorService executor = Executors.newVirtualThreadPerTaskExecutor();

    @Scheduled(fixedDelayString = "${app.interview.grading-poll-ms:500}")
    public void poll() {
        var timeouts = properties.getAi().getFastapi();
        var lease = Duration.ofSeconds(timeouts.getConnectTimeoutSeconds() + timeouts.getReadTimeoutSeconds() + 60L);
        while (slots.tryAcquire()) {
            boolean dispatched = false;
            try {
                var job = store.claimAnswer(lease);
                if (job == null) return;
                executor.execute(() -> grade(job));
                dispatched = true;
            } finally {
                if (!dispatched) slots.release();
            }
        }
    }

    private void grade(EvidenceStore.GradingJob job) {
        try {
            var result = ai.compute("respond", job.payload());
            if (!result.path("snapshot").path("turns").isArray()
                    || !java.util.stream.StreamSupport.stream(result.path("snapshot").path("turns").spliterator(), false)
                        .anyMatch(t -> job.payload().path("turn_id").equals(t.path("turn_id")) && t.hasNonNull("judgment")))
                throw new IllegalStateException("Grading result omitted the accepted turn");
            store.completeGrading(job, result);
        } catch (RuntimeException ex) {
            log.warn("Interview grading failed session_id={} attempt={} error={}", job.sessionId(), job.attempt(), ex.getClass().getSimpleName());
            store.gradingFailed(job);
        } finally {
            slots.release();
        }
    }

    @PreDestroy
    void shutdown() {
        executor.shutdownNow();
    }
}
