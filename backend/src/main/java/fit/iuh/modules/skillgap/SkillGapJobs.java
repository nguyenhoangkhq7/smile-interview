package fit.iuh.modules.skillgap;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import fit.iuh.exception.ResourceNotFoundException;
import fit.iuh.modules.skillgap.dto.SkillGapDtos.AnalyzeWithReportResponseDto;
import lombok.RequiredArgsConstructor;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.HttpStatus;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.server.ResponseStatusException;

import java.sql.ResultSet;
import java.sql.SQLException;
import java.util.List;
import java.util.UUID;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.util.HexFormat;

@Service
@RequiredArgsConstructor
public class SkillGapJobs {
    private final JdbcTemplate db;
    private final ObjectMapper json;

    @Value("${app.skill-gap.pipeline-version:1}")
    private String pipelineVersion;

    record Input(String cv, String jd, String skills, String report, String cachedKey, boolean fixed) {}
    public record Status(UUID job_id, String status, JsonNode result) {}
    public record Submission(JsonNode cached, Status job) {}
    record Claim(UUID id, String session, UUID owner, String key, int attempt) {}

    private Input input(String session, UUID owner) {
        return db.query("""
            SELECT coalesce(r.raw_text,'') cv, coalesce(d.raw_text,'') jd,
                   coalesce(p.skill_gap_json,s.skill_gap_json) skills,
                   coalesce(p.gap_report_json,s.gap_report_json) report,
                   s.skill_gap_input_key, p.id IS NOT NULL fixed
            FROM sessions s LEFT JOIN resumes r ON r.id=s.resume_id
            LEFT JOIN job_descriptions d ON d.id=s.jd_id
            LEFT JOIN application_profiles p ON p.id=s.application_profile_id
            WHERE s.id=? AND s.user_id=? FOR UPDATE OF s
            """, (rs, n) -> new Input(rs.getString("cv"), rs.getString("jd"), rs.getString("skills"),
                rs.getString("report"), rs.getString("skill_gap_input_key"), rs.getBoolean("fixed")), session, owner)
                .stream().findFirst().orElseThrow(() -> new ResourceNotFoundException("Session not found"));
    }

