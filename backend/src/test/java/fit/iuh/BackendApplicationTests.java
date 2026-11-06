package fit.iuh;

import fit.iuh.modules.auth.entity.Role;
import fit.iuh.modules.auth.entity.User;
import fit.iuh.modules.hrevaluation.entity.HrEvaluation;
import fit.iuh.modules.session.entity.JobDescription;
import fit.iuh.modules.session.entity.Resume;
import fit.iuh.modules.session.entity.Session;
import fit.iuh.modules.session.entity.SessionTurn;
import jakarta.persistence.EntityManager;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.transaction.annotation.Transactional;

import java.time.LocalDateTime;
import java.util.UUID;

import static org.assertj.core.api.Assertions.assertThat;

@SpringBootTest
class BackendApplicationTests {

    @Autowired
    private EntityManager entityManager;

    @Test
    void contextLoads() {
    }

    @Test
    @Transactional
    void currentPipelinePersistsAndCleansUpReferences() {
        User user = User.builder().username("Schema test").email("schema-test@smile.test")
                .password("test-hash").role(Role.USER).build();
        entityManager.persist(user);

        Resume resume = Resume.builder().id(UUID.randomUUID()).userId(user.getId())
                .fileName("cv.txt").rawText("Java and PostgreSQL")
                .createdAt(LocalDateTime.now()).build();
        JobDescription jd = JobDescription.builder().id(UUID.randomUUID()).userId(user.getId())
                .title("Backend developer").rawText("Java required")
                .createdAt(LocalDateTime.now()).build();
        entityManager.persist(resume);
        entityManager.persist(jd);
        entityManager.flush();
        user.setDefaultResumeId(resume.getId());

        Session session = Session.builder().id("schema-" + UUID.randomUUID()).userId(user.getId())
                .resume(resume).jobDescription(jd).status("In progress")
                .skillGapJson("[]").gapReportJson("{}")
                .aiInterviewSessionId("ai-test-session").interviewReportJson("{}")
                .startedAt(LocalDateTime.now()).build();
        entityManager.persist(session);
        SessionTurn turn = SessionTurn.builder().sessionId(session.getId())
                .question("Explain a transaction").answer("An atomic unit of work")
                .hrRating(5).hrFeedback("Clear answer").build();
        HrEvaluation evaluation = HrEvaluation.builder().sessionId(session.getId()).userId(user.getId())
                .ratingMatchingAccuracy(5).ratingAiRationale(4).ratingQuestionQuality(5).build();
        entityManager.persist(turn);
        entityManager.persist(evaluation);
        entityManager.flush();
        entityManager.clear();

        assertThat(turn.getId()).isPositive();
        assertThat(entityManager.find(User.class, user.getId()).getDefaultResumeId()).isEqualTo(resume.getId());
        assertThat(entityManager.find(Resume.class, resume.getId()).getRawText()).isEqualTo("Java and PostgreSQL");
        assertThat(entityManager.find(JobDescription.class, jd.getId()).getRawText()).isEqualTo("Java required");
        assertThat(entityManager.find(Session.class, session.getId()).getSkillGapJson()).isEqualTo("[]");
        assertThat(entityManager.find(SessionTurn.class, turn.getId()).getHrFeedback()).isEqualTo("Clear answer");
        assertThat(entityManager.find(HrEvaluation.class, evaluation.getId()).getRatingMatchingAccuracy()).isEqualTo(5);

        entityManager.createNativeQuery("DELETE FROM resumes WHERE id = :id")
                .setParameter("id", resume.getId()).executeUpdate();
        entityManager.clear();
        assertThat(entityManager.find(User.class, user.getId()).getDefaultResumeId()).isNull();
        assertThat(entityManager.find(Session.class, session.getId()).getResume()).isNull();

        entityManager.createNativeQuery("DELETE FROM sessions WHERE id = :id")
                .setParameter("id", session.getId()).executeUpdate();
        entityManager.clear();
        assertThat(entityManager.find(SessionTurn.class, turn.getId())).isNull();
        assertThat(entityManager.find(HrEvaluation.class, evaluation.getId())).isNull();
    }

}
