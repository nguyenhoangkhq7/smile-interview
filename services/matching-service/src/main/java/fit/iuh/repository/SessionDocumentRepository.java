package fit.iuh.repository;

import fit.iuh.entity.SessionDocument;
import fit.iuh.entity.enums.DocumentType;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Modifying;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;
import org.springframework.stereotype.Repository;

import java.util.Optional;
import java.util.UUID;

/**
 * Spring Data JPA repository for {@link SessionDocument} entities.
 *
 * <p>Each interview session has exactly one CV document and one JD document
 * persisted here as full Markdown text (pre-chunking). This table is the
 * single source of truth for document content used by the Assessment module.
 *
 * <p>The unique composite index on {@code (session_id, document_type)} ensures
 * data integrity — only one CV and one JD can exist per session.
 */
@Repository
public interface SessionDocumentRepository extends JpaRepository<SessionDocument, UUID> {

    /**
     * Returns the full Markdown document for a specific session and document type.
     *
     * <p>Used by {@code AssessmentService} to retrieve the complete CV or JD
     * content without joining chunks.
     *
     * @param sessionId    the unique interview session identifier
     * @param documentType the document type: {@code CV} or {@code JD}
     * @return an {@link Optional} containing the document, or empty if not yet ingested
     */
    Optional<SessionDocument> findBySessionIdAndDocumentType(
            String sessionId, DocumentType documentType);

    /**
     * Checks whether any document exists for a given session.
     *
     * @param sessionId the unique interview session identifier
     * @return {@code true} if at least one document exists for this session
     */
    boolean existsBySessionId(String sessionId);

    /**
     * Deletes all documents (CV and JD) associated with a session.
     * Called during re-ingestion to ensure a clean slate before new documents are saved.
     *
     * @param sessionId the unique interview session identifier
     */
    @Modifying
    @Query("DELETE FROM SessionDocument sd WHERE sd.sessionId = :sessionId")
    void deleteAllBySessionId(@Param("sessionId") String sessionId);
}