    private String key(Input input) {
        try {
            byte[] bytes = json.writeValueAsBytes(List.of(pipelineVersion, input.cv(), input.jd()));
            return HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(bytes));
        } catch (NoSuchAlgorithmException | JsonProcessingException ex) {
            throw new IllegalStateException("Cannot identify analysis inputs", ex);
        }
    }

    @Transactional
    public Submission submit(String session, UUID owner, boolean refresh) throws JsonProcessingException {
        Input in = input(session, owner);
        if (refresh && in.fixed()) throw new ResponseStatusException(HttpStatus.CONFLICT, "Profile analysis is fixed");
        String key = key(in);
        var existing = db.query("""
            SELECT id,status,result_json FROM skill_gap_jobs
            WHERE session_id=? AND owner_id=? AND input_key=? AND status IN ('PENDING','RUNNING')
            """, this::statusRow, session, owner, key);
        if (!existing.isEmpty()) return new Submission(null, existing.getFirst());
        if (!refresh && in.skills() != null && in.report() != null &&
                (in.fixed() || in.cachedKey() == null || key.equals(in.cachedKey()))) {
            var cached = json.createObjectNode().put("analysis_id", session);
            try {
                cached.set("skills", json.readTree(in.skills()));
                cached.set("report", json.readTree(in.report()));
                if (cached.path("skills").isArray() && cached.path("report").isObject())
                    return new Submission(cached, null);
            } catch (JsonProcessingException ex) {
                if (in.fixed()) throw ex;
            }
        }
        if (in.fixed()) throw new IllegalStateException("Invalid fixed profile analysis");
        UUID id = UUID.randomUUID();
        db.update("INSERT INTO skill_gap_jobs(id, session_id, owner_id, input_key, status) VALUES (?,?,?,?,'PENDING')",
                id, session, owner, key);
        return new Submission(null, new Status(id, "PENDING", null));
    }

    public Status status(String session, UUID owner, UUID job) {
        return db.query("""
            SELECT j.id,j.status,j.result_json FROM skill_gap_jobs j JOIN sessions s ON s.id=j.session_id
            WHERE j.id=? AND j.session_id=? AND j.owner_id=? AND s.user_id=?
            """, this::statusRow, job, session, owner, owner).stream().findFirst()
                .orElseThrow(() -> new ResourceNotFoundException("Analysis job not found"));
    }

    private Status statusRow(ResultSet rs, int row) throws SQLException {
        String result = rs.getString("result_json");
        try {
            return new Status(rs.getObject("id", UUID.class), rs.getString("status"), result == null ? null : json.readTree(result));
        } catch (JsonProcessingException ex) { throw new SQLException("Invalid stored analysis", ex); }
    }

    @Transactional
    public Claim claim(int leaseSeconds) {
        db.update("""
            UPDATE skill_gap_jobs SET status='FAILED',lease_until=NULL
            WHERE status='RUNNING' AND lease_until<=now() AND attempts>=3
            """);
        return db.query("""
            WITH candidate AS (
                SELECT id FROM skill_gap_jobs
                WHERE (status='PENDING' AND available_at<=now()) OR
                      (status='RUNNING' AND lease_until<=now() AND attempts<3)
                ORDER BY available_at,id LIMIT 1 FOR UPDATE SKIP LOCKED
            )
            UPDATE skill_gap_jobs j SET status='RUNNING', attempts=attempts+1,
                lease_until=now()+make_interval(secs => ?)
            FROM candidate c WHERE j.id=c.id
            RETURNING j.id,j.session_id,j.owner_id,j.input_key,j.attempts
            """,(rs, n) -> new Claim(rs.getObject(1, UUID.class), rs.getString(2), rs.getObject(3, UUID.class),
                rs.getString(4), rs.getInt(5)), leaseSeconds).stream().findFirst().orElse(null);
    }

    @Transactional
    public Input currentInput(Claim job) {
        Input in = input(job.session(), job.owner());
        if (!in.fixed() && key(in).equals(job.key())) return in;
        db.update("UPDATE skill_gap_jobs SET status='FAILED', lease_until=NULL WHERE id=? AND attempts=? AND status='RUNNING'",
                job.id(), job.attempt());
        return null;
    }

    @Transactional(rollbackFor = Exception.class)
    public void complete(Claim job, AnalyzeWithReportResponseDto result) throws JsonProcessingException {
        if (currentInput(job) == null) return;
        if (result == null || !job.session().equals(result.analysisId()) || result.skills() == null || result.report() == null)
            throw new IllegalStateException("Invalid analysis response");
        int won = db.update("""
            UPDATE skill_gap_jobs SET status='SUCCEEDED',result_json=?,lease_until=NULL
            WHERE id=? AND status='RUNNING' AND attempts=? AND lease_until>clock_timestamp()
            """, json.writeValueAsString(result), job.id(), job.attempt());
        if (won == 0) return;
        db.update("""
            UPDATE sessions SET skill_gap_json=?,gap_report_json=?,skill_gap_input_key=?
            WHERE id=? AND user_id=?
            """, json.writeValueAsString(result.skills()), json.writeValueAsString(result.report()), job.key(), job.session(), job.owner());
        db.update("""
            INSERT INTO analysis_push_deliveries(job_id,subscription_id)
            SELECT ?,id FROM analysis_push_subscriptions WHERE owner_id=?
            ON CONFLICT DO NOTHING
            """, job.id(), job.owner());
    }

    public void retry(Claim job) {
        db.update("""
            UPDATE skill_gap_jobs SET status=CASE WHEN attempts>=3 THEN 'FAILED' ELSE 'PENDING' END,
                available_at=now()+make_interval(secs => attempts*5),lease_until=NULL
            WHERE id=? AND attempts=? AND status='RUNNING'
            """, job.id(), job.attempt());
    }
}
