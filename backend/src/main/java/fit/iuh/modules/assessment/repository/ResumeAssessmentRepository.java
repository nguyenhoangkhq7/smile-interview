package fit.iuh.modules.assessment.repository;

import fit.iuh.modules.assessment.entity.JobCategory;
import fit.iuh.modules.assessment.entity.ResumeAssessment;
import org.springframework.data.jpa.repository.EntityGraph;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.Optional;
import java.util.UUID;

public interface ResumeAssessmentRepository extends JpaRepository<ResumeAssessment, UUID> {

    Optional<ResumeAssessment> findBySessionId(String sessionId);

    boolean existsBySessionId(String sessionId);

    void deleteBySessionId(String sessionId);

    long countByJobCategory(JobCategory jobCategory);
}
