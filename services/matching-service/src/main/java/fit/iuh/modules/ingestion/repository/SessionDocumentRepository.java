package fit.iuh.modules.ingestion.repository;

import fit.iuh.modules.ingestion.entity.DocumentType;
import fit.iuh.modules.ingestion.entity.SessionDocument;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;
import org.springframework.stereotype.Repository;

import java.util.Optional;

@Repository
public interface SessionDocumentRepository extends JpaRepository<SessionDocument, Long> {

    Optional<SessionDocument> findBySessionIdAndDocumentType(String sessionId, DocumentType documentType);

    boolean existsBySessionId(String sessionId);

    void deleteAllBySessionId(String sessionId);

    @Query(value = """
            SELECT d_cv.session_id
            FROM session_documents d_cv
            JOIN session_documents d_jd ON d_cv.session_id = d_jd.session_id
            JOIN resume_assessments ra ON d_cv.session_id = ra.session_id
            WHERE d_cv.document_type = 'CV'
              AND d_jd.document_type = 'JD'
              AND d_cv.markdown_content = :cvContent
              AND d_jd.markdown_content = :jdContent
              AND d_cv.session_id != :currentSessionId
            ORDER BY ra.created_at DESC
            LIMIT 1
            """, nativeQuery = true)
    Optional<String> findSessionWithSameContentAndAssessment(
            @Param("cvContent") String cvContent,
            @Param("jdContent") String jdContent,
            @Param("currentSessionId") String currentSessionId
    );
}
