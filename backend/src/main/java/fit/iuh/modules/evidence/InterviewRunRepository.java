package fit.iuh.modules.evidence;

import org.springframework.data.jpa.repository.JpaRepository;

public interface InterviewRunRepository extends JpaRepository<InterviewRun, String> {
    @org.springframework.data.jpa.repository.Query(value = "SELECT * FROM interview_runs WHERE session_id = :id FOR UPDATE", nativeQuery = true)
    java.util.Optional<InterviewRun> lockRun(String id);
    @org.springframework.data.jpa.repository.Query(value = """
            SELECT * FROM interview_runs WHERE grading_due_at <= CURRENT_TIMESTAMP
            ORDER BY grading_due_at, session_id LIMIT 1 FOR UPDATE SKIP LOCKED
            """, nativeQuery = true)
    java.util.Optional<InterviewRun> lockNextSubmission();
}
