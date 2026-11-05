package fit.iuh.modules.rulengine.repository;

import fit.iuh.modules.rulengine.entity.JobCategoryEntity;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

import java.util.Optional;

@Repository
public interface JobCategoryEntityRepository extends JpaRepository<JobCategoryEntity, Long> {
    Optional<JobCategoryEntity> findByCode(String code);
}
