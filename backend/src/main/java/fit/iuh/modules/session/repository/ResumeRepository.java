package fit.iuh.modules.session.repository;

import fit.iuh.modules.session.entity.Resume;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

import java.util.List;
import java.util.UUID;

@Repository
public interface ResumeRepository extends JpaRepository<Resume, UUID> {
    List<Resume> findByUserIdOrderByCreatedAtDesc(UUID userId);
    List<Resume> findAllByOrderByCreatedAtDesc();
}
