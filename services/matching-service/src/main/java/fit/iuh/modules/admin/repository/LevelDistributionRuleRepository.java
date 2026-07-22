package fit.iuh.modules.admin.repository;

import fit.iuh.modules.admin.entity.LevelDistributionRule;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

import java.util.Optional;

@Repository
public interface LevelDistributionRuleRepository extends JpaRepository<LevelDistributionRule, Long> {
    Optional<LevelDistributionRule> findByLevel(String level);
}
