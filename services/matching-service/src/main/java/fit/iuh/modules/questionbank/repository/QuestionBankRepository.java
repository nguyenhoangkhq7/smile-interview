package fit.iuh.modules.questionbank.repository;

import fit.iuh.modules.questionbank.entity.QuestionBank;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

import java.util.List;
import java.util.Optional;
import java.util.UUID;

@Repository
public interface QuestionBankRepository extends JpaRepository<QuestionBank, UUID> {

    Optional<QuestionBank> findBySessionId(String sessionId);

    List<QuestionBank> findBySessionIdOrderByCreatedAtDesc(String sessionId);

    void deleteBySessionId(String sessionId);
}
