package fit.iuh.modules.skillgap;

import fit.iuh.exception.ResourceNotFoundException;
import fit.iuh.modules.admin.queue.service.AdminQueueService;
import fit.iuh.modules.skillgap.dto.SkillGapDtos.AnalyzeWithReportResponseDto;
import fit.iuh.modules.skillgap.dto.SkillGapDtos.SkillGapReportDto;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.transaction.annotation.Transactional;

import java.util.List;
import java.util.UUID;

import static org.assertj.core.api.Assertions.*;

@SpringBootTest
@Transactional
class SkillGapJobsTest {
    @Autowired SkillGapJobs jobs;
    @Autowired AdminQueueService adminQueue;
    @Autowired JdbcTemplate db;

    private final UUID owner = UUID.fromString("a1111111-1111-1111-1111-111111111111");
    private final String session = UUID.randomUUID().toString();

    private void prepare() {
        db.update("INSERT INTO sessions(id,user_id) VALUES (?,?)", session, owner);
    }

    private AnalyzeWithReportResponseDto result() {
        return new AnalyzeWithReportResponseDto(session, List.of(), new SkillGapReportDto(null, false));
    }

    @Test void ownerChecksPrecedeCacheAndPollingAndDuplicatesShareWork() throws Exception {
        prepare();
        db.update("""
            INSERT INTO analysis_push_subscriptions(id,owner_id,endpoint,p256dh,auth_key) VALUES (?,?,?,?,?)
            """, UUID.randomUUID(), owner, "https://fcm.googleapis.com/test/" + session, "test", "test");
        var id = jobs.submit(session, owner, false).job().job_id();
        assertThat(jobs.submit(session, owner, true).job().job_id()).isEqualTo(id);
        var claim = jobs.claim(60);
        assertThat(jobs.currentInput(claim)).isNotNull();
        jobs.complete(claim, result());
        jobs.complete(claim, result());
        assertThat(db.queryForObject("SELECT count(*) FROM analysis_push_deliveries WHERE job_id=?",
                Integer.class, id)).isEqualTo(1);
        assertThat(jobs.status(session, owner, id).result().path("analysis_id").asText()).isEqualTo(session);
        assertThat(jobs.submit(session, owner, false).cached().path("skills").isArray()).isTrue();
        var other = UUID.randomUUID();
        assertThatThrownBy(() -> jobs.submit(session, other, false)).isInstanceOf(ResourceNotFoundException.class);
        assertThatThrownBy(() -> jobs.status(session, other, id)).isInstanceOf(ResourceNotFoundException.class);
        assertThatThrownBy(() -> jobs.status("other-session", owner, id)).isInstanceOf(ResourceNotFoundException.class);
        assertThat(jobs.submit(session, owner, true).job().job_id()).isNotEqualTo(id);
    }

    @Test void reclaimedLeaseFencesOldWorkerAndChangedDocumentsInvalidateCompletion() throws Exception {
        prepare();
        var id = jobs.submit(session, owner, false).job().job_id();
        var first = jobs.claim(60);
        db.update("UPDATE skill_gap_jobs SET lease_until=now() WHERE id=?", id);
        var replacement = jobs.claim(60);
        jobs.complete(first, result());
        assertThat(jobs.status(session, owner, id).status()).isEqualTo("RUNNING");
        var resume = UUID.randomUUID();
        db.update("INSERT INTO resumes(id,user_id,file_name,raw_text) VALUES (?,?,'cv','changed')", resume, owner);
        db.update("UPDATE sessions SET resume_id=? WHERE id=?", resume, session);
        jobs.complete(replacement, result());
        assertThat(jobs.status(session, owner, id).status()).isEqualTo("FAILED");
        assertThat(db.queryForObject("SELECT skill_gap_json FROM sessions WHERE id=?", String.class, session)).isNull();
    }

    @Test void repeatedFailureBecomesTerminalAndCanBeResubmitted() throws Exception {
        prepare();
        var id = jobs.submit(session, owner, false).job().job_id();
        for (int i = 1; i <= 3; i++) {
            var claim = jobs.claim(60);
            assertThat(claim.attempt()).isEqualTo(i);
            jobs.retry(claim);
            db.update("UPDATE skill_gap_jobs SET available_at=now() WHERE id=?", id);
        }
        assertThat(jobs.status(session, owner, id).status()).isEqualTo("FAILED");
        assertThat(jobs.submit(session, owner, false).job().job_id()).isNotEqualTo(id);
    }
    @Test void prioritizationAndReleaseFenceWorkersEvenWhenAttemptNumbersRepeat() throws Exception {
        prepare();
        UUID actor = UUID.randomUUID();
        db.update("INSERT INTO users(id,username,email,password_hash,role) VALUES (?, 'Queue admin', ?, 'unused', 'ADMIN')",
                actor, actor + "@example.test");
        String other = UUID.randomUUID().toString();
        db.update("INSERT INTO sessions(id,user_id) VALUES (?,?)", other, owner);
        var normal = jobs.submit(other, owner, false).job().job_id();
        var priority = jobs.submit(session, owner, false).job().job_id();
        db.update("UPDATE skill_gap_jobs SET available_at=now()-interval '1 minute' WHERE id=?", normal);

        adminQueue.prioritize(actor, priority);
        var original = jobs.claim(60);
        assertThat(original.id()).isEqualTo(priority);
        adminQueue.release(actor, priority, original.token());
        db.update("UPDATE skill_gap_jobs SET available_at=now() WHERE id=?", priority);
        adminQueue.prioritize(actor, priority);
        var replacement = jobs.claim(60);
        assertThat(replacement.attempt()).isEqualTo(original.attempt());
        assertThat(replacement.token()).isNotEqualTo(original.token());

        jobs.complete(original, result());
        jobs.retry(original);
        assertThat(jobs.status(session, owner, priority).status()).isEqualTo("RUNNING");
        assertThatThrownBy(() -> adminQueue.release(actor, priority, original.token()))
                .isInstanceOf(org.springframework.web.server.ResponseStatusException.class);
        jobs.complete(replacement, result());
        assertThat(jobs.status(session, owner, priority).status()).isEqualTo("SUCCEEDED");
    }
}
