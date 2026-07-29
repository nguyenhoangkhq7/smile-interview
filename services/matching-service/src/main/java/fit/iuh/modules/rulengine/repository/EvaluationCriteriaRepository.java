package fit.iuh.modules.rulengine.repository;

import fit.iuh.modules.rulengine.entity.EvaluationCriteria;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

import java.util.List;

@Repository
public interface EvaluationCriteriaRepository extends JpaRepository<EvaluationCriteria, Long> {

    /**
     * Returns all criteria whose embedding column is null (not yet pre-computed).
     */
    List<EvaluationCriteria> findByEmbeddingIsNull();
}
