package fit.iuh.modules.questionbank.repository;

import fit.iuh.modules.questionbank.entity.QuestionBank;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

import org.springframework.data.jpa.repository.Modifying;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;
import org.springframework.transaction.annotation.Transactional;

import java.util.List;
import java.util.Optional;
import java.util.UUID;

@Repository
public interface QuestionBankRepository extends JpaRepository<QuestionBank, UUID> {

    Optional<QuestionBank> findBySessionId(String sessionId);

    List<QuestionBank> findBySessionIdOrderByCreatedAtDesc(String sessionId);

    @Modifying(clearAutomatically = true, flushAutomatically = true)
    @Transactional
    @Query("DELETE FROM QuestionBank q WHERE q.sessionId = :sessionId")
    int deleteBySessionId(@Param("sessionId") String sessionId);
}
