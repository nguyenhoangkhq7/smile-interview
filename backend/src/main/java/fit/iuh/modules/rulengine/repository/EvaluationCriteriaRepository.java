package fit.iuh.modules.rulengine.repository;

import fit.iuh.modules.rulengine.entity.EvaluationCriteria;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;
import org.springframework.stereotype.Repository;

import java.util.List;
import java.util.Map;
import java.util.Set;

@Repository
public interface EvaluationCriteriaRepository extends JpaRepository<EvaluationCriteria, Long> {

    /**
     * Returns all criteria whose embedding column is null (not yet pre-computed).
     */
    List<EvaluationCriteria> findByEmbeddingIsNull();

    /**
     * Returns a projection of [criteriaId, level] for all existing mappings.
     * Used to compute mappedLevels for each EvaluationCriteria in one query.
     */
    @Query("""
            SELECT m.evaluationCriteria.id AS criteriaId, m.level AS level
            FROM CategoryCriteriaMapping m
            """)
    List<Object[]> findAllCriteriaIdAndLevel();
}
