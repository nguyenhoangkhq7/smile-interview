package fit.iuh.modules.skillgap;

import fit.iuh.config.AppProperties;
import fit.iuh.exception.AiServiceException;
import fit.iuh.modules.skillgap.SkillGapJobs.Failure;
import fit.iuh.modules.skillgap.client.SkillGapClient;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Component;

@Component
@RequiredArgsConstructor
@Slf4j
public class SkillGapWorker {
    private final SkillGapJobs jobs;
    private final SkillGapClient ai;
    private final AppProperties properties;

    @Scheduled(fixedDelayString = "${app.skill-gap.poll-ms:1000}")
    public void processNext() {
        var timeouts = properties.getAi().getFastapi();
        var job = jobs.claim(timeouts.getConnectTimeoutSeconds() + timeouts.getReadTimeoutSeconds() + 60);
        if (job == null) return;
        try {
            var input = jobs.currentInput(job);
            if (input == null) return;
            var result = ai.analyzeGap(job.session(), input.cv(), input.jd());
            jobs.complete(job, result);
        } catch (Exception ex) {
            log.warn("Analysis job {} failed on attempt {} ({})", job.id(), job.attempt(), ex.getClass().getSimpleName());
            jobs.retry(job, failure(ex));
        }
    }
    private static Failure failure(Exception error) {
        for (Throwable cause = error; cause != null; cause = cause.getCause()) {
            if (cause instanceof java.net.SocketTimeoutException || cause instanceof java.net.http.HttpTimeoutException) {
                return Failure.TIMEOUT;
            }
        }
        return error instanceof AiServiceException ? Failure.UPSTREAM : Failure.PROCESSING_FAILED;
    }
}
