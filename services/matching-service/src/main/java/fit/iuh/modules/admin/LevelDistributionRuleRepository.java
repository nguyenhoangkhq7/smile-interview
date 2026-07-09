package fit.iuh.modules.admin;

import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

import java.util.Optional;

/**
 * Spring Data JPA repository for {@link LevelDistributionRule}.
 */
@Repository
public interface LevelDistributionRuleRepository extends JpaRepository<LevelDistributionRule, Long> {

    /**
     * Finds the distribution rule for a specific seniority level.
     *
     * @param level the {@link fit.iuh.modules.assessment.SeniorityLevel} name (e.g., "FRESHER")
     * @return an {@link Optional} containing the rule if found
     */
    Optional<LevelDistributionRule> findByLevel(String level);
}
